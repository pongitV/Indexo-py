import sys
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QStackedWidget, QComboBox, QProgressBar,
    QMessageBox, QApplication, QGridLayout, QSizePolicy
)

from app.i18n.language_manager import tr, LanguageManager
from app.utils.theme_manager import get_app_icon_path, get_effective_theme, apply_app_theme
from app.config.settings_manager import SettingsManager
from app.ai.hardware_specs import detect_hardware_specs
from app.ai.model_manager import ModelManager, MODEL_CATALOGUE
from app.classification.entity_regex import generate_standard_filename
from app.widgets.smooth_scroll import SmoothScrollArea
from app.workers.ai_worker import AIWorker


class OnboardingWizard(QDialog):
    """
    Two-step interactive setup wizard:
    Step 0: Welcome Screen (Zero-Friction 1-Click Auto Setup, Hardware Diagnosis, Security Guarantees)
    Step 1: Advanced Settings (Theme, Language, AI Model Download, Rename Pattern, Confidence Threshold)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings_mgr = SettingsManager()
        self.lang_mgr = LanguageManager.get_instance()
        self.model_mgr = ModelManager()
        self.hardware_profile = detect_hardware_specs()
        self.active_worker = None

        # 1. Auto-detect system language on first launch if not configured
        configured_lang = self.settings_mgr.get("language", "")
        if not configured_lang:
            sys_lang = self.lang_mgr.detect_system_language()
            self.lang_mgr.set_language(sys_lang)
            self.settings_mgr.set("language", sys_lang)

        self.setWindowTitle(tr("app.title"))
        self.setMinimumSize(780, 620)
        self.resize(860, 720)
        self.setSizeGripEnabled(True)

        # Set Window Icon
        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        self.wizard_stack = QStackedWidget()

        # Step 0: Welcome Landing View
        self.step_welcome = self.create_welcome_step()
        self.wizard_stack.addWidget(self.step_welcome)

        # Step 1: Initial Settings View
        self.step_settings = self.create_settings_step()
        self.wizard_stack.addWidget(self.step_settings)

        main_layout.addWidget(self.wizard_stack)
        self.wizard_stack.setCurrentIndex(0)

    # =========================================================================
    # STEP 0: WELCOME SCREEN (ADAPTIVE, SPACIOUS & FULLY RESPONSIVE)
    # =========================================================================
    def create_welcome_step(self) -> QWidget:
        scroll = SmoothScrollArea()
        scroll.setObjectName("settings_scroll")
        scroll.setWidgetResizable(True)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # 1. Header with Logo, Catchphrase and Icon
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_path = get_app_icon_path()
        if icon_path.exists():
            lbl_icon = QLabel()
            pix = QPixmap(str(icon_path))
            if not pix.isNull():
                lbl_icon.setPixmap(
                    pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
                header_layout.addWidget(lbl_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.lbl_welcome_title = QLabel("INDEXO")
        self.lbl_welcome_title.setObjectName("lbl_before")
        self.lbl_welcome_title.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        title_vbox.addWidget(self.lbl_welcome_title)

        self.lbl_welcome_slogan = QLabel(tr("app.slogan"))
        self.lbl_welcome_slogan.setObjectName("lbl_subtext")
        self.lbl_welcome_slogan.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        self.lbl_welcome_slogan.setWordWrap(True)
        title_vbox.addWidget(self.lbl_welcome_slogan)
        header_layout.addLayout(title_vbox)

        layout.addLayout(header_layout)

        # 2. Spacious Computer Diagnostic Card (Auto-Adapting to Content Size)
        diag_card = QFrame()
        diag_card.setObjectName("card_options")
        diag_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        diag_layout = QVBoxLayout(diag_card)
        diag_layout.setContentsMargins(20, 16, 20, 16)
        diag_layout.setSpacing(14)

        self.lbl_diag_head = QLabel("💻 " + tr("onboarding.diag_title"))
        self.lbl_diag_head.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.lbl_diag_head.setObjectName("lbl_before")
        diag_layout.addWidget(self.lbl_diag_head)

        is_pt = self.lang_mgr.current_language == "ptBR"
        sys_lang_str = "Português (Brasil)" if is_pt else "English (US)"
        rec_model_name = MODEL_CATALOGUE.get(self.hardware_profile.recommended_model_id, None)
        rec_model_str = rec_model_name.name if rec_model_name else self.hardware_profile.recommended_model_id

        # 4 Diagnostic Metric Rows in a 2-Column Responsive Layout
        diag_grid = QGridLayout()
        diag_grid.setHorizontalSpacing(24)
        diag_grid.setVerticalSpacing(10)

        # Item 1: System Language
        self.lbl_m1 = QLabel(f"🌐 <b>{tr('onboarding.diag_lang')}:</b> {sys_lang_str}")
        self.lbl_m1.setFont(QFont("Inter", 10))
        self.lbl_m1.setWordWrap(True)
        diag_grid.addWidget(self.lbl_m1, 0, 0)

        # Item 2: CPU Cores & Threads
        cpu_display = self.hardware_profile.processor_name if len(self.hardware_profile.processor_name) < 40 else self.hardware_profile.processor_name[:38] + "..."
        self.lbl_m2 = QLabel(f"⚡ <b>{tr('onboarding.diag_cpu')}:</b> {self.hardware_profile.cpu_cores_logical} threads ({cpu_display})")
        self.lbl_m2.setFont(QFont("Inter", 10))
        self.lbl_m2.setWordWrap(True)
        diag_grid.addWidget(self.lbl_m2, 0, 1)

        # Item 3: RAM Memory
        self.lbl_m3 = QLabel(f"💾 <b>{tr('onboarding.diag_ram')}:</b> {self.hardware_profile.total_ram_gb:.1f} GB ({self.hardware_profile.available_ram_gb:.1f} GB {tr('unit.free')})")
        self.lbl_m3.setFont(QFont("Inter", 10))
        self.lbl_m3.setWordWrap(True)
        diag_grid.addWidget(self.lbl_m3, 1, 0)

        # Item 4: Vector Search Engine Status
        vec_status_str = f"<span style='color: #22c55e; font-weight: bold;'>{tr('onboarding.vector_status_active')}</span>"
        self.lbl_m4 = QLabel(f"🧠 <b>{tr('onboarding.vector_search_title')}:</b> {vec_status_str}")
        self.lbl_m4.setFont(QFont("Inter", 10))
        self.lbl_m4.setWordWrap(True)
        diag_grid.addWidget(self.lbl_m4, 1, 1)

        diag_layout.addLayout(diag_grid)

        # Profile Summary Badge
        self.lbl_prof_desc = QLabel(f"🎯 <b>{tr('onboarding.profile_optimized')}:</b> {self.hardware_profile.get_description()} · {rec_model_str}")
        self.lbl_prof_desc.setFont(QFont("Inter", 9))
        self.lbl_prof_desc.setObjectName("lbl_after")
        self.lbl_prof_desc.setWordWrap(True)
        diag_layout.addWidget(self.lbl_prof_desc)

        layout.addWidget(diag_card)

        # 3. Core Principles & Safety Features Card (Auto-Adapting to Content Size)
        features_card = QFrame()
        features_card.setObjectName("card_options")
        features_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        feat_layout = QVBoxLayout(features_card)
        feat_layout.setContentsMargins(20, 16, 20, 16)
        feat_layout.setSpacing(10)

        self.lbl_feat1 = QLabel(tr("onboarding.feature_1"))
        self.lbl_feat1.setFont(QFont("Inter", 10))
        self.lbl_feat1.setWordWrap(True)
        feat_layout.addWidget(self.lbl_feat1)

        self.lbl_feat2 = QLabel(tr("onboarding.feature_2"))
        self.lbl_feat2.setFont(QFont("Inter", 10))
        self.lbl_feat2.setWordWrap(True)
        feat_layout.addWidget(self.lbl_feat2)

        self.lbl_feat3 = QLabel(tr("onboarding.feature_3"))
        self.lbl_feat3.setFont(QFont("Inter", 10))
        self.lbl_feat3.setWordWrap(True)
        feat_layout.addWidget(self.lbl_feat3)

        layout.addWidget(features_card)

        # 4. Action Buttons: 1-Click Auto Start (Primary) + Customize (Secondary)
        btn_box = QVBoxLayout()
        btn_box.setSpacing(10)
        btn_box.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_auto_start = QPushButton(tr("onboarding.btn_auto_start"))
        self.btn_auto_start.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        self.btn_auto_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto_start.setStyleSheet(
            "QPushButton { background: #22c55e; color: #ffffff; padding: 14px 44px; border-radius: 8px; font-weight: bold; border: none; min-width: 380px; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        self.btn_auto_start.clicked.connect(self.apply_auto_defaults_and_start)
        btn_box.addWidget(self.btn_auto_start)

        self.btn_customize = QPushButton(tr("onboarding.btn_customize"))
        self.btn_customize.setFont(QFont("Inter", 10))
        self.btn_customize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_customize.setStyleSheet(
            "QPushButton { background: transparent; color: #205EA6; text-decoration: underline; border: none; padding: 4px; }"
            "QPushButton:hover { color: #164e8a; }"
        )
        self.btn_customize.clicked.connect(self.go_to_settings_step)
        btn_box.addWidget(self.btn_customize)

        layout.addLayout(btn_box)
        scroll.setWidget(panel)
        return scroll

    def apply_auto_defaults_and_start(self):
        # Auto-apply the detected profile and 80% safe confidence threshold seamlessly
        self.settings_mgr.set("language", self.lang_mgr.current_language)
        self.settings_mgr.set("theme", "system")
        self.settings_mgr.set("preferred_slm_model", self.hardware_profile.recommended_model_id)
        self.settings_mgr.set("rename_separator", " - ")
        self.settings_mgr.set("rename_date_format", "YYYY-MM-DD")
        self.settings_mgr.set("rename_casing", "title")
        self.settings_mgr.set("confidence_threshold", 0.80)
        self.settings_mgr.set("first_run", False)
        self.accept()

    # =========================================================================
    # STEP 1: INITIAL SETTINGS SCREEN (ADVANCED USERS)
    # =========================================================================
    def create_settings_step(self) -> QWidget:
        scroll = SmoothScrollArea()
        scroll.setObjectName("settings_scroll")
        scroll.setWidgetResizable(True)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header
        self.lbl_set_title = QLabel(tr("onboarding.settings_title"))
        self.lbl_set_title.setFont(QFont("Inter", 15, QFont.Weight.Bold))
        layout.addWidget(self.lbl_set_title)

        self.lbl_set_desc = QLabel(tr("onboarding.settings_desc"))
        self.lbl_set_desc.setObjectName("lbl_subtext")
        self.lbl_set_desc.setFont(QFont("Inter", 10))
        self.lbl_set_desc.setWordWrap(True)
        layout.addWidget(self.lbl_set_desc)

        # --- Card 1: Language & Theme SIDE BY SIDE ---
        card_theme_lang = QFrame()
        card_theme_lang.setObjectName("card_options")
        card_theme_lang.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        ctl_layout = QHBoxLayout(card_theme_lang)
        ctl_layout.setContentsMargins(18, 14, 18, 14)
        ctl_layout.setSpacing(20)

        # Left: Language Box
        lang_box = QVBoxLayout()
        lang_box.setSpacing(6)
        self.lbl_lang_label = QLabel(tr("settings.language_label"))
        self.lbl_lang_label.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        lang_box.addWidget(self.lbl_lang_label)

        self.combo_lang = QComboBox()
        self.combo_lang.setFont(QFont("Inter", 10))
        self.combo_lang.addItem("Português (ptBR)", "ptBR")
        self.combo_lang.addItem("English (enUS)", "enUS")
        curr_lang = self.lang_mgr.current_language
        self.combo_lang.setCurrentIndex(0 if curr_lang == "ptBR" else 1)
        self.combo_lang.currentIndexChanged.connect(self.on_language_changed)
        lang_box.addWidget(self.combo_lang)
        ctl_layout.addLayout(lang_box, 1)

        # Right: Theme Box
        theme_box = QVBoxLayout()
        theme_box.setSpacing(6)
        self.lbl_theme_label = QLabel(tr("settings.theme_title"))
        self.lbl_theme_label.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        theme_box.addWidget(self.lbl_theme_label)

        self.combo_theme = QComboBox()
        self.combo_theme.setFont(QFont("Inter", 10))
        self.combo_theme.addItem(tr("settings.theme_dark"), "dark")
        self.combo_theme.addItem(tr("settings.theme_light"), "light")
        self.combo_theme.addItem(tr("settings.theme_system"), "system")
        curr_theme = self.settings_mgr.get("theme", "system")
        theme_idx = 0 if curr_theme == "dark" else (1 if curr_theme == "light" else 2)
        self.combo_theme.setCurrentIndex(theme_idx)
        self.combo_theme.currentIndexChanged.connect(self.on_theme_changed)
        theme_box.addWidget(self.combo_theme)
        ctl_layout.addLayout(theme_box, 1)

        layout.addWidget(card_theme_lang)

        # --- Card 2: AI Local Selection & Downloads (Pre-Bundled Vector + SLM) ---
        card_ai = QFrame()
        card_ai.setObjectName("card_options")
        card_ai.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        cai_layout = QVBoxLayout(card_ai)
        cai_layout.setContentsMargins(18, 14, 18, 14)
        cai_layout.setSpacing(10)

        lbl_ai_head = QLabel("🤖 " + tr("settings.ai_title"))
        lbl_ai_head.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        cai_layout.addWidget(lbl_ai_head)

        # 1. Vector Search Status (Pre-Installed)
        vsearch_layout = QHBoxLayout()
        self.lbl_vsearch_status = QLabel()
        self.lbl_vsearch_status.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.lbl_vsearch_status.setWordWrap(True)
        vsearch_layout.addWidget(self.lbl_vsearch_status, 1)

        self.btn_download_vector = QPushButton(tr("settings.ai_btn_download_vector"))
        self.btn_download_vector.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self.btn_download_vector.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download_vector.setStyleSheet("background: #0284c7; color: white; padding: 5px 12px; border-radius: 4px; border: none;")
        self.btn_download_vector.clicked.connect(self.on_download_vector_clicked)
        vsearch_layout.addWidget(self.btn_download_vector)
        cai_layout.addLayout(vsearch_layout)

        # 2. SLM Model Selector Row
        ai_row = QHBoxLayout()
        self.lbl_model_label = QLabel(tr("settings.ai_model_label"))
        self.lbl_model_label.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        ai_row.addWidget(self.lbl_model_label)

        self.combo_ai_model = QComboBox()
        self.combo_ai_model.setFont(QFont("Inter", 10))
        for mid in ["qwen2.5-1.5b", "qwen2.5-0.5b", "qwen2.5-3b"]:
            info = MODEL_CATALOGUE.get(mid)
            if info:
                self.combo_ai_model.addItem(f"{info.name} (~{info.size_mb:.0f} MB)", mid)
        
        pref_slm = self.settings_mgr.get("preferred_slm_model", self.hardware_profile.recommended_model_id)
        idx_ai = self.combo_ai_model.findData(pref_slm)
        if idx_ai >= 0:
            self.combo_ai_model.setCurrentIndex(idx_ai)
        self.combo_ai_model.currentIndexChanged.connect(self.update_ai_status_labels)
        ai_row.addWidget(self.combo_ai_model, 1)
        cai_layout.addLayout(ai_row)

        # 3. SLM Status & Download Row
        slm_status_layout = QHBoxLayout()
        self.lbl_slm_status = QLabel()
        self.lbl_slm_status.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.lbl_slm_status.setWordWrap(True)
        slm_status_layout.addWidget(self.lbl_slm_status, 1)

        self.btn_download_slm = QPushButton(tr("settings.ai_download_btn"))
        self.btn_download_slm.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.btn_download_slm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download_slm.setStyleSheet("background: #2563eb; color: white; padding: 6px 14px; border-radius: 4px; border: none;")
        self.btn_download_slm.clicked.connect(self.on_download_slm_clicked)
        slm_status_layout.addWidget(self.btn_download_slm)
        cai_layout.addLayout(slm_status_layout)

        # Progress bar for active downloads
        self.ai_progress_bar = QProgressBar()
        self.ai_progress_bar.setVisible(False)
        self.ai_progress_bar.setFixedHeight(16)
        cai_layout.addWidget(self.ai_progress_bar)

        layout.addWidget(card_ai)

        # --- Card 3: Rename Pattern Customization ---
        card_rename = QFrame()
        card_rename.setObjectName("card_options")
        card_rename.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        cr_layout = QVBoxLayout(card_rename)
        cr_layout.setContentsMargins(18, 14, 18, 14)
        cr_layout.setSpacing(8)

        self.lbl_rename_head = QLabel(tr("settings.rename_title"))
        self.lbl_rename_head.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        cr_layout.addWidget(self.lbl_rename_head)

        grid_rename = QHBoxLayout()
        grid_rename.setSpacing(10)

        # Separator
        self.combo_sep = QComboBox()
        self.combo_sep.setFont(QFont("Inter", 10))
        for s in ["_", " - ", "-", ".", " "]:
            self.combo_sep.addItem(f"Sep: '{s}'", s)
        self.combo_sep.currentIndexChanged.connect(self.update_rename_preview)
        grid_rename.addWidget(self.combo_sep, 1)

        # Date Format
        self.combo_date_fmt = QComboBox()
        self.combo_date_fmt.setFont(QFont("Inter", 10))
        for df in ["YYYY-MM-DD", "DD-MM-YYYY", "YYYYMMDD", "DD_MM_YYYY"]:
            self.combo_date_fmt.addItem(df, df)
        self.combo_date_fmt.currentIndexChanged.connect(self.update_rename_preview)
        grid_rename.addWidget(self.combo_date_fmt, 1)

        # Casing
        self.combo_casing = QComboBox()
        self.combo_casing.setFont(QFont("Inter", 10))
        self.combo_casing.addItem("Title Case", "title")
        self.combo_casing.addItem("lowercase", "lower")
        self.combo_casing.addItem("UPPERCASE", "upper")
        self.combo_casing.currentIndexChanged.connect(self.update_rename_preview)
        grid_rename.addWidget(self.combo_casing, 1)

        cr_layout.addLayout(grid_rename)

        self.lbl_rename_preview = QLabel()
        self.lbl_rename_preview.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        self.lbl_rename_preview.setObjectName("lbl_after")
        self.lbl_rename_preview.setWordWrap(True)
        cr_layout.addWidget(self.lbl_rename_preview)
        layout.addWidget(card_rename)

        # --- Card 4: Minimum Confidence Threshold ---
        card_conf = QFrame()
        card_conf.setObjectName("card_options")
        card_conf.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        cconf_layout = QHBoxLayout(card_conf)
        cconf_layout.setContentsMargins(18, 14, 18, 14)
        cconf_layout.setSpacing(10)

        self.lbl_conf_head = QLabel(tr("settings.confidence_title"))
        self.lbl_conf_head.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        cconf_layout.addWidget(self.lbl_conf_head)

        self.combo_conf = QComboBox()
        self.combo_conf.setFont(QFont("Inter", 10))
        for val, lbl in [
            (0.50, tr("settings.confidence_50")),
            (0.60, tr("settings.confidence_60")),
            (0.70, tr("settings.confidence_70")),
            (0.80, tr("settings.confidence_80")),
            (0.85, tr("settings.confidence_85")),
            (0.90, tr("settings.confidence_90")),
            (0.95, tr("settings.confidence_95")),
        ]:
            self.combo_conf.addItem(lbl, val)
        self.combo_conf.setCurrentIndex(3)  # Default 0.80
        cconf_layout.addWidget(self.combo_conf, 1)
        layout.addWidget(card_conf)

        self.update_rename_preview()
        self.update_ai_status_labels()

        # Footer Buttons: [← Voltar] + [Salvar & Ir para o Menu Principal]
        footer_layout = QHBoxLayout()
        self.btn_back_welcome = QPushButton(tr("action.back"))
        self.btn_back_welcome.setFont(QFont("Inter", 10))
        self.btn_back_welcome.setStyleSheet("padding: 8px 16px; border-radius: 4px;")
        self.btn_back_welcome.clicked.connect(lambda: self.wizard_stack.setCurrentIndex(0))
        footer_layout.addWidget(self.btn_back_welcome)

        footer_layout.addStretch()

        self.btn_finish_setup = QPushButton(tr("onboarding.btn_finish"))
        self.btn_finish_setup.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.btn_finish_setup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_finish_setup.setStyleSheet(
            "QPushButton { background: #22c55e; color: #ffffff; padding: 10px 28px; border-radius: 6px; font-weight: bold; border: none; }"
            "QPushButton:hover { background: #16a34a; }"
        )
        self.btn_finish_setup.clicked.connect(self.save_and_finish_wizard)
        footer_layout.addWidget(self.btn_finish_setup)

        layout.addLayout(footer_layout)
        scroll.setWidget(panel)
        return scroll

    def go_to_settings_step(self):
        self.wizard_stack.setCurrentIndex(1)
        self.update_ai_status_labels()

    def on_language_changed(self):
        selected_lang = self.combo_lang.currentData() or "enUS"
        self.lang_mgr.set_language(selected_lang)
        self.settings_mgr.set("language", selected_lang)
        self.retranslate_wizard()

    def on_theme_changed(self):
        selected_theme = self.combo_theme.currentData() or "system"
        self.settings_mgr.set("theme", selected_theme)
        app = QApplication.instance()
        if app:
            apply_app_theme(app)

    def update_rename_preview(self):
        cfg = {
            "rename_separator": self.combo_sep.currentData() or "_",
            "rename_date_position": "prefix",
            "rename_date_format": self.combo_date_fmt.currentData() or "YYYY-MM-DD",
            "rename_casing": self.combo_casing.currentData() or "title",
        }
        ex_name = generate_standard_filename("2024-05-10", "Enel", "Conta Luz", ".pdf", "fatura_luz", cfg)
        self.lbl_rename_preview.setText(f"Preview:  {ex_name}")

    def update_ai_status_labels(self):
        # 1. Vector Search status
        if self.model_mgr.is_vector_search_ready():
            self.lbl_vsearch_status.setText(f"<span style='color: #22c55e;'>{tr('settings.ai_vector_search_ready')}</span>")
            self.btn_download_vector.setVisible(False)
        else:
            self.lbl_vsearch_status.setText(f"<span style='color: #f59e0b;'>{tr('settings.ai_vector_search_missing')}</span>")
            self.btn_download_vector.setVisible(True)

        # 2. SLM Model status
        chosen_slm = self.combo_ai_model.currentData() or "qwen2.5-1.5b"
        if self.model_mgr.is_model_downloaded(chosen_slm):
            self.lbl_slm_status.setText(f"<span style='color: #22c55e;'>{tr('settings.ai_ready')}</span>")
            self.btn_download_slm.setVisible(False)
        else:
            self.lbl_slm_status.setText(f"<span style='color: #94a3b8;'>{tr('settings.ai_not_downloaded')}</span>")
            self.btn_download_slm.setVisible(True)
            self.btn_download_slm.setText(tr("settings.ai_download_btn"))

    def on_download_vector_clicked(self):
        self.btn_download_vector.setEnabled(False)
        self.ai_progress_bar.setVisible(True)
        self.ai_progress_bar.setValue(0)

        # Download ONNX model, then tokenizer
        self.active_worker = AIWorker(action="download_model", model_id_to_download="embedding-multilingual-minilm", parent=self)
        self.active_worker.download_progress_signal.connect(lambda mid, d, t, p: self.ai_progress_bar.setValue(int(p)))

        def on_emb_done(_):
            self.active_worker = AIWorker(action="download_model", model_id_to_download="embedding-tokenizer", parent=self)
            self.active_worker.download_progress_signal.connect(lambda mid, d, t, p: self.ai_progress_bar.setValue(int(p)))
            def on_tok_done(__):
                self.ai_progress_bar.setVisible(False)
                self.btn_download_vector.setEnabled(True)
                self.update_ai_status_labels()
                QMessageBox.information(self, "Indexo", "Motor de busca vetorial baixado e ativado com sucesso!")
            self.active_worker.finished_signal.connect(on_tok_done)
            self.active_worker.start()

        def on_err(err):
            self.ai_progress_bar.setVisible(False)
            self.btn_download_vector.setEnabled(True)
            self.update_ai_status_labels()
            QMessageBox.warning(self, "Indexo", f"Erro no download: {err}")

        self.active_worker.finished_signal.connect(on_emb_done)
        self.active_worker.error_signal.connect(on_err)
        self.active_worker.start()

    def on_download_slm_clicked(self):
        chosen_slm = self.combo_ai_model.currentData() or "qwen2.5-1.5b"
        self.btn_download_slm.setEnabled(False)
        self.ai_progress_bar.setVisible(True)
        self.ai_progress_bar.setValue(0)

        self.active_worker = AIWorker(action="download_model", model_id_to_download=chosen_slm, parent=self)
        self.active_worker.download_progress_signal.connect(lambda mid, d, t, p: self.ai_progress_bar.setValue(int(p)))

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

        self.active_worker.finished_signal.connect(on_slm_done)
        self.active_worker.error_signal.connect(on_slm_err)
        self.active_worker.start()

    def retranslate_wizard(self):
        self.lbl_welcome_slogan.setText(tr("app.slogan"))
        self.lbl_feat1.setText(tr("onboarding.feature_1"))
        self.lbl_feat2.setText(tr("onboarding.feature_2"))
        self.lbl_feat3.setText(tr("onboarding.feature_3"))
        if hasattr(self, "btn_auto_start"):
            self.btn_auto_start.setText(tr("onboarding.btn_auto_start"))
        if hasattr(self, "btn_customize"):
            self.btn_customize.setText(tr("onboarding.btn_customize"))
        if hasattr(self, "lbl_diag_head"):
            self.lbl_diag_head.setText("💻 " + tr("onboarding.diag_title"))
        self.lbl_set_title.setText(tr("onboarding.settings_title"))
        self.lbl_set_desc.setText(tr("onboarding.settings_desc"))
        self.lbl_lang_label.setText(tr("settings.language_label"))
        self.lbl_theme_label.setText(tr("settings.theme_title"))
        self.lbl_model_label.setText(tr("settings.ai_model_label"))
        self.lbl_rename_head.setText(tr("settings.rename_title"))
        self.lbl_conf_head.setText(tr("settings.confidence_title"))
        self.btn_back_welcome.setText(tr("action.back"))
        self.btn_finish_setup.setText(tr("onboarding.btn_finish"))
        self.update_ai_status_labels()

    def save_and_finish_wizard(self):
        # Save configured options to settings
        self.settings_mgr.set("language", self.combo_lang.currentData() or "enUS")
        self.settings_mgr.set("theme", self.combo_theme.currentData() or "system")
        self.settings_mgr.set("preferred_slm_model", self.combo_ai_model.currentData() or "qwen2.5-1.5b")
        self.settings_mgr.set("rename_separator", self.combo_sep.currentData() or "_")
        self.settings_mgr.set("rename_date_format", self.combo_date_fmt.currentData() or "YYYY-MM-DD")
        self.settings_mgr.set("rename_casing", self.combo_casing.currentData() or "title")
        self.settings_mgr.set("confidence_threshold", float(self.combo_conf.currentData() or 0.80))
        self.settings_mgr.set("first_run", False)
        self.accept()
