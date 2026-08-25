import sys
import numpy as np
from pathlib import Path

# Add python-app to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "python-app"))

from app.ai.hardware_specs import detect_hardware_specs
from app.ai.model_manager import ModelManager, MODEL_CATALOGUE
from app.ai.vector_engine import VectorEngine
from app.ai.semantic_classifier import SemanticClassifier


def test_hardware_specs_detection():
    profile = detect_hardware_specs()
    assert profile.total_ram_gb > 0
    assert profile.cpu_cores_logical >= 1
    assert profile.tier in ("low_end", "mid_range", "high_end")
    assert profile.recommended_model_id in ("qwen2.5-0.5b", "qwen2.5-1.5b", "qwen2.5-3b")
    assert profile.recommended_threads >= 1
    print("✓ test_hardware_specs_detection passed:", profile.description)


def test_model_manager_catalogue():
    mgr = ModelManager()
    assert "qwen2.5-1.5b" in MODEL_CATALOGUE
    assert "embedding-multilingual-minilm" in MODEL_CATALOGUE
    
    rec_id = mgr.get_active_or_recommended_slm_id()
    assert rec_id in MODEL_CATALOGUE
    print("✓ test_model_manager_catalogue passed. Recommended model:", rec_id)


def test_vector_engine_math():
    v_engine = VectorEngine.get_instance()
    
    # Test Cosine Similarity Math
    vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    vec2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    vec3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    assert abs(v_engine.cosine_similarity(vec1, vec2) - 1.0) < 1e-5
    assert abs(v_engine.cosine_similarity(vec1, vec3) - 0.0) < 1e-5

    # Test Search Similar
    corpus = np.array([
        [1.0, 0.0, 0.0],
        [0.8, 0.6, 0.0],
        [0.0, 1.0, 0.0],
    ], dtype=np.float32)
    ids = ["doc1", "doc2", "doc3"]

    results = v_engine.search_similar(vec1, corpus, ids, top_k=2, min_score=0.5)
    assert len(results) == 2
    assert results[0][0] == "doc1"
    assert results[1][0] == "doc2"
    print("✓ test_vector_engine_math passed:", results)


def test_semantic_classifier_rules_fallback():
    classifier = SemanticClassifier()

    # Rule candidate with high confidence
    out = classifier.classify_single_file(
        rel_path="fatura_enel_maio_2024.pdf",
        ext=".pdf",
        size_bytes=10240,
        extracted_text="Enel Distribuição São Paulo Fatura de Energia Elétrica",
        initial_candidate={
            "categoria": "Faturas",
            "subcategoria": "Energia",
            "tags": ["Enel", "Luz"],
            "confianca": 0.90,
            "caminho_fisico": "Faturas/Enel"
        },
        force_ai=False
    )

    assert out.metodo == "rules"
    assert out.categoria == "Faturas"
    assert out.confianca == 0.90
    print("✓ test_semantic_classifier_rules_fallback passed:", out.to_dict())


if __name__ == "__main__":
    test_hardware_specs_detection()
    test_model_manager_catalogue()
    test_vector_engine_math()
    test_semantic_classifier_rules_fallback()
    print("\nAll AI tests passed successfully!")
