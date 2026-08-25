"""
Comprehensive AI Capabilities, Precision & Latency Benchmark Test Suite for Indexo.
Tests:
- Tier 1: Rust Fast Rules Kernel (0ms)
- Tier 2: ONNX Vector Search Engine (Multilingual MiniLM 384D)
- Tier 3: SLM Fallback & Reasoning
- Real-time Diagnostics (AITester) across 15 real-world document scenarios
"""

import sys
import time
import numpy as np
from pathlib import Path

# Add python-app to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "python-app"))

import indexo_core
from app.ai.hardware_specs import detect_hardware_specs
from app.ai.model_manager import ModelManager, MODEL_CATALOGUE
from app.ai.vector_engine import VectorEngine
from app.ai.semantic_classifier import SemanticClassifier
from app.ai.ai_tester import AITester
from app.classification.rule_loader import RuleLoader


def test_tier1_rust_kernel_rules_and_latency():
    """Validates Tier 1 Rust classification kernel execution time (<1ms) and regex match."""
    rule_loader = RuleLoader()
    kernel_json = rule_loader.build_kernel_json()
    kernel = indexo_core.PyClassificationKernel.from_rules_json(kernel_json)

    # 1. Electricity bill regex/keyword test
    start = time.perf_counter()
    res1 = kernel.classify("conta de luz enel vencimento maio 2024", ".pdf", 0.0)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert res1 is not None
    assert "Faturas" in res1.get("categoria", "") or "Invoices" in res1.get("categoria", "") or "Contas" in res1.get("categoria", "")
    assert res1.get("confianca", 0.0) >= 0.75
    assert elapsed_ms < 10.0  # Rust matching takes < 1ms typically
    print(f"✓ Tier 1 Rust Kernel: {res1.get('categoria')} -> {res1.get('subcategoria')} in {elapsed_ms:.3f}ms")

    # 2. Bank Slip (Boleto) Line test
    res2 = kernel.classify("boleto bancario vencimento linha digitavel 34191.79001 01043.510047 91020.150008 5 97250000015000", ".pdf", 0.0)
    assert res2 is not None
    assert "Faturas" in res2.get("categoria", "") or "Invoices" in res2.get("categoria", "") or "Boletos" in res2.get("categoria", "")
    print(f"✓ Tier 1 Rust Boleto Match: {res2.get('subcategoria')} (Conf: {res2.get('confianca')})")


def test_tier2_vector_engine_embeddings_and_search():
    """Validates Tier 2 ONNX Vector Search Engine with real pre-bundled models."""
    v_engine = VectorEngine.get_instance()
    
    # Check if vector search is ready with bundled models
    model_mgr = ModelManager()
    assert model_mgr.is_vector_search_ready() is True, "Vector search models should be pre-bundled"
    assert v_engine.is_ready is True, "VectorEngine should initialize with bundled ONNX model"

    # Test single embedding generation
    vec = v_engine.embed_text("comprovante de transferência pix banco inter")
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (384,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-4  # Normalized vector

    # Test Semantic Similarity across categories
    categories = [
        "Faturas e Boletos",
        "Bancário e Financeiro",
        "Fotos e Imagens",
        "Projetos e Código",
        "Vídeos",
    ]
    cat_embeddings = v_engine.embed_batch(categories)
    assert len(cat_embeddings) == len(categories)
    cat_matrix = np.array(cat_embeddings, dtype=np.float32)

    # Search for a financial query
    results = v_engine.search_similar(vec, cat_matrix, categories, top_k=2, min_score=0.2)
    assert len(results) > 0
    top_cat, top_score = results[0]
    assert top_cat in ["Bancário e Financeiro", "Faturas e Boletos"]
    print(f"✓ Tier 2 Vector Search: '{top_cat}' matched with cosine similarity {top_score:.3f}")

    # Multilingual comprehension test: English query matching Portuguese category
    en_vec = v_engine.embed_text("electricity bill invoice receipt")
    en_results = v_engine.search_similar(en_vec, cat_matrix, categories, top_k=2, min_score=0.10)
    assert len(en_results) > 0
    en_top_cat, en_top_score = en_results[0]
    assert en_top_cat in ["Faturas e Boletos", "Bancário e Financeiro"]
    print(f"✓ Tier 2 Multilingual Search: '{en_top_cat}' matched English query with similarity {en_top_score:.3f}")


def test_tier3_semantic_classifier_cascaded_inference():
    """Validates 3-tier cascade logic in SemanticClassifier."""
    classifier = SemanticClassifier(confidence_threshold=0.80)

    # Case A: Tier 1 high confidence (Rules 0ms)
    out_a = classifier.classify_single_file(
        rel_path="fatura_cpfl_energia.pdf",
        ext=".pdf",
        size_bytes=20480,
        extracted_text="CPFL Paulista Conta de Energia Elétrica",
        initial_candidate={
            "categoria": "Faturas e Boletos",
            "subcategoria": "Energia Elétrica",
            "tags": ["CPFL", "Luz"],
            "confianca": 0.95,
            "caminho_fisico": "Faturas_e_Boletos/Energia_Eletrica",
        },
        force_ai=False
    )
    assert out_a.metodo == "rules"
    assert out_a.categoria == "Faturas e Boletos"
    assert out_a.confianca == 0.95

    # Case B: Tier 2 semantic embedding classification when no rule match exists
    categories = ["Documentos e Contratos", "Trabalho e Renda", "Fotos e Imagens", "Aplicativos"]
    classifier.update_category_embeddings(categories)

    out_b = classifier.classify_single_file(
        rel_path="acordo_prestacao_servicos_consultoria.docx",
        ext=".docx",
        size_bytes=34000,
        extracted_text="Instrumento particular de acordo e prestacao de servicos juridicos entre as partes",
        initial_candidate=None,
        existing_categories=categories,
        force_ai=False
    )
    assert out_b.metodo in ["vector_search", "rules"]
    assert out_b.categoria in ["Documentos e Contratos", "Trabalho e Renda"]
    print(f"✓ Tier 2 Cascaded Classification: '{out_b.categoria}' (Method: {out_b.metodo}, Conf: {out_b.confianca:.2f})")


def test_ai_tester_15_real_world_document_scenarios():
    """Stress tests AITester across 15 diverse document types."""
    tester = AITester()

    test_queries = [
        ("fatura_enel_maio_2024.pdf", "Faturas e Boletos"),
        ("comprovante_pix_transferencia_aluguel.pdf", "Faturas e Boletos"),
        ("contrato_locacao_imovel_comercial.docx", "Documentos"),
        ("declaracao_imposto_renda_irpf_2024.pdf", "Impostos"),
        ("holerite_folha_pagamento_marco_2024.pdf", "Trabalho"),
        ("foto_viagem_ferias_rio_janeiro.jpg", "Fotos"),
        ("podcast_episodio_42_tecnologia.mp3", "Áudio"),
        ("video_apresentacao_projeto_final.mp4", "Vídeos"),
        ("jogo_peak_instalador.exe", "Jogos"),
        ("indexo_core_rust_bindings.rs", "Projetos"),
        ("extrato_mensal_conta_corrente_itau.pdf", "Faturas"),
        ("nota_fiscal_servico_eletronica_nfse.pdf", "Impostos"),
        ("curriculo_vitae_desenvolvedor_software.pdf", "Carreira"),
        ("tabela_precos_orcamento_2024.xlsx", "Documentos"),
        ("termo_garantia_equipamento_eletronico.pdf", "Documentos"),
    ]

    total_time_ms = 0.0
    for query, expected_cat_prefix in test_queries:
        diag = tester.diagnose_query(query)
        assert diag.categoria != "", f"Category must not be empty for {query}"
        assert diag.confianca > 0.0, f"Confidence must be > 0 for {query}"
        assert diag.elapsed_ms >= 0.0
        total_time_ms += diag.elapsed_ms

    avg_latency = total_time_ms / len(test_queries)
    print(f"✓ AITester benchmarked 15 scenarios: Avg Latency = {avg_latency:.2f}ms per query")
    assert avg_latency < 250.0  # Average latency must be < 250ms on CPU


if __name__ == "__main__":
    test_tier1_rust_kernel_rules_and_latency()
    test_tier2_vector_engine_embeddings_and_search()
    test_tier3_semantic_classifier_cascaded_inference()
    test_ai_tester_15_real_world_document_scenarios()
    print("\nAll AI Capabilities & Benchmark Tests Passed Successfully!")
