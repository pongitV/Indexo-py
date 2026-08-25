from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QDialog, QComboBox, QCheckBox, QDoubleSpinBox,
    QMessageBox, QFrame, QScrollArea, QAbstractItemView
)
from app.config.settings_manager import SettingsManager, get_system_rules_path
from app.classification.rule_loader import RuleLoader
from app.i18n.language_manager import tr, LanguageManager
from app.widgets.smooth_scroll import SmoothTableWidget
from loguru import logger
import json

class TagEditDialog(QDialog):
    tag_saved = Signal(dict)

    def __init__(self, tag_data: Optional[Dict[str, Any]] = None, is_system: bool = False, parent=None):
        super().__init__(parent)
        self.tag_data = tag_data or {}
        self.is_system = is_system
        self.init_ui()

    def init_ui(self):
        title = tr("tags.edit_tag") if self.tag_data else tr("tags.create_manual_tag")
        self.setWindowTitle(title)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 1. Name
        layout.addWidget(QLabel(f"<b>{tr('tags.name')}:</b>"))
        self.txt_name = QLineEdit(self.tag_data.get("nome") or self.tag_data.get("subcategoria") or "")
        layout.addWidget(self.txt_name)

        # 2. Category (Dynamic & Editable)
        layout.addWidget(QLabel(f"<b>{tr('tags.category')}:</b>"))
        self.combo_cat = QComboBox()
        self.combo_cat.setEditable(True)
        learned_categories = SettingsManager().get_all_categories()
        default_categories = ["Documentos", "Finanças", "Trabalho", "Projetos", "Imagens", "Jogos e Softwares", "Outros"]
        combined_categories = sorted(list(set(learned_categories + default_categories)))
        self.combo_cat.addItems(combined_categories)
        curr_cat = self.tag_data.get("categoria") or (combined_categories[0] if combined_categories else "Geral")
        self.combo_cat.setCurrentText(curr_cat)
        layout.addWidget(self.combo_cat)

        # 3. Keywords
        layout.addWidget(QLabel(f"<b>{tr('tags.keywords')}:</b>"))
        kw_list = self.tag_data.get("palavras_chave", [])
        self.txt_keywords = QLineEdit(", ".join(kw_list))
        self.txt_keywords.setPlaceholderText(tr("tags.keywords_placeholder"))
        layout.addWidget(self.txt_keywords)

        # 4. Entity (Optional)
        layout.addWidget(QLabel(f"<b>{tr('tags.entity')}:</b>"))
        self.txt_entity = QLineEdit(self.tag_data.get("entidade") or "")
        layout.addWidget(self.txt_entity)

        # 5. Physical Path / Destination Subfolder
        layout.addWidget(QLabel(f"<b>{tr('tags.caminho_fisico')}:</b>"))
        self.txt_path = QLineEdit(self.tag_data.get("caminho_fisico") or "")
        layout.addWidget(self.txt_path)

        # 6. Auto-classify Checkbox & Confidence
        conf_layout = QHBoxLayout()
        self.chk_auto = QCheckBox(tr("tags.auto_classify"))
        self.chk_auto.setChecked(bool(self.tag_data.get("usar_para_automacao", True)))
        conf_layout.addWidget(self.chk_auto)

        conf_layout.addStretch()
        conf_layout.addWidget(QLabel(f"{tr('tags.confidence')}:"))
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.1, 1.0)
        self.spin_conf.setSingleStep(0.05)
        self.spin_conf.setValue(float(self.tag_data.get("confianca_base", 1.0)))
        conf_layout.addWidget(self.spin_conf)

        layout.addLayout(conf_layout)

        # 7. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton(tr("action.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton(tr('tags.save'))
        btn_save.setStyleSheet("background: #205EA6; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.save_and_accept)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def save_and_accept(self):
        name = self.txt_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Indexo", tr("tags.name_required"))
            return

        cat = self.combo_cat.currentText().strip() or "Outros"
        keywords = [k.strip().lower() for k in self.txt_keywords.text().split(",") if k.strip()]
        entity = self.txt_entity.text().strip()
        caminho = self.txt_path.text().strip() or name.replace(" ", "_")

        tag_id = self.tag_data.get("id") or f"user_{name.lower().replace(' ', '_')}"

        new_tag = {
            "id": tag_id,
            "nome": name,
            "categoria": cat,
            "subcategoria": name,
            "entidade": entity,
            "caminho_fisico": caminho,
            "origem": "system" if self.is_system else "user",
            "idioma": LanguageManager.get_instance().current_language,
            "sinonimos": self.tag_data.get("sinonimos", []),
            "palavras_chave": keywords if keywords else [name.lower()],
            "regex": self.tag_data.get("regex", []),
            "extensoes": self.tag_data.get("extensoes", []),
            "confianca_base": self.spin_conf.value(),
            "usar_para_automacao": self.chk_auto.isChecked(),
            "version": 1
        }

        self.result_tag = new_tag
        self.tag_saved.emit(new_tag)
        self.accept()


class TagManagerView(QWidget):
    back_requested = Signal()
    tags_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_mgr = SettingsManager()
        self.rule_loader = RuleLoader()
        self.init_ui()

    def init_ui(self):
        self.setObjectName("settings_panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # 1. Header
        header_layout = QHBoxLayout()
        self.btn_back = QPushButton(tr("action.back"))
        self.btn_back.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.btn_back.setStyleSheet("padding: 6px 16px; border-radius: 4px;")
        self.btn_back.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back)

        self.lbl_title = QLabel(f"🏷️ {tr('tags.manager_title')}")
        self.lbl_title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        self.btn_create_tag = QPushButton(f"🏷️ {tr('tags.create_manual_tag')}")
        self.btn_create_tag.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.btn_create_tag.setStyleSheet("background: #205EA6; color: white; padding: 6px 16px; border-radius: 4px;")
        self.btn_create_tag.clicked.connect(self.create_manual_tag)
        header_layout.addWidget(self.btn_create_tag)

        layout.addLayout(header_layout)

        # 2. Filter search bar
        filter_bar = QHBoxLayout()
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText(tr("search.placeholder"))
        self.txt_filter.textChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.txt_filter)
        layout.addLayout(filter_bar)

        # 3. Tabs: System Tags vs User Tags
        self.tab_widget = QTabWidget()

        # Tab 1: System Tags
        self.table_system = SmoothTableWidget(0, 5)
        self.table_system.setHorizontalHeaderLabels([
            tr("tags.name"), tr("tags.category"), tr("tags.keywords"), tr("tags.confidence"), tr("tags.actions", default="Ações")
        ])
        self.table_system.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_system.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_system.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_system.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_system.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table_system.setColumnWidth(4, 180)
        self.table_system.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_system.verticalHeader().setDefaultSectionSize(46)
        self.table_system.verticalHeader().setVisible(False)
        self.tab_widget.addTab(self.table_system, tr("tags.tab_system"))

        # Tab 2: User Tags
        self.table_user = SmoothTableWidget(0, 5)
        self.table_user.setHorizontalHeaderLabels([
            tr("tags.name"), tr("tags.category"), tr("tags.keywords"), tr("tags.caminho_fisico"), tr("tags.actions", default="Ações")
        ])
        self.table_user.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_user.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_user.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_user.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_user.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table_user.setColumnWidth(4, 180)
        self.table_user.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_user.verticalHeader().setDefaultSectionSize(46)
        self.table_user.verticalHeader().setVisible(False)
        self.tab_widget.addTab(self.table_user, tr("tags.tab_user"))


        layout.addWidget(self.tab_widget, 1)

        self.load_tags()

    def load_tags(self):
        self.rule_loader.reload()
        all_rules = self.rule_loader.active_rules
        query = self.txt_filter.text().lower().strip()

        sys_rules = [r for r in all_rules if r.get("origem") == "system"]
        user_rules = self.settings_mgr.get_user_tags()

        # Populate System Table
        self.table_system.setRowCount(0)
        row = 0
        for r in sys_rules:
            name = r.get("nome") or r.get("subcategoria") or ""
            cat = r.get("categoria") or ""
            kws = ", ".join(r.get("palavras_chave", []))
            conf = f"{r.get('confianca_base', 1.0) * 100:.0f}%"

            if query and query not in name.lower() and query not in cat.lower() and query not in kws.lower():
                continue

            self.table_system.insertRow(row)
            self.table_system.setItem(row, 0, QTableWidgetItem(name))
            self.table_system.setItem(row, 1, QTableWidgetItem(cat))
            self.table_system.setItem(row, 2, QTableWidgetItem(kws))
            self.table_system.setItem(row, 3, QTableWidgetItem(conf))

            # Actions widget
            actions_widget = QWidget()
            a_layout = QHBoxLayout(actions_widget)
            a_layout.setContentsMargins(6, 4, 6, 4)
            a_layout.setSpacing(6)
            a_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            btn_edit = QPushButton(tr("tags.edit_tag"))
            btn_edit.setStyleSheet("padding: 4px 10px; font-size: 12px; font-weight: bold; border-radius: 4px;")
            btn_edit.setFixedHeight(28)
            btn_edit.clicked.connect(lambda _, rule=r: self.edit_tag_dialog(rule, is_system=True))
            a_layout.addWidget(btn_edit)
            a_layout.addStretch()

            self.table_system.setCellWidget(row, 4, actions_widget)
            self.table_system.setRowHeight(row, 46)
            row += 1

        # Populate User Table
        self.table_user.setRowCount(0)
        row = 0
        for r in user_rules:
            name = r.get("nome") or r.get("subcategoria") or ""
            cat = r.get("categoria") or ""
            kws = ", ".join(r.get("palavras_chave", []))
            path = r.get("caminho_fisico") or ""

            if query and query not in name.lower() and query not in cat.lower() and query not in kws.lower():
                continue

            self.table_user.insertRow(row)
            self.table_user.setItem(row, 0, QTableWidgetItem(name))
            self.table_user.setItem(row, 1, QTableWidgetItem(cat))
            self.table_user.setItem(row, 2, QTableWidgetItem(kws))
            self.table_user.setItem(row, 3, QTableWidgetItem(path))

            actions_widget = QWidget()
            a_layout = QHBoxLayout(actions_widget)
            a_layout.setContentsMargins(6, 4, 6, 4)
            a_layout.setSpacing(6)
            a_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            btn_edit = QPushButton(tr("tags.edit_tag"))
            btn_edit.setStyleSheet("padding: 4px 10px; font-size: 12px; font-weight: bold; border-radius: 4px;")
            btn_edit.setFixedHeight(28)
            btn_edit.clicked.connect(lambda _, rule=r: self.edit_tag_dialog(rule, is_system=False))
            a_layout.addWidget(btn_edit)

            btn_del = QPushButton(tr("tags.delete_tag"))
            btn_del.setStyleSheet("background: #AF3029; color: white; padding: 4px 10px; font-size: 12px; font-weight: bold; border-radius: 4px;")
            btn_del.setFixedHeight(28)
            btn_del.clicked.connect(lambda _, rule=r: self.delete_user_tag(rule))
            a_layout.addWidget(btn_del)
            a_layout.addStretch()

            self.table_user.setCellWidget(row, 4, actions_widget)
            self.table_user.setRowHeight(row, 46)
            row += 1

        # Set Tab text with live counts
        self.tab_widget.setTabText(0, f"{tr('tags.tab_system')} ({len(sys_rules)})")
        self.tab_widget.setTabText(1, f"{tr('tags.tab_user')} ({len(user_rules)})")

    def apply_filter(self):
        self.load_tags()

    def create_manual_tag(self):
        dlg = TagEditDialog(None, is_system=False, parent=self)
        dlg.tag_saved.connect(self.on_tag_saved)
        dlg.exec()

    def edit_tag_dialog(self, tag_data: Dict[str, Any], is_system: bool):
        dlg = TagEditDialog(tag_data, is_system=is_system, parent=self)
        dlg.tag_saved.connect(self.on_tag_saved)
        dlg.exec()

    def on_tag_saved(self, new_tag: Dict[str, Any]):
        self.settings_mgr.add_user_tag(new_tag)
        self.load_tags()
        self.tab_widget.setCurrentIndex(1)  # Immediately show the user tags tab
        self.tags_changed.emit()
        name = new_tag.get("nome", "")
        QMessageBox.information(self, "Indexo", tr("tags.saved_success", name=name))

    def delete_user_tag(self, tag_data: Dict[str, Any]):
        name = tag_data.get("nome", "")
        tag_id = tag_data.get("id")
        msg = tr("tags.delete_confirm", name=name)
        reply = QMessageBox.question(self, tr("tags.delete_tag"), msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.settings_mgr.remove_user_tag(tag_id)
            self.load_tags()
            self.tab_widget.setCurrentIndex(1)
            self.tags_changed.emit()
            QMessageBox.information(self, "Indexo", tr("tags.deleted_success", name=name))

    def retranslate_ui(self):
        self.btn_back.setText(tr("action.back"))
        self.lbl_title.setText(f"🏷️ {tr('tags.manager_title')}")
        self.btn_create_tag.setText(f"🏷️ {tr('tags.create_manual_tag')}")
        if hasattr(self, 'txt_filter'):
            self.txt_filter.setPlaceholderText(tr("search.placeholder"))
        self.table_system.setHorizontalHeaderLabels([
            tr("tags.name"), tr("tags.category"), tr("tags.keywords"), tr("tags.confidence"), tr("tags.actions", default="Ações")
        ])
        self.table_user.setHorizontalHeaderLabels([
            tr("tags.name"), tr("tags.category"), tr("tags.keywords"), tr("tags.caminho_fisico"), tr("tags.actions", default="Ações")
        ])
        self.load_tags()
