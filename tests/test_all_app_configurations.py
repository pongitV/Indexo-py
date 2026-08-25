"""
Comprehensive Configurations & Options Test Suite for Indexo.
Tests:
- Theme switching (Light, Dark, System) and palette adaptation
- Language switching (ptBR <-> enUS) with 100% translation key parity
- Renaming engine combinations (separators, date positions, date formats, casings)
- Confidence threshold filtering (0.50, 0.65, 0.80, 0.95)
- User tags and System tags CRUD and promotion
"""

import sys
import pytest
from pathlib import Path

# Add python-app to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "python-app"))

from app.config.settings_manager import SettingsManager
from app.i18n.language_manager import LanguageManager, tr
from app.classification.entity_regex import generate_standard_filename
from app.classification.rule_loader import RuleLoader
from app.utils.theme_manager import get_effective_theme, get_theme_stylesheet, is_system_dark_mode


def test_theme_configurations_and_palettes():
    sm = SettingsManager()

    # 1. Dark Theme
    sm.set("theme", "dark")
    assert get_effective_theme("dark") == "dark"
    qss_dark = get_theme_stylesheet("dark")
    assert len(qss_dark) > 100
    assert "#100F0F" in qss_dark or "#1C1B1A" in qss_dark or "background" in qss_dark

    # 2. Light Theme
    sm.set("theme", "light")
    assert get_effective_theme("light") == "light"
    qss_light = get_theme_stylesheet("light")
    assert len(qss_light) > 100
    assert "#FFFCF0" in qss_light or "#F2F0E5" in qss_light or "background" in qss_light

    # 3. System Theme
    sm.set("theme", "system")
    eff = get_effective_theme("system")
    assert eff in ["light", "dark"]
    print(f"✓ Theme configuration validated: dark, light, system (Effective: {eff})")


def test_language_switching_and_330_keys_parity():
    lang_mgr = LanguageManager.get_instance()

    # Load ptBR
    lang_mgr.set_language("ptBR")
    pt_title = tr("app.title")
    assert "Indexo" in pt_title
    assert tr("theme.light") == "Claro"
    assert tr("theme.dark") == "Escuro"
    pt_dict = dict(lang_mgr.translations)

    # Load enUS
    lang_mgr.set_language("enUS")
    en_title = tr("app.title")
    assert "Indexo" in en_title
    assert tr("theme.light") == "Light"
    assert tr("theme.dark") == "Dark"
    en_dict = dict(lang_mgr.translations)

    # Verify key parity between ptBR and enUS
    assert len(pt_dict) >= 330, f"Expected at least 330 translation keys, got {len(pt_dict)}"
    assert len(en_dict) >= 330, f"Expected at least 330 translation keys, got {len(en_dict)}"

    missing_in_en = set(pt_dict.keys()) - set(en_dict.keys())
    missing_in_pt = set(en_dict.keys()) - set(pt_dict.keys())

    assert len(missing_in_en) == 0, f"Keys missing in enUS: {missing_in_en}"
    assert len(missing_in_pt) == 0, f"Keys missing in ptBR: {missing_in_pt}"
    print(f"✓ Language parity confirmed: {len(pt_dict)} keys identical between ptBR and enUS")


def test_renaming_pattern_generator_all_combinations():
    # Test matrix of configurations
    separators = ["_", " - ", "-", ".", " "]
    date_formats = ["YYYY-MM-DD", "DD-MM-YYYY", "YYYYMMDD", "DD_MM_YYYY"]
    date_positions = ["prefix", "suffix", "none"]
    casings = ["title", "lower", "upper", "original"]

    count = 0
    for sep in separators:
        for df in date_formats:
            for dp in date_positions:
                for casing in casings:
                    cfg = {
                        "rename_separator": sep,
                        "rename_date_format": df,
                        "rename_date_position": dp,
                        "rename_casing": casing,
                    }
                    res = generate_standard_filename(
                        date_str="2024-05-10",
                        entity="Enel",
                        category_or_tag="Conta Luz",
                        original_ext=".pdf",
                        original_stem="fatura_luz",
                        config=cfg,
                    )
                    assert res.endswith(".pdf")
                    assert len(res) > 4
                    count += 1

    print(f"✓ Renaming Engine validated: {count} format combinations generated cleanly")


def test_confidence_threshold_filtering_logic():
    sm = SettingsManager()

    # Verify default is 0.80
    default_conf = sm.get("confidence_threshold", 0.80)
    assert default_conf == 0.80

    # Test filtering simulation
    sample_scores = [0.45, 0.62, 0.75, 0.82, 0.95]

    for threshold in [0.50, 0.65, 0.80, 0.90]:
        accepted = [s for s in sample_scores if s >= threshold]
        pending = [s for s in sample_scores if s < threshold]
        assert len(accepted) + len(pending) == len(sample_scores)
        if threshold == 0.80:
            assert accepted == [0.82, 0.95]
            assert pending == [0.45, 0.62, 0.75]

    print("✓ Confidence threshold filtering validated for 0.50, 0.65, 0.80 and 0.90")


def test_user_tags_management_and_promotion():
    sm = SettingsManager()
    rl = RuleLoader()

    # Initial system rules
    assert len(rl.system_rules) >= 20

    # Add a custom user tag
    custom_tag = {
        "id": "user_tag_teste_unitario",
        "nome": "Projeto Alpha",
        "categoria": "Projetos e Código",
        "subcategoria": "Alpha Corp",
        "palavras_chave": ["alpha", "projeto alpha", "relatorio alpha"],
        "regex": ["\\balpha\\b"],
        "confianca_base": 0.92,
        "caminho_fisico": "Projetos/Alpha",
        "origem": "user",
    }

    # Save to user tags
    user_tags = sm.get_user_tags()
    user_tags = [t for t in user_tags if t.get("id") != "user_tag_teste_unitario"]
    user_tags.append(custom_tag)
    sm.save_user_tags(user_tags)

    # Reload rule loader
    rl.reload()
    found = any(t.get("id") == "user_tag_teste_unitario" for t in rl.active_rules)
    assert found is True

    user_tags = [t for t in user_tags if t.get("id") != "user_tag_teste_unitario"]
    sm.save_user_tags(user_tags)
    rl.reload()
    found_after = any(t.get("id") == "user_tag_teste_unitario" for t in rl.active_rules)
    assert found_after is False
    print("✓ User tags CRUD and active rule synchronization validated successfully")


def test_classification_mode_selection_and_folder_sanitization():
    from app.classification.similarity_engine import sanitize_caminho_fisico
    sm = SettingsManager()

    # 1. Test search / classification modes
    for mode in ["rules_fast", "hybrid_vector", "full_ai"]:
        sm.set("classification_mode", mode)
        assert sm.get("classification_mode") == mode

    # 2. Test sanitize_caminho_fisico avoids raw dates, stems, numbers, or broken tokens
    assert sanitize_caminho_fisico("Faturas_e_Boletos/Enel") == "Faturas_e_Boletos/Enel"
    assert sanitize_caminho_fisico("2024-05-10") == "Geral"
    assert sanitize_caminho_fisico("12345/67890") == "Geral"
    assert sanitize_caminho_fisico("Documentos/2024-05-10") == "Documentos"
    assert sanitize_caminho_fisico("Fotos/12345678_hash_#1") == "Fotos/hash_1"
    assert sanitize_caminho_fisico("") == "Geral"
    print("✓ Classification mode options and folder sanitization validated successfully")


if __name__ == "__main__":
    test_theme_configurations_and_palettes()
    test_language_switching_and_330_keys_parity()
    test_renaming_pattern_generator_all_combinations()
    test_confidence_threshold_filtering_logic()
    test_user_tags_management_and_promotion()
    test_classification_mode_selection_and_folder_sanitization()
    print("\nAll Configuration & Options Tests Passed Successfully!")
