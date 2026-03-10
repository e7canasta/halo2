"""Gemini agent with autonomous roles.

GeminiAgent orchestrates 3 roles:
1. Fallback Classifier - final decision maker when all classifiers fail
2. Quality Validator - validates classifications before golden dataset
3. Template Master - improves templates and slots with "agency"
"""

from .gemini_agent import GeminiAgent
from .quality_validator import QualityValidator, ValidationResult
from .template_master import TemplateMaster, TemplateImprovement
from .model_config import ModelConfig

__all__ = [
    "GeminiAgent",
    "QualityValidator",
    "ValidationResult",
    "TemplateMaster",
    "TemplateImprovement",
    "ModelConfig",
]
