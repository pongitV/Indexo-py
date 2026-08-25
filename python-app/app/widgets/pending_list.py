import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QMessageBox, QFrame, QSplitter, QComboBox,
    QCheckBox, QMenu, QDialog, QInputDialog, QProgressBar
)
from app.i18n.language_manager import tr, LanguageManager
from app.classification.confidence import format_scores_breakdown
from app.classification.rule_loader import RuleLoader
from app.config.settings_manager import SettingsManager
from app.widgets.smooth_scroll import SmoothTableWidget
from app.widgets.tag_manager_view import TagEditDialog
from app.widgets.file_context_menu import (
    FileTagEditDialog, FileMoveCategoryDialog, FilePropertiesDialog,
    open_with_default_app, open_in_explorer, copy_path_to_clipboard,
    show_file_context_menu
)
from loguru import logger

class PendingListView(QWidget):
    file_selected = Signal(str)            # abs_path (for live preview in main window)
    file_reclassified = Signal(str, str, str)  # abs_path, new_tag, new_category
    file_marked_trash = Signal(str)        # abs_path
    promotion_suggested = Signal(str, str) # tag_name, entity
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending_items: List[Dict[str, Any]] = []
        self.filtered_items: List[Dict[str, Any]] = []
        self.selected_item: Optional[Dict[str, Any]] = None
        self.settings_mgr = SettingsManager()
        self.rule_loader = RuleLoader()
        self.manual_tag_counts: Dict[str, int] = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # 1. Top Header & Batch Toolbar
        top_bar = QHBoxLayout()
        self.lbl_title = QLabel(tr('pending.title', count=0))
        self.lbl_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        top_bar.addWidget(self.lbl_title)

        top_bar.addStretch()

        self.btn_classify_ai = QPushButton(tr('pending.classify_ai_btn'))
        self.btn_classify_ai.setStyleSheet(
            "QPushButton { background: #6366f1; color: white; font-weight: bold; padding: 5px 14px; font-size: 12px; border-radius: 4px; }"
            "QPushButton:hover { background: #4f46e5; }"
        )
        self.btn_classify_ai.clicked.connect(self.classify_pending_with_ai)
        top_bar.addWidget(self.btn_classify_ai)

        self.btn_accept_all_high = QPushButton(tr('action.accept_high_confidence'))
        self.btn_accept_all_high.setStyleSheet("background: #205EA6; color: white; font-weight: bold; padding: 5px 12px; font-size: 12px;")
        self.btn_accept_all_high.clicked.connect(self.accept_all_high)
        top_bar.addWidget(self.btn_accept_all_high)

        self.btn_trash_selected = QPushButton(tr("action.move_trash"))
        self.btn_trash_selected.setStyleSheet("background: #AF3029; color: white; padding: 5px 12px; font-size: 12px;")
        self.btn_trash_selected.clicked.connect(self.trash_selected_batch)
        top_bar.addWidget(self.btn_trash_selected)

        layout.addLayout(top_bar)

        # AI Progress Indicator Bar (hidden by default)
        self.ai_progress_card = QFrame()
        self.ai_progress_card.setObjectName("card_options")
        self.ai_progress_card.setVisible(False)
        ai_card_layout = QHBoxLayout(self.ai_progress_card)
        ai_card_layout.setContentsMargins(10, 6, 10, 6)
        ai_card_layout.setSpacing(10)

        self.lbl_ai_status = QLabel(tr("pending.ai_classifying"))
        self.lbl_ai_status.setFont(QFont("Inter", 9, QFont.Weight.Medium))
        ai_card_layout.addWidget(self.lbl_ai_status, 1)

        self.ai_progress_bar = QProgressBar()
        self.ai_progress_bar.setFixedHeight(12)
        self.ai_progress_bar.setMaximumWidth(220)
        ai_card_layout.addWidget(self.ai_progress_bar)

        layout.addWidget(self.ai_progress_card)

        # 2. Filter / Search Bar
        filter_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setFont(QFont("Inter", 10))
        self.search_input.setPlaceholderText(tr("pending.filter_placeholder"))
        self.search_input.textChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.search_input, 2)

        self.filter_mode_combo = QComboBox()
        self.filter_mode_combo.setFont(QFont("Inter", 10))
        self.filter_mode_combo.addItems([
            tr("pending.filter_all"),
            tr("pending.filter_with_suggestion"),
            tr("pending.filter_no_suggestion")
        ])
        self.filter_mode_combo.currentIndexChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.filter_mode_combo, 1)

        layout.addLayout(filter_bar)

        # 3. Main Splitter: Top Table + Bottom Quick Decision Card
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top Table Widget
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = SmoothTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            tr("pending.col_file"), tr("pending.col_suggestion"), tr("pending.col_category"), tr("pending.col_actions")
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 300)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table.itemDoubleClicked.connect(self.on_table_double_clicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.verticalHeader().setVisible(False)

        table_layout.addWidget(self.table)
        splitter.addWidget(table_container)

        # Bottom Decision Card
        self.decision_card = QFrame()
        self.decision_card.setObjectName("card_options")
        self.decision_card.setStyleSheet("QFrame#card_options { border-radius: 8px; padding: 12px; }")
        card_layout = QVBoxLayout(self.decision_card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        # Decision Card Header
        self.lbl_selected_title = QLabel(tr("pending.select_hint"))
        self.lbl_selected_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        card_layout.addWidget(self.lbl_selected_title)

        self.lbl_selected_meta = QLabel("")
        self.lbl_selected_meta.setObjectName("lbl_subtext")
        self.lbl_selected_meta.setFont(QFont("Consolas", 10))
        card_layout.addWidget(self.lbl_selected_meta)

        # Action Row 1: Primary Classification (Aceitar, Selecionar Tag, Criar Tag, Selecionar Categoria, Criar Categoria)
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        # 1. Aceitar Sugestão
        self.btn_accept_single_sug = QPushButton(f"✅ {tr('pending.btn_accept_sug')}")
        self.btn_accept_single_sug.setFixedHeight(36)
        self.btn_accept_single_sug.setStyleSheet(
            "QPushButton { background-color: #2E7D32; color: #FFFFFF; font-weight: bold; padding: 6px 16px; font-size: 13px; border-radius: 5px; border: none; } "
            "QPushButton:hover { background-color: #388E3C; } "
            "QPushButton:disabled { background-color: #242B24; color: #758375; }"
        )
        self.btn_accept_single_sug.clicked.connect(self.accept_current_suggestion)
        row1.addWidget(self.btn_accept_single_sug)

        # 2. Selecionar Tag
        self.btn_select_tag_single = QPushButton(f"🏷️ {tr('pending.btn_select_tag')}")
        self.btn_select_tag_single.setFixedHeight(36)
        self.btn_select_tag_single.setStyleSheet(
            "QPushButton { background-color: #205EA6; color: #FFFFFF; font-weight: bold; padding: 6px 14px; font-size: 13px; border-radius: 5px; border: none; } "
            "QPushButton:hover { background-color: #2870C4; } "
            "QPushButton:disabled { background-color: #1F2833; color: #728192; }"
        )
        self.btn_select_tag_single.clicked.connect(self.select_tag_for_selected)
        row1.addWidget(self.btn_select_tag_single)

        # 3. Criar Tag
        self.btn_create_tag_single = QPushButton(f"➕ {tr('pending.btn_create_tag')}")
        self.btn_create_tag_single.setFixedHeight(36)
        self.btn_create_tag_single.setStyleSheet(
            "QPushButton { background-color: #5E35B1; color: #FFFFFF; font-weight: bold; padding: 6px 14px; font-size: 13px; border-radius: 5px; border: none; } "
            "QPushButton:hover { background-color: #6D3FC0; } "
            "QPushButton:disabled { background-color: #292338; color: #837996; }"
        )
        self.btn_create_tag_single.clicked.connect(self.create_tag_for_selected)
        row1.addWidget(self.btn_create_tag_single)

        # 4. Selecionar Categoria
        self.btn_select_cat_single = QPushButton(f"📁 {tr('pending.btn_select_cat')}")
        self.btn_select_cat_single.setFixedHeight(36)
        self.btn_select_cat_single.setStyleSheet(
            "QPushButton { background-color: #282726; color: #CECDC3; border: 1px solid #343331; font-weight: bold; padding: 6px 14px; font-size: 13px; border-radius: 5px; } "
            "QPushButton:hover { background-color: #343331; } "
            "QPushButton:disabled { background-color: #1C1B1A; color: #6F6E69; }"
        )
        self.btn_select_cat_single.clicked.connect(self.select_category_for_selected)
        row1.addWidget(self.btn_select_cat_single)

        # 5. Criar Categoria
        self.btn_create_cat_single = QPushButton(f"📂 {tr('pending.btn_create_cat')}")
        self.btn_create_cat_single.setFixedHeight(36)
        self.btn_create_cat_single.setStyleSheet(
            "QPushButton { background-color: #282726; color: #CECDC3; border: 1px solid #343331; font-weight: bold; padding: 6px 14px; font-size: 13px; border-radius: 5px; } "
            "QPushButton:hover { background-color: #343331; } "
            "QPushButton:disabled { background-color: #1C1B1A; color: #6F6E69; }"
        )
        self.btn_create_cat_single.clicked.connect(self.create_category_for_selected)
        row1.addWidget(self.btn_create_cat_single)

        row1.addStretch()
        card_layout.addLayout(row1)

        # Action Row 2: Secondary Utilities (Abrir, Abrir Pasta, Lixeira)
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.btn_open_file = QPushButton(f"📄 {tr('action.open_file')}")
        self.btn_open_file.setFixedHeight(32)
        self.btn_open_file.setStyleSheet("QPushButton { padding: 5px 12px; font-size: 12px; border-radius: 4px; }")
        self.btn_open_file.clicked.connect(self.open_selected_file)
        row2.addWidget(self.btn_open_file)

        self.btn_open_dir = QPushButton(f"📂 {tr('action.open_folder')}")
        self.btn_open_dir.setFixedHeight(32)
        self.btn_open_dir.setStyleSheet("QPushButton { padding: 5px 12px; font-size: 12px; border-radius: 4px; }")
        self.btn_open_dir.clicked.connect(self.open_selected_folder)
        row2.addWidget(self.btn_open_dir)

        self.btn_trash_single = QPushButton(f"🗑️ {tr('action.move_trash')}")
        self.btn_trash_single.setFixedHeight(32)
        self.btn_trash_single.setStyleSheet(
            "QPushButton { background-color: #AF3029; color: #FFFFFF; font-weight: bold; padding: 5px 14px; font-size: 12px; border-radius: 4px; border: none; } "
            "QPushButton:hover { background-color: #C93B34; } "
            "QPushButton:disabled { background-color: #2D1D1C; color: #8A6E6D; }"
        )
        self.btn_trash_single.clicked.connect(self.trash_selected_single)
        row2.addWidget(self.btn_trash_single)

        row2.addStretch()
        card_layout.addLayout(row2)

        splitter.addWidget(self.decision_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.set_decision_card_enabled(False)

    def set_decision_card_enabled(self, enabled: bool):
        self.btn_accept_single_sug.setEnabled(enabled)
        self.btn_select_tag_single.setEnabled(enabled)
        self.btn_create_tag_single.setEnabled(enabled)
        self.btn_select_cat_single.setEnabled(enabled)
        self.btn_create_cat_single.setEnabled(enabled)
        self.btn_open_file.setEnabled(enabled)
        self.btn_open_dir.setEnabled(enabled)
        self.btn_trash_single.setEnabled(enabled)

    def populate_pending(self, items: List[Dict[str, Any]]):
        self.pending_items = [it for it in items if it.get("status") == "pendente"]
        self.lbl_title.setText(f"❓ {tr('pending.title', count=len(self.pending_items))}")
        self.apply_filter()

    def apply_filter(self):
        query = self.search_input.text().lower().strip()
        mode = self.filter_mode_combo.currentIndex()

        self.filtered_items = []
        for it in self.pending_items:
            rel = it.get("rel_path", "").lower()
            name = Path(rel).name.lower()
            cand = it.get("candidate")
            cand_name = (cand.get("nome") or "").lower() if cand else ""

            # Text filter
            if query and query not in rel and query not in name and query not in cand_name:
                continue

            # Mode filter: 1 = Has suggestion, 2 = No suggestion
            if mode == 1 and not cand:
                continue
            if mode == 2 and cand:
                continue

            self.filtered_items.append(it)

        self.render_table()

    def render_table(self):
        self.table.setRowCount(0)
        for row, it in enumerate(self.filtered_items):
            self.table.insertRow(row)

            # 1. File column
            rel = it.get("rel_path", "")
            f_name = Path(rel).name
            item_file = QTableWidgetItem(f"📄 {f_name}")
            item_file.setFont(QFont("Inter", 11, QFont.Weight.Medium))
            item_file.setToolTip(f"Caminho Relativo: {rel}\nCaminho Absoluto: {it.get('abs_path')}")
            item_file.setData(Qt.ItemDataRole.UserRole, it)
            self.table.setItem(row, 0, item_file)

            # 2. Suggestion column
            cand = it.get("candidate")
            scores = it.get("scores", {})
            breakdown = format_scores_breakdown(scores)

            if cand:
                sug_name = cand.get("nome", "-")
                conf_pct = it.get("confidence", 0.0) * 100
                conf_badge = f"[{conf_pct:.0f}%]" if conf_pct > 0 else ""
                item_sug = QTableWidgetItem(f"🏷️ {sug_name} {conf_badge}")
                item_sug.setFont(QFont("Inter", 11, QFont.Weight.Bold))
                item_sug.setForeground(QColor("#205EA6"))
                item_sug.setToolTip(f"Motivo / Detalhes:\n{breakdown}")
            else:
                item_sug = QTableWidgetItem("❓ Sem sugestão")
                item_sug.setFont(QFont("Inter", 10))
                item_sug.setForeground(QColor("#888888"))
            self.table.setItem(row, 1, item_sug)

            # 3. Category column
            cat = cand.get("categoria", "-") if cand else "-"
            item_cat = QTableWidgetItem(cat)
            item_cat.setFont(QFont("Inter", 10))
            self.table.setItem(row, 2, item_cat)

            # 4. Row Quick Action Buttons: [Aceitar] + [🏷️ Tag / Categoria ▾]
            self.table.setItem(row, 3, QTableWidgetItem(""))
            actions_widget = QWidget()
            a_layout = QHBoxLayout(actions_widget)
            a_layout.setContentsMargins(6, 4, 6, 4)
            a_layout.setSpacing(8)
            a_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            # Quick Action 1: Aceitar
            if cand:
                btn_acc = QPushButton("✅ Aceitar")
                btn_acc.setToolTip(f"Aceitar a sugestão '{cand.get('nome')}'")
                btn_acc.setStyleSheet("QPushButton { background-color: #2E7D32; color: #FFFFFF; font-weight: bold; padding: 5px 12px; font-size: 12px; border-radius: 4px; border: none; min-height: 28px; } QPushButton:hover { background-color: #388E3C; }")
                btn_acc.setFixedHeight(34)
                btn_acc.setMinimumWidth(100)
                btn_acc.clicked.connect(lambda _, item_data=it: self.accept_specific_suggestion(item_data))
                a_layout.addWidget(btn_acc)

            # Quick Action 2: Tag Menu (Selecionar Tag / Criar Tag / Selecionar Categoria / Criar Categoria)
            btn_tag_menu = QPushButton("🏷️ Tag / Categoria ▾")
            btn_tag_menu.setToolTip("Opções de Tag e Categoria")
            btn_tag_menu.setStyleSheet("QPushButton { background-color: #282726; color: #CECDC3; border: 1px solid #343331; padding: 5px 12px; font-size: 12px; font-weight: bold; border-radius: 4px; min-height: 28px; } QPushButton:hover { background-color: #343331; }")
            btn_tag_menu.setFixedHeight(34)
            btn_tag_menu.setMinimumWidth(150)
            
            tag_menu = QMenu(self)
            act_sel_tag = tag_menu.addAction("🏷️ Selecionar Tag...")
            act_sel_tag.triggered.connect(lambda _, item_data=it: self.prompt_select_tag(item_data))
            
            act_create_tag = tag_menu.addAction("➕ Criar Nova Tag...")
            act_create_tag.triggered.connect(lambda _, item_data=it: self.prompt_create_tag(item_data))
            
            tag_menu.addSeparator()
            
            act_sel_cat = tag_menu.addAction("📁 Selecionar Categoria...")
            act_sel_cat.triggered.connect(lambda _, item_data=it: self.prompt_select_category(item_data))
            
            act_create_cat = tag_menu.addAction("📂 Criar Nova Categoria...")
            act_create_cat.triggered.connect(lambda _, item_data=it: self.prompt_create_category(item_data))
            
            btn_tag_menu.clicked.connect(lambda _, b=btn_tag_menu, m=tag_menu: m.exec(b.mapToGlobal(QPoint(0, b.height()))))
            a_layout.addWidget(btn_tag_menu)
            a_layout.addStretch()

            self.table.setCellWidget(row, 3, actions_widget)
            self.table.setRowHeight(row, 54)

        if self.filtered_items:
            self.table.selectRow(0)
        else:
            self.selected_item = None
            self.lbl_selected_title.setText("Nenhum arquivo pendente encontrado com os filtros atuais.")
            self.lbl_selected_meta.setText("")
            self.set_decision_card_enabled(False)

    def on_table_selection_changed(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self.selected_item = None
            self.lbl_selected_title.setText("Selecione um arquivo acima para revisar e definir sua classificação.")
            self.lbl_selected_meta.setText("")
            self.set_decision_card_enabled(False)
            return

        row = selected_rows[0].row()
        if row < 0 or row >= len(self.filtered_items):
            return

        it = self.filtered_items[row]
        self.selected_item = it
        self.set_decision_card_enabled(True)

        abs_path = it.get("abs_path", "")
        self.file_selected.emit(abs_path)

        f_name = Path(abs_path).name if abs_path else it.get("rel_path", "")
        size_kb = it.get("size", 0) / 1024
        self.lbl_selected_title.setText(f"📄 Arquivo Selecionado: {f_name} ({size_kb:.1f} KB)")
        self.lbl_selected_meta.setText(f"Caminho: {abs_path}")

        cand = it.get("candidate")
        if cand:
            sug_name = cand.get("nome", "")
            conf_pct = it.get("confidence", 0.0) * 100
            self.btn_accept_single_sug.setText(f"✅ Aceitar '{sug_name}' [{conf_pct:.0f}%]")
            self.btn_accept_single_sug.setVisible(True)
        else:
            self.btn_accept_single_sug.setVisible(False)

    def on_table_double_clicked(self, item: QTableWidgetItem):
        it = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        if it and it.get("abs_path"):
            open_with_default_app(it["abs_path"])

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        it = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not it:
            return

        abs_path = it.get("abs_path", "")
        filename = Path(abs_path).name if abs_path else it.get("rel_path", "")
        cand = it.get("candidate")

        show_file_context_menu(
            parent=self,
            item_data=it,
            on_reclassified=lambda p, t, c: self.file_reclassified.emit(p, t, c),
            on_deleted=lambda p: self.file_marked_trash.emit(p),
            on_preview=lambda p: self.file_selected.emit(p),
            global_pos=self.table.viewport().mapToGlobal(pos)
        )

    # --- 1. Aceitar Sugestão ---
    def accept_current_suggestion(self):
        if self.selected_item:
            self.accept_specific_suggestion(self.selected_item)

    def accept_specific_suggestion(self, item_data: Dict[str, Any]):
        cand = item_data.get("candidate")
        if not cand:
            return
        tag_name = cand.get("nome", "")
        category = cand.get("categoria", "Outros")
        abs_path = item_data.get("abs_path", "")

        self.file_reclassified.emit(abs_path, tag_name, category)
        self.record_manual_classification(tag_name, item_data.get("entity") or "")

        self.pending_items = [it for it in self.pending_items if it.get("abs_path") != abs_path]
        self.lbl_title.setText(f"❓ {tr('pending.title', count=len(self.pending_items))}")
        self.apply_filter()

    # --- 2. Selecionar Tag ---
    def select_tag_for_selected(self):
        if self.selected_item:
            self.prompt_select_tag(self.selected_item)

    def prompt_select_tag(self, item_data: Dict[str, Any]):
        abs_path = item_data.get("abs_path", "")
        filename = Path(abs_path).name
        current_tag = item_data.get("tag_name", "")
        current_cat = item_data.get("category", "")

        dlg = FileTagEditDialog(filename, current_tag, current_cat, file_path=abs_path, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.file_reclassified.emit(abs_path, dlg.selected_tag, dlg.selected_category)
            self.record_manual_classification(dlg.selected_tag, item_data.get("entity") or "")
            self.pending_items = [it for it in self.pending_items if it.get("abs_path") != abs_path]
            self.lbl_title.setText(f"❓ {tr('pending.title', count=len(self.pending_items))}")
            self.apply_filter()

    # --- 3. Criar Tag ---
    def create_tag_for_selected(self):
        if self.selected_item:
            self.prompt_create_tag(self.selected_item)

    def prompt_create_tag(self, item_data: Dict[str, Any]):
        abs_path = item_data.get("abs_path", "")
        stem = Path(abs_path).stem
        initial_keywords = [w.lower() for w in stem.replace("_", " ").replace("-", " ").split() if len(w) > 2]

        initial_data = {
            "nome": stem.replace("_", " ").title(),
            "categoria": "Documentos e Contratos",
            "palavras_chave": initial_keywords,
            "caminho_fisico": f"Documentos/{stem.title()}"
        }

        dlg = TagEditDialog(tag_data=initial_data, is_system=False, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and hasattr(dlg, "result_tag") and dlg.result_tag:
            new_tag = dlg.result_tag
            self.settings_mgr.add_user_tag(new_tag)
            tag_name = new_tag.get("nome", "")
            category = new_tag.get("categoria", "Outros")

            self.file_reclassified.emit(abs_path, tag_name, category)
            self.record_manual_classification(tag_name, item_data.get("entity") or "")

            self.pending_items = [it for it in self.pending_items if it.get("abs_path") != abs_path]
            self.lbl_title.setText(f"❓ {tr('pending.title', count=len(self.pending_items))}")
            self.apply_filter()

    # --- 4. Selecionar Categoria ---
    def select_category_for_selected(self):
        if self.selected_item:
            self.prompt_select_category(self.selected_item)

    def prompt_select_category(self, item_data: Dict[str, Any]):
        abs_path = item_data.get("abs_path", "")
        filename = Path(abs_path).name
        current_cat = item_data.get("category", "")

        dlg = FileMoveCategoryDialog(filename, current_cat, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.file_reclassified.emit(abs_path, "", dlg.selected_category)
            self.pending_items = [it for it in self.pending_items if it.get("abs_path") != abs_path]
            self.lbl_title.setText(f"❓ {tr('pending.title', count=len(self.pending_items))}")
            self.apply_filter()

    # --- 5. Criar Categoria ---
    def create_category_for_selected(self):
        if self.selected_item:
            self.prompt_create_category(self.selected_item)

    def prompt_create_category(self, item_data: Dict[str, Any]):
        abs_path = item_data.get("abs_path", "")
        filename = Path(abs_path).name
        new_cat, ok = QInputDialog.getText(
            self,
            "Criar Nova Categoria",
            f"Digite o nome da nova pasta / categoria para o arquivo:\n'{filename}'"
        )
        if ok and new_cat.strip():
            category_name = new_cat.strip()
            self.file_reclassified.emit(abs_path, "", category_name)
            self.pending_items = [it for it in self.pending_items if it.get("abs_path") != abs_path]
            self.lbl_title.setText(f"❓ {tr('pending.title', count=len(self.pending_items))}")
            self.apply_filter()

    def show_properties(self, item_data: Dict[str, Any]):
        abs_path = item_data.get("abs_path", "")
        dlg = FilePropertiesDialog(abs_path, item_data, self)
        dlg.exec()

    def open_selected_file(self):
        if self.selected_item and self.selected_item.get("abs_path"):
            open_with_default_app(self.selected_item["abs_path"])

    def open_selected_folder(self):
        if self.selected_item and self.selected_item.get("abs_path"):
            open_in_explorer(self.selected_item["abs_path"])

    def trash_selected_single(self):
        if not self.selected_item or not self.selected_item.get("abs_path"):
            return
        abs_path = self.selected_item["abs_path"]
        name = Path(abs_path).name

        reply = QMessageBox.question(
            self,
            "Confirmar Envio para Lixeira",
            f"Deseja marcar '{name}' para envio à lixeira virtual?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.file_marked_trash.emit(abs_path)
            self.pending_items = [it for it in self.pending_items if it.get("abs_path") != abs_path]
            self.lbl_title.setText(f"❓ {tr('pending.title', count=len(self.pending_items))}")
            self.apply_filter()

    def trash_selected_batch(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.information(self, "Indexo", tr("dialog.select_at_least_one"))
            return

        count = len(selected_rows)
        reply = QMessageBox.question(
            self,
            tr("dialog.confirm_trash_batch_title"),
            tr("dialog.confirm_trash_batch_msg", count=count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for r in selected_rows:
                it = self.table.item(r.row(), 0).data(Qt.ItemDataRole.UserRole)
                if it and it.get("abs_path"):
                    self.file_marked_trash.emit(it["abs_path"])
                    self.pending_items = [p for p in self.pending_items if p.get("abs_path") != it["abs_path"]]

            self.lbl_title.setText(f"❓ {tr('pending.title', count=len(self.pending_items))}")
            self.apply_filter()
            QMessageBox.information(self, "Indexo", tr("dialog.marked_trash_count", count=count))

    def accept_all_high(self):
        promoted = []
        for it in list(self.pending_items):
            cand = it.get("candidate")
            if cand and it.get("confidence", 0.0) >= 0.40:
                tag_name = cand.get("nome")
                category = cand.get("categoria", "Outros")
                abs_path = it.get("abs_path", "")
                self.file_reclassified.emit(abs_path, tag_name, category)
                self.record_manual_classification(tag_name, it.get("entity") or "")
                promoted.append(it)

        self.pending_items = [it for it in self.pending_items if it not in promoted]
        self.lbl_title.setText(f"❓ {tr('pending.title', count=len(self.pending_items))}")
        self.apply_filter()
        QMessageBox.information(self, "Indexo", tr("dialog.accept_suggestions_success", count=len(promoted)))

    def record_manual_classification(self, tag_name: str, entity: str):
        count = self.manual_tag_counts.get(tag_name, 0) + 1
        self.manual_tag_counts[tag_name] = count

        n_target = int(self.settings_mgr.get("promotion_n", 3))
        if count >= n_target:
            self.promotion_suggested.emit(tag_name, entity)
            self.manual_tag_counts[tag_name] = 0

    def classify_pending_with_ai(self):
        if not self.pending_items:
            QMessageBox.information(self, "Indexo", tr("pending.no_files_to_classify"))
            return

        from app.ai.model_manager import ModelManager
        from app.workers.ai_worker import AIWorker

        mgr = ModelManager()
        active_slm = mgr.get_active_or_recommended_slm_id()

        # Check if model is downloaded
        if not mgr.is_model_downloaded(active_slm) and not mgr.is_vector_search_ready():
            reply = QMessageBox.question(
                self,
                "Modelo de IA Necessário",
                "O modelo de IA local ainda não foi baixado.\nDeseja abrir as Configurações para baixar o modelo de IA em 1 clique?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # User can go to Settings to download
                pass
            return

        self.btn_classify_ai.setEnabled(False)
        self.btn_classify_ai.setText("🤖 Analisando com IA...")
        self.ai_progress_card.setVisible(True)
        self.ai_progress_bar.setMaximum(len(self.pending_items))
        self.ai_progress_bar.setValue(0)
        self.lbl_ai_status.setText(f"🤖 Classificando 0/{len(self.pending_items)} arquivos com IA local...")

        files_data = []
        for it in self.pending_items:
            abs_p = it.get("abs_path", "")
            text_snip = ""
            try:
                p = Path(abs_p)
                if p.exists() and p.is_file() and p.stat().st_size < 5 * 1024 * 1024:
                    if p.suffix.lower() in (".txt", ".md", ".json", ".csv", ".log", ".py", ".rs", ".js"):
                        text_snip = p.read_text(encoding="utf-8", errors="ignore")[:800]
            except Exception:
                pass

            files_data.append({
                "rel_path": it.get("rel_path", ""),
                "abs_path": abs_p,
                "ext": Path(abs_p).suffix.lower(),
                "size": it.get("size", 0),
                "text": text_snip,
                "initial_candidate": it.get("candidate"),
            })

        self.ai_worker = AIWorker(
            action="classify_batch",
            files_to_classify=files_data,
            parent=self
        )

        completed_count = 0
        total_count = len(self.pending_items)

        def on_item_done(res):
            nonlocal completed_count
            completed_count += 1
            self.ai_progress_bar.setValue(completed_count)
            rel = res.get("file_rel", "")
            self.lbl_ai_status.setText(f"🤖 IA analisando ({completed_count}/{total_count}): {rel}")

            for it in self.pending_items:
                if it.get("rel_path") == rel:
                    it["candidate"] = {
                        "nome": res.get("pasta_sugerida") or res.get("categoria", "Outros"),
                        "categoria": res.get("categoria", "Documentos"),
                        "subcategoria": res.get("subcategoria", ""),
                        "tags": res.get("tags", []),
                    }
                    it["confidence"] = res.get("confianca", 0.85)
                    it["scores"] = {"ia_local": 1.0}
                    break
            self.apply_filter()

        def on_all_done(results):
            self.btn_classify_ai.setEnabled(True)
            self.btn_classify_ai.setText(f"✨ {tr('pending.classify_ai_btn')}")
            self.ai_progress_card.setVisible(False)
            self.apply_filter()
            QMessageBox.information(
                self,
                "Indexo IA",
                f"Classificação com IA local concluída para {len(results)} arquivo(s)!\n"
                "Revise as sugestões e clique em 'Aceitar' ou 'Aceitar Sugestões'."
            )

        def on_error(err):
            self.btn_classify_ai.setEnabled(True)
            self.btn_classify_ai.setText(f"✨ {tr('pending.classify_ai_btn')}")
            self.ai_progress_card.setVisible(False)
            logger.error(f"AI Worker error: {err}")

        self.ai_worker.file_classified_signal.connect(on_item_done)
        self.ai_worker.finished_signal.connect(on_all_done)
        self.ai_worker.error_signal.connect(on_error)
        self.ai_worker.start()

    def retranslate_ui(self):
        self.lbl_title.setText(tr('pending.title', count=len(self.pending_items)))
        self.btn_classify_ai.setText(tr('pending.classify_ai_btn'))
        self.btn_accept_all_high.setText(tr('action.accept_high_confidence'))
        self.btn_trash_selected.setText(tr("action.move_trash"))
        self.lbl_ai_status.setText(tr("pending.ai_classifying"))
        self.search_input.setPlaceholderText(tr("pending.filter_placeholder"))
        curr_mode = self.filter_mode_combo.currentIndex()
        self.filter_mode_combo.blockSignals(True)
        self.filter_mode_combo.clear()
        self.filter_mode_combo.addItems([
            tr("pending.filter_all"),
            tr("pending.filter_with_suggestion"),
            tr("pending.filter_no_suggestion")
        ])
        self.filter_mode_combo.setCurrentIndex(curr_mode if curr_mode >= 0 else 0)
        self.filter_mode_combo.blockSignals(False)
        self.table.setHorizontalHeaderLabels([
            tr("pending.col_file"), tr("pending.col_suggestion"), tr("pending.col_category"), tr("pending.col_actions")
        ])
        self.lbl_selected_title.setText(tr("pending.select_hint"))
        self.btn_accept_single_sug.setText(f"✅ {tr('pending.btn_accept_sug')}")
        self.btn_select_tag_single.setText(f"🏷️ {tr('pending.btn_select_tag')}")
        self.btn_create_tag_single.setText(f"➕ {tr('pending.btn_create_tag')}")
        self.btn_select_cat_single.setText(f"📁 {tr('pending.btn_select_cat')}")
        self.btn_create_cat_single.setText(f"📂 {tr('pending.btn_create_cat')}")
        self.btn_open_file.setText(f"📄 {tr('action.open_file')}")
        self.btn_open_dir.setText(f"📂 {tr('action.open_folder')}")
        self.btn_trash_single.setText(f"🗑️ {tr('action.move_trash')}")
        self.apply_filter()
