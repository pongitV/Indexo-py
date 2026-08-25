from typing import Dict, Any

DEFAULT_CONFIDENCE_THRESHOLD = 0.85
SUGGESTION_THRESHOLD = 0.40

def is_high_confidence(confidence: float, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> bool:
    return confidence >= threshold

def should_suggest(confidence: float) -> bool:
    return confidence >= SUGGESTION_THRESHOLD

def format_scores_breakdown(scores: Dict[str, float]) -> str:
    """Formats scores breakdown for 'Why?' tooltip: 'conteúdo X · tipo Y · origem Z'."""
    conteudo = scores.get("conteudo", 0.0)
    tipo = scores.get("tipo", 0.0)
    origem = scores.get("origem", 0.0)
    return f"conteúdo {conteudo:.2f} · tipo {tipo:.2f} · origem {origem:.2f}"
