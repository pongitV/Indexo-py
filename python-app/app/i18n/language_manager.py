import json
import locale
import os
import sys
from pathlib import Path
from typing import Dict, Any

from app.config.settings_manager import get_app_dir

class LanguageManager:
    _instance = None

    def __init__(self):
        self.current_language = "enUS"
        self.translations: Dict[str, str] = {}
        self.fallback_translations: Dict[str, str] = {}
        self.load_dictionaries()

    @classmethod
    def get_instance(cls) -> "LanguageManager":
        if cls._instance is None:
            cls._instance = LanguageManager()
        return cls._instance

    def detect_system_language(self) -> str:
        try:
            loc = locale.getlocale()[0] or os.environ.get("LANG", "") or ""
            loc_lower = str(loc).lower()
            if any(p in loc_lower for p in ["portuguese", "pt", "brazil", "br", "1252", "utf-8", "cp1252"]):
                return "ptBR"
            if loc_lower.startswith("en"):
                return "enUS"
        except Exception:
            pass
        return "enUS"



    def get_i18n_dir(self) -> Path:
        # 1. Custom resources/i18n next to executable
        d = get_app_dir() / "resources" / "i18n"
        if d.exists():
            return d
        # 2. Bundled resources inside PyInstaller package (_MEIPASS)
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            d_bundled = Path(sys._MEIPASS) / "resources" / "i18n"
            if d_bundled.exists():
                return d_bundled
        # 3. Check inside package / dev root
        d2 = Path(__file__).resolve().parent.parent.parent.parent / "resources" / "i18n"
        if d2.exists():
            return d2
        return d

    def load_dictionaries(self):
        i18n_dir = self.get_i18n_dir()
        en_path = i18n_dir / "enUS.json"
        if en_path.exists():
            try:
                with open(en_path, "r", encoding="utf-8") as f:
                    self.fallback_translations = json.load(f)
            except Exception:
                self.fallback_translations = {}

        # Set default based on settings or system
        from app.config.settings_manager import SettingsManager
        sm = SettingsManager()
        configured_lang = sm.get("language", "")
        if not configured_lang:
            configured_lang = self.detect_system_language()
        
        self.set_language(configured_lang)

    def set_language(self, lang_code: str):
        if lang_code not in ["ptBR", "enUS"]:
            lang_code = "enUS"
        self.current_language = lang_code

        i18n_dir = self.get_i18n_dir()
        lang_path = i18n_dir / f"{lang_code}.json"
        if lang_path.exists():
            try:
                with open(lang_path, "r", encoding="utf-8") as f:
                    self.translations = json.load(f)
            except Exception:
                self.translations = dict(self.fallback_translations)
        else:
            self.translations = dict(self.fallback_translations)

    def tr(self, key: str, default: Optional[str] = None, **kwargs) -> str:
        fallback = default if default is not None else key
        text = self.translations.get(key, self.fallback_translations.get(key, fallback))
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

def tr(key: str, default: Optional[str] = None, **kwargs) -> str:
    return LanguageManager.get_instance().tr(key, default=default, **kwargs)
