import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple, Union
from loguru import logger

try:
    import onnxruntime as ort
    from tokenizers import Tokenizer
    ONNX_AVAILABLE = True
except Exception as e:
    logger.warning("onnxruntime/tokenizers initialization notice: {}", e)
    ONNX_AVAILABLE = False
    ort = None
    Tokenizer = None

from app.ai.model_manager import ModelManager


class VectorEngine:
    """
    Ultra-lightweight and fast vector embedding engine powered by ONNX Runtime.
    Uses MiniLM / Multilingual MiniLM to compute 384-dim normalized semantic embeddings
    in ~2-5ms per document on CPU.
    """

    _instance: Optional["VectorEngine"] = None

    def __init__(self, model_manager: Optional[ModelManager] = None):
        self.model_manager = model_manager or ModelManager()
        self.tokenizer = None
        self.session = None
        self._is_ready = False
        self._dimension = 384

    @classmethod
    def get_instance(cls) -> "VectorEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_ready(self) -> bool:
        if self._is_ready:
            return True
        return self._try_init()

    def _try_init(self) -> bool:
        if not ONNX_AVAILABLE:
            logger.warning("ONNX Runtime or Tokenizers not installed. Vector search unavailable.")
            return False

        if not self.model_manager.is_vector_search_ready():
            return False

        try:
            model_path = self.model_manager.get_model_path("embedding-multilingual-minilm")
            tokenizer_path = self.model_manager.get_model_path("embedding-tokenizer")

            if not model_path or not tokenizer_path:
                return False

            logger.info(f"Loading ONNX embedding model from {model_path}...")
            self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
            self.tokenizer.enable_truncation(max_length=256)
            self.tokenizer.enable_padding(length=256)

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self.session = ort.InferenceSession(
                str(model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"]
            )
            self._is_ready = True
            logger.info("VectorEngine successfully initialized with ONNX Runtime.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize VectorEngine: {e}")
            self._is_ready = False
            return False

    def embed_text(self, text: str) -> Optional[np.ndarray]:
        """Generates a 384-dimensional normalized float32 vector for a single text."""
        if not text or not text.strip():
            return None

        results = self.embed_batch([text])
        if results and len(results) > 0:
            return results[0]
        return None

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Generates normalized vectors for a batch of texts."""
        if not self.is_ready or not texts:
            return []

        try:
            cleaned = [t.strip().replace("\n", " ")[:1000] for t in texts]
            encodings = self.tokenizer.encode_batch(cleaned)

            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
            token_type_ids = np.zeros_like(input_ids, dtype=np.int64)

            # Check required input names in ONNX model
            input_names = [inp.name for inp in self.session.get_inputs()]
            feed_dict = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
            if "token_type_ids" in input_names:
                feed_dict["token_type_ids"] = token_type_ids

            outputs = self.session.run(None, feed_dict)
            token_embeddings = outputs[0]  # Shape: (batch_size, seq_len, hidden_dim)

            # Mean pooling over attention mask
            input_mask_expanded = np.expand_dims(attention_mask, -1).astype(np.float32)
            sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
            sum_mask = np.clip(input_mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
            mean_pooled = sum_embeddings / sum_mask

            # L2 Normalize
            norms = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
            normalized = mean_pooled / np.clip(norms, a_min=1e-9, a_max=None)

            return [normalized[i].astype(np.float32) for i in range(len(texts))]
        except Exception as e:
            logger.error(f"Error computing embeddings batch: {e}")
            return []

    @staticmethod
    def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Calculates cosine similarity between two unit vectors."""
        if vec_a is None or vec_b is None:
            return 0.0
        return float(np.dot(vec_a, vec_b))

    @staticmethod
    def search_similar(
        query_vector: np.ndarray,
        corpus_vectors: np.ndarray,
        corpus_ids: List[Union[int, str]],
        top_k: int = 20,
        min_score: float = 0.35,
    ) -> List[Tuple[Union[int, str], float]]:
        """
        Performs fast matrix multiplication search over pre-computed normalized vectors.
        corpus_vectors shape: (N, 384)
        """
        if query_vector is None or corpus_vectors.size == 0 or len(corpus_ids) == 0:
            return []

        # Vectorized dot product against all rows
        scores = np.dot(corpus_vectors, query_vector)
        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score >= min_score:
                results.append((corpus_ids[idx], round(score, 4)))

        return results
