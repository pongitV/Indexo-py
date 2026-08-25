import os
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, Callable
import requests
from loguru import logger

from app.ai.hardware_specs import detect_hardware_specs


@dataclass
class ModelInfo:
    id: str
    name: str
    type: str  # "slm" or "embedding"
    format: str  # "gguf" or "onnx"
    filename: str
    size_mb: float
    ram_usage_mb: float
    download_url: str
    description: str
    sha256: Optional[str] = None


# Supported models catalogue
MODEL_CATALOGUE: Dict[str, ModelInfo] = {
    "embedding-multilingual-minilm": ModelInfo(
        id="embedding-multilingual-minilm",
        name="Multilingual MiniLM (Vector Search)",
        type="embedding",
        format="onnx",
        filename="multilingual-minilm-l12-v2.onnx",
        size_mb=65.0,
        ram_usage_mb=120.0,
        download_url="https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/resolve/main/onnx/model_quantized.onnx",
        description="Modelo de embeddings multilíngue (PT/EN/50+ idiomas) ultraleve para busca semântica instantânea no Ctrl+K.",
    ),
    "embedding-tokenizer": ModelInfo(
        id="embedding-tokenizer",
        name="Tokenizer Multilingual",
        type="embedding",
        format="json",
        filename="tokenizer.json",
        size_mb=9.0,
        ram_usage_mb=10.0,
        download_url="https://huggingface.co/Xenova/paraphrase-multilingual-MiniLM-L12-v2/resolve/main/tokenizer.json",
        description="Vocabulário e tokenizador para o modelo de busca semântica.",
    ),
    "qwen2.5-0.5b": ModelInfo(
        id="qwen2.5-0.5b",
        name="Qwen 2.5 0.5B Instruct (Ultra-Leve)",
        type="slm",
        format="gguf",
        filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
        size_mb=398.0,
        ram_usage_mb=650.0,
        download_url="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        description="Modelo SLM ultracompacto, ideal para CPUs muito fracas ou computadores com menos de 6 GB de RAM.",
    ),
    "qwen2.5-1.5b": ModelInfo(
        id="qwen2.5-1.5b",
        name="Qwen 2.5 1.5B Instruct (Equilibrado / Recomendado)",
        type="slm",
        format="gguf",
        filename="qwen2.5-1.5b-instruct-q4_k_m.gguf",
        size_mb=986.0,
        ram_usage_mb=1600.0,
        download_url="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        description="Equilíbrio perfeito entre inteligência de categorização, raciocínio em português e consumo leve de RAM (< 2 GB).",
    ),
    "qwen2.5-3b": ModelInfo(
        id="qwen2.5-3b",
        name="Qwen 2.5 3B Instruct (Alto Desempenho)",
        type="slm",
        format="gguf",
        filename="qwen2.5-3b-instruct-q4_k_m.gguf",
        size_mb=1930.0,
        ram_usage_mb=2900.0,
        download_url="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        description="Maior profundidade de raciocínio para computadores com 16 GB+ de RAM.",
    ),
}


import sys
import shutil
from app.config.settings_manager import get_data_dir, get_app_dir


class ModelManager:
    """
    Manages local AI model storage, downloads, verification and paths in data/models/.
    Also resolves pre-bundled models from resources/models/.
    """

    def __init__(self, models_dir: Optional[Path] = None):
        if models_dir is None:
            self.models_dir = get_data_dir() / "models"
        else:
            self.models_dir = Path(models_dir)

        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._cancel_flag = False
        self._sync_bundled_models()

    def _sync_bundled_models(self):
        """Discovers bundled models from resources/models and ensures they are accessible."""
        candidates = []
        # 1. Next to executable
        candidates.append(get_app_dir() / "resources" / "models")
        # 2. Inside PyInstaller temp bundle
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "resources" / "models")
            candidates.append(Path(sys._MEIPASS) / "data" / "models")
        # 3. Development tree
        candidates.append(Path(__file__).resolve().parent.parent.parent.parent / "resources" / "models")

        for c_dir in candidates:
            if c_dir.exists() and c_dir != self.models_dir:
                try:
                    for f in c_dir.glob("*"):
                        if f.is_file():
                            target = self.models_dir / f.name
                            if not target.exists() or target.stat().st_size != f.stat().st_size:
                                shutil.copy2(f, target)
                                logger.info(f"Synchronized pre-installed model: {f.name} ({f.stat().st_size / 1024 / 1024:.1f} MB)")
                except Exception as e:
                    logger.debug(f"Could not auto-copy bundled models from {c_dir}: {e}")

    def get_model_path(self, model_id: str) -> Optional[Path]:
        """Returns the local path to the model if it exists and is complete."""
        info = MODEL_CATALOGUE.get(model_id)
        if not info:
            return None
        target_path = self.models_dir / info.filename
        if target_path.exists() and target_path.stat().st_size > 1000:
            return target_path
        
        # Fallback to direct check in resources/models
        candidates = [
            get_app_dir() / "resources" / "models" / info.filename,
            Path(__file__).resolve().parent.parent.parent.parent / "resources" / "models" / info.filename,
        ]
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.insert(0, Path(sys._MEIPASS) / "resources" / "models" / info.filename)

        for c in candidates:
            if c.exists() and c.stat().st_size > 1000:
                return c
        return None

    def is_model_downloaded(self, model_id: str) -> bool:
        """Checks if a model exists locally with expected size."""
        path = self.get_model_path(model_id)
        if not path or not path.exists():
            return False
        info = MODEL_CATALOGUE.get(model_id)
        if not info:
            return False
        min_expected = (info.size_mb * 0.85) * 1024 * 1024
        return path.stat().st_size >= min_expected

    def is_vector_search_ready(self) -> bool:
        """Returns true if both embedding model and tokenizer are downloaded."""
        return (
            self.is_model_downloaded("embedding-multilingual-minilm")
            and self.is_model_downloaded("embedding-tokenizer")
        )

    def get_active_or_recommended_slm_id(self, preferred_id: Optional[str] = None) -> str:
        """
        Returns the best SLM ID: checks if a model is downloaded or recommends based on hardware.
        """
        if preferred_id and self.is_model_downloaded(preferred_id):
            return preferred_id

        # Check in order: 1.5b -> 0.5b -> 3b
        for mid in ["qwen2.5-1.5b", "qwen2.5-0.5b", "qwen2.5-3b"]:
            if self.is_model_downloaded(mid):
                return mid

        # Fallback to hardware spec recommendation
        specs = detect_hardware_specs()
        return specs.recommended_model_id

    def cancel_download(self):
        self._cancel_flag = True

    def download_model(
        self,
        model_id: str,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
    ) -> bool:
        """
        Downloads a model from HuggingFace with progress reporting and cancellation support.
        progress_callback: (downloaded_bytes, total_bytes, percent)
        """
        info = MODEL_CATALOGUE.get(model_id)
        if not info:
            logger.error(f"Unknown model id: {model_id}")
            return False

        target_path = self.models_dir / info.filename
        temp_path = self.models_dir / f"{info.filename}.part"
        self._cancel_flag = False

        logger.info(f"Downloading model '{info.name}' from {info.download_url} to {target_path}")

        try:
            headers = {"User-Agent": "Indexo-Desktop-App/1.0"}
            response = requests.get(info.download_url, stream=True, timeout=30, headers=headers)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", int(info.size_mb * 1024 * 1024)))
            downloaded = 0
            chunk_size = 1024 * 512  # 512 KB chunks

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self._cancel_flag:
                        logger.warning(f"Download of {model_id} cancelled by user.")
                        temp_path.unlink(missing_ok=True)
                        return False

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        percent = (downloaded / total_size) * 100 if total_size > 0 else 0.0
                        if progress_callback:
                            progress_callback(downloaded, total_size, percent)

            # Move temp file to final target
            if temp_path.exists():
                temp_path.replace(target_path)

            logger.info(f"Model '{info.name}' downloaded successfully ({target_path.stat().st_size} bytes).")
            return True

        except Exception as e:
            logger.error(f"Failed to download model {model_id}: {e}")
            temp_path.unlink(missing_ok=True)
            return False

    def delete_model(self, model_id: str) -> bool:
        """Unloads and deletes a model file from data/models/ to free disk space."""
        info = MODEL_CATALOGUE.get(model_id)
        if not info:
            logger.error(f"Unknown model id: {model_id}")
            return False

        try:
            from app.ai.llm_engine import LLMEngine
            LLMEngine.get_instance().unload_model()
        except Exception:
            pass

        target_path = self.models_dir / info.filename
        if target_path.exists():
            try:
                target_path.unlink()
                logger.info(f"Model '{info.name}' ({target_path}) deleted from disk.")
                return True
            except Exception as e:
                logger.error(f"Failed to delete model file {target_path}: {e}")
                return False
        return True
