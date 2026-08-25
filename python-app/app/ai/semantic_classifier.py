from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from loguru import logger

from app.ai.vector_engine import VectorEngine
from app.ai.llm_engine import LLMEngine, ClassificationResult
from app.ai.model_manager import ModelManager
from app.classification.tag_discovery import is_mechanical_token
from app.classification.similarity_engine import sanitize_caminho_fisico

CANONICAL_CATEGORIES = [
    "Faturas e Boletos",
    "Financeiro",
    "Documentos e Contratos",
    "Documentos Pessoais",
    "Trabalho e Projetos",
    "Estudos e Cursos",
    "Impostos e Tributos",
    "Fotos e Imagens",
    "Músicas e Áudios",
    "Vídeos",
    "Jogos",
    "Aplicativos e Programas",
]


@dataclass
class SemanticClassificationOutput:
    file_rel: str
    categoria: str
    subcategoria: str
    tags: List[str]
    pasta_sugerida: str
    confianca: float
    metodo: str  # "rules", "vector_search", "slm_reasoning", "fallback"
    resumo: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_rel": self.file_rel,
            "categoria": self.categoria,
            "subcategoria": self.subcategoria,
            "tags": self.tags,
            "pasta_sugerida": self.pasta_sugerida,
            "confianca": self.confianca,
            "metodo": self.metodo,
            "resumo": self.resumo,
        }


class SemanticClassifier:
    """
    Tiered Cascaded Classifier:
    - Tier 1: Fast Rules & Heuristics (Rust Core) -> 0ms
    - Tier 2: Vector Semantic Similarity (ONNX MiniLM) -> 2ms
    - Tier 3: SLM Reasoning (Qwen 2.5) -> ~150ms on CPU for ambiguous/pending files
    """

    def __init__(
        self,
        vector_engine: Optional[VectorEngine] = None,
        llm_engine: Optional[LLMEngine] = None,
        confidence_threshold: float = 0.80,
    ):
        self.vector_engine = vector_engine or VectorEngine.get_instance()
        self.llm_engine = llm_engine or LLMEngine.get_instance()
        self.confidence_threshold = confidence_threshold
        self._category_embeddings_cache: Dict[str, Any] = {}

    def _sanitize_categories(self, categories: Optional[List[str]]) -> List[str]:
        """Cleanses category list ensuring ONLY clean, canonical human titles are used."""
        valid_cats = set(CANONICAL_CATEGORIES)
        if categories:
            for c in categories:
                c_clean = str(c).strip()
                if c_clean and len(c_clean) >= 3 and not is_mechanical_token(c_clean):
                    valid_cats.add(c_clean)
        return sorted(list(valid_cats))

    def update_category_embeddings(self, categories: Optional[List[str]] = None):
        """Pre-computes embeddings for known clean category names to enable 2ms classification."""
        if not self.vector_engine.is_ready:
            return

        clean_cats = self._sanitize_categories(categories)
        vectors = self.vector_engine.embed_batch(clean_cats)
        for cat, vec in zip(clean_cats, vectors):
            if vec is not None:
                self._category_embeddings_cache[cat] = vec

    def classify_single_file(
        self,
        rel_path: str,
        ext: str,
        size_bytes: int,
        extracted_text: str = "",
        initial_candidate: Optional[Dict[str, Any]] = None,
        existing_categories: Optional[List[str]] = None,
        force_ai: bool = False,
    ) -> SemanticClassificationOutput:
        """
        Classifies a single file through the cascade.
        """
        filename = Path(rel_path).name

        # 1. Check if Tier 1 (Initial Rules Candidate) is confident enough
        if initial_candidate and not force_ai:
            conf = float(initial_candidate.get("confianca", 0.0))
            if conf >= self.confidence_threshold:
                cat = initial_candidate.get("categoria", "Documentos")
                subcat = initial_candidate.get("subcategoria", "")
                caminho = initial_candidate.get("caminho_fisico", cat)
                return SemanticClassificationOutput(
                    file_rel=rel_path,
                    categoria=cat,
                    subcategoria=subcat,
                    tags=initial_candidate.get("tags", []),
                    pasta_sugerida=sanitize_caminho_fisico(caminho, cat),
                    confianca=conf,
                    metodo="rules",
                    resumo="Classificado pelo motor de regras rápidas",
                )

        # 2. Tier 2: Vector Search against clean canonical category embeddings
        clean_cats = self._sanitize_categories(existing_categories)
        if self.vector_engine.is_ready and not force_ai:
            if not self._category_embeddings_cache:
                self.update_category_embeddings(clean_cats)

            doc_text = f"{filename} {extracted_text[:300]}"
            doc_vec = self.vector_engine.embed_text(doc_text)

            if doc_vec is not None and self._category_embeddings_cache:
                best_cat = None
                best_score = 0.0

                for cat, cat_vec in self._category_embeddings_cache.items():
                    sim = self.vector_engine.cosine_similarity(doc_vec, cat_vec)
                    if sim > best_score:
                        best_score = sim
                        best_cat = cat

                if best_cat and best_score >= 0.45:
                    clean_dest = sanitize_caminho_fisico(best_cat)
                    return SemanticClassificationOutput(
                        file_rel=rel_path,
                        categoria=best_cat,
                        subcategoria="Geral",
                        tags=[best_cat],
                        pasta_sugerida=clean_dest,
                        confianca=round(best_score, 2),
                        metodo="vector_search",
                        resumo=f"Classificado por similaridade vetorial semântica ({best_score * 100:.0f}%)",
                    )

        # 3. Tier 3: SLM Deep Reasoning (Qwen2.5) for ambiguous or unclassified files
        if self.llm_engine.is_available() or force_ai:
            slm_result = self.llm_engine.classify_file(
                filename=filename,
                ext=ext,
                size_bytes=size_bytes,
                extracted_text=extracted_text,
                existing_categories=clean_cats,
            )

            if slm_result:
                cat = slm_result.categoria
                caminho = slm_result.pasta_sugerida or cat
                return SemanticClassificationOutput(
                    file_rel=rel_path,
                    categoria=cat,
                    subcategoria=slm_result.subcategoria,
                    tags=slm_result.tags,
                    pasta_sugerida=sanitize_caminho_fisico(caminho, cat),
                    confianca=slm_result.confianca,
                    metodo="slm_reasoning",
                    resumo=slm_result.resumo_curto or "Classificado com raciocínio de IA local",
                )

        # Fallback to initial candidate or default
        cat = initial_candidate.get("categoria", "Outros") if initial_candidate else "Outros"
        conf = float(initial_candidate.get("confianca", 0.3)) if initial_candidate else 0.2
        return SemanticClassificationOutput(
            file_rel=rel_path,
            categoria=cat,
            subcategoria="",
            tags=[],
            pasta_sugerida=sanitize_caminho_fisico(cat),
            confianca=conf,
            metodo="fallback",
            resumo="Classificação padrão / pendente de revisão",
        )
