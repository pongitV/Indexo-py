import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidgetItem, QPushButton, QFileDialog, QMessageBox,
    QHeaderView, QCheckBox
)
import indexo_core
from app.widgets.smooth_scroll import SmoothTableWidget
from app.config.settings_manager import SettingsManager
from app.i18n.language_manager import tr, LanguageManager
from app.classification.rule_loader import RuleLoader
from loguru import logger

class FolderReviewView(QWidget):
    """
    Modo 'Mover Apenas': Organiza e agrupa arquivos em pastas sem alterar os nomes originais dos arquivos.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_mgr = SettingsManager()
        self.target_dir: Optional[Path] = None
        self.move_plan: List[Dict[str, Any]] = []
        self.rule_loader = RuleLoader()
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

        self.btn_clean_empty = QPushButton(tr('action.clean_empty_folders'))
        self.btn_clean_empty.clicked.connect(self.clean_empty_folders)
        top_layout.addWidget(self.btn_clean_empty)

        self.btn_apply = QPushButton(tr("folder_review.btn_move_only"))
        self.btn_apply.setStyleSheet("background: #205EA6; color: white; font-weight: bold; padding: 6px 16px; font-size: 13px;")
        self.btn_apply.clicked.connect(self.apply_moves)
        self.btn_apply.setEnabled(False)
        top_layout.addWidget(self.btn_apply)

        layout.addLayout(top_layout)

        # Table with Checkbox, Original Name, Target Folder, Status
        self.table = SmoothTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            tr("table.include"),
            tr("folder_review.col_original"),
            tr("folder_review.col_dest_folder"),
            tr("table.status")
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, tr("action.select_folder"))
        if not folder:
            return

        self.target_dir = Path(folder)
        self.lbl_folder_path.setText(str(self.target_dir))
        self.scan_and_plan()

    def scan_preorganized_folders(self, root_dir: Path):
        """Called automatically when a folder is loaded in MainWindow."""
        self.target_dir = root_dir
        self.lbl_folder_path.setText(str(root_dir))
        self.scan_and_plan()

    def load_from_items(self, items: List[Dict[str, Any]], root_dir: Path):
        self.target_dir = root_dir
        self.lbl_folder_path.setText(str(root_dir))
        self.move_plan = []

        dest_root_name = "Indexo_Files"
        default_general = "Geral" if LanguageManager.get_instance().current_language == "ptBR" else "General"

        for it in items:
            abs_p = Path(it.get("abs_path", ""))
            if not abs_p.exists() or dest_root_name in abs_p.parts:
                continue

            caminho_fisico = it.get("caminho_fisico") or it.get("category") or default_general
            dest_rel = f"{dest_root_name}/{caminho_fisico}"

            self.move_plan.append({
                "src_path": abs_p,
                "filename": abs_p.name,
                "dest_rel_folder": dest_rel,
                "status": tr("status.ready_to_move", default="Pronto para mover") if it.get("status") == "identificado" else tr("status.pending"),
                "include": it.get("status") == "identificado"
            })

        self.populate_table()
        self.btn_apply.setEnabled(any(it["include"] for it in self.move_plan))

    def scan_and_plan(self):
        if not self.target_dir or not self.target_dir.exists():
            return

        ignored_exts = set(self.settings_mgr.get("ignored_extensions", []))
        dest_root_name = "Indexo_Files"
        default_general = "Geral" if LanguageManager.get_instance().current_language == "ptBR" else "General"
        self.move_plan = []

        for p in self.target_dir.rglob("*"):
            if not p.is_file() or dest_root_name in p.parts:
                continue

            ext = p.suffix.lower()
            if ext in ignored_exts or p.name.startswith("."):
                continue

            # Classify file category without modifying filename
            rule = self.rule_loader.classify_file(p.name, "")
            caminho_fisico = rule.get("caminho_fisico") if rule else default_general
            dest_rel = f"{dest_root_name}/{caminho_fisico}"

            self.move_plan.append({
                "src_path": p,
                "filename": p.name,
                "dest_rel_folder": dest_rel,
                "status": tr("status.ready_to_move", default="Pronto para mover"),
                "include": True
            })

        self.populate_table()
        self.btn_apply.setEnabled(any(it["include"] for it in self.move_plan))

    def populate_table(self):
        self.table.setRowCount(len(self.move_plan))
        for row, it in enumerate(self.move_plan):
            chk = QCheckBox()
            chk.setChecked(it["include"])
            chk.stateChanged.connect(lambda state, r=row: self.on_check_changed(r, state))
            self.table.setCellWidget(row, 0, chk)

            item_file = QTableWidgetItem(f"📄 {it['filename']}")
            item_file.setFont(QFont("Inter", 10, QFont.Weight.Medium))
            self.table.setItem(row, 1, item_file)

            item_dest = QTableWidgetItem(f"📁 {it['dest_rel_folder']}")
            item_dest.setFont(QFont("Inter", 10))
            self.table.setItem(row, 2, item_dest)

            item_status = QTableWidgetItem(it["status"])
            item_status.setFont(QFont("Inter", 9))
            self.table.setItem(row, 3, item_status)

    def on_check_changed(self, row: int, state: int):
        self.move_plan[row]["include"] = bool(state == Qt.CheckState.Checked.value or state == 2)
        self.btn_apply.setEnabled(any(it["include"] for it in self.move_plan))

    def apply_moves(self):
        if not self.target_dir:
            return

        to_move = [it for it in self.move_plan if it["include"]]
        if not to_move:
            QMessageBox.information(self, "Indexo", tr("folder_review.no_files_selected"))
            return

        msg = tr("folder_review.confirm_move_msg", count=len(to_move))
        reply = QMessageBox.question(
            self,
            tr("folder_review.confirm_move_title"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        moved = 0
        for it in self.move_plan:
            if it["include"]:
                src = it["src_path"]
                if not src.exists():
                    continue

                dest_dir = self.target_dir / it["dest_rel_folder"]
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                # Keep exact original filename, resolve collision safely
                resolved = indexo_core.py_resolve_collision(str(dest_dir), src.name)
                dest = Path(resolved)

                try:
                    os.replace(src, dest)
                    moved += 1
                    logger.info("Move Only: {} -> {}", src, dest)
                except Exception as e:
                    logger.error("Failed to move file {}: {}", src, e)

        QMessageBox.information(self, "Indexo", tr("folder_review.move_success", count=moved))
        self.scan_and_plan()

    def retranslate_ui(self):
        self.btn_select_folder.setText(f"📁 {tr('action.select_folder')}")
        self.btn_clean_empty.setText(tr("action.clean_empty_folders"))
        self.btn_apply.setText(tr("folder_review.btn_move_only"))
        self.table.setHorizontalHeaderLabels([
            tr("table.include"),
            tr("folder_review.col_original"),
            tr("folder_review.col_dest_folder"),
            tr("table.status")
        ])

    def clean_empty_folders(self):
        if not self.target_dir or not self.target_dir.exists():
            QMessageBox.information(self, "Indexo", tr("dialog.select_root_first"))
            return

        empty_folders = []
        for root, dirs, files in os.walk(self.target_dir, topdown=False):
            p = Path(root)
            if p == self.target_dir or p.name == "Indexo_Files" or p.name.startswith("."):
                continue
            if not os.listdir(p):
                empty_folders.append(p)

        if not empty_folders:
            QMessageBox.information(self, "Indexo", tr("dialog.no_empty_folders"))
            return

        msg = tr("dialog.confirm_clean_empty", count=len(empty_folders))
        reply = QMessageBox.question(self, tr("action.clean_empty_folders"), msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            removed = 0
            for d in empty_folders:
                try:
                    d.rmdir()
                    removed += 1
                    logger.info("Removed empty directory: {}", d)
                except Exception as e:
                    logger.warning("Could not remove empty folder {}: {}", d, e)
            QMessageBox.information(self, "Indexo", tr("dialog.clean_empty_success", count=removed))
