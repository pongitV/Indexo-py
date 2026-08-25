import os
import sys
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication

# Ensure python-app is on sys.path
sys_path = Path(__file__).resolve().parent.parent / "python-app"
if str(sys_path) not in sys.path:
    sys.path.insert(0, str(sys_path))

from app.i18n.language_manager import LanguageManager, tr
from app.config.settings_manager import SettingsManager
from app.onboarding.onboarding_wizard import OnboardingWizard
from app.main_window import MainWindow
from app.ai.ai_tester import AITester


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_language_detection_and_manager():
    lang_mgr = LanguageManager.get_instance()
    sys_lang = lang_mgr.detect_system_language()
    assert sys_lang in ["ptBR", "enUS"]

    # Test dictionary translation lookup
    lang_mgr.set_language("ptBR")
    assert "INDEXO" in tr("welcome.heading")
    assert "Alexandria" in tr("welcome.slogan")

    lang_mgr.set_language("enUS")
    assert "INDEXO" in tr("welcome.heading")
    assert "Alexandria" in tr("welcome.slogan")


def test_onboarding_wizard_auto_start(qapp):
    wizard = OnboardingWizard()
    assert wizard.wizard_stack.count() == 2
    assert wizard.wizard_stack.currentIndex() == 0

    # Step 0: Welcome Screen with 1-Click Auto Setup
    assert wizard.lbl_welcome_title.text() == "INDEXO"
    assert wizard.btn_auto_start is not None
    assert wizard.btn_customize is not None

    # Test 1-Click Auto Setup
    wizard.apply_auto_defaults_and_start()
    sm = SettingsManager()
    assert sm.get("first_run") is False
    assert sm.get("confidence_threshold") == 0.80


def test_onboarding_wizard_customize_steps(qapp):
    wizard = OnboardingWizard()
    assert wizard.wizard_stack.currentIndex() == 0

    # Transition to Step 1: Initial Settings via Customize button
    wizard.btn_customize.click()
    assert wizard.wizard_stack.currentIndex() == 1

    # Verify initial settings widgets
    assert wizard.combo_lang.count() >= 2
    assert wizard.combo_theme.count() >= 2
    assert wizard.combo_ai_model.count() >= 2
    assert "Preview:" in wizard.lbl_rename_preview.text()

    # Back button transitions back to Step 0
    wizard.btn_back_welcome.click()
    assert wizard.wizard_stack.currentIndex() == 0


def test_main_window_home_menu_and_navigation(qapp):
    window = MainWindow()
    
    # Starts on Root View 0 (Home Menu with Icon, Title, Phrase, Select Folder button)
    assert window.root_stack.currentIndex() == 0
    assert window.btn_welcome_select is not None
    assert window.btn_menu_settings is not None
    assert window.btn_menu_tags is not None
    assert window.btn_menu_guide is not None

    # Open Settings View (Index 2)
    window.btn_menu_settings.click()
    assert window.root_stack.currentIndex() == 2

    # Return to Home Menu (Index 0)
    window.settings_widget.btn_back.click()
    assert window.root_stack.currentIndex() == 0

    # Open Tag Manager View (Index 3)
    window.btn_menu_tags.click()
    assert window.root_stack.currentIndex() == 3

    # Return to Home Menu (Index 0)
    window.tag_manager_widget.btn_back.click()
    assert window.root_stack.currentIndex() == 0

    # Open Guide View (Index 4)
    window.btn_menu_guide.click()
    assert window.root_stack.currentIndex() == 4

    # Return to Home Menu (Index 0)
    window.guide_widget.btn_back.click()
    assert window.root_stack.currentIndex() == 0


def test_ai_tester_diagnosis_and_transparency():
    tester = AITester()
    
    # Test summary status
    summary = tester.get_ai_status_summary()
    assert "status_text" in summary
    assert "color" in summary
    assert summary["color"].startswith("#")

    # Test real-time diagnosis on real-world queries
    diag1 = tester.diagnose_query("fatura_enel_maio_2024.pdf")
    assert diag1.categoria != ""
    assert diag1.confianca > 0.0
    assert diag1.elapsed_ms >= 0.0
    assert "Regras" in diag1.engine_label or "Busca" in diag1.engine_label or "SLM" in diag1.engine_label

    diag2 = tester.diagnose_query("contrato_prestacao_servicos.pdf")
    assert diag2.categoria != ""
    assert diag2.confianca > 0.0


def test_ai_live_inspector_and_thought_stream(qapp):
    from app.widgets.ai_live_inspector_view import AILiveInspectorView

    view = AILiveInspectorView()
    sample_items = [
        {"rel_path": "fatura_luz_enel_maio.pdf", "category": "Faturas e Boletos", "confidence": 0.95, "size": 12040, "extracted_text": "Enel Energia Eletrica 150.00"},
        {"rel_path": "contrato_locacao.pdf", "category": "Documentos e Contratos", "confidence": 0.88, "size": 35000, "extracted_text": "Contrato de Locacao"},
    ]

    view.load_items(sample_items)
    assert view.file_list.count() == 2

    # Select first file and verify thoughts rendered
    view.file_list.setCurrentRow(0)
    assert "fatura_luz_enel_maio.pdf" in view.lbl_thought_file.text()
    assert len(view.txt_chain_steps.toPlainText()) > 10
    assert len(view.txt_json_output.toPlainText()) > 10


def test_settings_view_delete_model_button_presence(qapp):
    from app.widgets.settings_view import SettingsView
    sv = SettingsView()
    assert sv.btn_delete_slm is not None
    assert sv.btn_download_slm is not None


def test_secondary_views_and_dynamic_retranslation(qapp, tmp_path):
    from app.widgets.dry_run_tree import DryRunTreeView
    from app.widgets.lite_mode import LiteModeView
    from app.widgets.folder_review import FolderReviewView
    from app.widgets.file_context_menu import FilePropertiesDialog, FileMoveCategoryDialog, FileTagEditDialog

    # 1. Test DryRunTreeView
    dry_view = DryRunTreeView()
    sample_items = [
        {"rel_path": "doc1.pdf", "category": "Documentos", "caminho_fisico": "Documentos", "suggested_filename": "2024_doc1.pdf", "confidence": 0.90},
        {"rel_path": "foto1.jpg", "category": "Fotos", "caminho_fisico": "Fotos", "suggested_filename": "foto1.jpg", "confidence": 0.85},
    ]
    dry_view.populate_dry_run(sample_items, tmp_path)
    assert "2" in dry_view.lbl_summary.text()
    assert dry_view.tree_before.topLevelItemCount() > 0
    assert dry_view.tree_after.topLevelItemCount() > 0

    # 2. Test LiteModeView
    test_file = tmp_path / "fatura_luz.pdf"
    test_file.write_text("dummy test content", encoding="utf-8")

    lite_view = LiteModeView()
    lite_view.target_dir = tmp_path
    lite_view.scan_and_plan()
    assert len(lite_view.rename_plan) >= 1
    lite_view.retranslate_ui()

    # 3. Test FolderReviewView
    folder_view = FolderReviewView()
    folder_view.load_from_items(sample_items, tmp_path)
    assert len(folder_view.move_plan) >= 1
    folder_view.retranslate_ui()

    # 4. Test FilePropertiesDialog
    props_dlg = FilePropertiesDialog(str(test_file), {"category": "Faturas", "confidence": 0.95})
    assert props_dlg.file_path == str(test_file)

    # 5. Test FileMoveCategoryDialog
    move_dlg = FileMoveCategoryDialog("fatura_luz.pdf", "Faturas")
    assert move_dlg.filename == "fatura_luz.pdf"

    # 6. Test FileTagEditDialog
    tag_dlg = FileTagEditDialog("fatura_luz.pdf", "Conta de Luz", "Faturas", file_path=str(test_file))
    assert tag_dlg.current_tag == "Conta de Luz"


def test_language_switching_across_all_views(qapp):
    """Verify that changing language dynamically updates all views, titles, buttons, and tables."""
    window = MainWindow()

    # 1. Switch to English
    window.change_language("enUS")
    assert LanguageManager.get_instance().current_language == "enUS"
    assert "Indexo" in window.windowTitle()
    assert "Select Folder" in window.btn_welcome_select.text()
    assert "Tags & Categories" in window.btn_menu_tags.text()
    assert "Guide" in window.btn_menu_guide.text()
    assert "Settings" in window.btn_menu_settings.text()
    assert "Organization" in window.combo_view_switcher.itemText(0)
    assert "Pending" in window.combo_view_switcher.itemText(1)
    assert "Duplicate" in window.combo_view_switcher.itemText(2)
    assert "Statistics" in window.combo_view_switcher.itemText(3)
    assert "Trash" in window.combo_view_switcher.itemText(4)

    # Check Guide in English
    assert window.guide_widget.topics_list.count() == 7
    assert "How Indexo Organizes" in window.guide_widget.topics_list.item(0).text()

    # Check Tag Manager in English
    assert window.tag_manager_widget.table_system.horizontalHeaderItem(4).text() == "Actions"
    assert window.tag_manager_widget.table_user.horizontalHeaderItem(4).text() == "Actions"

    # 2. Switch to Portuguese
    window.change_language("ptBR")
    assert LanguageManager.get_instance().current_language == "ptBR"
    assert "Selecionar Pasta" in window.btn_welcome_select.text()
    assert "Tags & Categorias" in window.btn_menu_tags.text()
    assert "Guia" in window.btn_menu_guide.text()
    assert "Configurações" in window.btn_menu_settings.text()
    assert "Organização" in window.combo_view_switcher.itemText(0)
    assert "Pendentes" in window.combo_view_switcher.itemText(1)
    assert "Duplicados" in window.combo_view_switcher.itemText(2)
    assert "Estatísticas" in window.combo_view_switcher.itemText(3)
    assert "Lixeira" in window.combo_view_switcher.itemText(4)

    # Check Guide in Portuguese
    assert "Como o Indexo Organiza" in window.guide_widget.topics_list.item(0).text()

    # Check Tag Manager in Portuguese
    assert window.tag_manager_widget.table_system.horizontalHeaderItem(4).text() == "Ações"
    assert window.tag_manager_widget.table_user.horizontalHeaderItem(4).text() == "Ações"

