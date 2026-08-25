from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QPushButton,
    QMessageBox, QSplitter, QFrame, QScrollArea
)
import indexo_core
from app.widgets.smooth_scroll import SmoothScrollArea
from app.i18n.language_manager import tr
from app.config.settings_manager import get_db_path
from loguru import logger

class DuplicateView(QWidget):
    file_marked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups: List[List[Dict[str, Any]]] = []
        self.filtered_groups: List[List[Dict[str, Any]]] = []
        self.current_group_idx: int = -1
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header with search and filters
        top_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("search.filter_duplicates"))
        self.search_input.textChanged.connect(self.apply_filter)
        top_bar.addWidget(self.search_input, 2)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([tr("sort.name"), tr("sort.size"), tr("sort.date")])
        self.sort_combo.currentIndexChanged.connect(self.apply_filter)
        top_bar.addWidget(self.sort_combo, 1)

        layout.addLayout(top_bar)

        # Splitter: Top = Duplicate groups list, Bottom = Side-by-side comparison
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top list widget container
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        self.lbl_list_title = QLabel(tr("duplicate.select_to_compare"))
        self.lbl_list_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        top_layout.addWidget(self.lbl_list_title)

        self.list_groups = QListWidget()
        self.list_groups.setFont(QFont("Inter", 10))
        self.list_groups.currentRowChanged.connect(self.on_group_selected)
        top_layout.addWidget(self.list_groups)
        splitter.addWidget(top_widget)

        # Bottom comparison container
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)

        self.lbl_comp_title = QLabel(tr("duplicate.comp_title"))
        self.lbl_comp_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        bottom_layout.addWidget(self.lbl_comp_title)

        self.comparison_container = QWidget()
        self.comparison_layout = QHBoxLayout(self.comparison_container)
        self.comparison_layout.setContentsMargins(8, 8, 8, 8)
        self.comparison_layout.setSpacing(12)

        self.scroll_comp = SmoothScrollArea()
        self.scroll_comp.setWidgetResizable(True)
        self.scroll_comp.setWidget(self.comparison_container)
        bottom_layout.addWidget(self.scroll_comp)
        splitter.addWidget(bottom_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

    def load_duplicates(self, root_id: int):
        try:
            db_path = str(get_db_path())
            db = indexo_core.PyIndexoDatabase.open(db_path)
            self.groups = db.find_duplicates(root_id)
            self.apply_filter()
        except Exception as e:
            logger.error("Failed to load duplicates: {}", e)

    def apply_filter(self):
        query = self.search_input.text().lower()
        sort_mode = self.sort_combo.currentIndex()

        self.filtered_groups = []
        for g in self.groups:
            if not query or any(query in f.get("rel_path", "").lower() for f in g):
                self.filtered_groups.append(g)

        # Sorting
        if sort_mode == 1:  # Size
            self.filtered_groups.sort(key=lambda g: g[0].get("size", 0), reverse=True)
        elif sort_mode == 2:  # Date
            self.filtered_groups.sort(key=lambda g: g[0].get("mtime", 0), reverse=True)
        else:
            self.filtered_groups.sort(key=lambda g: g[0].get("rel_path", "").lower())

        self.list_groups.clear()
        for idx, g in enumerate(self.filtered_groups):
            first = g[0]
            name = Path(first.get("rel_path", "")).name
            size_kb = first.get("size", 0) / 1024
            summary_txt = tr("duplicate.copies_summary", count=len(g), size=f"{size_kb:.1f} KB")
            item = QListWidgetItem(f"{name} ({summary_txt})")
            self.list_groups.addItem(item)

        if self.filtered_groups:
            self.list_groups.setCurrentRow(0)
        else:
            self.clear_comparison()

    def clear_comparison(self):
        while self.comparison_layout.count():
            child = self.comparison_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def on_group_selected(self, row: int):
        if row < 0 or row >= len(self.filtered_groups):
            self.clear_comparison()
            return

        self.current_group_idx = row
        group = self.filtered_groups[row]
        self.render_comparison(group)

    def render_comparison(self, group: List[Dict[str, Any]]):
        self.clear_comparison()

        for f in group:
            col = QFrame()
            col.setObjectName("comparison_col")
            col_layout = QVBoxLayout(col)

            lbl_name = QLabel(Path(f["rel_path"]).name)
            lbl_name.setFont(QFont("Inter", 10, QFont.Weight.Bold))
            lbl_name.setWordWrap(True)
            col_layout.addWidget(lbl_name)

            path_txt = QLabel(f"{tr('meta.path')}: {f.get('abs_path')}")
            path_txt.setFont(QFont("Consolas", 8))
            path_txt.setWordWrap(True)
            col_layout.addWidget(path_txt)

            size_txt = QLabel(f"{tr('meta.size')}: {f.get('size', 0) / 1024:.1f} KB")
            col_layout.addWidget(size_txt)

            hash_txt = QLabel(f"{tr('meta.hash')}: {f.get('hash_sha256', '')[:16]}...")
            hash_txt.setFont(QFont("Consolas", 8))
            col_layout.addWidget(hash_txt)

            col_layout.addStretch()

            # Action button
            btn_mark_del = QPushButton(tr('action.mark_delete'))
            btn_mark_del.setStyleSheet("background: #AF3029; color: white; font-weight: bold; padding: 6px;")
            btn_mark_del.clicked.connect(lambda _, file_data=f: self.mark_for_deletion_prompt(file_data))
            col_layout.addWidget(btn_mark_del)

            self.comparison_layout.addWidget(col)

    def mark_for_deletion_prompt(self, file_data: Dict[str, Any]):
        file_id = file_data.get("id")
        name = Path(file_data.get("rel_path", "")).name

        msg = tr("dialog.confirm_mark_trash_named", name=name)
        reply = QMessageBox.question(
            self,
            tr("dialog.confirm_delete_title"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                db_path = str(get_db_path())
                db = indexo_core.PyIndexoDatabase.open(db_path)
                db.mark_for_deletion(file_id, True)
                logger.info("AUDIT: User marked duplicate file for deletion: ID={}, Path={}", file_id, file_data.get("abs_path"))
                self.file_marked.emit()
                if self.groups and len(self.groups) > 0:
                    root_id = self.groups[0][0].get("folder_root_id", 1)
                    self.load_duplicates(root_id)
            except Exception as e:
                logger.error("Failed to mark duplicate for deletion: {}", e)
                QMessageBox.critical(self, tr("dialog.error_title"), tr("dialog.mark_file_fail", err=str(e)))

    def retranslate_ui(self):
        self.search_input.setPlaceholderText(tr("search.filter_duplicates"))
        curr_sort = self.sort_combo.currentIndex()
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        self.sort_combo.addItems([tr("sort.name"), tr("sort.size"), tr("sort.date")])
        self.sort_combo.setCurrentIndex(curr_sort if curr_sort >= 0 else 0)
        self.sort_combo.blockSignals(False)
        self.lbl_list_title.setText(tr("duplicate.select_to_compare"))
        self.lbl_comp_title.setText(tr("duplicate.comp_title"))
        self.apply_filter()
