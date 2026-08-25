import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from loguru import logger
import indexo_core

from app.config.settings_manager import (
    get_system_rules_path,
    get_user_rules_path,
    SettingsManager,
)
from app.i18n.language_manager import LanguageManager, tr

class RuleLoader:
    def __init__(self):
        self.settings_mgr = SettingsManager()
        self.system_rules: List[Dict[str, Any]] = []
        self.user_rules: List[Dict[str, Any]] = []
        self.active_rules: List[Dict[str, Any]] = []
        self.load_all_rules()

    def load_all_rules(self):
        self.system_rules = self.load_system_rules()
        self.user_rules = self.load_user_rules()
        self.active_rules = self.combine_rules(self.user_rules, self.system_rules)

    def reload(self):
        self.load_all_rules()


    def load_system_rules(self) -> List[Dict[str, Any]]:
        path = get_system_rules_path()
        if not path.exists():
            logger.warning("system_rules.json not found at {}", path)
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rules = data.get("rules", [])
            valid_rules = []
            for r in rules:
                r["origem"] = "system"
                valid_rules.append(r)
            return valid_rules
        except Exception as e:
            logger.error("Failed to load system_rules.json: {}", e)
            return []

    def load_user_rules(self) -> List[Dict[str, Any]]:
        data = self.settings_mgr.load_or_init()
        tags = data.get("tags", [])
        valid_rules = []
        app_lang = LanguageManager.get_instance().current_language

        for t in tags:
            caminho = t.get("caminho_fisico", "")
            try:
                # Anti-path-traversal check via Rust core
                valid_caminho = indexo_core.py_validate_caminho_fisico(caminho)
                t["caminho_fisico"] = valid_caminho
            except Exception as e:
                logger.warning("Ignoring invalid user tag '{}': {}", t.get("nome"), e)
                continue

            t["origem"] = "user"
            tag_lang = t.get("idioma", "")
            # Check if tag language differs from current app language
            t["needs_language_warning"] = bool(tag_lang and tag_lang != app_lang)
            valid_rules.append(t)

        return valid_rules

    def combine_rules(self, user_rules: List[Dict[str, Any]], system_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Format each rule to match RuleDefinition struct in Rust
        combined = []

        # User rules first
        for u in user_rules:
            combined.append({
                "id": u.get("id", ""),
                "nome": u.get("nome", ""),
                "categoria": u.get("categoria", ""),
                "subcategoria": u.get("subcategoria"),
                "entidade": u.get("entidade"),
                "caminho_fisico": u.get("caminho_fisico", ""),
                "origem": "user",
                "categoria_key": u.get("categoria_key"),
                "palavras_chave": u.get("palavras_chave", []),
                "regex": u.get("regex", []),
                "extensoes": u.get("extensoes", []),
                "confianca_base": float(u.get("confianca_base", 1.0)),
                "usar_para_automacao": bool(u.get("usar_para_automacao", True)),
                "idioma": u.get("idioma"),
                "sinonimos": u.get("sinonimos", [])
            })

        # System rules second
        app_lang = LanguageManager.get_instance().current_language
        for s in system_rules:
            cat_key = s.get("categoria_key")
            cat_name = tr(cat_key) if cat_key else s.get("categoria", "")

            subcat = s.get("subcategoria")
            if app_lang == "enUS" and s.get("sinonimos"):
                subcat = s.get("sinonimos")[0]

            cat_slug = cat_name.replace(" ", "_").replace("/", "_")
            sub_slug = subcat.replace(" ", "_").replace("/", "_") if subcat else ""
            caminho_fisico = f"{cat_slug}/{sub_slug}" if sub_slug and sub_slug != cat_slug else cat_slug

            combined.append({
                "id": s.get("id", ""),
                "nome": subcat or cat_name,
                "categoria": cat_name,
                "subcategoria": subcat,
                "entidade": s.get("entidade"),
                "caminho_fisico": caminho_fisico,
                "origem": "system",
                "categoria_key": cat_key,
                "palavras_chave": s.get("palavras_chave", []),
                "regex": s.get("regex", []),
                "extensoes": s.get("extensoes", []),
                "confianca_base": float(s.get("confianca_base", 1.0)),
                "usar_para_automacao": bool(s.get("usar_para_automacao", True)),
                "idioma": s.get("idioma", "ptBR"),
                "sinonimos": s.get("sinonimos", [])
            })

        return combined



    def build_kernel_json(self) -> str:
        return json.dumps(self.active_rules, ensure_ascii=False)
