"""spaCy model provider with singleton pattern.

CRITICAL: Only ONE spaCy model instance in memory (40MB).
Follows same pattern as embeddings.py for consistency.
"""

import spacy
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)

_nlp_instance: Optional[spacy.Language] = None
_custom_model_loaded: bool = False


def get_nlp() -> spacy.Language:
    """Get global spaCy instance (singleton).

    Loads custom model if exists, otherwise base model.

    CRITICAL: Only ONE spaCy model in memory (40MB).

    Returns:
        spacy.Language: spaCy model instance
    """
    global _nlp_instance, _custom_model_loaded

    if _nlp_instance is None:
        custom_path = "models/ner_custom"

        if os.path.exists(custom_path):
            logger.info(f"Loading custom NER model from {custom_path}")
            try:
                _nlp_instance = spacy.load(custom_path)
                _custom_model_loaded = True
            except Exception as e:
                logger.error(f"Failed to load custom model: {e}, falling back to base")
                _nlp_instance = spacy.load("es_core_news_md")
                _custom_model_loaded = False
        else:
            logger.info("Loading base model: es_core_news_md")
            try:
                _nlp_instance = spacy.load("es_core_news_md")
                _custom_model_loaded = False
            except OSError:
                logger.error(
                    "Model 'es_core_news_md' not found. "
                    "Install with: python -m spacy download es_core_news_md"
                )
                raise

        logger.info(f"spaCy model loaded (custom={_custom_model_loaded})")

    return _nlp_instance


def reload_nlp() -> spacy.Language:
    """Reload spaCy model (after fine-tuning).

    Returns:
        spacy.Language: Reloaded spaCy model
    """
    global _nlp_instance
    _nlp_instance = None
    return get_nlp()


def is_custom_model_loaded() -> bool:
    """Check if custom model is loaded.

    Returns:
        bool: True if custom model loaded, False if base model
    """
    return _custom_model_loaded
