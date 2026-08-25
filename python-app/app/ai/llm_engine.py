import json
import re
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union
from loguru import logger

from app.ai.model_manager import ModelManager, MODEL_CATALOGUE
from app.ai.hardware_specs import detect_hardware_specs

try:
    import sys
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        lib_dir = Path(sys._MEIPASS) / "llama_cpp" / "lib"
        lib_dir.mkdir(parents=True, exist_ok=True)

    from llama_cpp import Llama, LlamaGrammar
    LLAMA_CPP_AVAILABLE = True
except Exception as e:
    logger.warning("llama-cpp initialization notice: {}", e)
    LLAMA_CPP_AVAILABLE = False
    Llama = None
    LlamaGrammar = None


# GBNF grammar to force strict, hallucination-free JSON output
INDEXO_JSON_GBNF = r'''
root ::= "{" ws "\"categoria\":" ws string "," ws "\"subcategoria\":" ws string "," ws "\"tags\":" ws stringlist "," ws "\"pasta_sugerida\":" ws string "," ws "\"confianca\":" ws number "," ws "\"resumo_curto\":" ws string ws "}"
stringlist ::= "[" ws (string (ws "," ws string)*)? ws "]"
string ::= "\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\""
number ::= ("0" | [1-9] [0-9]*) ("." [0-9]+)?
ws ::= [ \t\n\r]*
'''


@dataclass
class ClassificationResult:
    categoria: str
    subcategoria: str
    tags: List[str]
    pasta_sugerida: str
    confianca: float
    resumo_curto: str
    raw_json: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "categoria": self.categoria,
            "subcategoria": self.subcategoria,
            "tags": self.tags,
            "pasta_sugerida": self.pasta_sugerida,
            "confianca": self.confianca,
            "resumo_curto": self.resumo_curto,
        }


class LLMEngine:
    """
    Local SLM Engine for file classification, folder suggestion and semantic reasoning.
    Utilizes Qwen2.5 (0.5B, 1.5B or 3B GGUF) via llama-cpp with strict GBNF grammar.
    """

    _instance: Optional["LLMEngine"] = None

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager()
        self.llm = None
        self.current_model_id: Optional[str] = None
        self.grammar = None
        self.last_used_timestamp = 0.0

    @classmethod
    def get_instance(cls) -> "LLMEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_available(self) -> bool:
        """Returns True if llama-cpp-python is available and at least one SLM model is downloaded."""
        if not LLAMA_CPP_AVAILABLE:
            return False
        for mid in ["qwen2.5-1.5b", "qwen2.5-0.5b", "qwen2.5-3b"]:
            if self.model_manager.is_model_downloaded(mid):
                return True
        return False

    def load_model(self, model_id: Optional[str] = None, n_threads: Optional[int] = None) -> bool:
        """Loads or swaps the SLM model into memory."""
        if not LLAMA_CPP_AVAILABLE:
            logger.warning("llama-cpp-python is not installed.")
            return False

        specs = detect_hardware_specs()
        chosen_id = model_id or self.model_manager.get_active_or_recommended_slm_id()
        model_path = self.model_manager.get_model_path(chosen_id)

        if not model_path:
            logger.warning(f"SLM model {chosen_id} is not downloaded yet.")
            return False

        # If already loaded same model, keep it
        if self.llm is not None and self.current_model_id == chosen_id:
            return True

        self.unload_model()

        threads = n_threads or specs.recommended_threads
        logger.info(f"Loading SLM {chosen_id} from {model_path} with {threads} CPU threads...")

        try:
            # Context size: 1024 tokens is more than enough for concise file classification
            self.llm = Llama(
                model_path=str(model_path),
                n_ctx=1024,
                n_threads=threads,
                n_batch=256,
                verbose=False,
            )
            self.current_model_id = chosen_id
            self.last_used_timestamp = time.time()

            try:
                self.grammar = LlamaGrammar.from_string(INDEXO_JSON_GBNF)
            except Exception as ge:
                logger.warning(f"Could not initialize GBNF grammar: {ge}. Will use JSON prompt mode.")
                self.grammar = None

            logger.info(f"SLM {chosen_id} loaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to load SLM model {chosen_id}: {e}")
            self.llm = None
            self.current_model_id = None
            return False

    def unload_model(self):
        """Unloads model to immediately release 1-2 GB RAM back to OS."""
        if self.llm is not None:
            del self.llm
            self.llm = None
            self.current_model_id = None
            self.grammar = None
            logger.info("SLM model unloaded from RAM.")

    def classify_file(
        self,
        filename: str,
        ext: str,
        size_bytes: int,
        extracted_text: str = "",
        existing_categories: Optional[List[str]] = None,
    ) -> Optional[ClassificationResult]:
        """
        Runs reasoning on file metadata and extracted content snippet,
        returning structured JSON classification.
        """
        if self.llm is None:
            if not self.load_model():
                return None

        self.last_used_timestamp = time.time()

        # Compact snippet: Head 400 chars + Tail 200 chars
        clean_text = extracted_text.strip().replace("\r", "")
        if len(clean_text) > 600:
            snippet = clean_text[:400] + " ... [trecho omitido] ... " + clean_text[-200:]
        else:
            snippet = clean_text or "(Arquivo sem texto extraído ou binário)"

        cats_hint = ", ".join(existing_categories[:15]) if existing_categories else "Financeiro, Documentos, Trabalho, Pessoal, Jogos, Fotos, Cursos"

        system_prompt = (
            "Você é o motor de inteligência do organizador de arquivos Indexo. "
            "Sua tarefa é analisar os dados do arquivo e determinar a melhor Categoria, Subcategoria, "
            "Tags relevantes, Pasta de destino sugerida e nível de confiança (0.0 a 1.0). "
            "Responda estritamente em JSON."
        )

        user_prompt = (
            f"Arquivo: {filename}\n"
            f"Extensão: {ext}\n"
            f"Tamanho: {size_bytes} bytes\n"
            f"Categorias existentes de referência: {cats_hint}\n"
            f"Conteúdo/Metadados extraídos:\n\"\"\"\n{snippet}\n\"\"\"\n\n"
            "Classifique este arquivo estruturadamente em JSON."
        )

        try:
            prompt = (
                f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
                f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

            kwargs = {
                "prompt": prompt,
                "max_tokens": 200,
                "temperature": 0.1,
                "top_p": 0.9,
                "stop": ["<|im_end|>", "<|endoftext|>"],
            }
            if self.grammar is not None:
                kwargs["grammar"] = self.grammar

            output = self.llm(**kwargs)
            text_response = output["choices"][0]["text"].strip()

            # Parse JSON
            # Extract JSON substring if wrapped in markdown codeblocks
            json_match = re.search(r"\{.*\}", text_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(text_response)

            return ClassificationResult(
                categoria=str(data.get("categoria", "Documentos")),
                subcategoria=str(data.get("subcategoria", "Geral")),
                tags=[str(t) for t in data.get("tags", []) if t],
                pasta_sugerida=str(data.get("pasta_sugerida", "Outros")),
                confianca=float(data.get("confianca", 0.85)),
                resumo_curto=str(data.get("resumo_curto", "")),
                raw_json=data,
            )
        except Exception as e:
            logger.error(f"Error during SLM classification of '{filename}': {e}")
            return None
