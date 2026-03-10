"""NLP module for spaCy integration and slot filling."""

from .provider import get_nlp, reload_nlp, is_custom_model_loaded

__all__ = ["get_nlp", "reload_nlp", "is_custom_model_loaded"]
