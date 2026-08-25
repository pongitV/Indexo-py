import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_CONFIGS: Dict[str, Any] = {
    "version": 1,
    "configs": {
        "rename_enabled": True,
        "confidence_threshold": 0.80,
        "default_mode": "automatico",
        "language": "enUS",  # enUS default
        "theme": "system",  # "light", "dark", "system"


        "density": "comfortable",  # "comfortable", "compact"
        "read_only_mode": True,
        "index_content": True,
        "include_hidden": False,
        "promotion_n": 3,
        "advanced_mode": False,
        "classification_mode": "rules_fast",  # "rules_fast", "hybrid_vector", "full_ai"

        # File Renaming Pattern customization
        "rename_separator": " - ",  # " - ", "_", "-", ".", " "
        "rename_date_position": "suffix",  # "suffix", "prefix", "none"
        "rename_date_format": "DD-MM-YYYY",  # "DD-MM-YYYY", "YYYY-MM-DD", "YYYY_MM_DD", "YYYYMMDD", "DD_MM_YYYY", "MM-DD-YYYY"
        "rename_casing": "title",  # "title", "lower", "upper", "original"


        "ignored_extensions": [
            ".exe", ".msi", ".dll", ".sys", ".ini", ".cfg",
            ".lock", ".tmp", ".log", ".dat", ".bin"
        ],
        "ignored_folders": [],
        "silenced_promotions": []

    },
    "tags": []
}

def get_app_dir() -> Path:
    """Returns the portable directory next to executable or script."""
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent.parent

def get_configs_dir() -> Path:
    d = get_app_dir() / "configs"
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_data_dir() -> Path:
    d = get_app_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_user_rules_path() -> Path:
    return get_configs_dir() / "user_rules.json"

def get_db_path() -> Path:
    return get_data_dir() / "indexo.db"

def get_system_rules_path() -> Path:
    # 1. Custom user system_rules in configs/ next to executable
    app_sys = get_configs_dir() / "system_rules.json"
    if app_sys.exists():
        return app_sys
    # 2. Custom resources/system_rules.json next to executable
    res_sys = get_app_dir() / "resources" / "system_rules.json"
    if res_sys.exists():
        return res_sys
    # 3. Bundled resources inside PyInstaller package (_MEIPASS)
    import sys
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled_sys = Path(sys._MEIPASS) / "resources" / "system_rules.json"
        if bundled_sys.exists():
            return bundled_sys
    # 4. Project dev root
    dev_sys = Path(__file__).resolve().parent.parent.parent.parent / "resources" / "system_rules.json"
    if dev_sys.exists():
        return dev_sys
    return app_sys


class SettingsManager:
    """Manages reading, writing, migration and backup of user_rules.json and general settings."""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.user_rules_file = get_user_rules_path()
            cls._instance.data = cls._instance.load_or_init()
        return cls._instance

    def __init__(self):
        pass

    def load_or_init(self) -> Dict[str, Any]:
        if not self.user_rules_file.exists():
            data = json.loads(json.dumps(DEFAULT_CONFIGS))
            self.save_data(data)
            return data

        try:
            with open(self.user_rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Ensure required keys exist
            if "configs" not in data:
                data["configs"] = {}
            for k, v in DEFAULT_CONFIGS["configs"].items():
                if k not in data["configs"]:
                    data["configs"][k] = v
            if "tags" not in data:
                data["tags"] = []
            return data
        except Exception:
            # Try restore backup
            bak = self.user_rules_file.with_suffix(".bak.json")
            if bak.exists():
                try:
                    with open(bak, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data
                except Exception:
                    pass
            data = json.loads(json.dumps(DEFAULT_CONFIGS))
            self.save_data(data)
            return data

    def save_data(self, data: Dict[str, Any] = None):
        if data is not None:
            self.data = data
        
        # Make backup
        if self.user_rules_file.exists():
            bak = self.user_rules_file.with_suffix(".bak.json")
            shutil.copy2(self.user_rules_file, bak)

        with open(self.user_rules_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get("configs", {}).get(key, default)

    def set(self, key: str, value: Any):
        if "configs" not in self.data:
            self.data["configs"] = {}
        self.data["configs"][key] = value
        self.save_data()

    def is_power_user(self) -> bool:
        return bool(self.get("advanced_mode", False))

    def set_power_user(self, enabled: bool):
        self.set("advanced_mode", bool(enabled))

    def get_user_tags(self) -> List[Dict[str, Any]]:
        return self.data.get("tags", [])

    def save_user_tags(self, tags: List[Dict[str, Any]]):
        self.data["tags"] = tags
        self.save_data()

    def add_user_tag(self, tag: Dict[str, Any]):
        tags = self.data.get("tags", [])
        # replace if exists
        tags = [t for t in tags if t.get("id") != tag.get("id")]
        tags.append(tag)
        self.data["tags"] = tags
        self.save_data()

    def remove_user_tag(self, tag_id: str):
        tags = self.data.get("tags", [])
        self.data["tags"] = [t for t in tags if t.get("id") != tag_id]
        self.save_data()

    def get_all_categories(self) -> List[str]:
        """Returns all dynamically learned and active categories from user tags."""
        tags = self.get_user_tags()
        cats = sorted(list({t.get("categoria") for t in tags if t.get("categoria")}))
        return cats
