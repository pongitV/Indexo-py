import os
import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, QThreadPool, QRunnable, QObject, Signal
from PySide6.QtGui import QPixmap, QImage, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QScrollArea, QFrame, QSizePolicy, QTabWidget
)
import pymupdf
from loguru import logger
from app.utils.formatters import format_file_size, format_timestamp
from app.i18n.language_manager import tr

class PreviewWorkerSignals(QObject):
    text_ready = Signal(str, str)         # file_path, content
    image_ready = Signal(str, QImage)     # file_path, QImage
    error_ready = Signal(str, str)        # file_path, error_msg

class AsyncPreviewWorker(QRunnable):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.signals = PreviewWorkerSignals()

    def run(self):
        try:
            ext = self.path.suffix.lower()
            if ext in [".txt", ".log", ".csv", ".json", ".md", ".py", ".rs", ".js", ".html", ".ini", ".cfg"]:
                with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(4000)
                self.signals.text_ready.emit(str(self.path), content)
            elif ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"]:
                img = QImage(str(self.path))
                if not img.isNull():
                    self.signals.image_ready.emit(str(self.path), img)
                else:
                    self.signals.error_ready.emit(str(self.path), tr("preview.no_preview", name=self.path.name))
            elif ext == ".pdf":
                doc = pymupdf.open(self.path)
                if len(doc) > 0:
                    page = doc[0]
                    pix = page.get_pixmap(dpi=150)
                    img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
                    self.signals.image_ready.emit(str(self.path), img)
                else:
                    self.signals.error_ready.emit(str(self.path), tr("preview.empty_pdf"))
                doc.close()
            else:
                self.signals.error_ready.emit(str(self.path), tr("preview.no_preview", name=self.path.name))
        except Exception as e:
            logger.debug("Async preview failed for {}: {}", self.path, e)
            self.signals.error_ready.emit(str(self.path), str(e))

class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path: Optional[Path] = None
        self.threadpool = QThreadPool.globalInstance()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header with filename and close button
        header = QHBoxLayout()
        self.lbl_title = QLabel("")
        self.lbl_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        header.addWidget(self.lbl_title, 1)

        self.btn_close = QPushButton("✕")
        self.btn_close.setToolTip("Fechar / Close (Esc)")
        self.btn_close.setStyleSheet("padding: 2px 8px; font-weight: bold; border-radius: 4px;")
        self.btn_close.clicked.connect(self.close_preview)
        header.addWidget(self.btn_close)

        layout.addLayout(header)

        # Tab Widget for Clean Separation between Content and Metadata
        self.preview_tabs = QTabWidget()
        self.preview_tabs.setFont(QFont("Inter", 9, QFont.Weight.Medium))

        # --- Tab 1: Content ---
        self.tab_content = QWidget()
        content_layout = QVBoxLayout(self.tab_content)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(6)

        self.txt_viewer = QTextEdit()
        self.txt_viewer.setReadOnly(True)
        self.txt_viewer.setFont(QFont("Consolas", 9))
        self.txt_viewer.setVisible(False)
        content_layout.addWidget(self.txt_viewer)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.lbl_image)
        self.scroll_area.setVisible(False)
        content_layout.addWidget(self.scroll_area)

        self.lbl_no_content = QLabel("")
        self.lbl_no_content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_no_content.setObjectName("lbl_subtext")
        self.lbl_no_content.setFont(QFont("Inter", 9))
        self.lbl_no_content.setVisible(False)
        content_layout.addWidget(self.lbl_no_content)

        self.preview_tabs.addTab(self.tab_content, tr("preview.tab_content"))

        # --- Tab 2: Details ---
        self.tab_details = QWidget()
        details_layout = QVBoxLayout(self.tab_details)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(10)

        card = QFrame()
        card.setObjectName("card_options")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setSpacing(8)

        self.lbl_detail_name = QLabel()
        self.lbl_detail_name.setWordWrap(True)
        self.lbl_detail_name.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        c_layout.addWidget(self.lbl_detail_name)

        self.lbl_detail_size = QLabel()
        self.lbl_detail_size.setFont(QFont("Inter", 9))
        c_layout.addWidget(self.lbl_detail_size)

        self.lbl_detail_modified = QLabel()
        self.lbl_detail_modified.setFont(QFont("Inter", 9))
        c_layout.addWidget(self.lbl_detail_modified)

        self.lbl_detail_path = QLabel()
        self.lbl_detail_path.setWordWrap(True)
        self.lbl_detail_path.setFont(QFont("Consolas", 8))
        self.lbl_detail_path.setObjectName("lbl_subtext")
        c_layout.addWidget(self.lbl_detail_path)

        details_layout.addWidget(card)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_open_explorer = QPushButton(tr('action.open_explorer'))
        self.btn_open_explorer.clicked.connect(self.open_in_explorer)
        btn_layout.addWidget(self.btn_open_explorer)

        self.btn_open_external = QPushButton(tr('action.play_external'))
        self.btn_open_external.clicked.connect(self.open_in_external_app)
        btn_layout.addWidget(self.btn_open_external)

        details_layout.addLayout(btn_layout)
        details_layout.addStretch()

        self.preview_tabs.addTab(self.tab_details, tr("preview.tab_details"))

        layout.addWidget(self.preview_tabs)
        self.setVisible(False)

    def close_preview(self):
        self.current_path = None
        self.setVisible(False)

    def preview_file(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            return

        self.current_path = path
        self.lbl_title.setText(path.name)
        self.setVisible(True)

        stat = path.stat()
        size_str = format_file_size(stat.st_size)
        mtime_str = format_timestamp(stat.st_mtime)

        # Update Details Tab
        self.lbl_detail_name.setText(f"{path.name}")
        self.lbl_detail_size.setText(f"{tr('preview.meta_size')} {size_str}")
        self.lbl_detail_modified.setText(f"{tr('preview.meta_modified')} {mtime_str}")
        self.lbl_detail_path.setText(f"{path.resolve()}")

        # Loading placeholder
        self.txt_viewer.setVisible(False)
        self.scroll_area.setVisible(False)
        self.lbl_no_content.setText(tr("preview.loading"))
        self.lbl_no_content.setVisible(True)

        # Dispatch async worker
        worker = AsyncPreviewWorker(path)
        worker.signals.text_ready.connect(self._on_text_ready)
        worker.signals.image_ready.connect(self._on_image_ready)
        worker.signals.error_ready.connect(self._on_error_ready)
        self.threadpool.start(worker)

        self.preview_tabs.setCurrentIndex(0)

    def _on_text_ready(self, file_path: str, content: str):
        if self.current_path and str(self.current_path) == file_path:
            self.lbl_no_content.setVisible(False)
            self.scroll_area.setVisible(False)
            self.txt_viewer.setPlainText(content)
            self.txt_viewer.verticalScrollBar().setValue(0)
            self.txt_viewer.setVisible(True)

    def _on_image_ready(self, file_path: str, image: QImage):
        if self.current_path and str(self.current_path) == file_path:
            self.lbl_no_content.setVisible(False)
            self.txt_viewer.setVisible(False)
            pixmap = QPixmap.fromImage(image)
            scaled = pixmap.scaled(380, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_image.setPixmap(scaled)
            self.scroll_area.verticalScrollBar().setValue(0)
            self.scroll_area.setVisible(True)

    def _on_error_ready(self, file_path: str, error_msg: str):
        if self.current_path and str(self.current_path) == file_path:
            self.txt_viewer.setVisible(False)
            self.scroll_area.setVisible(False)
            self.lbl_no_content.setText(error_msg)
            self.lbl_no_content.setVisible(True)

    def open_in_explorer(self):
        if self.current_path and self.current_path.exists():
            import subprocess
            subprocess.run(["explorer", f"/select,{str(self.current_path.resolve())}"])

    def open_in_external_app(self):
        if self.current_path and self.current_path.exists():
            import webbrowser
            webbrowser.open(str(self.current_path))
