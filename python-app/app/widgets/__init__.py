"""
UI Widgets and Presentation Components for Indexo.
"""

from app.widgets.organization_view import OrganizationSplitView
from app.widgets.pending_list import PendingListView
from app.widgets.settings_view import SettingsView
from app.widgets.palette import SearchPaletteDialog
from app.widgets.stats_view import StatsView
from app.widgets.tag_manager_view import TagManagerView
from app.widgets.trash_view import TrashView
from app.widgets.folder_review import FolderReviewView
from app.widgets.shortcuts_dialog import ShortcutsGuideDialog
from app.widgets.preview_panel import PreviewPanel
from app.widgets.duplicate_view import DuplicateView
from app.widgets.tree_view import VirtualTreeView
from app.widgets.lite_mode import LiteModeView
from app.widgets.guide_view import GuideView

__all__ = [
    "OrganizationSplitView",
    "PendingListView",
    "SettingsView",
    "GuideView",
    "SearchPaletteDialog",
    "StatsView",
    "TagManagerView",
    "TrashView",
    "FolderReviewView",
    "ShortcutsGuideDialog",
    "PreviewPanel",
    "DuplicateView",
    "VirtualTreeView",
    "LiteModeView",
]
