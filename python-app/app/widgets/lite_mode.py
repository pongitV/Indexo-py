import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QFileDialog, QMessageBox,
    QHeaderView, QCheckBox
)
import indexo_core
from app.widgets.smooth_scroll import SmoothTableWidget
from app.config.settings_manager import SettingsManager
from app.classification.entity_regex import extract_primary_date, generate_standard_filename
from app.i18n.language_manager import tr
from loguru import logger

class LiteModeView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_mgr = SettingsManager()
        self.target_dir: Optional[Path] = None
        self.rename_plan: List[Dict[str, Any]] = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        top_layout = QHBoxLayout()
        self.btn_select_folder = QPushButton(f"📁 {tr('action.select_folder')}")
        self.btn_select_folder.clicked.connect(self.select_folder)
        top_layout.addWidget(self.btn_select_folder)

        self.lbl_folder_path = QLabel(tr("view.no_folder_selected"))
        self.lbl_folder_path.setObjectName("lbl_subtext")
        self.lbl_folder_path.setFont(QFont("Consolas", 10))
        top_layout.addWidget(self.lbl_folder_path)

        top_layout.addStretch()

        self.btn_apply = QPushButton(tr("lite.btn_rename_only"))
        self.btn_apply.setStyleSheet("background: #205EA6; color: white; font-weight: bold; padding: 6px 16px; font-size: 13px;")
        self.btn_apply.clicked.connect(self.apply_renames)
        self.btn_apply.setEnabled(False)
        top_layout.addWidget(self.btn_apply)

        layout.addLayout(top_layout)

        # Table with Antes x Depois
        self.table = SmoothTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            tr("table.include"),
            tr("table.original_name"),
            tr("table.suggested_name"),
            tr("table.status")
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, tr("action.select_folder_lite"))
        if not folder:
            return

        self.target_dir = Path(folder)
        self.lbl_folder_path.setText(str(self.target_dir))
        self.scan_and_plan()

    def scan_and_plan(self):
        if not self.target_dir or not self.target_dir.exists():
            return

        ignored_exts = set(self.settings_mgr.get("ignored_extensions", []))
        rename_cfg = self.settings_mgr.data.get("configs", {})
        self.rename_plan = []

        for p in self.target_dir.glob("*"):
            if not p.is_file():
                continue

            ext = p.suffix.lower()
            if ext in ignored_exts or p.name.startswith("."):
                self.rename_plan.append({
                    "src_path": p,
                    "old_name": p.name,
                    "new_name": p.name,
                    "status": tr("status.ignored"),
                    "include": False
                })
                continue

            date_str = extract_primary_date("", int(p.stat().st_mtime))
            suggested = generate_standard_filename(date_str, None, "", ext, p.stem, rename_cfg)
            
            sanitized = indexo_core.py_sanitize_filename(suggested)
            resolved = indexo_core.py_resolve_collision(str(self.target_dir), sanitized)
            new_name = Path(resolved).name

            self.rename_plan.append({
                "src_path": p,
                "old_name": p.name,
                "new_name": new_name,
                "status": tr("status.ready_to_rename") if new_name != p.name else tr("status.no_change"),
                "include": new_name != p.name
            })

        self.populate_table()
        self.btn_apply.setEnabled(any(it["include"] for it in self.rename_plan))

    def populate_table(self):
        self.table.setRowCount(len(self.rename_plan))
        for row, it in enumerate(self.rename_plan):
            chk = QCheckBox()
            chk.setChecked(it["include"])
            chk.stateChanged.connect(lambda state, r=row: self.on_check_changed(r, state))
            self.table.setCellWidget(row, 0, chk)

            self.table.setItem(row, 1, QTableWidgetItem(it["old_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(it["new_name"]))
            self.table.setItem(row, 3, QTableWidgetItem(it["status"]))

    def on_check_changed(self, row: int, state: int):
        self.rename_plan[row]["include"] = bool(state == Qt.CheckState.Checked.value or state == 2)
        self.btn_apply.setEnabled(any(it["include"] for it in self.rename_plan))

    def apply_renames(self):
        if not self.target_dir:
            return

        to_rename = [it for it in self.rename_plan if it["include"]]
        if not to_rename:
            QMessageBox.information(self, "Indexo", tr("lite.no_files_selected"))
            return

        msg = tr("lite.confirm_rename_msg", count=len(to_rename))
        reply = QMessageBox.question(
            self,
            tr("lite.confirm_rename_title"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        applied = 0
        for it in to_rename:
            src = it["src_path"]
            dest = self.target_dir / it["new_name"]
            try:
                os.replace(src, dest)
                applied += 1
                logger.info("Rename Only: {} -> {}", src.name, dest.name)
            except Exception as e:
                logger.error("Rename Only failed on {}: {}", src.name, e)

        QMessageBox.information(self, "Indexo", tr("lite.rename_success", count=applied))
        self.scan_and_plan()

    def retranslate_ui(self):
        self.btn_select_folder.setText(f"📁 {tr('action.select_folder')}")
        self.btn_apply.setText(tr("lite.btn_rename_only"))
        self.table.setHorizontalHeaderLabels([
            tr("table.include"),
            tr("table.original_name"),
            tr("table.suggested_name"),
            tr("table.status")
        ])
