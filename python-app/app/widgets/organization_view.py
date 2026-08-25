import os
import csv
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QBrush, QIcon, QAction, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QFileDialog, QMessageBox,
    QSplitter, QFrame, QInputDialog, QMenu, QDialog,
    QHeaderView, QComboBox, QTableWidgetItem
)
from app.i18n.language_manager import tr, LanguageManager
from app.config.settings_manager import SettingsManager
from app.widgets.smooth_scroll import SmoothTreeWidget, SmoothTableWidget
from app.utils.formatters import format_file_size
from app.widgets.file_context_menu import (
    FileTagEditDialog, FileMoveCategoryDialog, FilePropertiesDialog,
    open_with_default_app, open_in_explorer, copy_path_to_clipboard,
    show_file_context_menu
)
from loguru import logger

class ExplorerTreeWidget(SmoothTreeWidget):
    """Custom TreeWidget with standard explorer keyboard shortcuts (F2, Del, F5, Ctrl+C) and smooth scrolling."""
    rename_requested = Signal()
    delete_requested = Signal()
    refresh_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_F2:
            self.rename_requested.emit()
        elif event.key() == Qt.Key.Key_Delete:
            self.delete_requested.emit()
        elif event.key() == Qt.Key.Key_F5:
            self.refresh_requested.emit()
        elif event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            item = self.currentItem()
            if item:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data and data.get("abs_path"):
                    copy_path_to_clipboard(data["abs_path"])
        else:
            super().keyPressEvent(event)


class OrganizationSplitView(QWidget):
    file_selected = Signal(str)  # abs_path
    folder_perm_toggled = Signal(str, bool)  # folder_name, is_allowed
    tag_rename_requested = Signal(str, str)  # tag_id, new_name
    file_reclassified = Signal(str, str, str)  # abs_path, new_tag, new_category
    file_marked_trash = Signal(str)  # abs_path
    bundle_action_changed = Signal(str, str)  # folder_rel, action
    refresh_requested = Signal()
    execute_requested = Signal()
    restore_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_mgr = SettingsManager()
        self.root_dir: Optional[Path] = None
        self.items: List[Dict[str, Any]] = []
        self.allowed_folders: Set[str] = set()
        self.cohesive_bundles: List[Dict[str, Any]] = []
        self.user_tags: List[Dict[str, Any]] = []
        self.selected_folder_info: Optional[Dict[str, Any]] = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 1. Top Summary Card
        self.card_top = QFrame()
        self.card_top.setObjectName("card_top")
        card_layout = QHBoxLayout(self.card_top)
        card_layout.setContentsMargins(12, 8, 12, 8)

        self.lbl_summary = QLabel(tr("view.select_folder_hint"))
        self.lbl_summary.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        card_layout.addWidget(self.lbl_summary)

        card_layout.addStretch()

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.setStyleSheet("padding: 4px 14px; font-size: 13px;")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        card_layout.addWidget(self.btn_refresh)

        layout.addWidget(self.card_top)

        # 2. Main Central Splitter: ANTES (Origem) x DEPOIS (Semântico Sugerido)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: ANTES (Origem)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        left_header = QHBoxLayout()
        self.lbl_before = QLabel(tr("view.before_title"))
        self.lbl_before.setObjectName("lbl_before")
        self.lbl_before.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        left_header.addWidget(self.lbl_before)
        left_header.addStretch()
        left_layout.addLayout(left_header)

        self.tree_before = ExplorerTreeWidget()
        self.tree_before.setHeaderHidden(True)
        self.tree_before.setFont(QFont("Inter", 12))
        self.tree_before.setStyleSheet(
            "QTreeWidget { font-size: 13px; }"
            "QTreeWidget::item { min-height: 30px; padding: 4px 6px; }"
        )
        self.tree_before.itemClicked.connect(self.on_before_item_clicked)
        self.tree_before.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree_before.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_before.customContextMenuRequested.connect(lambda pos: self.show_tree_context_menu(self.tree_before, pos))
        self.tree_before.rename_requested.connect(lambda: self.trigger_rename_current(self.tree_before))
        self.tree_before.delete_requested.connect(lambda: self.trigger_delete_current(self.tree_before))
        self.tree_before.refresh_requested.connect(self.refresh_requested.emit)
        left_layout.addWidget(self.tree_before)
        splitter.addWidget(left_widget)

        # Right Panel: DEPOIS (Semântico Sugerido)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        right_header = QHBoxLayout()
        self.lbl_after = QLabel(tr("view.after_title"))
        self.lbl_after.setObjectName("lbl_after")
        self.lbl_after.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        right_header.addWidget(self.lbl_after)
        right_header.addStretch()
        right_layout.addLayout(right_header)

        self.tree_after = ExplorerTreeWidget()
        self.tree_after.setHeaderHidden(True)
        self.tree_after.setFont(QFont("Inter", 12))
        self.tree_after.setStyleSheet(
            "QTreeWidget { font-size: 13px; }"
            "QTreeWidget::item { min-height: 30px; padding: 4px 6px; }"
        )
        self.tree_after.setVerticalScrollMode(QTreeWidget.ScrollMode.ScrollPerPixel)
        self.tree_after.setHorizontalScrollMode(QTreeWidget.ScrollMode.ScrollPerPixel)
        self.tree_after.itemClicked.connect(self.on_after_item_clicked)
        self.tree_after.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree_after.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_after.customContextMenuRequested.connect(lambda pos: self.show_tree_context_menu(self.tree_after, pos))
        self.tree_after.rename_requested.connect(lambda: self.trigger_rename_current(self.tree_after))
        self.tree_after.delete_requested.connect(lambda: self.trigger_delete_current(self.tree_after))
        right_layout.addWidget(self.tree_after)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        # 3. Cohesive Bundles Panel (Embaixo das Árvores de Organização)
        self.card_cohesive = QFrame()
        self.card_cohesive.setObjectName("card_top")
        self.card_cohesive.setStyleSheet("QFrame#card_top { border: 1px solid rgba(32, 94, 166, 0.3); border-radius: 6px; padding: 4px; }")
        cohesive_layout = QVBoxLayout(self.card_cohesive)
        cohesive_layout.setContentsMargins(10, 8, 10, 8)
        cohesive_layout.setSpacing(6)

        cohesive_top = QHBoxLayout()
        self.lbl_cohesive_title = QLabel(tr("cohesive.title"))
        self.lbl_cohesive_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        cohesive_top.addWidget(self.lbl_cohesive_title)
        cohesive_top.addStretch()

        self.btn_select_all_cohesive = QPushButton(tr("cohesive.select_all_parent"))
        self.btn_select_all_cohesive.setStyleSheet("padding: 3px 10px; font-size: 11px;")
        self.btn_select_all_cohesive.clicked.connect(self.set_all_cohesive_to_move_parent)
        cohesive_top.addWidget(self.btn_select_all_cohesive)
        cohesive_layout.addLayout(cohesive_top)

        self.lbl_cohesive_desc = QLabel(tr("cohesive.desc"))
        self.lbl_cohesive_desc.setObjectName("lbl_subtext")
        self.lbl_cohesive_desc.setFont(QFont("Inter", 9))
        self.lbl_cohesive_desc.setWordWrap(True)
        cohesive_layout.addWidget(self.lbl_cohesive_desc)

        self.table_cohesive = SmoothTableWidget(0, 5)
        self.table_cohesive.setHorizontalHeaderLabels([
            tr("cohesive.col_folder"),
            tr("cohesive.col_type"),
            tr("cohesive.col_main"),
            tr("cohesive.col_files"),
            tr("cohesive.col_action")
        ])
        self.table_cohesive.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_cohesive.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cohesive.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_cohesive.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cohesive.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_cohesive.setMaximumHeight(140)
        cohesive_layout.addWidget(self.table_cohesive)

        self.card_cohesive.setVisible(False)
        layout.addWidget(self.card_cohesive)

        # 4. Contextual Options Card for Selected Folder
        self.card_options = QFrame()
        self.card_options.setObjectName("card_options")
        opts_layout = QHBoxLayout(self.card_options)
        opts_layout.setContentsMargins(10, 8, 10, 8)
        opts_layout.setSpacing(10)

        self.lbl_selected_folder = QLabel(tr("view.click_folder_hint"))
        self.lbl_selected_folder.setFont(QFont("Inter", 9, QFont.Weight.Medium))
        opts_layout.addWidget(self.lbl_selected_folder, 1)

        self.btn_open_explorer = QPushButton(tr('action.open_explorer'))
        self.btn_open_explorer.clicked.connect(self.open_selected_folder_in_explorer)
        self.btn_open_explorer.setVisible(False)
        opts_layout.addWidget(self.btn_open_explorer)

        self.btn_rename_tag = QPushButton(tr('action.rename_tag'))
        self.btn_rename_tag.clicked.connect(self.rename_selected_tag)
        self.btn_rename_tag.setVisible(False)
        opts_layout.addWidget(self.btn_rename_tag)

        layout.addWidget(self.card_options)

        # 5. Bottom Action Bar: Restore, Export CSV and Execute
        bottom_bar = QHBoxLayout()
        self.btn_restore = QPushButton(tr('action.restore_last_session'))
        self.btn_restore.setStyleSheet("background: #5E4080; color: white; font-weight: bold; padding: 8px 16px;")
        self.btn_restore.clicked.connect(self.restore_requested.emit)
        self.btn_restore.setVisible(False)
        bottom_bar.addWidget(self.btn_restore)

        bottom_bar.addStretch()

        self.btn_export_csv = QPushButton(tr('action.export_csv'))
        self.btn_export_csv.setStyleSheet("padding: 8px 16px; font-size: 13px;")
        self.btn_export_csv.clicked.connect(self.export_csv)
        bottom_bar.addWidget(self.btn_export_csv)

        self.btn_organize = QPushButton(f"{tr('action.organize')} (Ctrl+Enter)")
        self.btn_organize.setStyleSheet("background: #205EA6; color: white; font-weight: bold; padding: 8px 24px; font-size: 13px;")
        self.btn_organize.clicked.connect(self.execute_requested.emit)
        bottom_bar.addWidget(self.btn_organize)

        layout.addLayout(bottom_bar)

    def clear(self):
        self.tree_before.clear()
        self.tree_after.clear()
        self.items.clear()
        self.cohesive_bundles.clear()
        self.table_cohesive.setRowCount(0)
        self.card_cohesive.setVisible(False)
        self.selected_folder_info = None
        self.update_options_card()

    def populate_results(
        self,
        items: List[Dict[str, Any]],
        root_dir: Path,
        allowed_folders: Set[str],
        user_tags: Optional[List[Dict[str, Any]]] = None,
        cohesive_bundles: Optional[List[Dict[str, Any]]] = None
    ):
        self.items = items
        self.root_dir = root_dir
        self.allowed_folders = allowed_folders
        self.user_tags = user_tags or []
        if cohesive_bundles is not None:
            self.cohesive_bundles = cohesive_bundles

        total = len(items)
        identified = sum(1 for it in items if it.get("status") == "identificado")
        pending = sum(1 for it in items if it.get("status") == "pendente")
        confirmed = sum(1 for it in items if it.get("folder_status") == "confirmado")
        intruders = sum(1 for it in items if it.get("is_intruder", False))

        summary_text = (
            f"{total} analisados  ·  "
            f"{confirmed} confirmados na pasta  ·  "
            f"{intruders} intrusos realocados  ·  "
            f"{pending} pendentes"
        )
        self.lbl_summary.setText(summary_text)

        # --- A. Populating Cohesive Bundles Table ---
        self._populate_cohesive_table()

        # --- B. Populating Tree ANTES (Origem) ---
        self._populate_tree_before(total)

        # --- C. Populating Tree DEPOIS (Semântico Sugerido) ---
        self._populate_tree_after(total)

    def _populate_cohesive_table(self):
        if not self.cohesive_bundles:
            self.card_cohesive.setVisible(False)
            self.table_cohesive.setRowCount(0)
            return

        self.card_cohesive.setVisible(True)
        self.table_cohesive.setRowCount(len(self.cohesive_bundles))

        for row, bundle in enumerate(self.cohesive_bundles):
            folder_name = bundle.get("folder_name", "")
            cat = bundle.get("category", "")
            primary_exe = bundle.get("primary_executable") or bundle.get("reason", "-")
            file_count = bundle.get("file_count", 0)
            size_str = format_file_size(bundle.get("total_size", 0))

            item_folder = QTableWidgetItem(f"{folder_name}")
            item_folder.setFont(QFont("Inter", 10, QFont.Weight.Bold))
            self.table_cohesive.setItem(row, 0, item_folder)

            item_cat = QTableWidgetItem(f"{cat}")
            item_cat.setFont(QFont("Inter", 9, QFont.Weight.Medium))
            self.table_cohesive.setItem(row, 1, item_cat)

            item_main = QTableWidgetItem(f"{primary_exe}")
            item_main.setFont(QFont("Inter", 9))
            self.table_cohesive.setItem(row, 2, item_main)

            item_count = QTableWidgetItem(f"{file_count} arquivos ({size_str})")
            item_count.setFont(QFont("Inter", 9))
            self.table_cohesive.setItem(row, 3, item_count)

            combo = QComboBox()
            combo.setFont(QFont("Inter", 9))
            combo.addItem(tr("bundle.action_move_parent"), "move_parent")
            combo.addItem(tr("bundle.action_keep"), "keep")
            combo.addItem(tr("bundle.action_disassemble"), "disassemble")

            curr_action = bundle.get("action", "move_parent")
            idx = combo.findData(curr_action)
            if idx >= 0:
                combo.setCurrentIndex(idx)

            folder_rel = bundle.get("folder_rel", "")
            combo.currentIndexChanged.connect(lambda _, c=combo, f=folder_rel: self._on_bundle_combo_changed(f, c))
            self.table_cohesive.setCellWidget(row, 4, combo)

    def _on_bundle_combo_changed(self, folder_rel: str, combo: QComboBox):
        action = combo.currentData()
        self.bundle_action_changed.emit(folder_rel, action)
        total = len(self.items)
        self._populate_tree_after(total)

    def set_all_cohesive_to_move_parent(self):
        for row, bundle in enumerate(self.cohesive_bundles):
            bundle["action"] = "move_parent"
            combo = self.table_cohesive.cellWidget(row, 4)
            if isinstance(combo, QComboBox):
                combo.setCurrentIndex(0)
        self._populate_tree_after(len(self.items))

    def _populate_tree_before(self, total: int):
        self.tree_before.clear()
        if not self.items:
            return

        bundle_folder_names = {b.get("folder_name", ""): b for b in self.cohesive_bundles}

        root_name = self.root_dir.name if self.root_dir else tr("view.before_title")
        root_before = QTreeWidgetItem(self.tree_before)
        root_before.setText(0, f"{root_name} ({tr('summary.files_count', count=total)})")
        root_before.setFont(0, QFont("Inter", 10, QFont.Weight.Bold))
        root_before.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "folder_name": root_name, "abs_path": str(self.root_dir), "is_source": True, "count": total})

        source_groups: Dict[str, List[Dict[str, Any]]] = {}
        for it in self.items:
            rel = it.get("rel_path", "").replace("\\", "/")
            parts = rel.split("/")
            folder_name = parts[0] if len(parts) > 1 else "."
            if folder_name not in source_groups:
                source_groups[folder_name] = []
            source_groups[folder_name].append(it)

        for folder_name, f_list in sorted(source_groups.items()):
            folder_node = root_before if folder_name == "." else QTreeWidgetItem(root_before)
            if folder_node != root_before:
                is_bundle = folder_name in bundle_folder_names
                badge = f" [{bundle_folder_names[folder_name].get('category', '')}]" if is_bundle else ""
                folder_node.setText(0, f"{folder_name}{badge} ({len(f_list)})")
                folder_node.setFont(0, QFont("Inter", 10, QFont.Weight.Medium))
                folder_path = str(self.root_dir / folder_name)
                folder_node.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "folder",
                    "folder_name": folder_name,
                    "abs_path": folder_path,
                    "is_source": True,
                    "count": len(f_list),
                    "is_bundle": is_bundle
                })

            for it in f_list:
                f_item = QTreeWidgetItem(folder_node)
                f_name = Path(it.get("rel_path", "")).name
                is_intruder = it.get("is_intruder", False)
                is_confirmed = it.get("folder_status") == "confirmado"

                if is_intruder:
                    dest_cat = it.get("category", "Outros")
                    f_item.setText(0, f"{f_name}  ·  Intruso ➔ {dest_cat}")
                    f_item.setForeground(0, QColor("#e06c75"))
                elif is_confirmed:
                    f_item.setText(0, f"{f_name}  ·  Confirmado")
                    f_item.setForeground(0, QColor("#98c379"))
                else:
                    f_item.setText(0, f"{f_name}")

                f_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "file",
                    "abs_path": it.get("abs_path"),
                    "item": it
                })

            folder_node.setExpanded(True)

        root_before.setExpanded(True)

    def _populate_tree_after(self, total: int):
        self.tree_after.clear()
        if not self.items and not self.cohesive_bundles:
            return

        root_after = QTreeWidgetItem(self.tree_after)
        root_after.setFont(0, QFont("Inter", 10, QFont.Weight.Bold))
        root_after.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "folder_name": "Indexo_Files", "is_source": False})

        bundle_action_map = {b.get("folder_rel", ""): b.get("action", "move_parent") for b in self.cohesive_bundles}
        dest_categories: Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]] = {}

        if self.user_tags:
            for ut in self.user_tags:
                u_cat = ut.get("categoria") or tr("type.other")
                u_tag = ut.get("nome") or ut.get("subcategoria") or "Geral"
                if u_cat not in dest_categories:
                    dest_categories[u_cat] = {"bundles": {}, "tags": {}}
                if u_tag not in dest_categories[u_cat]["tags"]:
                    dest_categories[u_cat]["tags"][u_tag] = []

        threshold = float(self.settings_mgr.get("confidence_threshold", 0.65))

        for it in self.items:
            cat = it.get("category") or tr("type.other")
            tag = it.get("tag_name") or it.get("caminho_fisico") or tr("type.other")
            bundle_folder = it.get("bundle_folder")
            is_in_bundle = it.get("is_in_bundle", False) and bundle_folder in bundle_action_map
            bundle_action = bundle_action_map.get(bundle_folder, "move_parent") if is_in_bundle else "disassemble"
            conf = float(it.get("confidence", 0.0))
            status = it.get("status", "")

            if not (is_in_bundle and bundle_action == "move_parent"):
                if conf < threshold or status != "identificado":
                    continue

            if cat not in dest_categories:
                dest_categories[cat] = {"bundles": {}, "tags": {}}

            if is_in_bundle and bundle_action == "move_parent":
                if bundle_folder not in dest_categories[cat]["bundles"]:
                    dest_categories[cat]["bundles"][bundle_folder] = []
                dest_categories[cat]["bundles"][bundle_folder].append(it)
            elif is_in_bundle and bundle_action == "keep":
                continue
            else:
                if tag not in dest_categories[cat]["tags"]:
                    dest_categories[cat]["tags"][tag] = []
                dest_categories[cat]["tags"][tag].append(it)

        total_organized = sum(sum(len(fl) for fl in cd["bundles"].values()) + sum(len(fl) for fl in cd["tags"].values()) for cd in dest_categories.values())
        root_after.setText(0, f"Indexo_Files ({tr('summary.classified_count', count=total_organized)})")

        for cat_name, cat_data in sorted(dest_categories.items()):
            bundle_items_count = sum(len(fl) for fl in cat_data["bundles"].values())
            tag_items_count = sum(len(fl) for fl in cat_data["tags"].values())
            total_cat = bundle_items_count + tag_items_count

            if total_cat == 0 and not (self.user_tags and any(ut.get("categoria") == cat_name for ut in self.user_tags)):
                continue

            cat_node = QTreeWidgetItem(root_after)
            cat_node.setText(0, f"{cat_name} ({tr('summary.files_count', count=total_cat)})")
            cat_node.setFont(0, QFont("Inter", 9, QFont.Weight.Bold))
            cat_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "folder_name": cat_name, "is_source": False, "count": total_cat, "is_category": True})

            for b_folder, f_list in sorted(cat_data["bundles"].items()):
                b_node = QTreeWidgetItem(cat_node)
                b_node.setText(0, f"{b_folder} ({len(f_list)} arquivos — Pasta Coesa)")
                b_node.setFont(0, QFont("Inter", 9, QFont.Weight.Bold))
                b_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "folder_name": b_folder, "is_source": False, "count": len(f_list), "category": cat_name, "is_bundle": True})

                for it in f_list:
                    f_item = QTreeWidgetItem(b_node)
                    sug_name = it.get("suggested_filename") or Path(it.get("rel_path", "")).name
                    f_item.setText(0, f"{sug_name}")
                    f_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "abs_path": it.get("abs_path"), "item": it})
                b_node.setExpanded(True)

            for tag_name, f_list in sorted(cat_data["tags"].items()):
                tag_node = cat_node if (tag_name == cat_name and not cat_data["bundles"]) else QTreeWidgetItem(cat_node)
                if tag_node != cat_node:
                    tag_node.setText(0, f"{tag_name} ({tr('summary.files_count', count=len(f_list))})")
                    tag_node.setFont(0, QFont("Inter", 9, QFont.Weight.Medium))
                    tag_node.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "folder_name": tag_name, "is_source": False, "count": len(f_list), "category": cat_name})

                for it in f_list:
                    f_item = QTreeWidgetItem(tag_node)
                    conf_pct = it.get("confidence", 0.0) * 100
                    is_intruder = it.get("is_intruder", False)
                    is_confirmed = it.get("folder_status") == "confirmado"
                    sug_name = it.get("suggested_filename") or Path(it.get("rel_path", "")).name
                    if is_intruder:
                        origin_f = it.get("origin_folder") or "Origem"
                        badge = f"[Intruso de {origin_f}]"
                        f_item.setForeground(0, QColor("#61afef"))
                    elif is_confirmed:
                        badge = "[Confirmado]"
                        f_item.setForeground(0, QColor("#98c379"))
                    else:
                        badge = f"[{conf_pct:.0f}%]" if conf_pct > 0 else f"[{tr('status.pending')}]"
                    f_item.setText(0, f"{sug_name}  ·  {badge}")
                    f_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "file", "abs_path": it.get("abs_path"), "item": it})
            cat_node.setExpanded(True)
        root_after.setExpanded(True)

    def on_before_item_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") == "folder":
            self.selected_folder_info = data
            self.update_options_card()
            for it in self.items:
                rel = it.get("rel_path", "")
                parts = rel.split("/")
                f_name = parts[0] if len(parts) > 1 else "."
                if f_name == data.get("folder_name") or data.get("folder_name") == ".":
                    self.file_selected.emit(it.get("abs_path"))
                    break
        elif data.get("type") == "file":
            abs_path = data.get("abs_path")
            if abs_path:
                self.file_selected.emit(abs_path)

    def on_after_item_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") == "folder":
            self.selected_folder_info = data
            self.update_options_card()
            for it in self.items:
                if it.get("category") == data.get("folder_name") or it.get("tag_name") == data.get("folder_name"):
                    self.file_selected.emit(it.get("abs_path"))
                    break
        elif data.get("type") == "file":
            abs_path = data.get("abs_path")
            if abs_path:
                self.file_selected.emit(abs_path)

    def on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data.get("type") == "file":
            abs_path = data.get("abs_path")
            if abs_path:
                open_with_default_app(abs_path)
        elif data.get("type") == "folder":
            item.setExpanded(not item.isExpanded())

    def show_tree_context_menu(self, tree: QTreeWidget, pos):
        item = tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") == "file":
            item_info = data.get("item", {}) or {"abs_path": data.get("abs_path")}
            show_file_context_menu(
                parent=self,
                item_data=item_info,
                on_reclassified=lambda p, t, c: self.file_reclassified.emit(p, t, c),
                on_deleted=lambda p: self.file_marked_trash.emit(p),
                on_preview=lambda p: self.file_selected.emit(p),
                global_pos=tree.viewport().mapToGlobal(pos)
            )
            return

        menu = QMenu(self)
        if data.get("type") == "folder":
            is_source = data.get("is_source", False)
            folder_name = data.get("folder_name", "")
            folder_path = data.get("abs_path")

            if is_source:
                act_new_sub = menu.addAction("+ Nova Subpasta aqui...")
                act_new_sub.triggered.connect(lambda: self.prompt_create_folder_in_source(folder_path))

                act_rename_f = menu.addAction("Renomear Pasta (F2)...")
                act_rename_f.triggered.connect(lambda: self.prompt_rename_source_folder(folder_path))

                act_copy = menu.addAction("Copiar Caminho da Pasta")
                act_copy.triggered.connect(lambda: copy_path_to_clipboard(folder_path or ""))

                act_refresh = menu.addAction("Atualizar (F5)")
                act_refresh.triggered.connect(self.refresh_requested.emit)
            else:
                act_new_cat = menu.addAction("+ Nova Tag nesta Categoria...")
                act_new_cat.triggered.connect(self.prompt_create_user_category)

                act_rename = menu.addAction(f"{tr('action.rename_tag')} (F2)...")
                act_rename.triggered.connect(self.rename_selected_tag)

            act_explorer = menu.addAction(f"{tr('action.open_explorer')}")
            act_explorer.triggered.connect(self.open_selected_folder_in_explorer)

        menu.exec(tree.viewport().mapToGlobal(pos))

    def trigger_rename_current(self, tree: QTreeWidget):
        item = tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data.get("type") == "file":
            self.prompt_rename_file(data.get("abs_path"))
        elif data.get("type") == "folder":
            if data.get("is_source"):
                self.prompt_rename_source_folder(data.get("abs_path"))
            else:
                self.rename_selected_tag()

    def trigger_delete_current(self, tree: QTreeWidget):
        item = tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data.get("type") == "file":
            abs_path = data.get("abs_path")
            if abs_path:
                self.file_marked_trash.emit(abs_path)

    def prompt_create_folder_in_source(self, target_parent: Optional[str] = None):
        base_dir = Path(target_parent) if target_parent else self.root_dir
        if not base_dir or not base_dir.exists():
            QMessageBox.warning(self, "Indexo", tr("dialog.select_working_folder_first"))
            return

        name, ok = QInputDialog.getText(self, tr("dialog.new_folder_title"), tr("dialog.new_folder_prompt"))
        if ok and name.strip():
            new_path = base_dir / name.strip()
            try:
                new_path.mkdir(parents=True, exist_ok=True)
                QMessageBox.information(self, "Indexo", tr("dialog.folder_created_success", name=name.strip()))
                self.refresh_requested.emit()
            except Exception as e:
                QMessageBox.critical(self, tr("dialog.error_title"), tr("dialog.folder_create_fail", err=str(e)))

    def prompt_rename_file(self, abs_path: str):
        if not abs_path or not os.path.exists(abs_path):
            return
        p = Path(abs_path)
        new_name, ok = QInputDialog.getText(self, "Renomear Arquivo", "Novo nome do arquivo:", text=p.name)
        if ok and new_name.strip() and new_name.strip() != p.name:
            target = p.parent / new_name.strip()
            try:
                p.rename(target)
                QMessageBox.information(self, "Indexo", "Arquivo renomeado com sucesso!")
                self.refresh_requested.emit()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao renomear arquivo: {e}")

    def prompt_rename_source_folder(self, folder_path: Optional[str]):
        if not folder_path or not os.path.exists(folder_path):
            return
        p = Path(folder_path)
        if p == self.root_dir:
            QMessageBox.warning(self, "Indexo", "Não é possível renomear a pasta raiz ativa.")
            return
        new_name, ok = QInputDialog.getText(self, "Renomear Pasta", "Novo nome da pasta:", text=p.name)
        if ok and new_name.strip() and new_name.strip() != p.name:
            target = p.parent / new_name.strip()
            try:
                p.rename(target)
                QMessageBox.information(self, "Indexo", "Pasta renomeada com sucesso!")
                self.refresh_requested.emit()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao renomear pasta: {e}")

    def prompt_create_user_category(self):
        name, ok = QInputDialog.getText(self, "Nova Categoria/Tag", "Nome da categoria/tag:")
        if ok and name.strip():
            tag_id = f"user_{name.strip().lower().replace(' ', '_')}"
            new_tag = {
                "id": tag_id,
                "nome": name.strip(),
                "categoria": name.strip(),
                "subcategoria": name.strip(),
                "entidade": "",
                "caminho_fisico": name.strip().replace(" ", "_"),
                "origem": "user",
                "idioma": LanguageManager.get_instance().current_language,
                "sinonimos": [],
                "palavras_chave": [name.strip().lower()],
                "confianca_base": 1.0,
                "usar_para_automacao": True,
                "version": 1
            }
            self.settings_mgr.add_user_tag(new_tag)
            self.tag_rename_requested.emit(tag_id, name.strip())
            QMessageBox.information(self, "Indexo", f"Categoria/Tag '{name.strip()}' criada com sucesso!")

    def prompt_edit_file_tag(self, abs_path: str, filename: str, current_tag: str, current_cat: str):
        dlg = FileTagEditDialog(filename, current_tag, current_cat, file_path=abs_path, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.file_reclassified.emit(abs_path, dlg.selected_tag, dlg.selected_category)

    def prompt_move_file_category(self, abs_path: str, filename: str, current_cat: str):
        dlg = FileMoveCategoryDialog(filename, current_cat, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.file_reclassified.emit(abs_path, "", dlg.selected_category)

    def show_file_properties(self, abs_path: str, item_data: Dict[str, Any]):
        dlg = FilePropertiesDialog(abs_path, item_data, self)
        dlg.exec()

    def update_options_card(self):
        if not self.selected_folder_info:
            self.lbl_selected_folder.setText(tr("view.click_folder_hint"))
            self.btn_open_explorer.setVisible(False)
            self.btn_rename_tag.setVisible(False)
            return

        info = self.selected_folder_info
        folder_name = info.get("folder_name", "")
        count = info.get("count", 0)
        is_source = info.get("is_source", False)

        if is_source:
            self.lbl_selected_folder.setText(
                f"📁 Pasta de Origem: <b>{folder_name}</b> ({count} arquivos)"
            )
            self.btn_open_explorer.setVisible(True)
            self.btn_rename_tag.setVisible(False)
        else:
            self.lbl_selected_folder.setText(
                f"🏷️ Categoria de Destino: <b>{folder_name}</b> ({count} arquivos)"
            )
            self.btn_open_explorer.setVisible(False)
            self.btn_rename_tag.setVisible(True)

    def open_selected_folder_in_explorer(self):
        if not self.selected_folder_info or not self.root_dir:
            return
        folder_name = self.selected_folder_info.get("folder_name", "")
        target = self.root_dir if folder_name == "." else (self.root_dir / folder_name)
        open_in_explorer(str(target))

    def rename_selected_tag(self):
        if not self.selected_folder_info:
            return
        old_name = self.selected_folder_info.get("folder_name", "")
        new_name, ok = QInputDialog.getText(self, tr("action.rename_tag"), tr("dialog.rename_tag_prompt", name=old_name), text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            tag_id = f"user_{new_name.strip().lower().replace(' ', '_')}"
            new_tag = {
                "id": tag_id,
                "nome": new_name.strip(),
                "categoria": new_name.strip(),
                "subcategoria": new_name.strip(),
                "entidade": "",
                "caminho_fisico": new_name.strip().replace(" ", "_"),
                "origem": "user",
                "idioma": LanguageManager.get_instance().current_language,
                "sinonimos": [old_name],
                "palavras_chave": [new_name.strip().lower(), old_name.lower()],
                "confianca_base": 1.0,
                "usar_para_automacao": True,
                "version": 1
            }
            self.settings_mgr.add_user_tag(new_tag)
            self.tag_rename_requested.emit(tag_id, new_name.strip())
            QMessageBox.information(self, "Indexo", tr("dialog.rename_tag_success", name=new_name.strip()))

    def export_csv(self):
        if not self.items:
            QMessageBox.information(self, "Indexo", tr("dialog.no_data_export"))
            return

        file_path, _ = QFileDialog.getSaveFileName(self, tr("action.export_csv"), "indexo_relatorio.csv", "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([tr("table.original_name"), tr("table.status"), tr("table.suggested_name"), tr("nav.summary"), "Confianca", "Status", "Pasta Coesa"])
                for it in self.items:
                    writer.writerow([
                        it.get("rel_path"),
                        it.get("caminho_fisico"),
                        it.get("suggested_filename"),
                        it.get("category"),
                        f"{it.get('confidence', 0.0) * 100:.1f}%",
                        it.get("status"),
                        it.get("bundle_folder") or "-"
                    ])
            QMessageBox.information(self, "Indexo", tr("dialog.export_csv_success", path=file_path))
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao exportar CSV: {e}")

    def retranslate_ui(self):
        self.btn_export_csv.setText(f"{tr('action.export_csv')}")
        self.lbl_before.setText(tr("view.before_title"))
        self.lbl_after.setText(tr("view.after_title"))
        self.lbl_cohesive_title.setText(tr("cohesive.title"))
        self.lbl_cohesive_desc.setText(tr("cohesive.desc"))
        self.btn_select_all_cohesive.setText(tr("cohesive.select_all_parent"))
        self.btn_open_explorer.setText(f"{tr('action.open_explorer')}")
        self.btn_rename_tag.setText(f"{tr('action.rename_tag')}")
        self.btn_restore.setText(f"{tr('action.restore_last_session')}")
        self.btn_organize.setText(f"{tr('action.organize')} (Ctrl+Enter)")
        self.table_cohesive.setHorizontalHeaderLabels([
            tr("cohesive.col_folder"),
            tr("cohesive.col_type"),
            tr("cohesive.col_main"),
            tr("cohesive.col_files"),
            tr("cohesive.col_action")
        ])
        self.update_options_card()
        if self.root_dir and self.items:
            user_tags = self.settings_mgr.get_user_tags()
            self.populate_results(self.items, self.root_dir, self.allowed_folders, user_tags, self.cohesive_bundles)
