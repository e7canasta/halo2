"""Intent classification system with Chain of Responsibility pattern."""

from .base import IntentClassifier, ClassificationResult
from .chain import ClassifierChain
from .policy_chain import PolicyDrivenChain
from .envelope import ClassificationEnvelope, Decision
from .policies import ChainPolicy, ThresholdPolicy, CarePolicy, ConsensusPolicy
from .interceptors import (
    ChainInterceptor,
    TelemetryInterceptor,
    LearningInterceptor,
    AlertInterceptor,
    ClassificationLogInterceptor,
)
from .classifiers import (
    ExactMatchClassifier,
    EmbeddingClassifier,
    KeywordClassifier,
    LLMClassifier,
)

__all__ = [
    # Legacy
    "IntentClassifier",
    "ClassificationResult",
    "ClassifierChain",
    # New policy-driven
    "PolicyDrivenChain",
    "ClassificationEnvelope",
    "Decision",
    "ChainPolicy",
    "ThresholdPolicy",
    "CarePolicy",
    "ConsensusPolicy",
    "ChainInterceptor",
    "TelemetryInterceptor",
    "LearningInterceptor",
    "AlertInterceptor",
    "ClassificationLogInterceptor",
    # Classifiers
    "ExactMatchClassifier",
    "EmbeddingClassifier",
    "KeywordClassifier",
    "LLMClassifier",
]
