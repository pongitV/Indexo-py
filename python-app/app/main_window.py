import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFileDialog, QMessageBox,
    QProgressBar, QSplitter, QFrame, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QScrollArea,
    QComboBox, QAbstractItemView, QTabWidget, QMenu
)
from loguru import logger
import indexo_core

from app.config.settings_manager import (
    SettingsManager, get_app_dir, get_db_path, get_user_rules_path
)
from app.i18n.language_manager import tr, LanguageManager
from app.workers.index_worker import IndexWorker
from app.widgets.tree_view import VirtualTreeView
from app.widgets.preview_panel import PreviewPanel
from app.widgets.organization_view import OrganizationSplitView
from app.widgets.duplicate_view import DuplicateView
from app.widgets.trash_view import TrashView
from app.widgets.pending_list import PendingListView
from app.widgets.palette import SearchPaletteDialog
from app.widgets.lite_mode import LiteModeView
from app.widgets.folder_review import FolderReviewView
from app.widgets.tag_manager_view import TagManagerView
from app.widgets.settings_view import SettingsView
from app.widgets.stats_view import StatsView
from app.widgets.ai_live_inspector_view import AILiveInspectorView
from app.widgets.shortcuts_dialog import ShortcutsGuideDialog
from app.widgets.guide_view import GuideView
from app.widgets.smooth_scroll import SmoothScrollArea
from app.utils.file_ops import move_file_safe, move_folder_safe, restore_session, get_restore_path
from app.utils.theme_manager import get_app_icon_path, apply_app_theme, is_system_dark_mode
from app.classification.entity_regex import generate_standard_filename

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_mgr = SettingsManager()
        self.current_folder: Optional[Path] = None
        self.last_results: List[Dict[str, Any]] = []
        self.last_cohesive_bundles: List[Dict[str, Any]] = []
        self.last_duplicates_count: int = 0
        self.last_duplicates_bytes: int = 0
        self.worker: Optional[IndexWorker] = None
        self.allowed_folders: set = set()
        self.previous_root_index: int = 0
        
        self.init_ui()
        self.setup_shortcuts()
        self.apply_theme()
        self.check_restore_availability()
        self.update_power_user_ui_visibility()

    def init_ui(self):
        self.setWindowTitle(tr("app.title"))
        self.resize(1280, 840)
        self.setMinimumSize(980, 680)

        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(14, 12, 14, 12)
        self.main_layout.setSpacing(8)

        # 1. Top Bar (Clean, Solid Folder Action, No Redundant Buttons)
        top_bar = QHBoxLayout()
        # 1. Main Root View Stack:
        # [0] Home Menu (Icon, Title, Slogan, Solid Select Folder Button, Top-Right Settings)
        # [1] Workspace (Clean Dropdown View Switcher, Large Antes x Depois Tree, etc.)
        # [2] Dedicated Full-Screen Settings View
        # [3] Dedicated Full-Screen Tag Manager View
        # [4] Dedicated Full-Screen Guide View
        self.root_stack = QStackedWidget()

        # View 0: Clean Home Menu Screen
        self.menu_widget = self.create_menu_view()
        self.root_stack.addWidget(self.menu_widget)

        # View 1: Main Workspace / Usage Screen
        self.workspace_widget = self.create_workspace_view()
        self.root_stack.addWidget(self.workspace_widget)

        # View 2: Dedicated Clean Settings Screen
        self.settings_widget = SettingsView()
        self.settings_widget.back_requested.connect(self.go_back_from_settings_or_tags)
        self.settings_widget.theme_changed.connect(self.change_theme)
        self.settings_widget.font_size_changed.connect(self.change_font_size)
        self.settings_widget.language_changed.connect(self.change_language)
        self.settings_widget.confidence_threshold_changed.connect(self.on_confidence_threshold_changed)
        self.settings_widget.tag_manager_requested.connect(self.toggle_tag_manager_view)
        self.settings_widget.shortcuts_requested.connect(self.show_shortcuts_guide)
        self.root_stack.addWidget(self.settings_widget)

        # View 3: Dedicated Full-Screen Tag Manager Screen
        self.tag_manager_widget = TagManagerView()
        self.tag_manager_widget.back_requested.connect(self.go_back_from_settings_or_tags)
        self.root_stack.addWidget(self.tag_manager_widget)

        # View 4: Dedicated Full-Screen Guide Screen
        self.guide_widget = GuideView()
        self.guide_widget.back_requested.connect(self.go_back_from_settings_or_tags)
        self.root_stack.addWidget(self.guide_widget)

        # Compatibility aliases
        self.welcome_widget = self.menu_widget
        self.btn_select_dir = getattr(self, 'btn_workspace_select_dir', None)
        self.btn_settings_icon = getattr(self, 'btn_menu_settings', None)
        self.btn_guide = getattr(self, 'btn_menu_guide', None)
        self.rename_card = self.settings_widget.rename_card
        self.prof_card = self.settings_widget.prof_card
        self.main_layout.addWidget(self.root_stack, 1)

        # 2. Bottom Bar
        self.bottom_bar = QHBoxLayout()
        self.bottom_bar.setContentsMargins(4, 4, 4, 4)
        self.bottom_bar.setSpacing(10)

        self.lbl_status = QLabel(tr("status.ready"), main_widget)
        self.lbl_status.setFont(QFont("Inter", 10))
        self.bottom_bar.addWidget(self.lbl_status, 1)

        self.progress_bar = QProgressBar(main_widget)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setMaximumWidth(280)
        self.bottom_bar.addWidget(self.progress_bar)

        self.btn_cancel_scan = QPushButton(tr("action.cancel"), main_widget)
        self.btn_cancel_scan.setVisible(False)
        self.btn_cancel_scan.setFont(QFont("Inter", 10))
        self.btn_cancel_scan.clicked.connect(self.cancel_scan)
        self.bottom_bar.addWidget(self.btn_cancel_scan)

        self.main_layout.addLayout(self.bottom_bar)

        # Start on Home Menu
        self.root_stack.setCurrentIndex(0)

    def create_menu_view(self) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 20, 24, 24)
        panel_layout.setSpacing(12)

        # Top Bar in Home Menu: Configurações in top-right corner
        top_bar = QHBoxLayout()
        self.lbl_menu_logo = QLabel("INDEXO")
        self.lbl_menu_logo.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        self.lbl_menu_logo.setObjectName("lbl_before")
        top_bar.addWidget(self.lbl_menu_logo)

        top_bar.addStretch()

        self.btn_menu_tags = QPushButton(f"🏷️ {tr('nav.tags')}")
        self.btn_menu_tags.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.btn_menu_tags.setToolTip("Gerenciador de Tags & Categorias (Ctrl+M)")
        self.btn_menu_tags.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu_tags.setStyleSheet("padding: 6px 14px; border-radius: 5px;")
        self.btn_menu_tags.clicked.connect(self.toggle_tag_manager_view)
        top_bar.addWidget(self.btn_menu_tags)

        self.btn_menu_guide = QPushButton("📖 Guia")
        self.btn_menu_guide.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.btn_menu_guide.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu_guide.setStyleSheet("padding: 6px 14px; border-radius: 5px;")
        self.btn_menu_guide.clicked.connect(self.toggle_guide_view)
        top_bar.addWidget(self.btn_menu_guide)

        self.btn_menu_settings = QPushButton(f"⚙️ {tr('nav.settings')}")
        self.btn_menu_settings.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.btn_menu_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu_settings.setStyleSheet("padding: 6px 14px; border-radius: 5px;")
        self.btn_menu_settings.clicked.connect(self.toggle_settings_view)
        top_bar.addWidget(self.btn_menu_settings)

        panel_layout.addLayout(top_bar)

        # Center Container
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setSpacing(14)

        icon_path = get_app_icon_path()
        if icon_path.exists():
            lbl_icon = QLabel()
            pix = QPixmap(str(icon_path))
            if not pix.isNull():
                lbl_icon.setPixmap(pix.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                center_layout.addWidget(lbl_icon)

        self.lbl_menu_title = QLabel("INDEXO")
        self.lbl_menu_title.setObjectName("lbl_before")
        self.lbl_menu_title.setFont(QFont("Inter", 30, QFont.Weight.Bold))
        self.lbl_menu_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.lbl_menu_title)

        self.lbl_menu_phrase = QLabel("Organização Semântica Inteligente de Arquivos")
        self.lbl_menu_phrase.setFont(QFont("Inter", 12, QFont.Weight.Medium))
        self.lbl_menu_phrase.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_menu_phrase.setObjectName("lbl_subtext")
        center_layout.addWidget(self.lbl_menu_phrase)

        center_layout.addSpacing(14)

        # Solid Primary Button for Selecting Folder
        self.btn_welcome_select = QPushButton(f"📁 {tr('action.select_folder')} (Ctrl+O)")
        self.btn_welcome_select.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        self.btn_welcome_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_welcome_select.setStyleSheet(
            "QPushButton { background: #2563eb; color: white; padding: 12px 36px; border-radius: 8px; font-weight: bold; border: none; font-size: 13px; min-width: 280px; }"
            "QPushButton:hover { background: #1d4ed8; }"
        )
        self.btn_welcome_select.clicked.connect(self.select_folder_dialog)
        center_layout.addWidget(self.btn_welcome_select, 0, Qt.AlignmentFlag.AlignCenter)

        panel_layout.addStretch(1)
        panel_layout.addWidget(center_container, 0, Qt.AlignmentFlag.AlignCenter)
        panel_layout.addStretch(2)

        return panel

    def create_workspace_view(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Top Bar of Workspace
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.btn_back_to_menu = QPushButton("← Menu")
        self.btn_back_to_menu.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.btn_back_to_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back_to_menu.setStyleSheet("padding: 6px 12px; border-radius: 5px;")
        self.btn_back_to_menu.clicked.connect(lambda: self.root_stack.setCurrentIndex(0))
        top_bar.addWidget(self.btn_back_to_menu)

        self.btn_workspace_select_dir = QPushButton(f"📁 {tr('action.select_folder')}")
        self.btn_workspace_select_dir.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.btn_workspace_select_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_workspace_select_dir.setStyleSheet(
            "QPushButton { background: #2563eb; color: white; padding: 6px 14px; border-radius: 5px; font-weight: bold; border: none; }"
            "QPushButton:hover { background: #1d4ed8; }"
        )
        self.btn_workspace_select_dir.clicked.connect(self.select_folder_dialog)
        top_bar.addWidget(self.btn_workspace_select_dir)

        self.lbl_current_folder = QLabel(tr("view.select_folder_hint"))
        self.lbl_current_folder.setObjectName("lbl_subtext")
        self.lbl_current_folder.setFont(QFont("Consolas", 10))
        top_bar.addWidget(self.lbl_current_folder)

        top_bar.addStretch()

        # View Mode Dropdown Switcher
        self.combo_view_switcher = QComboBox()
        self.combo_view_switcher.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.combo_view_switcher.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo_view_switcher.setStyleSheet("QComboBox { padding: 5px 14px; border-radius: 5px; min-width: 250px; font-weight: bold; }")
        self.combo_view_switcher.addItem("📁 Organização (Antes x Depois)", 0)
        self.combo_view_switcher.addItem("❓ Arquivos Pendentes", 1)
        self.combo_view_switcher.addItem("👯 Arquivos Duplicados", 2)
        self.combo_view_switcher.addItem("📊 Estatísticas & Métricas", 3)
        self.combo_view_switcher.addItem("🗑️ Lixeira de Segurança", 4)
        self.combo_view_switcher.addItem("🧠 Inspecionar Raciocínio IA", 5)
        self.combo_view_switcher.currentIndexChanged.connect(self.on_view_switcher_changed)
        top_bar.addWidget(self.combo_view_switcher)

        top_bar.addStretch()

        self.btn_search_palette = QPushButton(f"🔍 {tr('search.placeholder')}")
        self.btn_search_palette.setFont(QFont("Inter", 10))
        self.btn_search_palette.setStyleSheet("padding: 6px 12px; border-radius: 5px;")
        self.btn_search_palette.clicked.connect(self.open_search_palette)
        top_bar.addWidget(self.btn_search_palette)

        self.btn_workspace_tags = QPushButton(f"🏷️ {tr('nav.tags')}")
        self.btn_workspace_tags.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.btn_workspace_tags.setToolTip("Gerenciador de Tags & Categorias (Ctrl+M)")
        self.btn_workspace_tags.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_workspace_tags.setStyleSheet("padding: 6px 12px; border-radius: 5px;")
        self.btn_workspace_tags.clicked.connect(self.toggle_tag_manager_view)
        top_bar.addWidget(self.btn_workspace_tags)

        self.btn_workspace_guide = QPushButton("📖 Guia")
        self.btn_workspace_guide.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.btn_workspace_guide.setToolTip("Guia de uso e conceitos (F1)")
        self.btn_workspace_guide.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_workspace_guide.setStyleSheet("padding: 6px 12px; border-radius: 5px;")
        self.btn_workspace_guide.clicked.connect(self.toggle_guide_view)
        top_bar.addWidget(self.btn_workspace_guide)

        self.btn_workspace_settings = QPushButton(f"⚙️ {tr('nav.settings')}")
        self.btn_workspace_settings.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self.btn_workspace_settings.setToolTip(f"{tr('nav.settings')} (Ctrl+,)")
        self.btn_workspace_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_workspace_settings.setStyleSheet("padding: 6px 12px; border-radius: 5px;")
        self.btn_workspace_settings.clicked.connect(self.toggle_settings_view)
        top_bar.addWidget(self.btn_workspace_settings)

        layout.addLayout(top_bar)

        # Main horizontal splitter with clean views on the left and collapsible preview on the right
        workspace_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.main_tabs = QTabWidget()
        self.main_tabs.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        self.main_tabs.setDocumentMode(True)
        if self.main_tabs.tabBar():
            self.main_tabs.tabBar().setVisible(False)  # Clean! Replaced by dropdown

        # Tab 0: Primary Central Organization Split View (Large & Spacious)
        self.organization_view = OrganizationSplitView()
        self.organization_view.file_selected.connect(self.on_file_selected_for_preview)
        self.organization_view.folder_perm_toggled.connect(self.on_folder_perm_toggled)
        self.organization_view.tag_rename_requested.connect(self.on_tag_renamed)
        self.organization_view.file_reclassified.connect(self.on_file_reclassified)
        self.organization_view.file_marked_trash.connect(self.on_file_marked_trash)
        self.organization_view.bundle_action_changed.connect(self.on_bundle_action_changed)
        self.organization_view.refresh_requested.connect(self.start_scan)
        self.organization_view.execute_requested.connect(self.execute_organization)
        self.organization_view.restore_requested.connect(self.restore_last_session_action)

        # Tab 1: Pending Queue
        self.pending_view = PendingListView()
        self.pending_view.file_selected.connect(self.on_file_selected_for_preview)
        self.pending_view.file_reclassified.connect(self.on_file_reclassified)
        self.pending_view.file_marked_trash.connect(self.on_file_marked_trash)
        self.pending_view.promotion_suggested.connect(self.on_promotion_suggested)
        self.pending_view.refresh_requested.connect(self.start_scan)

        # Tab 2: Duplicates
        self.duplicate_view = DuplicateView()
        self.duplicate_view.file_marked.connect(self.on_trash_or_duplicate_changed)

        # Tab 3: Stats & Visual Charts View
        self.stats_view = StatsView()

        # Tab 4: Safety Trash & History
        self.trash_view = TrashView()
        self.trash_view.trash_updated.connect(self.on_trash_or_duplicate_changed)

        # Tab 5: Live AI Thought & Reasoning Inspector Tab
        self.ai_live_view = AILiveInspectorView()

        # Backward compatibility tabs
        self.tree_view = VirtualTreeView()
        self.tree_view.file_selected.connect(self.on_file_selected_for_preview)
        self.tree_view.tag_rename_requested.connect(self.on_tag_renamed)
        self.tree_view.file_reclassified.connect(self.on_file_reclassified)
        self.tree_view.file_marked_trash.connect(self.on_file_marked_trash)
        self.tree_view.refresh_requested.connect(self.start_scan)
        self.tree_view.tag_manager_requested.connect(self.toggle_tag_manager_view)

        self.lite_mode_view = LiteModeView()
        self.folder_review_view = FolderReviewView()

        self.repopulate_tabs()
        self.main_tabs.currentChanged.connect(self.on_tab_changed)

        workspace_splitter.addWidget(self.main_tabs)

        # Right/Collapsible Preview Panel
        self.preview_panel = PreviewPanel()
        self.preview_panel.setMaximumWidth(420)
        workspace_splitter.addWidget(self.preview_panel)

        workspace_splitter.setStretchFactor(0, 8)
        workspace_splitter.setStretchFactor(1, 2)

        layout.addWidget(workspace_splitter, 1)
        return container

    def on_view_switcher_changed(self, index: int):
        if hasattr(self, 'main_tabs'):
            self.main_tabs.setCurrentIndex(index)

    def toggle_guide_view(self):
        if self.root_stack.currentIndex() == 4:
            self.go_back_from_settings_or_tags()
        else:
            if self.root_stack.currentIndex() not in [2, 3, 4]:
                self.previous_root_index = self.root_stack.currentIndex()
            self.root_stack.setCurrentIndex(4)

    def toggle_settings_view(self):
        if self.root_stack.currentIndex() == 2:
            self.go_back_from_settings_or_tags()
        else:
            if self.root_stack.currentIndex() not in [2, 3, 4]:
                self.previous_root_index = self.root_stack.currentIndex()
            self.root_stack.setCurrentIndex(2)
            if hasattr(self, 'settings_scroll') and self.settings_scroll.verticalScrollBar():
                self.settings_scroll.verticalScrollBar().setValue(0)

    def toggle_tag_manager_view(self):
        if self.root_stack.currentIndex() == 3:
            self.go_back_from_settings_or_tags()
        else:
            if self.root_stack.currentIndex() not in [2, 3, 4]:
                self.previous_root_index = self.root_stack.currentIndex()
            self.tag_manager_widget.load_tags()
            self.root_stack.setCurrentIndex(3)

    def go_back_from_settings_or_tags(self):
        self.root_stack.setCurrentIndex(self.previous_root_index)

    def handle_escape_key(self):
        if self.root_stack.currentIndex() in [2, 3, 4]:
            self.go_back_from_settings_or_tags()
        elif self.preview_panel.isVisible():
            self.preview_panel.close_preview()

    def repopulate_tabs(self):
        curr_widget = self.main_tabs.currentWidget() if hasattr(self, 'main_tabs') else None
        self.main_tabs.blockSignals(True)
        self.main_tabs.clear()

        # 1. Primary Central Organization View
        self.main_tabs.addTab(self.organization_view, "Organização")

        # 2. Pending / Ambiguous Files Queue
        self.main_tabs.addTab(self.pending_view, "Pendentes")

        # 3. Duplicates Detector
        self.main_tabs.addTab(self.duplicate_view, "Duplicados")

        # 4. Folder Analysis & Stats View
        self.main_tabs.addTab(self.stats_view, "Estatísticas")

        # 5. Safety Trash & Session History
        self.main_tabs.addTab(self.trash_view, "Lixeira")

        # 6. Live AI Thought & Reasoning Inspector
        self.main_tabs.addTab(self.ai_live_view, "Inspecionar IA")

        self.main_tabs.blockSignals(False)

        if curr_widget is not None:
            idx = self.main_tabs.indexOf(curr_widget)
            if idx >= 0:
                self.main_tabs.setCurrentIndex(idx)
                return
        self.main_tabs.setCurrentIndex(0)

    def on_tab_changed(self, index: int):
        widget = self.main_tabs.widget(index)
        if widget == self.ai_live_view and self.last_results:
            self.ai_live_view.load_items(self.last_results)
        elif widget == self.stats_view and self.last_results:
            self.stats_view.update_stats(self.last_results, getattr(self, 'last_duplicates_count', 0), getattr(self, 'last_duplicates_bytes', 0))
        elif widget == self.duplicate_view and self.last_results:
            root_id = self.last_results[0].get("root_id", 1)
            self.duplicate_view.load_duplicates(root_id)
        elif widget == self.trash_view:
            self.trash_view.load_trash()
        elif widget == self.pending_view and self.last_results:
            self.pending_view.populate_pending(self.last_results)

    def update_power_user_ui_visibility(self):
        if hasattr(self, 'rename_card'):
            self.rename_card.setVisible(True)
        if hasattr(self, 'prof_card'):
            self.prof_card.setVisible(True)
        if hasattr(self, 'tag_shortcut_card'):
            self.tag_shortcut_card.setVisible(True)
        if hasattr(self, 'main_tabs'):
            self.repopulate_tabs()

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self.select_folder_dialog)
        QShortcut(QKeySequence("Ctrl+K"), self, self.open_search_palette)
        QShortcut(QKeySequence("Ctrl+M"), self, self.toggle_tag_manager_view)
        QShortcut(QKeySequence("Ctrl+,"), self, self.toggle_settings_view)
        QShortcut(QKeySequence("F1"), self, self.toggle_guide_view)
        QShortcut(QKeySequence("Escape"), self, self.handle_escape_key)
        QShortcut(QKeySequence("Ctrl+Return"), self, self.execute_organization)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self.execute_organization)

    def navigate_to_tab(self, target_widget: QWidget):
        self.root_stack.setCurrentIndex(1)
        self.main_tabs.setCurrentWidget(target_widget)
        idx = self.main_tabs.indexOf(target_widget)
        if hasattr(self, 'combo_view_switcher') and idx >= 0:
            self.combo_view_switcher.setCurrentIndex(idx)
        if not self.current_folder:
            self.lbl_status.setText(tr("view.select_folder_hint"))

    def on_tags_changed_by_manager(self):
        user_tags = self.settings_mgr.get_user_tags()
        self.tree_view.populate_results(self.last_results, user_tags)
        if self.current_folder:
            self.organization_view.populate_results(self.last_results, self.current_folder, self.allowed_folders, user_tags, self.last_cohesive_bundles)

    def on_confidence_threshold_changed(self, threshold: float):
        user_tags = self.settings_mgr.get_user_tags()
        if self.current_folder:
            self.organization_view.populate_results(
                self.last_results, self.current_folder, self.allowed_folders, user_tags, self.last_cohesive_bundles
            )

    def select_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, tr("action.select_folder"))
        if folder:
            self.set_active_folder(Path(folder))

    def set_active_folder(self, folder: Path):
        self.current_folder = folder
        self.lbl_current_folder.setText(str(folder))
        self.preview_panel.close_preview()
        self.root_stack.setCurrentIndex(1)
        if hasattr(self, 'combo_view_switcher'):
            self.combo_view_switcher.setCurrentIndex(0)
        self.main_tabs.setCurrentIndex(0)
        self.start_scan()

    def start_scan(self):
        if not self.current_folder or not self.current_folder.exists():
            return

        self.preview_panel.close_preview()
        self.last_results.clear()
        self.last_cohesive_bundles.clear()
        self.organization_view.clear()
        self.tree_view.clear()
        self.allowed_folders.clear()

        self.progress_bar.setVisible(True)
        self.btn_cancel_scan.setVisible(True)

        self.worker = IndexWorker(self.current_folder)
        self.worker.progress_changed.connect(self.on_scan_progress)
        self.worker.file_classified.connect(self.on_file_classified)
        self.worker.scan_finished.connect(self.on_scan_finished)
        self.worker.error_occurred.connect(self.on_scan_error)
        self.worker.start()

    def cancel_scan(self):
        if self.worker:
            self.worker.cancel()
            self.lbl_status.setText(tr("status.scan_cancelled"))
            self.progress_bar.setVisible(False)
            self.btn_cancel_scan.setVisible(False)

    def on_scan_progress(self, current: int, total: int, file_name: str):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.lbl_status.setText(tr("status.scanning_file", current=current, total=total, file=file_name))
        else:
            self.lbl_status.setText(f"{file_name}")

    def on_file_classified(self, item: Dict[str, Any]):
        self.last_results.append(item)

    def on_scan_finished(self, summary: Dict[str, Any]):
        self.progress_bar.setVisible(False)
        self.btn_cancel_scan.setVisible(False)

        total = summary["total_files"]
        self.lbl_status.setText(tr("status.ready_processed", count=total, elapsed=summary["elapsed_seconds"]))

        # Calculate duplicates metrics
        dup_groups = summary.get("duplicates_groups", [])
        dup_bytes = sum(sum(it.get("size", 0) for it in g[1:]) for g in dup_groups) if dup_groups else 0
        self.last_duplicates_count = summary.get("duplicates", 0)
        self.last_duplicates_bytes = dup_bytes
        self.last_cohesive_bundles = summary.get("cohesive_bundles", [])

        # Update stats view
        self.stats_view.update_stats(self.last_results, self.last_duplicates_count, self.last_duplicates_bytes)

        user_tags = self.settings_mgr.get_user_tags()
        # Populate central Pre/Post organization view (Antes x Depois) with cohesive bundles
        self.organization_view.populate_results(
            self.last_results, self.current_folder, self.allowed_folders, user_tags, self.last_cohesive_bundles
        )

        # Populate side virtual tree
        self.tree_view.populate_results(self.last_results, user_tags)

        # Populate Live AI Reasoning Inspector
        if hasattr(self, 'ai_live_view') and self.last_results:
            self.ai_live_view.load_items(self.last_results)

        self.check_restore_availability()

    def on_bundle_action_changed(self, folder_rel: str, action: str):
        for b in self.last_cohesive_bundles:
            if b.get("folder_rel") == folder_rel:
                b["action"] = action
                break

    def show_shortcuts_guide(self):
        dlg = ShortcutsGuideDialog(self)
        dlg.exec()

    def on_folder_perm_toggled(self, folder_name: str, is_allowed: bool):
        if is_allowed:
            self.allowed_folders.add(folder_name)
        else:
            self.allowed_folders.discard(folder_name)

    def on_tag_renamed(self, tag_id: str, new_name: str):
        user_tags = self.settings_mgr.get_user_tags()
        self.tree_view.populate_results(self.last_results, user_tags)
        if self.current_folder:
            self.organization_view.populate_results(self.last_results, self.current_folder, self.allowed_folders, user_tags, self.last_cohesive_bundles)

    def on_file_reclassified(self, abs_path: str, new_tag_name: str, new_category: str):
        for it in self.last_results:
            if it.get("abs_path") == abs_path:
                if new_tag_name:
                    it["tag_name"] = new_tag_name
                if new_category:
                    it["category"] = new_category
                    it["caminho_fisico"] = new_category.replace(" ", "_")
                it["status"] = "identificado"
                it["confidence"] = 1.0
                primary_date = it.get("primary_date", "")
                ext = Path(abs_path).suffix.lower()
                rename_cfg = self.settings_mgr.data.get("configs", {})
                it["suggested_filename"] = generate_standard_filename(
                    primary_date, it.get("entity"), it.get("tag_name", ""), ext, Path(abs_path).stem, rename_cfg
                )
                break

        user_tags = self.settings_mgr.get_user_tags()
        if self.current_folder:
            self.organization_view.populate_results(self.last_results, self.current_folder, self.allowed_folders, user_tags, self.last_cohesive_bundles)
        self.tree_view.populate_results(self.last_results, user_tags)
        self.pending_view.populate_pending(self.last_results)
        self.stats_view.update_stats(self.last_results, self.last_duplicates_count, self.last_duplicates_bytes)
        self.lbl_status.setText(tr("dialog.tag_updated_file", name=Path(abs_path).name))

    def on_file_marked_trash(self, abs_path: str):
        db_path = str(get_db_path())
        try:
            db = indexo_core.PyIndexoDatabase.open(db_path)
            for it in self.last_results:
                if it.get("abs_path") == abs_path:
                    it["status"] = "marked_for_deletion"
                    file_id = it.get("file_id")
                    if file_id:
                        db.mark_for_deletion(file_id, True)
                    break
        except Exception as e:
            logger.error("Failed to mark file for deletion: {}", e)

        user_tags = self.settings_mgr.get_user_tags()
        if self.current_folder:
            self.organization_view.populate_results(self.last_results, self.current_folder, self.allowed_folders, user_tags, self.last_cohesive_bundles)
        self.tree_view.populate_results(self.last_results, user_tags)
        self.pending_view.populate_pending(self.last_results)
        self.stats_view.update_stats(self.last_results, self.last_duplicates_count, self.last_duplicates_bytes)
        self.trash_view.load_trash()
        QMessageBox.information(self, tr("dialog.trash_marked_title", default="Lixeira"), tr("dialog.trash_marked_msg", name=Path(abs_path).name))

    def on_file_selected_for_preview(self, abs_path: str):
        self.preview_panel.preview_file(abs_path)

    def execute_organization(self):
        """Organizes files physically into Indexo_Files after user confirmation, preserving cohesive bundles."""
        if not self.last_results or not self.current_folder:
            return

        eligible = [it for it in self.last_results if it.get("status") == "identificado"]
        if not eligible and not self.organization_view.cohesive_bundles:
            QMessageBox.information(self, "Indexo", tr("dialog.no_identified_files", default="Nenhum arquivo identificado para organizar."))
            return

        count = len(eligible)
        bundles_to_move = [b for b in self.organization_view.cohesive_bundles if b.get("action") == "move_parent"]
        bundle_msg = tr("dialog.bundle_notice", count=len(bundles_to_move)) if bundles_to_move else ""
        msg = tr("dialog.confirm_org_disk_msg", count=count, bundle_msg=bundle_msg)
        reply = QMessageBox.question(
            self,
            tr("dialog.confirm_org_disk_title"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        rename_enabled = bool(self.settings_mgr.get("rename_enabled", True))
        dest_root = self.current_folder / "Indexo_Files"

        moved_count = 0
        handled_bundle_folders = set()

        # 1. Move cohesive bundles whose action is "move_parent"
        for bundle in self.organization_view.cohesive_bundles:
            folder_rel = bundle.get("folder_rel", "")
            action = bundle.get("action", "move_parent")
            cat_name = bundle.get("category", "Outros")

            if action == "move_parent":
                src_folder = self.current_folder / folder_rel
                dest_folder = dest_root / cat_name / bundle.get("folder_name", folder_rel)
                if src_folder.exists() and "Indexo_Files" not in src_folder.parts:
                    if move_folder_safe(src_folder, dest_folder, self.current_folder):
                        moved_count += bundle.get("file_count", 1)
                        handled_bundle_folders.add(folder_rel)
            elif action == "keep":
                handled_bundle_folders.add(folder_rel)

        # 2. Move loose or disassembled files with confidence >= 0.65
        for it in self.last_results:
            conf = float(it.get("confidence", 0.0))
            status = it.get("status", "")
            if status == "identificado" and conf >= 0.65:
                bundle_folder = it.get("bundle_folder")
                if bundle_folder and bundle_folder in handled_bundle_folders:
                    continue

                src = Path(it["abs_path"])
                if not src.exists() or "Indexo_Files" in src.parts:
                    continue

                default_general = "Geral" if LanguageManager.get_instance().current_language == "ptBR" else "General"
                caminho_fisico = it.get("caminho_fisico") or it.get("category") or default_general
                dest_dir = dest_root / caminho_fisico
                
                target_name = it.get("suggested_filename") if rename_enabled else src.name
                resolved = indexo_core.py_resolve_collision(str(dest_dir), target_name or src.name)
                dest = Path(resolved)

                if move_file_safe(src, dest, self.current_folder):
                    moved_count += 1

        QMessageBox.information(
            self,
            tr("dialog.org_disk_completed_title"),
            tr("dialog.org_disk_completed_msg", count=moved_count, dest=str(dest_root))
        )
        self.check_restore_availability()
        self.start_scan()

    def check_restore_availability(self):
        if self.current_folder:
            restore_file = get_restore_path(self.current_folder)
            self.organization_view.btn_restore.setVisible(restore_file.exists())

    def restore_last_session_action(self):
        if not self.current_folder:
            return

        count, errors = restore_session(self.current_folder)
        if errors:
            QMessageBox.warning(self, tr("dialog.restore_warning_title"), tr("dialog.restore_warning_msg", count=count, errors="\n".join(errors[:5])))
        else:
            QMessageBox.information(self, tr("dialog.undo_completed_title"), tr("dialog.undo_completed_msg", count=count))

        self.check_restore_availability()
        self.start_scan()

    def on_trash_or_duplicate_changed(self):
        self.trash_view.load_trash()

    def on_promotion_suggested(self, tag_name: str, entity: str):
        msg = tr("dialog.promotion_prompt", tag=tag_name)
        reply = QMessageBox.question(self, tr("dialog.promotion_title"), msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            new_tag = {
                "id": f"user_{tag_name.lower().replace(' ', '_')}",
                "nome": tag_name,
                "categoria": tag_name,
                "subcategoria": tag_name,
                "entidade": entity,
                "caminho_fisico": tag_name.replace(" ", "_"),
                "origem": "user",
                "idioma": LanguageManager.get_instance().current_language,
                "sinonimos": [],
                "palavras_chave": [tag_name.lower(), entity.lower()] if entity else [tag_name.lower()],
                "confianca_base": 1.0,
                "usar_para_automacao": True,
                "version": 1
            }
            self.settings_mgr.add_user_tag(new_tag)
            QMessageBox.information(self, tr("dialog.promotion_title"), tr("dialog.promotion_success", tag=tag_name))

    def on_file_selected_for_preview(self, abs_path: str):
        if not abs_path:
            return
        p = Path(abs_path)
        if not p.exists():
            return

        item_data = None
        for it in self.last_results:
            if it.get("abs_path") == abs_path:
                item_data = it
                break

        self.preview_panel.load_file(abs_path, item_data)

    def on_palette_folder_selected(self, folder_path: str):
        if not folder_path:
            return
        p = Path(folder_path)
        if p.exists() and p.is_dir():
            self.set_active_folder(p)

    def open_search_palette(self):
        dlg = SearchPaletteDialog(self.current_folder, self.last_results, self)
        dlg.folder_selected.connect(self.on_palette_folder_selected)
        dlg.file_selected.connect(self.on_file_selected_for_preview)
        dlg.exec()

    def go_home_menu(self):
        self.root_stack.setCurrentIndex(0)
        self.btn_workspace_select_dir.setVisible(False)
        self.lbl_current_folder.setVisible(False)

    def change_theme(self, theme_name: str):
        self.settings_mgr.set("theme", theme_name)
        self.apply_theme()

    def change_font_size(self, size: int):
        self.settings_mgr.set("font_size", size)
        self.apply_theme()

    def apply_theme(self):
        theme = self.settings_mgr.get("theme", "system")
        font_size = int(self.settings_mgr.get("font_size", 15))
        apply_app_theme(None, theme, font_size)

    def change_language(self, lang: str):
        self.settings_mgr.set("language", lang)
        LanguageManager.get_instance().set_language(lang)

        self.setWindowTitle(tr("app.title"))

        if hasattr(self, 'btn_welcome_select'):
            self.btn_welcome_select.setText(f"📁 {tr('action.select_folder')} (Ctrl+O)")
        if hasattr(self, 'btn_workspace_select_dir'):
            self.btn_workspace_select_dir.setText(f"📁 {tr('action.select_folder')}")
        if hasattr(self, 'btn_menu_tags'):
            self.btn_menu_tags.setText(f"🏷️ {tr('nav.tags')}")
        if hasattr(self, 'btn_workspace_tags'):
            self.btn_workspace_tags.setText(f"🏷️ {tr('nav.tags')}")
        if hasattr(self, 'btn_menu_guide'):
            self.btn_menu_guide.setText(f"📖 {tr('nav.guide')}")
        if hasattr(self, 'btn_workspace_guide'):
            self.btn_workspace_guide.setText(f"📖 {tr('nav.guide')}")
        if hasattr(self, 'btn_menu_settings'):
            self.btn_menu_settings.setText(f"⚙️ {tr('nav.settings')}")
        if hasattr(self, 'btn_workspace_settings'):
            self.btn_workspace_settings.setText(f"⚙️ {tr('nav.settings')}")
        if hasattr(self, 'btn_search_palette'):
            self.btn_search_palette.setText(f"🔍 {tr('search.placeholder')}")
        if hasattr(self, 'btn_back_to_menu'):
            self.btn_back_to_menu.setText(tr("action.back_to_menu", default="← Menu"))
        if hasattr(self, 'lbl_menu_phrase'):
            self.lbl_menu_phrase.setText(tr("app.slogan", default="Organização Semântica Inteligente de Arquivos"))

        if hasattr(self, 'combo_view_switcher'):
            curr_idx = self.combo_view_switcher.currentIndex()
            self.combo_view_switcher.blockSignals(True)
            self.combo_view_switcher.clear()
            self.combo_view_switcher.addItem(tr("view_mode.organization"), 0)
            self.combo_view_switcher.addItem(tr("view_mode.pending"), 1)
            self.combo_view_switcher.addItem(tr("view_mode.duplicates"), 2)
            self.combo_view_switcher.addItem(tr("view_mode.stats"), 3)
            self.combo_view_switcher.addItem(tr("view_mode.trash"), 4)
            self.combo_view_switcher.addItem(tr("view_mode.ai_live"), 5)
            self.combo_view_switcher.setCurrentIndex(curr_idx if curr_idx >= 0 else 0)
            self.combo_view_switcher.blockSignals(False)

        if not self.current_folder and hasattr(self, 'lbl_current_folder'):
            self.lbl_current_folder.setText(tr("view.select_folder_hint"))

        # Propagate retranslation to sub-views
        if hasattr(self, 'settings_widget') and hasattr(self.settings_widget, 'retranslate_ui'):
            self.settings_widget.retranslate_ui()
        if hasattr(self, 'guide_widget') and hasattr(self.guide_widget, 'retranslate_ui'):
            self.guide_widget.retranslate_ui()
        if hasattr(self, 'organization_view') and hasattr(self.organization_view, 'retranslate_ui'):
            self.organization_view.retranslate_ui()
        if hasattr(self, 'tag_manager_widget') and hasattr(self.tag_manager_widget, 'retranslate_ui'):
            self.tag_manager_widget.retranslate_ui()
        if hasattr(self, 'ai_live_view') and hasattr(self.ai_live_view, 'retranslate_ui'):
            self.ai_live_view.retranslate_ui()
        if hasattr(self, 'lite_mode_view') and hasattr(self.lite_mode_view, 'retranslate_ui'):
            self.lite_mode_view.retranslate_ui()
        if hasattr(self, 'folder_review_view') and hasattr(self.folder_review_view, 'retranslate_ui'):
            self.folder_review_view.retranslate_ui()
        if hasattr(self, 'tree_view') and hasattr(self.tree_view, 'retranslate_ui'):
            self.tree_view.retranslate_ui()
        if hasattr(self, 'pending_view') and hasattr(self.pending_view, 'retranslate_ui'):
            self.pending_view.retranslate_ui()
        if hasattr(self, 'duplicate_view') and hasattr(self.duplicate_view, 'retranslate_ui'):
            self.duplicate_view.retranslate_ui()
        if hasattr(self, 'stats_view') and hasattr(self.stats_view, 'retranslate_ui'):
            self.stats_view.retranslate_ui()
        if hasattr(self, 'trash_view') and hasattr(self.trash_view, 'retranslate_ui'):
            self.trash_view.retranslate_ui()

        self.repopulate_tabs()
        
        self.btn_cancel_scan.setText(tr("action.cancel"))
        self.lbl_status.setText(tr("status.ready"))
        
        if self.current_folder:
            self.start_scan()
        self.lbl_status.setText(tr("dialog.language_updated_msg"))

    def on_scan_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.btn_cancel_scan.setVisible(False)
        QMessageBox.critical(self, "Scan Error", f"An error occurred during indexing:\n{err_msg}")

    def closeEvent(self, event):
        """Cleanly shutdown threads, background workers, and flush database connections."""
        try:
            if hasattr(self, 'index_worker') and self.index_worker and self.index_worker.isRunning():
                self.index_worker.cancel()
                self.index_worker.wait(300)
            from PySide6.QtCore import QThreadPool
            QThreadPool.globalInstance().waitForDone(300)
        except Exception as e:
            logger.debug("Error during shutdown cleanup: {}", e)
        event.accept()
