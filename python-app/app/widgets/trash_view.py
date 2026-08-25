from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QPushButton,
    QMessageBox, QAbstractItemView
)
import indexo_core
from app.i18n.language_manager import tr
from app.config.settings_manager import get_db_path
from app.utils.file_ops import send_file_to_recycle_bin, delete_file_permanently
from loguru import logger

class TrashView(QWidget):
    trash_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.marked_files: List[Dict[str, Any]] = []
        self.filtered_files: List[Dict[str, Any]] = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Top stats header
        self.lbl_stats = QLabel(tr("trash.stats", count=0, size="0 MB"))
        self.lbl_stats.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        layout.addWidget(self.lbl_stats)

        # Search bar and sort filters
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("search.filter_trash"))
        self.search_input.textChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.search_input, 2)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([tr("sort.name"), tr("sort.size"), tr("sort.date_marked")])
        self.sort_combo.currentIndexChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.sort_combo, 1)

        layout.addLayout(filter_bar)

        # List of marked files with multi-selection
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)

        # Bottom action bar
        action_bar = QHBoxLayout()
        self.btn_unmark = QPushButton(tr('action.unmark_delete'))
        self.btn_unmark.clicked.connect(self.unmark_selected)
        action_bar.addWidget(self.btn_unmark)

        self.btn_delete_perm = QPushButton(tr('action.delete_permanently'))
        self.btn_delete_perm.setStyleSheet("background: #AF3029; color: white; font-weight: bold;")
        self.btn_delete_perm.clicked.connect(self.delete_permanently_selected)
        action_bar.addWidget(self.btn_delete_perm)

        action_bar.addStretch()

        self.btn_empty_trash = QPushButton(tr('action.empty_trash'))
        self.btn_empty_trash.setStyleSheet("background: #5E1412; color: white; font-weight: bold;")
        self.btn_empty_trash.clicked.connect(self.empty_trash)
        action_bar.addWidget(self.btn_empty_trash)

        layout.addLayout(action_bar)

    def load_trash(self):
        try:
            db_path = str(get_db_path())
            db = indexo_core.PyIndexoDatabase.open(db_path)
            self.marked_files = db.list_marked_for_deletion()
            self.apply_filter()
        except Exception as e:
            logger.error("Failed to load trash: {}", e)

    def apply_filter(self):
        query = self.search_input.text().lower()
        sort_mode = self.sort_combo.currentIndex()

        self.filtered_files = [
            f for f in self.marked_files
            if not query or query in f.get("rel_path", "").lower() or query in f.get("abs_path", "").lower()
        ]

        if sort_mode == 1:  # Size
            self.filtered_files.sort(key=lambda f: f.get("size", 0), reverse=True)
        elif sort_mode == 2:  # Marked date
            self.filtered_files.sort(key=lambda f: f.get("marked_at") or 0, reverse=True)
        else:
            self.filtered_files.sort(key=lambda f: f.get("rel_path", "").lower())

        total_bytes = sum(f.get("size", 0) for f in self.marked_files)
        total_mb = total_bytes / (1024 * 1024)
        self.lbl_stats.setText(tr("trash.stats", count=len(self.marked_files), size=f"{total_mb:.1f} MB"))

        self.list_widget.clear()
        for f in self.filtered_files:
            name = Path(f["rel_path"]).name
            size_kb = f.get("size", 0) / 1024
            item = QListWidgetItem(f"{name}  [{size_kb:.1f} KB]  —  {f.get('abs_path')}")
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.list_widget.addItem(item)

    def get_selected_files(self) -> List[Dict[str, Any]]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.list_widget.selectedItems()]

    def unmark_selected(self):
        selected = self.get_selected_files()
        if not selected:
            QMessageBox.information(self, "Indexo", tr("dialog.no_file_selected"))
            return

        db_path = str(get_db_path())
        db = indexo_core.PyIndexoDatabase.open(db_path)

        for f in selected:
            file_id = f["id"]
            db.mark_for_deletion(file_id, False)
            logger.info("AUDIT: User unmarked file from trash: ID={}, Path={}", file_id, f.get("abs_path"))

        self.load_trash()
        self.trash_updated.emit()
        QMessageBox.information(self, "Indexo", tr("dialog.unmark_success", count=len(selected)))

    def delete_permanently_selected(self):
        selected = self.get_selected_files()
        if not selected:
            QMessageBox.information(self, "Indexo", tr("dialog.no_file_selected"))
            return

        count = len(selected)
        msg = tr("dialog.confirm_permanent_batch", count=count)
        reply = QMessageBox.warning(
            self,
            tr("dialog.confirm_delete_title"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            db_path = str(get_db_path())
            db = indexo_core.PyIndexoDatabase.open(db_path)

            deleted_count = 0
            for f in selected:
                file_id = f["id"]
                path = Path(f["abs_path"])
                if send_file_to_recycle_bin(path):
                    db.delete_file_record(file_id)
                    deleted_count += 1
                    logger.info("AUDIT: User permanently deleted file via Recycle Bin: ID={}, Path={}", file_id, path)

            self.load_trash()
            self.trash_updated.emit()
            QMessageBox.information(self, "Indexo", tr("dialog.delete_perm_success", count=deleted_count))

    def empty_trash(self):
        if not self.marked_files:
            QMessageBox.information(self, "Indexo", tr("dialog.trash_already_empty"))
            return

        count = len(self.marked_files)
        total_mb = sum(f.get("size", 0) for f in self.marked_files) / (1024 * 1024)

        msg = tr("dialog.confirm_empty_trash", count=count, size=f"{total_mb:.1f} MB")
        reply = QMessageBox.critical(
            self,
            tr("action.empty_trash"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            db_path = str(get_db_path())
            db = indexo_core.PyIndexoDatabase.open(db_path)

            for f in self.marked_files:
                file_id = f["id"]
                path = Path(f["abs_path"])
                delete_file_permanently(path)
                db.delete_file_record(file_id)
                logger.info("AUDIT: User emptied trash file permanently: ID={}, Path={}", file_id, path)

            self.load_trash()
            self.trash_updated.emit()
            QMessageBox.information(self, "Indexo", tr("dialog.trash_emptied_success"))

    def retranslate_ui(self):
        self.search_input.setPlaceholderText(tr("search.filter_trash"))
        curr_sort = self.sort_combo.currentIndex()
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        self.sort_combo.addItems([tr("sort.name"), tr("sort.size"), tr("sort.date_marked")])
        self.sort_combo.setCurrentIndex(curr_sort if curr_sort >= 0 else 0)
        self.sort_combo.blockSignals(False)
        self.btn_unmark.setText(tr('action.unmark_delete'))
        self.btn_delete_perm.setText(tr('action.delete_permanently'))
        self.btn_empty_trash.setText(tr('action.empty_trash'))
        self.apply_filter()
