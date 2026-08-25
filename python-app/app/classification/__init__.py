"""
Classification and Tag Discovery Module for Indexo.
"""

from app.classification.similarity_engine import SimilarityEngine, CohesiveBundle
from app.classification.tag_discovery import TagDiscoveryEngine
from app.classification.rule_loader import RuleLoader
from app.classification.confidence import is_high_confidence, should_suggest, format_scores_breakdown

__all__ = [
    "SimilarityEngine",
    "CohesiveBundle",
    "TagDiscoveryEngine",
    "RuleLoader",
    "is_high_confidence",
    "should_suggest",
    "format_scores_breakdown",
]
