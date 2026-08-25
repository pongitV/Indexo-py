import sys
import winreg
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QApplication
from app.config.settings_manager import get_app_dir, SettingsManager

def get_app_icon_path() -> Path:
    """Resolves the application icon path across dev and PyInstaller environments."""
    # 1. Next to executable (portable folder)
    p1 = get_app_dir() / "resources" / "icon.png"
    if p1.exists():
        return p1
    # 2. PyInstaller bundle temp dir (_MEIPASS)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        p2 = Path(sys._MEIPASS) / "resources" / "icon.png"
        if p2.exists():
            return p2
    # 3. Inside app/resources
    p3 = Path(__file__).resolve().parent.parent / "resources" / "icon.png"
    if p3.exists():
        return p3
    # 4. Project root resources
    p4 = Path(__file__).resolve().parent.parent.parent.parent / "resources" / "icon.png"
    if p4.exists():
        return p4
    return p1

def is_system_dark_mode() -> bool:
    """Checks Windows Registry to detect system light/dark theme preference."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return val == 0
    except Exception:
        return False

def get_effective_theme(theme_config: Optional[str] = None) -> str:
    """Returns 'dark' or 'light' based on config and system setting."""
    if not theme_config or theme_config == "system":
        return "dark" if is_system_dark_mode() else "light"
    return "dark" if theme_config == "dark" else "light"

def get_theme_stylesheet(theme_config: Optional[str] = None, font_size: int = 15) -> str:
    """Loads and formats the theme QSS stylesheet."""
    effective_theme = get_effective_theme(theme_config)
    qss_filename = "dark_theme.qss" if effective_theme == "dark" else "light_theme.qss"

    # Search in multiple potential locations
    qss_candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        qss_candidates.append(Path(sys._MEIPASS) / "app" / "resources" / "styles" / qss_filename)
        qss_candidates.append(Path(sys._MEIPASS) / "resources" / "styles" / qss_filename)
    
    qss_candidates.append(Path(__file__).resolve().parent.parent / "resources" / "styles" / qss_filename)
    qss_candidates.append(get_app_dir() / "resources" / "styles" / qss_filename)

    content = ""
    for candidate in qss_candidates:
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    content = f.read()
                break
            except Exception:
                pass

    if content:
        # Dynamic Universal Font Scaling
        content = content.replace("15px", f"{font_size}px")
        content = content.replace("14px", f"{max(12, font_size - 1)}px")
        content = content.replace("13px", f"{max(11, font_size - 2)}px")

    return content

def apply_app_theme(app: Optional[QApplication] = None, theme_config: Optional[str] = None, font_size: Optional[int] = None):
    """Applies theme stylesheet to the entire QApplication."""
    target_app = app or QApplication.instance()
    if not target_app:
        return

    sm = SettingsManager()
    if theme_config is None:
        theme_config = sm.get("theme", "system")
    if font_size is None:
        font_size = int(sm.get("font_size", 15))

    stylesheet = get_theme_stylesheet(theme_config, font_size)
    if stylesheet:
        target_app.setStyleSheet(stylesheet)
