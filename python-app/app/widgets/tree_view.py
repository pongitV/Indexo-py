import os
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon, QColor, QBrush, QAction, QKeyEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QHBoxLayout, QPushButton, QInputDialog, QMessageBox,
    QMenu, QDialog
)
from app.i18n.language_manager import tr, LanguageManager
from app.config.settings_manager import SettingsManager
from app.widgets.smooth_scroll import SmoothTreeWidget
from app.widgets.file_context_menu import (
    FileTagEditDialog, FileMoveCategoryDialog, FilePropertiesDialog,
    open_with_default_app, open_in_explorer, copy_path_to_clipboard,
    show_file_context_menu
)

class VirtualTreeView(QWidget):
    file_selected = Signal(str)  # abs_path
    tag_rename_requested = Signal(str, str) # tag_id, old_name
    file_reclassified = Signal(str, str, str) # abs_path, new_tag, new_category
    file_marked_trash = Signal(str) # abs_path
    tag_manager_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_mgr = SettingsManager()
        self.categories_map: Dict[str, QTreeWidgetItem] = {}
        self.tags_map: Dict[str, QTreeWidgetItem] = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.lbl_title = QLabel(tr('nav.tags'))
        self.lbl_title.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        header.addWidget(self.lbl_title)

        header.addStretch()

        self.btn_refresh = QPushButton(tr('action.refresh', default="Atualizar"))
        self.btn_refresh.setStyleSheet("padding: 4px 10px; font-size: 13px;")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self.btn_refresh)

        self.btn_new_tag = QPushButton(tr('action.create_tag'))
        self.btn_new_tag.setStyleSheet("background: #205EA6; color: white; font-weight: bold; padding: 4px 12px; font-size: 13px;")
        self.btn_new_tag.clicked.connect(self.prompt_create_user_tag)
        header.addWidget(self.btn_new_tag)

        layout.addLayout(header)

        self.tree = SmoothTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setFont(QFont("Inter", 11))
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        layout.addWidget(self.tree)

    def retranslate_ui(self):
        self.lbl_title.setText(tr('nav.tags'))
        self.btn_refresh.setText(tr('action.refresh', default="Atualizar"))
        self.btn_new_tag.setText(tr('action.create_tag'))

    def clear(self):
        self.tree.clear()
        self.categories_map.clear()
        self.tags_map.clear()

    def populate_results(self, results: List[Dict[str, Any]], user_tags: List[Dict[str, Any]]):
        self.clear()
        app_lang = LanguageManager.get_instance().current_language

        # Group by category and tag
        grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

        # 1. Ensure user tags are always present in the tree
        if user_tags:
            for ut in user_tags:
                u_cat = ut.get("categoria") or tr("type.other")
                u_tag = ut.get("nome") or ut.get("subcategoria") or "Geral"
                if u_cat not in grouped:
                    grouped[u_cat] = {}
                if u_tag not in grouped[u_cat]:
                    grouped[u_cat][u_tag] = []

        # 2. Add scanned file results
        for item in results:
            cat = item.get("category") or tr("type.other")
            tag = item.get("tag_name") or "Geral"
            if cat not in grouped:
                grouped[cat] = {}
            if tag not in grouped[cat]:
                grouped[cat][tag] = []
            grouped[cat][tag].append(item)

        for cat_name, tags in sorted(grouped.items()):
            cat_item = QTreeWidgetItem(self.tree)
            total_cat_files = sum(len(f_list) for f_list in tags.values())
            cat_item.setText(0, f"📁 {cat_name} ({total_cat_files})")
            cat_item.setFont(0, QFont("Inter", 9, QFont.Weight.Bold))
            cat_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "category", "category": cat_name})
            self.categories_map[cat_name] = cat_item

            for tag_name, file_list in sorted(tags.items()):
                tag_item = QTreeWidgetItem(cat_item)
                
                # Check user tag language warning
                is_user = any(u.get("nome") == tag_name for u in user_tags)
                tag_obj = next((u for u in user_tags if u.get("nome") == tag_name), None)
                tag_lang = tag_obj.get("idioma", "") if tag_obj else ""
                
                lang_warning = ""
                if is_user and tag_lang and tag_lang != app_lang:
                    lang_warning = " [Idioma diferente]"

                tag_item.setText(0, f"🏷️ {tag_name}{lang_warning} ({len(file_list)})")
                tag_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "tag",
                    "tag_name": tag_name,
                    "category": cat_name,
                    "tag_id": tag_obj.get("id") if tag_obj else None
                })

                for f in file_list:
                    f_item = QTreeWidgetItem(tag_item)
                    f_item.setText(0, f"📄 {f['suggested_filename']}")
                    f_item.setData(0, Qt.ItemDataRole.UserRole, {
                        "type": "file",
                        "abs_path": f["abs_path"],
                        "tag_name": tag_name,
                        "category": cat_name,
                        "item": f
                    })

            cat_item.setExpanded(True)

    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") == "file":
            self.file_selected.emit(data["abs_path"])
        elif data.get("type") == "tag" and "[Idioma diferente]" in item.text(0):
            tag_name = data.get("tag_name")
            tag_id = data.get("tag_id")
            self.show_tag_language_popup(tag_id, tag_name)

    def on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data.get("type") == "file":
            abs_path = data.get("abs_path")
            if abs_path:
                open_with_default_app(abs_path)
        elif data.get("type") in ["tag", "category"]:
            item.setExpanded(not item.isExpanded())

    def show_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") == "file":
            item_info = data.get("item", {}) or {"abs_path": data.get("abs_path"), "tag_name": data.get("tag_name"), "category": data.get("category")}
            show_file_context_menu(
                parent=self,
                item_data=item_info,
                on_reclassified=lambda p, t, c: self.file_reclassified.emit(p, t, c),
                on_deleted=lambda p: self.file_marked_trash.emit(p),
                on_preview=lambda p: self.file_selected.emit(p),
                global_pos=self.tree.viewport().mapToGlobal(pos)
            )
            return

        menu = QMenu(self)
        if data.get("type") in ["tag", "category"]:
            tag_name = data.get("tag_name") or data.get("category", "")
            tag_id = data.get("tag_id")

            act_new_tag = menu.addAction("+ Nova Tag Manual aqui...")
            act_new_tag.triggered.connect(self.prompt_create_user_tag)

            if tag_id:
                act_rename = menu.addAction(f"{tr('action.rename_tag')} (F2)...")
                act_rename.triggered.connect(lambda: self.show_tag_language_popup(tag_id, tag_name))

            act_refresh = menu.addAction("Atualizar (F5)")
            act_refresh.triggered.connect(self.refresh_requested.emit)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

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

    def show_tag_language_popup(self, tag_id: Optional[str], old_name: str):
        if not tag_id:
            return
        
        msg = tr("dialog.tag_language_message", old_lang="anterior", new_lang=LanguageManager.get_instance().current_language)
        new_name, ok = QInputDialog.getText(self, tr("dialog.tag_language_title"), f"{msg}\n\n{tr('dialog.tag_name_prompt')}", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            tags = self.settings_mgr.get_user_tags()
            for t in tags:
                if t.get("id") == tag_id:
                    syns = t.get("sinonimos", [])
                    if old_name not in syns:
                        syns.append(old_name)
                    t["nome"] = new_name.strip()
                    t["sinonimos"] = syns
                    t["idioma"] = LanguageManager.get_instance().current_language
            self.settings_mgr.save_data()
            self.tag_rename_requested.emit(tag_id, new_name.strip())

    def prompt_create_user_tag(self):
        name, ok = QInputDialog.getText(self, tr("action.create_tag"), tr("tags.prompt_create_name"))
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
            QMessageBox.information(self, "Indexo", tr("dialog.tag_created_success", name=name.strip()))
