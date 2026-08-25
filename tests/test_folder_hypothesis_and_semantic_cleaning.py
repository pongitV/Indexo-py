import pytest
from pathlib import Path
from app.classification.folder_validator import FolderContextValidator, FolderHypothesisResult
from app.classification.tag_discovery import TagDiscoveryEngine, is_mechanical_token, clean_token
from app.classification.similarity_engine import SimilarityEngine, sanitize_caminho_fisico
from app.classification.entity_regex import generate_standard_filename, extract_primary_date, extract_amount


def test_folder_context_validator_boletos_and_intruders():
    validator = FolderContextValidator()

    # 1. Real boleto inside "Boletos"
    res_boleto = validator.evaluate_folder_and_file(
        folder_rel="Boletos",
        rel_path="Boletos/conta_enel.pdf",
        abs_path="/path/Boletos/conta_enel.pdf",
        ext=".pdf",
        extracted_text="ENEL DISTRIBUICAO SP Consumo Ativo kWh 150 Valor a Pagar R$ 125,40 Vencimento 15/05/2024",
        file_type="document"
    )
    assert res_boleto.is_semantic_folder is True
    assert res_boleto.matches_hypothesis is True
    assert res_boleto.is_intruder is False
    assert res_boleto.folder_status == "confirmado"
    assert res_boleto.confidence >= 0.90
    assert "Faturas" in res_boleto.suggested_category or "Boletos" in res_boleto.suggested_category

    # 2. Stray photo inside "Boletos" (Intruder)
    res_foto = validator.evaluate_folder_and_file(
        folder_rel="Boletos",
        rel_path="Boletos/foto_praia.jpg",
        abs_path="/path/Boletos/foto_praia.jpg",
        ext=".jpg",
        extracted_text="",
        file_type="image"
    )
    assert res_foto.is_semantic_folder is True
    assert res_foto.matches_hypothesis is False
    assert res_foto.is_intruder is True
    assert res_foto.folder_status == "intruso"

    # 3. File in generic "Downloads" folder
    res_downloads = validator.evaluate_folder_and_file(
        folder_rel="Downloads",
        rel_path="Downloads/relatorio.pdf",
        abs_path="/path/Downloads/relatorio.pdf",
        ext=".pdf",
        extracted_text="Relatorio de Vendas Mensal",
        file_type="document"
    )
    assert res_downloads.is_semantic_folder is False
    assert res_downloads.is_intruder is False
    assert res_downloads.folder_status == "novo_agrupamento"


def test_tag_discovery_blocks_mechanical_noise_and_hashes():
    # Test helper functions
    assert is_mechanical_token("wa0001") is True
    assert is_mechanical_token("IMG_2024") is True
    assert is_mechanical_token("0a8f9b") is True
    assert is_mechanical_token("dcim") is True
    assert is_mechanical_token("temp12") is True
    assert is_mechanical_token("v1.2.3") is True
    assert is_mechanical_token("enel") is False
    assert is_mechanical_token("sabesp") is False
    assert is_mechanical_token("contrato") is False

    engine = TagDiscoveryEngine()
    fake_entries = [
        {"rel_path": "IMG-20230814-WA0001.jpg", "file_type": "image", "extracted_text": ""},
        {"rel_path": "IMG-20230814-WA0002.jpg", "file_type": "image", "extracted_text": ""},
        {"rel_path": "0a1f9e83_temp.dat", "file_type": "binary", "extracted_text": ""},
        {"rel_path": "0a1f9e83_backup.dat", "file_type": "binary", "extracted_text": ""},
        {"rel_path": "Fatura_Enel_Maio.pdf", "file_type": "document", "extracted_text": "Enel Energia Eletrica"},
        {"rel_path": "Fatura_Enel_Junho.pdf", "file_type": "document", "extracted_text": "Enel Energia Eletrica"},
    ]

    discovered = engine.discover_tags(Path("/fake/root"), fake_entries)
    discovered_ids = [t["id"] for t in discovered]
    discovered_names = [t["nome"].lower() for t in discovered]

    # Must NOT discover any WA0001 or 0a1f9e83 tags
    assert not any("wa" in tid for tid in discovered_ids)
    assert not any("0a1f" in tid for tid in discovered_ids)
    assert not any("wa0001" in n for n in discovered_names)


def test_similarity_engine_hierarchy_and_intruder_rerouting():
    engine = SimilarityEngine()

    # File 1: Boleto in Boletos folder -> confirmed in place
    h1 = engine.classify_by_hierarchy(
        rel_path="Boletos/fatura_luz.pdf",
        abs_path="/test/Boletos/fatura_luz.pdf",
        file_type="document",
        extracted_text="Enel Energia Eletrica Boleto Bancario Vencimento 20/05/2024",
        candidate={"categoria": "Faturas e Boletos", "confianca": 0.95, "scores": {"conteudo": 0.9}}
    )
    assert h1["status"] == "identificado"
    assert h1["folder_status"] == "confirmado"
    assert h1["is_intruder"] is False
    assert h1["confidence"] >= 0.90

    # File 2: Photo in Boletos folder -> identified as intruder and re-routed to Fotos e Imagens
    h2 = engine.classify_by_hierarchy(
        rel_path="Boletos/ferias.jpg",
        abs_path="/test/Boletos/ferias.jpg",
        file_type="image",
        extracted_text="",
        candidate=None
    )
    assert h2["status"] == "identificado"
    assert h2["is_intruder"] is True
    assert h2["folder_status"] == "intruso"
    assert h2["origin_folder"] == "boletos"
    assert h2["category"] in ["Fotos e Imagens", "Photos and Images", "Fotos"]


def test_sanitize_caminho_fisico_cleanliness():
    assert sanitize_caminho_fisico("wa0001/0002") == "Geral"
    assert sanitize_caminho_fisico("0a1f9e83/temp") == "Geral"
    assert sanitize_caminho_fisico("2024-05-10") == "Geral"
    assert sanitize_caminho_fisico("Faturas_e_Boletos/Boletos") == "Faturas_e_Boletos/Boletos"
    assert sanitize_caminho_fisico("Fotos e Imagens/Viagens") == "Fotos_e_Imagens/Viagens"


def test_standard_renaming_with_entities_and_amounts():
    text = "ENEL DISTRIBUICAO SP Fatura de Energia Eletrica Vencimento 10/06/2024 Valor Total R$ 184,50"
    date_str = extract_primary_date(text)
    amount = extract_amount(text)

    cfg = {
        "rename_separator": " - ",
        "rename_date_position": "prefix",
        "rename_date_format": "YYYY-MM-DD",
        "rename_casing": "title"
    }

    renamed = generate_standard_filename(
        date_str=date_str,
        entity="Enel",
        category_or_tag="Conta Luz",
        original_ext=".pdf",
        original_stem="fatura_12345",
        config=cfg,
        amount=amount
    )

    assert "2024-06-10" in renamed
    assert "Enel" in renamed
    assert "Conta Luz" in renamed
    assert "R$184,50" in renamed
    assert renamed.endswith(".pdf")
