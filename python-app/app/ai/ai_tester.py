"""
AI Testing and Real-Time Diagnosis Module for Indexo.
Allows users and developers to test how the 3-tier cascaded AI classifies any filename or document text.
"""

import time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import indexo_core

from app.ai.semantic_classifier import SemanticClassifier
from app.ai.model_manager import ModelManager
from app.ai.vector_engine import VectorEngine
from app.ai.llm_engine import LLMEngine
from app.config.settings_manager import SettingsManager
from app.classification.rule_loader import RuleLoader


@dataclass
class AITestDiagnosis:
    engine_used: str  # "rules_rust", "vector_search", "slm_qwen"
    engine_label: str
    elapsed_ms: float
    categoria: str
    subcategoria: str
    pasta_sugerida: str
    tags: List[str]
    confianca: float
    reasoning: str
    is_ai_active: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_used": self.engine_used,
            "engine_label": self.engine_label,
            "elapsed_ms": self.elapsed_ms,
            "categoria": self.categoria,
            "subcategoria": self.subcategoria,
            "pasta_sugerida": self.pasta_sugerida,
            "tags": self.tags,
            "confianca": self.confianca,
            "reasoning": self.reasoning,
            "is_ai_active": self.is_ai_active,
        }


class AITester:
    """
    Diagnostic tool to test semantic classification in real-time.
    """

    def __init__(self):
        self.classifier = SemanticClassifier()
        self.model_mgr = ModelManager()
        self.settings_mgr = SettingsManager()
        self.rule_loader = RuleLoader()
        kernel_json = self.rule_loader.build_kernel_json()
        self.kernel = indexo_core.PyClassificationKernel.from_rules_json(kernel_json)

    def get_ai_status_summary(self) -> Dict[str, Any]:
        """
        Returns live status of all AI engines for badges and status pills.
        """
        preferred_slm = self.settings_mgr.get("preferred_slm_model", "qwen2.5-1.5b")
        slm_ready = self.model_mgr.is_model_downloaded(preferred_slm)
        vector_ready = self.model_mgr.is_vector_search_ready()

        if slm_ready:
            status_type = "slm_active"
            status_text = f"🟢 IA Local Ativa ({preferred_slm})"
            color = "#22c55e"
        elif vector_ready:
            status_type = "vector_active"
            status_text = "🟢 Busca Semântica Ativa (Vetorial)"
            color = "#0284c7"
        else:
            status_type = "rules_only"
            status_text = "⚡ Motor Nativo Ativo (Regras 0ms)"
            color = "#eab308"

        return {
            "status_type": status_type,
            "status_text": status_text,
            "color": color,
            "slm_ready": slm_ready,
            "vector_ready": vector_ready,
            "preferred_slm": preferred_slm,
        }

    def diagnose_query(self, query_text: str, existing_categories: Optional[List[str]] = None) -> AITestDiagnosis:
        """
        Executes real-time classification on a query string or filename and measures exact latency.
        """
        start_time = time.perf_counter()
        
        query = query_text.strip()
        if not query:
            return AITestDiagnosis(
                engine_used="none",
                engine_label="Nenhum texto informado",
                elapsed_ms=0.0,
                categoria="Geral",
                subcategoria="Outros",
                pasta_sugerida="Documentos/Outros",
                tags=[],
                confianca=0.0,
                reasoning="Texto vazio",
                is_ai_active=False,
            )

        cats = existing_categories or self.settings_mgr.get_all_categories()
        if not cats:
            cats = ["Documentos", "Finanças", "Trabalho", "Projetos", "Imagens", "Outros"]

        ext = Path(query).suffix.lower() if "." in query else ".pdf"
        normalized_text = query.replace("_", " ").replace("-", " ").replace(".", " ")
        combined_text = f"{query} {normalized_text}"

        # 1. Evaluate Rust Fast Kernel Candidate
        initial_match = None
        try:
            kernel_res = self.kernel.classify(combined_text, ext, 0.0)
            if kernel_res:
                initial_match = {
                    "categoria": kernel_res.categoria,
                    "subcategoria": kernel_res.subcategoria or "",
                    "caminho_fisico": kernel_res.caminho_fisico,
                    "confianca": kernel_res.confianca,
                    "tags": [kernel_res.categoria],
                }
        except Exception:
            pass

        # 2. Match active user & system rule tags by keywords/stem
        if not initial_match or initial_match.get("confianca", 0.0) < 0.65:
            all_rules = self.rule_loader.active_rules
            norm_lower = normalized_text.lower()
            for r in all_rules:
                kws = [k.lower() for k in r.get("palavras_chave", []) if k]
                if any(k in norm_lower for k in kws):
                    initial_match = {
                        "categoria": r.get("categoria", "Documentos"),
                        "subcategoria": r.get("subcategoria", ""),
                        "caminho_fisico": r.get("caminho_fisico", "Documentos"),
                        "confianca": float(r.get("confianca_base", 0.95)),
                        "tags": [r.get("nome", r.get("categoria", "Documentos"))],
                    }
                    break

        output = self.classifier.classify_single_file(
            rel_path=query,
            ext=ext,
            size_bytes=1024,
            extracted_text=combined_text,
            initial_candidate=initial_match,
            existing_categories=cats,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if output.metodo == "rules":
            engine_used = "rules_rust"
            engine_label = f"⚡ Regras Nativas Rust ({elapsed_ms:.1f}ms)"
            reasoning = "Classificado instantaneamente pelo motor de regras e regexes nativas."
            is_ai_active = False
        elif output.metodo == "vector_search":
            engine_used = "vector_search"
            engine_label = f"🧠 Busca Vetorial ONNX ({elapsed_ms:.1f}ms)"
            reasoning = "Similaridade semântica por embeddings vetoriais de 384 dimensões."
            is_ai_active = True
        elif output.metodo in ["slm_reasoning", "slm"]:
            engine_used = "slm_qwen"
            engine_label = f"🤖 SLM Qwen 2.5 Local ({elapsed_ms:.1f}ms)"
            reasoning = "Raciocínio generativo do modelo de linguagem local via llama-cpp."
            is_ai_active = True
        else:
            engine_used = "fallback"
            engine_label = f"📁 Heurística Padrão ({elapsed_ms:.1f}ms)"
            reasoning = "Classificação padrão por extensão de arquivo."
            is_ai_active = False

        return AITestDiagnosis(
            engine_used=engine_used,
            engine_label=engine_label,
            elapsed_ms=elapsed_ms,
            categoria=output.categoria,
            subcategoria=output.subcategoria,
            pasta_sugerida=output.pasta_sugerida,
            tags=output.tags,
            confianca=output.confianca,
            reasoning=reasoning,
            is_ai_active=is_ai_active,
        )
