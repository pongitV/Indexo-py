from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import QThread, Signal
from loguru import logger

from app.ai.model_manager import ModelManager
from app.ai.semantic_classifier import SemanticClassifier, SemanticClassificationOutput
from app.ai.vector_engine import VectorEngine
from app.ai.llm_engine import LLMEngine


class AIWorker(QThread):
    """
    Asynchronous worker thread for AI tasks:
    - Model downloads with live progress
    - Batch classification of files with SLM
    - Vector embeddings generation
    """

    # (current, total, message)
    progress_signal = Signal(int, int, str)
    # (model_id, downloaded_bytes, total_bytes, percent)
    download_progress_signal = Signal(str, int, int, float)
    # (result_dict)
    file_classified_signal = Signal(dict)
    # (list of result dicts)
    finished_signal = Signal(list)
    # (error_message)
    error_signal = Signal(str)

    def __init__(
        self,
        action: str,  # "classify_batch", "download_model", "embed_files"
        files_to_classify: Optional[List[Dict[str, Any]]] = None,
        model_id_to_download: Optional[str] = None,
        existing_categories: Optional[List[str]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.action = action
        self.files_to_classify = files_to_classify or []
        self.model_id_to_download = model_id_to_download
        self.existing_categories = existing_categories or []
        self._is_cancelled = False
        self.model_manager = ModelManager()

    def cancel(self):
        self._is_cancelled = True
        self.model_manager.cancel_download()

    def run(self):
        try:
            if self.action == "download_model":
                self._run_download()
            elif self.action == "classify_batch":
                self._run_classify_batch()
            elif self.action == "embed_files":
                self._run_embed_files()
        except Exception as e:
            logger.error(f"Error in AIWorker ({self.action}): {e}")
            self.error_signal.emit(str(e))

    def _run_download(self):
        if not self.model_id_to_download:
            self.error_signal.emit("No model specified for download.")
            return

        def on_progress(downloaded, total, percent):
            self.download_progress_signal.emit(
                self.model_id_to_download, downloaded, total, percent
            )

        success = self.model_manager.download_model(
            self.model_id_to_download, progress_callback=on_progress
        )

        if success:
            self.finished_signal.emit([{"status": "success", "model_id": self.model_id_to_download}])
        else:
            if not self._is_cancelled:
                self.error_signal.emit(f"Falha ao baixar o modelo {self.model_id_to_download}.")

    def _run_classify_batch(self):
        classifier = SemanticClassifier()
        total = len(self.files_to_classify)
        results = []

        logger.info(f"AIWorker starting batch classification of {total} files...")

        for idx, item in enumerate(self.files_to_classify, 1):
            if self._is_cancelled:
                logger.info("Batch classification cancelled by user.")
                break

            rel_path = item.get("rel_path", "")
            ext = item.get("ext", Path(rel_path).suffix.lower())
            size = item.get("size", 0)
            text = item.get("text", "")
            initial = item.get("initial_candidate")

            self.progress_signal.emit(idx, total, f"Analisando com IA: {Path(rel_path).name}")

            out = classifier.classify_single_file(
                rel_path=rel_path,
                ext=ext,
                size_bytes=size,
                extracted_text=text,
                initial_candidate=initial,
                existing_categories=self.existing_categories,
                force_ai=True,
            )

            res_dict = out.to_dict()
            results.append(res_dict)
            self.file_classified_signal.emit(res_dict)

        self.finished_signal.emit(results)

    def _run_embed_files(self):
        vector_engine = VectorEngine.get_instance()
        if not vector_engine.is_ready:
            self.error_signal.emit("Motor de busca vetorial não está inicializado.")
            return

        total = len(self.files_to_classify)
        results = []

        for idx, item in enumerate(self.files_to_classify, 1):
            if self._is_cancelled:
                break

            rel_path = item.get("rel_path", "")
            text = f"{Path(rel_path).name} {item.get('text', '')[:400]}"
            self.progress_signal.emit(idx, total, f"Gerando vetor: {Path(rel_path).name}")

            vec = vector_engine.embed_text(text)
            if vec is not None:
                results.append({"rel_path": rel_path, "vector": vec})

        self.finished_signal.emit(results)
