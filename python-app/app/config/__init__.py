"""
Configuration and Settings Management Module.
"""

from app.config.settings_manager import (
    SettingsManager,
    get_app_dir,
    get_db_path,
    get_user_rules_path,
)

__all__ = [
    "SettingsManager",
    "get_app_dir",
    "get_db_path",
    "get_user_rules_path",
]
