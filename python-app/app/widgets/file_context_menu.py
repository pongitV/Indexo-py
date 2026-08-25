import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QAction, QClipboard, QGuiApplication, QCursor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QMessageBox, QMenu, QWidget,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy
)
from app.i18n.language_manager import tr, LanguageManager
from app.config.settings_manager import SettingsManager
from app.classification.rule_loader import RuleLoader
from app.widgets.smooth_scroll import SmoothTableWidget
from app.utils.formatters import format_file_size, format_timestamp, format_percentage
from loguru import logger

def open_with_default_app(file_path: str) -> bool:
    try:
        if file_path and os.path.exists(file_path):
            os.startfile(file_path)
            return True
    except Exception as e:
        logger.error("Failed to open file {}: {}", file_path, e)
    return False

def open_in_explorer(path: str) -> bool:
    try:
        if not path or not os.path.exists(path):
            return False
        if os.path.isdir(path):
            os.startfile(path)
        else:
            subprocess.run(["explorer", f"/select,{path}"])
        return True
    except Exception as e:
        logger.error("Failed to open explorer {}: {}", path, e)
    return False

def copy_path_to_clipboard(path: str):
    clipboard = QGuiApplication.clipboard()
    if clipboard and path:
        clipboard.setText(path)

class FileTagEditDialog(QDialog):
    def __init__(self, filename: str, current_tag: str, current_category: str, file_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.file_path = file_path
        self.current_tag = current_tag
        self.current_category = current_category
        self.settings_mgr = SettingsManager()
        self.rule_loader = RuleLoader()
        self.selected_tag: str = current_tag
        self.selected_category: str = current_category
        self.learned_keywords: List[str] = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"🏷️ {tr('tags.edit_tag')} — {self.filename}")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl_file = QLabel(tr("dialog.file_label", file=self.filename))
        lbl_file.setFont(QFont("Inter", 10))
        lbl_file.setWordWrap(True)
        layout.addWidget(lbl_file)

        # 1. Choose or type tag
        layout.addWidget(QLabel(f"<b>{tr('menu.select_tag')}</b>"))
        self.combo_tag = QComboBox()
        self.combo_tag.setEditable(True)
        
        # Load all tags
        self.rule_loader.reload()
        all_rules = self.rule_loader.active_rules
        user_tags = self.settings_mgr.get_user_tags()

        tag_items = []
        for r in user_tags:
            t_name = r.get("nome") or r.get("subcategoria") or ""
            cat = r.get("categoria") or "Outros"
            tag_items.append((f"🏷️ {t_name} ({cat})", t_name, cat))

        for r in all_rules:
            if r.get("origem") == "system":
                t_name = r.get("nome") or r.get("subcategoria") or ""
                cat = r.get("categoria") or "Outros"
                tag_items.append((f"🏷️ {t_name} ({cat})", t_name, cat))

        for label, t_name, cat in tag_items:
            self.combo_tag.addItem(label, {"tag": t_name, "category": cat})

        # Set current
        idx = -1
        for i in range(self.combo_tag.count()):
            data = self.combo_tag.itemData(i)
            if data and data.get("tag") == self.current_tag:
                idx = i
                break
        if idx >= 0:
            self.combo_tag.setCurrentIndex(idx)
        else:
            self.combo_tag.setEditText(self.current_tag)

        self.combo_tag.currentIndexChanged.connect(self.on_tag_combo_changed)
        layout.addWidget(self.combo_tag)

        # 2. Destination Category
        layout.addWidget(QLabel(f"<b>{tr('menu.dest_category')}</b>"))
        self.combo_cat = QComboBox()
        self.combo_cat.setEditable(True)
        categories = [
            tr("cat.faturas_boletos"),
            tr("cat.impostos_tributos"),
            tr("cat.documentos_contratos"),
            tr("cat.trabalho_renda"),
            tr("cat.bancario_financeiro"),
            tr("cat.documentos_pessoais"),
            tr("cat.carreira_educacao"),
            tr("cat.midia_fotos"),
            tr("cat.midia_audio"),
            tr("cat.midia_video"),
            tr("type.other")
        ]
        self.combo_cat.addItems(categories)
        self.combo_cat.setCurrentText(self.current_category or categories[0])
        layout.addWidget(self.combo_cat)

        # 3. Active Learning Checkbox
        self.chk_learn = QPushButton(tr("dialog.active_learning_chk"))
        self.chk_learn.setCheckable(True)
        self.chk_learn.setChecked(True)
        self.chk_learn.setStyleSheet("text-align: left; padding: 4px 8px;")
        layout.addWidget(self.chk_learn)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton(tr("action.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton(tr("dialog.save_change"))
        btn_save.setStyleSheet("background: #205EA6; color: white; font-weight: bold; padding: 6px 16px;")
        btn_save.clicked.connect(self.save_and_accept)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def on_tag_combo_changed(self, index: int):
        data = self.combo_tag.itemData(index)
        if data and data.get("category"):
            self.combo_cat.setCurrentText(data.get("category"))

    def save_and_accept(self):
        text = self.combo_tag.currentText().strip()
        data = self.combo_tag.currentData()
        if data and "tag" in data:
            self.selected_tag = data["tag"]
        else:
            clean_text = text.split(" (")[0].strip()
            self.selected_tag = clean_text

        self.selected_category = self.combo_cat.currentText().strip() or "Outros"

        # Learn keywords from file text
        learned_kws = [self.selected_tag.lower()]
        if self.chk_learn.isChecked() and self.file_path and os.path.exists(self.file_path):
            try:
                from app.classification.entity_regex import extract_keywords_from_text
                from app.extraction.pdf_extractor import extract_pdf_text_and_meta
                file_text = ""
                p = Path(self.file_path)
                if p.suffix.lower() == ".pdf":
                    file_text, _, _ = extract_pdf_text_and_meta(p)
                else:
                    file_text = p.read_text(encoding="utf-8", errors="ignore")
                extracted = extract_keywords_from_text(file_text, self.filename)
                for kw in extracted:
                    if kw not in learned_kws:
                        learned_kws.append(kw)
                self.learned_keywords = learned_kws
            except Exception as e:
                logger.debug("Could not extract auto-learning text from {}: {}", self.file_path, e)

        # Update or add tag in settings
        user_tags = self.settings_mgr.get_user_tags()
        existing = next((u for u in user_tags if u.get("nome") == self.selected_tag), None)
        if existing:
            current_kws = existing.get("palavras_chave", [])
            for kw in learned_kws:
                if kw not in current_kws:
                    current_kws.append(kw)
            existing["palavras_chave"] = current_kws
            self.settings_mgr.save_data()
        else:
            tag_id = f"user_{self.selected_tag.lower().replace(' ', '_')}"
            new_tag = {
                "id": tag_id,
                "nome": self.selected_tag,
                "categoria": self.selected_category,
                "subcategoria": self.selected_tag,
                "entidade": "",
                "caminho_fisico": self.selected_category.replace(" ", "_"),
                "origem": "user",
                "idioma": LanguageManager.get_instance().current_language,
                "sinonimos": [],
                "palavras_chave": learned_kws,
                "confianca_base": 1.0,
                "usar_para_automacao": True,
                "version": 1
            }
            self.settings_mgr.add_user_tag(new_tag)

        self.accept()


class FileMoveCategoryDialog(QDialog):
    def __init__(self, filename: str, current_category: str, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.selected_category: str = current_category
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"📁 {tr('dialog.move_file_title')} — {self.filename}")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl_file = QLabel(tr("dialog.file_label", file=self.filename))
        lbl_file.setFont(QFont("Inter", 10))
        lbl_file.setWordWrap(True)
        layout.addWidget(lbl_file)

        layout.addWidget(QLabel(f"<b>{tr('menu.dest_category')}</b>"))
        self.combo_cat = QComboBox()
        self.combo_cat.setEditable(True)
        categories = [
            tr("cat.faturas_boletos"),
            tr("cat.impostos_tributos"),
            tr("cat.documentos_contratos"),
            tr("cat.trabalho_renda"),
            tr("cat.bancario_financeiro"),
            tr("cat.documentos_pessoais"),
            tr("cat.carreira_educacao"),
            tr("cat.midia_fotos"),
            tr("cat.midia_audio"),
            tr("cat.midia_video"),
            tr("type.other")
        ]
        self.combo_cat.addItems(categories)
        self.combo_cat.setCurrentText(self.selected_category or categories[0])
        layout.addWidget(self.combo_cat)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton(tr("action.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_move = QPushButton(f"📁 {tr('action.move', default='Mover')}")
        btn_move.setStyleSheet("background: #205EA6; color: white; font-weight: bold; padding: 6px 16px;")
        btn_move.clicked.connect(self.save_and_accept)
        btn_layout.addWidget(btn_move)

        layout.addLayout(btn_layout)

    def save_and_accept(self):
        self.selected_category = self.combo_cat.currentText().strip() or "Outros"
        self.accept()


class FilePropertiesDialog(QDialog):
    def __init__(self, file_path: str, item_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.item_data = item_data or {}
        self.init_ui()

    def init_ui(self):
        p = Path(self.file_path)
        self.setWindowTitle(f"{tr('properties.title')} — {p.name}")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # File header card
        header = QFrame()
        header.setStyleSheet("background: rgba(255,255,255,0.05); border-radius: 6px; padding: 10px;")
        h_layout = QVBoxLayout(header)
        h_layout.setSpacing(4)
        
        lbl_name = QLabel(f"<b>{p.name}</b>")
        lbl_name.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        h_layout.addWidget(lbl_name)

        lbl_path = QLabel(f"<code>{str(p.parent)}</code>")
        lbl_path.setWordWrap(True)
        lbl_path.setStyleSheet("color: #888; font-size: 11px;")
        h_layout.addWidget(lbl_path)
        layout.addWidget(header)

        # Details Table
        table = SmoothTableWidget(0, 2)
        table.setHorizontalHeaderLabels([tr("properties.property"), tr("properties.value")])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        def add_row(prop: str, val: str):
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, QTableWidgetItem(prop))
            table.setItem(r, 1, QTableWidgetItem(val))

        # Size & Dates
        if p.exists():
            st = p.stat()
            size_str = f"{format_file_size(st.st_size)} ({st.st_size:,} bytes)"
            add_row(tr("properties.size"), size_str)
            add_row(tr("properties.created"), format_timestamp(st.st_ctime))
            add_row(tr("properties.modified"), format_timestamp(st.st_mtime))
            add_row(tr("properties.extension"), p.suffix.upper() or tr("properties.no_ext"))
        
        # Classification
        if self.item_data:
            cat = self.item_data.get("category", "-")
            tag = self.item_data.get("tag_name", "-")
            conf = self.item_data.get("confidence", 0.0)
            sug = self.item_data.get("suggested_filename", "-")
            add_row(tr("properties.category"), cat)
            add_row(tr("properties.tag"), tag)
            add_row(tr("properties.confidence"), format_percentage(conf))
            add_row(tr("properties.suggested_name"), sug)

        table.scrollToTop()
        table.setCurrentItem(None)
        layout.addWidget(table, 1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_copy = QPushButton(tr("properties.copy_path"))
        btn_copy.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_copy.clicked.connect(lambda: copy_path_to_clipboard(self.file_path))
        btn_layout.addWidget(btn_copy)

        btn_open = QPushButton(tr("properties.open_folder"))
        btn_open.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_open.clicked.connect(lambda: open_in_explorer(self.file_path))
        btn_layout.addWidget(btn_open)

        btn_layout.addStretch()

        btn_close = QPushButton(tr("properties.close"))
        btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)


def show_file_context_menu(
    parent: QWidget,
    item_data: Dict[str, Any],
    on_reclassified: Optional[Callable[[str, str, str], None]] = None,
    on_deleted: Optional[Callable[[str], None]] = None,
    on_preview: Optional[Callable[[str], None]] = None,
    global_pos: Optional[QPoint] = None
) -> Optional[QAction]:
    """
    Unified, complete, DRY context menu for any file in the application.
    Used across OrganizationSplitView, VirtualTreeView, PendingListView, and SearchPalette.
    """
    abs_path = item_data.get("abs_path", "")
    if not abs_path:
        return None

    filename = Path(abs_path).name
    current_tag = item_data.get("tag_name") or ""
    current_cat = item_data.get("category") or ""

    menu = QMenu(parent)
    menu.setFont(QFont("Inter", 10))

    # 1. Preview / Open
    act_preview = menu.addAction("👁️ " + tr("action.preview", default="Visualizar no Painel"))
    act_open = menu.addAction("📄 " + tr("action.open_file", default="Abrir Arquivo"))
    act_folder = menu.addAction("📂 " + tr("action.open_folder", default="Abrir Pasta no Explorer"))

    menu.addSeparator()

    # 2. Reclassify / Move
    act_edit_tag = menu.addAction("🏷️ " + tr("action.edit_tag", default="Alterar Tag Semântica..."))
    act_move_cat = menu.addAction("📁 " + tr("action.move_category", default="Mover de Categoria..."))

    menu.addSeparator()

    # 3. Copy & Properties
    act_copy_path = menu.addAction("📋 " + tr("action.copy_path", default="Copiar Caminho Absoluto"))
    act_props = menu.addAction("ℹ️ " + tr("action.properties", default="Propriedades do Arquivo"))

    menu.addSeparator()

    # 4. Trash / Delete
    act_trash = menu.addAction("🗑️ " + tr("action.move_trash", default="Mover para Lixeira Virtual"))

    if global_pos is None:
        global_pos = QCursor.pos()

    action = menu.exec(global_pos)
    if action == act_preview:
        if on_preview:
            on_preview(abs_path)
        else:
            open_with_default_app(abs_path)
    elif action == act_open:
        open_with_default_app(abs_path)
    elif action == act_folder:
        open_in_explorer(abs_path)
    elif action == act_edit_tag:
        dlg = FileTagEditDialog(filename, current_tag, current_cat, abs_path, parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if on_reclassified:
                on_reclassified(abs_path, dlg.selected_tag, dlg.selected_category)
    elif action == act_move_cat:
        dlg = FileMoveCategoryDialog(filename, current_cat, parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            if on_reclassified:
                on_reclassified(abs_path, current_tag, dlg.selected_category)
    elif action == act_copy_path:
        copy_path_to_clipboard(abs_path)
    elif action == act_props:
        dlg = FilePropertiesDialog(abs_path, item_data, parent)
        dlg.exec()
    elif action == act_trash:
        if on_deleted:
            on_deleted(abs_path)

    return action
