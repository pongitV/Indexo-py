import os
import json
import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QFileDialog, QMessageBox, QProgressBar, QLineEdit
)
from app.config.settings_manager import SettingsManager, get_app_dir, get_user_rules_path
from app.i18n.language_manager import tr, LanguageManager
from app.widgets.smooth_scroll import SmoothScrollArea
from app.classification.entity_regex import generate_standard_filename
from loguru import logger

class SettingsView(QWidget):
    back_requested = Signal()
    theme_changed = Signal(str)
    language_changed = Signal(str)
    font_size_changed = Signal(int)
    confidence_threshold_changed = Signal(float)
    tag_manager_requested = Signal()
    shortcuts_requested = Signal()
    power_user_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_mgr = SettingsManager()
        self.init_ui()

    def init_ui(self):
        self.setObjectName("settings_panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(14)

        # Top Header with "← Back" button and Title
        header_layout = QHBoxLayout()
        self.btn_back = QPushButton(tr("action.back"))
        self.btn_back.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.btn_back.setStyleSheet("padding: 6px 16px; border-radius: 4px;")
        self.btn_back.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.btn_back)

        self.lbl_title = QLabel(tr('nav.settings'))
        self.lbl_title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Scrollable container for settings cards
        self.settings_scroll = SmoothScrollArea()
        self.settings_scroll.setObjectName("settings_scroll")

        container = QWidget()
        container.setObjectName("settings_container")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(12)

        # 1. Theme Configuration Card
        theme_card = QFrame()
        theme_card.setObjectName("card_options")
        theme_layout = QVBoxLayout(theme_card)
        theme_layout.setContentsMargins(14, 14, 14, 14)
        theme_layout.setSpacing(8)

        self.lbl_theme_title = QLabel(tr("settings.theme_title"))
        self.lbl_theme_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        theme_layout.addWidget(self.lbl_theme_title)

        theme_btns = QHBoxLayout()
        self.btn_theme_light = QPushButton(tr("settings.theme_light"))
        self.btn_theme_light.clicked.connect(lambda: self.theme_changed.emit("light"))
        theme_btns.addWidget(self.btn_theme_light)

        self.btn_theme_dark = QPushButton(tr("settings.theme_dark"))
        self.btn_theme_dark.clicked.connect(lambda: self.theme_changed.emit("dark"))
        theme_btns.addWidget(self.btn_theme_dark)

        self.btn_theme_sys = QPushButton(tr("settings.theme_system"))
        self.btn_theme_sys.clicked.connect(lambda: self.theme_changed.emit("system"))
        theme_btns.addWidget(self.btn_theme_sys)

        theme_btns.addStretch()
        theme_layout.addLayout(theme_btns)
        c_layout.addWidget(theme_card)

        # 1.5 Universal Font Size Card (Acessibilidade & Legibilidade)
        font_card = QFrame()
        font_card.setObjectName("card_options")
        font_card_layout = QVBoxLayout(font_card)
        font_card_layout.setContentsMargins(14, 14, 14, 14)
        font_card_layout.setSpacing(8)

        self.lbl_font_size_title = QLabel(tr('settings.font_size_label'))
        self.lbl_font_size_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        font_card_layout.addWidget(self.lbl_font_size_title)

        font_btns = QHBoxLayout()
        self.btn_fs_small = QPushButton(tr("settings.font_size_small"))
        self.btn_fs_small.clicked.connect(lambda: self.font_size_changed.emit(13))
        font_btns.addWidget(self.btn_fs_small)

        self.btn_fs_normal = QPushButton(tr("settings.font_size_normal"))
        self.btn_fs_normal.clicked.connect(lambda: self.font_size_changed.emit(15))
        font_btns.addWidget(self.btn_fs_normal)

        self.btn_fs_large = QPushButton(tr("settings.font_size_large"))
        self.btn_fs_large.clicked.connect(lambda: self.font_size_changed.emit(17))
        font_btns.addWidget(self.btn_fs_large)

        self.btn_fs_xlarge = QPushButton(tr("settings.font_size_xlarge"))
        self.btn_fs_xlarge.clicked.connect(lambda: self.font_size_changed.emit(19))
        font_btns.addWidget(self.btn_fs_xlarge)

        font_btns.addStretch()
        font_card_layout.addLayout(font_btns)
        c_layout.addWidget(font_card)

        # 2. Language Selection Card
        lang_card = QFrame()
        lang_card.setObjectName("card_options")
        lang_card_layout = QVBoxLayout(lang_card)
        lang_card_layout.setContentsMargins(14, 14, 14, 14)
        lang_card_layout.setSpacing(8)

        self.lbl_lang_title = QLabel(tr("settings.language_label"))
        self.lbl_lang_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        lang_card_layout.addWidget(self.lbl_lang_title)

        lang_btns = QHBoxLayout()
        self.btn_en = QPushButton("English (enUS)")
        self.btn_en.clicked.connect(lambda: self.language_changed.emit("enUS"))
        lang_btns.addWidget(self.btn_en)

        self.btn_pt = QPushButton("Português (ptBR)")
        self.btn_pt.clicked.connect(lambda: self.language_changed.emit("ptBR"))
        lang_btns.addWidget(self.btn_pt)

        lang_btns.addStretch()
        lang_card_layout.addLayout(lang_btns)
        c_layout.addWidget(lang_card)

        # 2.5 Minimum Confidence Threshold Card
        self.conf_card = QFrame()
        self.conf_card.setObjectName("card_options")
        conf_layout = QVBoxLayout(self.conf_card)
        conf_layout.setContentsMargins(14, 14, 14, 14)
        conf_layout.setSpacing(8)

        self.lbl_conf_title = QLabel(tr("settings.confidence_title"))
        self.lbl_conf_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        conf_layout.addWidget(self.lbl_conf_title)

        self.lbl_conf_desc = QLabel(tr("settings.confidence_desc"))
        self.lbl_conf_desc.setObjectName("lbl_subtext")
        self.lbl_conf_desc.setFont(QFont("Inter", 9))
        self.lbl_conf_desc.setWordWrap(True)
        conf_layout.addWidget(self.lbl_conf_desc)

        self.combo_confidence = QComboBox()
        self.populate_confidence_options()
        self.combo_confidence.currentIndexChanged.connect(self.on_confidence_changed)
        conf_layout.addWidget(self.combo_confidence)
        c_layout.addWidget(self.conf_card)

        # 2.7 Classification & Search Engine Mode Card
        self.search_mode_card = QFrame()
        self.search_mode_card.setObjectName("card_options")
        sm_layout = QVBoxLayout(self.search_mode_card)
        sm_layout.setContentsMargins(14, 14, 14, 14)
        sm_layout.setSpacing(8)

        self.lbl_search_mode_title = QLabel(tr("settings.classification_mode_title"))
        self.lbl_search_mode_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        sm_layout.addWidget(self.lbl_search_mode_title)

        self.lbl_search_mode_desc = QLabel(tr("settings.classification_mode_desc"))
        self.lbl_search_mode_desc.setObjectName("lbl_subtext")
        self.lbl_search_mode_desc.setFont(QFont("Inter", 9))
        self.lbl_search_mode_desc.setWordWrap(True)
        sm_layout.addWidget(self.lbl_search_mode_desc)

        self.combo_search_mode = QComboBox()
        self.combo_search_mode.setFont(QFont("Inter", 9, QFont.Weight.Medium))
        self.lbl_search_mode_detail = QLabel()
        self.lbl_search_mode_detail.setObjectName("lbl_subtext")
        self.lbl_search_mode_detail.setFont(QFont("Inter", 8))
        self.lbl_search_mode_detail.setWordWrap(True)

        self.populate_search_mode_options()
        self.combo_search_mode.currentIndexChanged.connect(self.on_search_mode_changed)
        sm_layout.addWidget(self.combo_search_mode)
        sm_layout.addWidget(self.lbl_search_mode_detail)

        c_layout.addWidget(self.search_mode_card)

        # 2.8 Local AI Configuration Card (Vector Search & SLM Qwen2.5)
        self.ai_card = QFrame()
        self.ai_card.setObjectName("card_options")
        ai_layout = QVBoxLayout(self.ai_card)
        ai_layout.setContentsMargins(14, 14, 14, 14)
        ai_layout.setSpacing(10)

        self.lbl_ai_title = QLabel(tr("settings.ai_title"))
        self.lbl_ai_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        ai_layout.addWidget(self.lbl_ai_title)

        self.lbl_ai_desc = QLabel(tr("settings.ai_desc"))
        self.lbl_ai_desc.setObjectName("lbl_subtext")
        self.lbl_ai_desc.setFont(QFont("Inter", 9))
        self.lbl_ai_desc.setWordWrap(True)
        ai_layout.addWidget(self.lbl_ai_desc)

        # Hardware Diagnostic Banner
        from app.ai.hardware_specs import detect_hardware_specs
        from app.ai.model_manager import ModelManager, MODEL_CATALOGUE
        self.hardware_profile = detect_hardware_specs()
        self.model_mgr = ModelManager()

        specs_box = QFrame()
        specs_box.setObjectName("card_options")
        specs_layout = QVBoxLayout(specs_box)
        specs_layout.setContentsMargins(8, 6, 8, 6)
        specs_layout.setSpacing(4)

        lbl_specs_head = QLabel(tr("settings.ai_specs_title"))
        lbl_specs_head.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        lbl_specs_head.setObjectName("lbl_before")
        specs_layout.addWidget(lbl_specs_head)

        self.lbl_specs_info = QLabel(
            f"CPU: {self.hardware_profile.cpu_cores_logical} {tr('unit.threads')} · RAM: {self.hardware_profile.total_ram_gb:.1f} GB ({self.hardware_profile.available_ram_gb:.1f} GB {tr('unit.free')})\n"
            f"{self.hardware_profile.get_description()}"
        )
        self.lbl_specs_info.setFont(QFont("Inter", 9))
        self.lbl_specs_info.setObjectName("lbl_subtext")
        self.lbl_specs_info.setWordWrap(True)
        specs_layout.addWidget(self.lbl_specs_info)
        ai_layout.addWidget(specs_box)

        # 1. Vector Search Status & Download Row
        vsearch_layout = QHBoxLayout()
        self.lbl_vsearch_status = QLabel()
        self.lbl_vsearch_status.setFont(QFont("Inter", 9, QFont.Weight.Medium))
        vsearch_layout.addWidget(self.lbl_vsearch_status, 1)

        self.btn_download_vector = QPushButton(tr("settings.ai_btn_download_vector"))
        self.btn_download_vector.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.btn_download_vector.setStyleSheet("background: #0284c7; color: white; padding: 4px 10px; border-radius: 4px; border: none;")
        self.btn_download_vector.clicked.connect(self.on_download_vector_clicked)
        vsearch_layout.addWidget(self.btn_download_vector)
        ai_layout.addLayout(vsearch_layout)

        # 2. SLM Model Selection & Download
        slm_select_layout = QHBoxLayout()
        lbl_slm_lbl = QLabel(tr("settings.ai_model_label"))
        lbl_slm_lbl.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        slm_select_layout.addWidget(lbl_slm_lbl)

        self.combo_slm = QComboBox()
        self.combo_slm.setFont(QFont("Inter", 9))
        for mid in ["qwen2.5-1.5b", "qwen2.5-0.5b", "qwen2.5-3b"]:
            info = MODEL_CATALOGUE.get(mid)
            if info:
                self.combo_slm.addItem(f"{info.name} (~{info.size_mb:.0f} MB)", mid)

        # Pre-select based on settings or hardware recommendation
        preferred = self.settings_mgr.get("preferred_slm_model", self.hardware_profile.recommended_model_id)
        idx = self.combo_slm.findData(preferred)
        if idx >= 0:
            self.combo_slm.setCurrentIndex(idx)
        self.combo_slm.currentIndexChanged.connect(self.on_slm_model_changed)
        slm_select_layout.addWidget(self.combo_slm, 1)
        ai_layout.addLayout(slm_select_layout)

        # SLM Status & Download button Row
        slm_status_layout = QHBoxLayout()
        self.lbl_slm_status = QLabel()
        self.lbl_slm_status.setFont(QFont("Inter", 9, QFont.Weight.Medium))
        slm_status_layout.addWidget(self.lbl_slm_status, 1)

        self.btn_download_slm = QPushButton(tr("settings.ai_download_btn"))
        self.btn_download_slm.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.btn_download_slm.setStyleSheet("background: #2563eb; color: white; padding: 5px 12px; border-radius: 4px; border: none;")
        self.btn_download_slm.clicked.connect(self.on_download_slm_clicked)
        slm_status_layout.addWidget(self.btn_download_slm)

        self.btn_delete_slm = QPushButton(tr("settings.ai_delete_btn"))
        self.btn_delete_slm.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.btn_delete_slm.setStyleSheet("background: #dc2626; color: white; padding: 5px 12px; border-radius: 4px; border: none;")
        self.btn_delete_slm.clicked.connect(self.on_delete_slm_clicked)
        self.btn_delete_slm.setVisible(False)
        slm_status_layout.addWidget(self.btn_delete_slm)
        ai_layout.addLayout(slm_status_layout)

        # Progress bar for active downloads
        self.ai_progress_bar = QProgressBar()
        self.ai_progress_bar.setVisible(False)
        self.ai_progress_bar.setFixedHeight(16)
        ai_layout.addWidget(self.ai_progress_bar)

        # 3. Interactive AI Playground / Diagnostic Sub-Card
        tester_box = QFrame()
        tester_box.setObjectName("card_options")
        tb_layout = QVBoxLayout(tester_box)
        tb_layout.setContentsMargins(10, 10, 10, 10)
        tb_layout.setSpacing(6)

        self.lbl_tester_head = QLabel(tr("ai.tester_title"))
        self.lbl_tester_head.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        tb_layout.addWidget(self.lbl_tester_head)

        self.lbl_tester_desc = QLabel(tr("ai.tester_desc"))
        self.lbl_tester_desc.setObjectName("lbl_subtext")
        self.lbl_tester_desc.setFont(QFont("Inter", 8))
        tb_layout.addWidget(self.lbl_tester_desc)

        input_row = QHBoxLayout()
        self.input_tester_query = QLineEdit()
        self.input_tester_query.setFont(QFont("Inter", 9))
        self.input_tester_query.setPlaceholderText(tr("ai.tester_input_placeholder"))
        self.input_tester_query.returnPressed.connect(self.run_ai_test)
        input_row.addWidget(self.input_tester_query, 1)

        self.btn_run_test = QPushButton(tr("ai.tester_btn_test"))
        self.btn_run_test.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.btn_run_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run_test.setStyleSheet("background: #0284c7; color: white; padding: 6px 12px; border-radius: 4px; border: none;")
        self.btn_run_test.clicked.connect(self.run_ai_test)
        input_row.addWidget(self.btn_run_test)
        tb_layout.addLayout(input_row)

        self.lbl_test_result = QLabel("")
        self.lbl_test_result.setFont(QFont("Inter", 9))
        self.lbl_test_result.setWordWrap(True)
        self.lbl_test_result.setVisible(False)
        tb_layout.addWidget(self.lbl_test_result)

        ai_layout.addWidget(tester_box)

        self.update_ai_status_labels()
        c_layout.addWidget(self.ai_card)

        # 3. File Renaming Pattern Customization Card
        self.rename_card = QFrame()
        self.rename_card.setObjectName("card_options")
        ren_layout = QVBoxLayout(self.rename_card)
        ren_layout.setContentsMargins(14, 14, 14, 14)
        ren_layout.setSpacing(8)

        self.lbl_rename_title = QLabel(tr('settings.rename_title'))
        self.lbl_rename_title.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        ren_layout.addWidget(self.lbl_rename_title)

        grid = QHBoxLayout()
        
        # Separator
        sep_vbox = QVBoxLayout()
        self.lbl_sep = QLabel(tr("settings.rename_sep_label"))
        sep_vbox.addWidget(self.lbl_sep)
        self.combo_sep = QComboBox()
        self.combo_sep.addItem("_ (Underscore)", "_")
        self.combo_sep.addItem("- (Hyphen)", "-")
        self.combo_sep.addItem(" - (Dash with spaces)", " - ")
        self.combo_sep.addItem(". (Dot)", ".")
        self.combo_sep.addItem("  (Space)", " ")
        curr_sep = self.settings_mgr.get("rename_separator", " - ")
        idx_sep = self.combo_sep.findData(curr_sep)
        if idx_sep >= 0:
            self.combo_sep.setCurrentIndex(idx_sep)
        self.combo_sep.currentIndexChanged.connect(self.on_rename_setting_changed)
        sep_vbox.addWidget(self.combo_sep)
        grid.addLayout(sep_vbox)

        # Date Position
        pos_vbox = QVBoxLayout()
        self.lbl_date_pos = QLabel(tr("settings.rename_date_pos_label"))
        pos_vbox.addWidget(self.lbl_date_pos)
        self.combo_date_pos = QComboBox()
        self.combo_date_pos.addItem(tr("settings.date_pos_prefix"), "prefix")
        self.combo_date_pos.addItem(tr("settings.date_pos_suffix"), "suffix")
        self.combo_date_pos.addItem(tr("settings.date_pos_none"), "none")
        curr_pos = self.settings_mgr.get("rename_date_position", "suffix")
        idx_pos = self.combo_date_pos.findData(curr_pos)
        if idx_pos >= 0:
            self.combo_date_pos.setCurrentIndex(idx_pos)
        self.combo_date_pos.currentIndexChanged.connect(self.on_rename_setting_changed)
        pos_vbox.addWidget(self.combo_date_pos)
        grid.addLayout(pos_vbox)

        # Date Format
        fmt_vbox = QVBoxLayout()
        self.lbl_date_fmt = QLabel(tr("settings.rename_date_fmt_label"))
        fmt_vbox.addWidget(self.lbl_date_fmt)
        self.combo_date_fmt = QComboBox()
        self.combo_date_fmt.addItem("DD-MM-YYYY (10-05-2024)", "DD-MM-YYYY")
        self.combo_date_fmt.addItem("YYYY-MM-DD (2024-05-10)", "YYYY-MM-DD")
        self.combo_date_fmt.addItem("YYYY_MM_DD (2024_05_10)", "YYYY_MM_DD")
        self.combo_date_fmt.addItem("YYYYMMDD (20240510)", "YYYYMMDD")
        self.combo_date_fmt.addItem("DD_MM_YYYY (10_05_2024)", "DD_MM_YYYY")
        self.combo_date_fmt.addItem("DDMMYYYY (10052024)", "DDMMYYYY")
        self.combo_date_fmt.addItem("MM-DD-YYYY (05-10-2024)", "MM-DD-YYYY")
        curr_fmt = self.settings_mgr.get("rename_date_format", "DD-MM-YYYY")
        idx_fmt = self.combo_date_fmt.findData(curr_fmt)
        if idx_fmt >= 0:
            self.combo_date_fmt.setCurrentIndex(idx_fmt)
        self.combo_date_fmt.currentIndexChanged.connect(self.on_rename_setting_changed)
        fmt_vbox.addWidget(self.combo_date_fmt)
        grid.addLayout(fmt_vbox)

        # Casing
        case_vbox = QVBoxLayout()
        self.lbl_casing = QLabel(tr("settings.rename_casing_label"))
        case_vbox.addWidget(self.lbl_casing)
        self.combo_casing = QComboBox()
        self.combo_casing.addItem(tr("settings.casing_title"), "title")
        self.combo_casing.addItem(tr("settings.casing_lower"), "lower")
        self.combo_casing.addItem(tr("settings.casing_upper"), "upper")
        self.combo_casing.addItem(tr("settings.casing_original"), "original")
        curr_case = self.settings_mgr.get("rename_casing", "title")
        idx_case = self.combo_casing.findData(curr_case)
        if idx_case >= 0:
            self.combo_casing.setCurrentIndex(idx_case)
        self.combo_casing.currentIndexChanged.connect(self.on_rename_setting_changed)
        case_vbox.addWidget(self.combo_casing)
        grid.addLayout(case_vbox)

        ren_layout.addLayout(grid)

        # Live Preview Label
        self.lbl_rename_preview = QLabel("")
        self.lbl_rename_preview.setStyleSheet("color: #205EA6; font-weight: bold; font-family: Consolas; font-size: 12px; padding: 4px;")
        ren_layout.addWidget(self.lbl_rename_preview)
        self.update_rename_preview()

        c_layout.addWidget(self.rename_card)

        # 6. Privacy & Local Content Card
        privacy_card = QFrame()
        privacy_card.setObjectName("privacy_card")
        priv_layout = QVBoxLayout(privacy_card)
        priv_layout.setContentsMargins(14, 14, 14, 14)
        priv_layout.setSpacing(6)
        
        self.lbl_priv = QLabel(tr("settings.privacy_title"))
        self.lbl_priv.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        priv_layout.addWidget(self.lbl_priv)

        self.lbl_priv_desc = QLabel(tr("settings.privacy_desc"))
        self.lbl_priv_desc.setObjectName("lbl_subtext")
        self.lbl_priv_desc.setFont(QFont("Inter", 9))
        priv_layout.addWidget(self.lbl_priv_desc)

        self.btn_clear_content = QPushButton(tr('action.clear_content'))
        self.btn_clear_content.clicked.connect(self.clear_privacy_content)
        priv_layout.addWidget(self.btn_clear_content, 0, Qt.AlignmentFlag.AlignLeft)

        c_layout.addWidget(privacy_card)

        # 7. Profile Backup (Export / Import Rules)
        self.prof_card = QFrame()
        self.prof_card.setObjectName("prof_card")
        prof_layout = QVBoxLayout(self.prof_card)
        prof_layout.setContentsMargins(14, 14, 14, 14)
        prof_layout.setSpacing(6)
        
        self.lbl_prof = QLabel(tr("settings.profile_backup_title"))
        self.lbl_prof.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        prof_layout.addWidget(self.lbl_prof)

        prof_btns = QHBoxLayout()
        self.btn_export_prof = QPushButton(tr('action.export_profile'))
        self.btn_export_prof.clicked.connect(self.export_profile)
        prof_btns.addWidget(self.btn_export_prof)

        self.btn_import_prof = QPushButton(tr('action.import_profile'))
        self.btn_import_prof.clicked.connect(self.import_profile)
        prof_btns.addWidget(self.btn_import_prof)

        prof_btns.addStretch()
        prof_layout.addLayout(prof_btns)
        c_layout.addWidget(self.prof_card)

        # 8. Export Log
        self.btn_export_log = QPushButton(tr('action.export_log'))
        self.btn_export_log.clicked.connect(self.export_log_file)
        c_layout.addWidget(self.btn_export_log, 0, Qt.AlignmentFlag.AlignLeft)

        c_layout.addStretch()
        self.settings_scroll.setWidget(container)
        layout.addWidget(self.settings_scroll)

    def on_rename_setting_changed(self):
        sep = self.combo_sep.currentData() or "_"
        pos = self.combo_date_pos.currentData() or "prefix"
        fmt = self.combo_date_fmt.currentData() or "YYYY-MM-DD"
        case = self.combo_casing.currentData() or "title"

        self.settings_mgr.set("rename_separator", sep)
        self.settings_mgr.set("rename_date_position", pos)
        self.settings_mgr.set("rename_date_format", fmt)
        self.settings_mgr.set("rename_casing", case)

        self.update_rename_preview()

    def update_rename_preview(self):
        cfg = {
            "rename_separator": self.combo_sep.currentData() or "_",
            "rename_date_position": self.combo_date_pos.currentData() or "prefix",
            "rename_date_format": self.combo_date_fmt.currentData() or "YYYY-MM-DD",
            "rename_casing": self.combo_casing.currentData() or "title"
        }
        ex_name = generate_standard_filename("2024-05-10", "Enel", "Conta Luz", ".pdf", "fatura_luz", cfg)
        self.lbl_rename_preview.setText(f"{tr('settings.rename_preview_label', default='Exemplo:')}  {ex_name}")

    def clear_privacy_content(self):
        reply = QMessageBox.question(
            self,
            tr("settings.privacy_title"),
            "Deseja realmente limpar todos os textos e miniaturas extraídos da memória e do banco local?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                app_dir = get_app_dir()
                cache_dir = app_dir / "cache"
                if cache_dir.exists():
                    shutil.rmtree(cache_dir, ignore_errors=True)
                QMessageBox.information(self, "Indexo", "Cache e textos locais limpos com sucesso!")
            except Exception as e:
                logger.error("Failed to clear local cache: {}", e)
                QMessageBox.warning(self, "Indexo", f"Falha ao limpar cache: {e}")

    def export_profile(self):
        file_path, _ = QFileDialog.getSaveFileName(self, tr("action.export_profile"), "indexo_rules_profile.json", "JSON (*.json)")
        if file_path:
            try:
                user_rules_path = get_user_rules_path()
                if user_rules_path.exists():
                    shutil.copy2(user_rules_path, file_path)
                else:
                    rules = self.settings_mgr.get_user_tags()
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(rules, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Indexo", "Perfil de regras exportado com sucesso!")
            except Exception as e:
                logger.error("Failed to export profile: {}", e)
                QMessageBox.warning(self, "Indexo", f"Falha ao exportar perfil: {e}")

    def import_profile(self):
        file_path, _ = QFileDialog.getOpenFileName(self, tr("action.import_profile"), "", "JSON (*.json)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    rules = json.load(f)
                if isinstance(rules, list):
                    for r in rules:
                        if isinstance(r, dict) and "nome" in r:
                            self.settings_mgr.add_user_tag(r)
                    QMessageBox.information(self, "Indexo", "Perfil de regras importado com sucesso!")
                else:
                    QMessageBox.warning(self, "Indexo", "Arquivo de perfil inválido.")
            except Exception as e:
                logger.error("Failed to import profile: {}", e)
                QMessageBox.warning(self, "Indexo", f"Falha ao importar perfil: {e}")

    def export_log_file(self):
        log_dir = get_app_dir() / "logs"
        log_file = log_dir / "indexo.log"
        if not log_file.exists():
            QMessageBox.information(self, "Indexo", "Nenhum arquivo de log encontrado para exportar.")
            return

        dest_path, _ = QFileDialog.getSaveFileName(self, tr("action.export_log"), "indexo_diagnostic.log", "Log (*.log *.txt)")
        if dest_path:
            try:
                shutil.copy2(log_file, dest_path)
                QMessageBox.information(self, "Indexo", "Arquivo de diagnóstico exportado com sucesso!")
            except Exception as e:
                logger.error("Failed to export log file: {}", e)
                QMessageBox.warning(self, "Indexo", f"Falha ao exportar log: {e}")

    def populate_confidence_options(self):
        curr_val = round(float(self.settings_mgr.get("confidence_threshold", 0.80)), 2)
        self.combo_confidence.blockSignals(True)
        self.combo_confidence.clear()

        levels = [
            (0.50, tr("settings.confidence_50")),
            (0.60, tr("settings.confidence_60")),
            (0.65, tr("settings.confidence_65")),
            (0.70, tr("settings.confidence_70")),
            (0.75, tr("settings.confidence_75")),
            (0.80, tr("settings.confidence_80")),
            (0.85, tr("settings.confidence_85")),
            (0.90, tr("settings.confidence_90")),
            (0.95, tr("settings.confidence_95")),
        ]

        selected_idx = 5  # Default to 0.80
        for idx, (val, label) in enumerate(levels):
            self.combo_confidence.addItem(label, val)
            if abs(val - curr_val) < 0.01:
                selected_idx = idx

        self.combo_confidence.setCurrentIndex(selected_idx)
        self.combo_confidence.blockSignals(False)

    def on_confidence_changed(self):
        val = float(self.combo_confidence.currentData() or 0.80)
        self.settings_mgr.set("confidence_threshold", val)
        self.confidence_threshold_changed.emit(val)

    def retranslate_ui(self):
        self.btn_back.setText(tr("action.back"))
        self.lbl_title.setText(tr('nav.settings'))
        self.lbl_theme_title.setText(tr("settings.theme_title"))
        self.btn_theme_light.setText(tr("settings.theme_light"))
        self.btn_theme_dark.setText(tr("settings.theme_dark"))
        self.btn_theme_sys.setText(tr("settings.theme_system"))
        self.lbl_font_size_title.setText(tr('settings.font_size_label'))
        self.btn_fs_small.setText(tr("settings.font_size_small"))
        self.btn_fs_normal.setText(tr("settings.font_size_normal"))
        self.btn_fs_large.setText(tr("settings.font_size_large"))
        self.btn_fs_xlarge.setText(tr("settings.font_size_xlarge"))
        self.lbl_lang_title.setText(tr("settings.language_label"))
        self.lbl_conf_title.setText(tr("settings.confidence_title"))
        self.lbl_conf_desc.setText(tr("settings.confidence_desc"))
        self.populate_confidence_options()
        self.lbl_rename_title.setText(tr('settings.rename_title'))
        self.lbl_sep.setText(tr("settings.rename_sep_label"))
        self.lbl_date_pos.setText(tr("settings.rename_date_pos_label"))
        self.lbl_date_fmt.setText(tr("settings.rename_date_fmt_label"))
        self.lbl_casing.setText(tr("settings.rename_casing_label"))
        self.lbl_priv.setText(tr("settings.privacy_title"))
        self.lbl_priv_desc.setText(tr("settings.privacy_desc"))
        self.btn_clear_content.setText(tr('action.clear_content'))
        self.lbl_prof.setText(tr("settings.profile_backup_title"))
        self.btn_export_prof.setText(tr('action.export_profile'))
        self.btn_import_prof.setText(tr('action.import_profile'))
        self.btn_export_log.setText(tr('action.export_log'))
        if hasattr(self, 'input_tester_query'):
            self.input_tester_query.setPlaceholderText(tr("ai.tester_input_placeholder"))
        if hasattr(self, 'btn_run_test'):
            self.btn_run_test.setText(tr("ai.tester_btn_test"))
        self.update_rename_preview()
        self.update_ai_status_labels()

    def update_ai_status_labels(self):
        from app.ai.model_manager import ModelManager
        mgr = ModelManager()

        # Vector search status
        if mgr.is_vector_search_ready():
            self.lbl_vsearch_status.setText(f"<span style='color: #22c55e;'>{tr('settings.ai_vector_search_ready')}</span>")
            self.btn_download_vector.setVisible(False)
        else:
            self.lbl_vsearch_status.setText(f"<span style='color: #f59e0b;'>{tr('settings.ai_vector_search_missing')}</span>")
            self.btn_download_vector.setVisible(True)

        # SLM status
        chosen_slm = self.combo_slm.currentData() or "qwen2.5-1.5b"
        if mgr.is_model_downloaded(chosen_slm):
            self.lbl_slm_status.setText(f"<span style='color: #22c55e;'>{tr('settings.ai_ready')}</span>")
            self.btn_download_slm.setVisible(False)
            self.btn_delete_slm.setVisible(True)
        else:
            self.lbl_slm_status.setText(f"<span style='color: #94a3b8;'>{tr('settings.ai_not_downloaded')}</span>")
            self.btn_download_slm.setVisible(True)
            self.btn_download_slm.setText(tr("settings.ai_download_btn"))
            self.btn_delete_slm.setVisible(False)

    def on_slm_model_changed(self):
        chosen = self.combo_slm.currentData()
        if chosen:
            self.settings_mgr.set("preferred_slm_model", chosen)
        self.update_ai_status_labels()

    def on_delete_slm_clicked(self):
        from app.ai.model_manager import ModelManager, MODEL_CATALOGUE
        chosen_slm = self.combo_slm.currentData() or "qwen2.5-1.5b"
        info = MODEL_CATALOGUE.get(chosen_slm)
        model_name = info.name if info else chosen_slm
        size_mb = f"{info.size_mb:.0f}" if info else ""

        reply = QMessageBox.question(
            self,
            tr("settings.ai_delete_title"),
            tr("settings.ai_delete_confirm", model=model_name, size=size_mb),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            mgr = ModelManager()
            if mgr.delete_model(chosen_slm):
                QMessageBox.information(self, "Indexo", tr("settings.ai_delete_success", model=model_name))
            else:
                QMessageBox.warning(self, "Indexo", tr("settings.ai_delete_fail"))
            self.update_ai_status_labels()

    def on_download_vector_clicked(self):
        from app.workers.ai_worker import AIWorker
        self.btn_download_vector.setEnabled(False)
        self.ai_progress_bar.setVisible(True)
        self.ai_progress_bar.setValue(0)

        # Download embedding model first, then tokenizer
        self.worker_vec = AIWorker(action="download_model", model_id_to_download="embedding-multilingual-minilm", parent=self)
        self.worker_vec.download_progress_signal.connect(lambda mid, d, t, p: self.ai_progress_bar.setValue(int(p)))
        
        def on_vec_err(err):
            self.ai_progress_bar.setVisible(False)
            self.btn_download_vector.setEnabled(True)
            self.update_ai_status_labels()
            QMessageBox.warning(self, "Indexo", f"Erro no download do motor vetorial: {err}")

        def on_emb_done(_):
            self.worker_tok = AIWorker(action="download_model", model_id_to_download="embedding-tokenizer", parent=self)
            self.worker_tok.download_progress_signal.connect(lambda mid, d, t, p: self.ai_progress_bar.setValue(int(p)))
            def on_tok_done(__):
                self.ai_progress_bar.setVisible(False)
                self.btn_download_vector.setEnabled(True)
                self.update_ai_status_labels()
                QMessageBox.information(self, "Indexo", "Motor de busca vetorial baixado e ativado com sucesso!")
            self.worker_tok.finished_signal.connect(on_tok_done)
            self.worker_tok.error_signal.connect(on_vec_err)
            self.worker_tok.start()

        self.worker_vec.finished_signal.connect(on_emb_done)
        self.worker_vec.error_signal.connect(on_vec_err)
        self.worker_vec.start()

    def on_download_slm_clicked(self):
        from app.workers.ai_worker import AIWorker
        chosen_slm = self.combo_slm.currentData() or "qwen2.5-1.5b"
        self.btn_download_slm.setEnabled(False)
        self.ai_progress_bar.setVisible(True)
        self.ai_progress_bar.setValue(0)

        self.worker_slm = AIWorker(action="download_model", model_id_to_download=chosen_slm, parent=self)
        self.worker_slm.download_progress_signal.connect(lambda mid, d, t, p: self.ai_progress_bar.setValue(int(p)))
        
        def on_slm_done(_):
            self.ai_progress_bar.setVisible(False)
            self.btn_download_slm.setEnabled(True)
            self.update_ai_status_labels()
            QMessageBox.information(self, "Indexo", f"Modelo de IA ({chosen_slm}) baixado e pronto para uso local!")

        def on_slm_err(err):
            self.ai_progress_bar.setVisible(False)
            self.btn_download_slm.setEnabled(True)
            self.update_ai_status_labels()
            QMessageBox.warning(self, "Indexo", f"Erro no download do modelo: {err}")

        self.worker_slm.finished_signal.connect(on_slm_done)
        self.worker_slm.error_signal.connect(on_slm_err)
        self.worker_slm.start()

    def run_ai_test(self):
        from app.ai.ai_tester import AITester
        text = self.input_tester_query.text().strip()
        if not text:
            return
        tester = AITester()
        diag = tester.diagnose_query(text)
        
        tags_str = ", ".join(diag.tags) if diag.tags else "Nenhuma"
        conf_percent = diag.confianca * 100.0
        
        res_html = (
            f"<b>{tr('ai.tester_result_engine')}:</b> <span style='color: #2563eb;'>{diag.engine_label}</span><br>"
            f"<b>{tr('ai.tester_result_category')}:</b> <b>{diag.categoria}</b> » {diag.subcategoria}<br>"
            f"<b>{tr('ai.tester_result_folder')}:</b> <code>{diag.pasta_sugerida}</code><br>"
            f"<b>{tr('ai.tester_result_confidence')}:</b> {conf_percent:.1f}% &nbsp;·&nbsp; "
            f"<b>{tr('ai.tester_result_tags')}:</b> <i>{tags_str}</i>"
        )
        self.lbl_test_result.setText(res_html)
        self.lbl_test_result.setVisible(True)

    def populate_search_mode_options(self):
        self.combo_search_mode.blockSignals(True)
        self.combo_search_mode.clear()
        self.combo_search_mode.addItem(tr("settings.mode_rules_fast"), "rules_fast")
        self.combo_search_mode.addItem(tr("settings.mode_hybrid_vector"), "hybrid_vector")
        self.combo_search_mode.addItem(tr("settings.mode_full_ai"), "full_ai")

        current_mode = self.settings_mgr.get("classification_mode", "rules_fast")
        idx = self.combo_search_mode.findData(current_mode)
        if idx >= 0:
            self.combo_search_mode.setCurrentIndex(idx)
        self.combo_search_mode.blockSignals(False)
        self.update_search_mode_detail()

    def on_search_mode_changed(self, index: int):
        data = self.combo_search_mode.itemData(index)
        if data:
            self.settings_mgr.set("classification_mode", data)
            self.update_search_mode_detail()

    def update_search_mode_detail(self):
        mode = self.combo_search_mode.currentData() or "rules_fast"
        if mode == "rules_fast":
            self.lbl_search_mode_detail.setText(f"ℹ️ {tr('settings.mode_rules_fast_desc')}")
        elif mode == "hybrid_vector":
            self.lbl_search_mode_detail.setText(f"ℹ️ {tr('settings.mode_hybrid_vector_desc')}")
        else:
            self.lbl_search_mode_detail.setText(f"ℹ️ {tr('settings.mode_full_ai_desc')}")


