"""
AI Subsystem for Indexo: Vector Search, SLM Inference, Model Management and AI Diagnostics.
"""

from app.ai.hardware_specs import detect_hardware_specs, HardwareProfile
from app.ai.model_manager import ModelManager, MODEL_CATALOGUE, ModelInfo
from app.ai.vector_engine import VectorEngine
from app.ai.llm_engine import LLMEngine, ClassificationResult
from app.ai.semantic_classifier import SemanticClassifier, SemanticClassificationOutput
from app.ai.ai_tester import AITester, AITestDiagnosis

__all__ = [
    "detect_hardware_specs",
    "HardwareProfile",
    "ModelManager",
    "MODEL_CATALOGUE",
    "ModelInfo",
    "VectorEngine",
    "LLMEngine",
    "ClassificationResult",
    "SemanticClassifier",
    "SemanticClassificationOutput",
    "AITester",
    "AITestDiagnosis",
]
