"""Factory for building classifier chains.

Configuración centralizada de la cadena de clasificadores.
"""

from .chain import ClassifierChain
from .policy_chain import PolicyDrivenChain
from .policies import ThresholdPolicy, CarePolicy
from .interceptors import TelemetryInterceptor, LearningInterceptor, ClassificationLogInterceptor
from .classifiers import (
    ExactMatchClassifier,
    EmbeddingClassifier,
    KeywordClassifier,
    LLMClassifier,
    SpaCySlotFiller,
    GeminiClassifier,
)
from .classifiers.functiongemma import FunctionGemmaClassifier
from ..backend import Backend
from ..storage import FileStore


# System prompt for LLM classifier
LLM_SYSTEM_PROMPT = """Asistente de hogar. Responde SOLO JSON.

Tools:
- light_control: {"action": "on|off|dim|brightness", "room": "sala|cocina|...", "level": 0-100}
- climate_control: {"action": "set_temp|mode|status", "room": "sala|...", "temperature": 22, "mode": "heat|cool|auto|off"}
- blinds_control: {"action": "open|close|position", "room": "sala|...", "position": 0-100}
- home_status: {"scope": "all|room|device", "room": "sala|..."}

Ejemplos:
"enciende la luz del salon" -> {"tool": "light_control", "parameters": {"action": "on", "room": "salon"}}
"como esta la casa?" -> {"tool": "home_status", "parameters": {"scope": "all"}}
"muestra el estado de todos los dispositivos" -> {"tool": "home_status", "parameters": {"scope": "all"}}
"pon el aire a 22 grados" -> {"tool": "climate_control", "parameters": {"action": "set_temp", "temperature": 22}}
"cierra las persianas de la cocina" -> {"tool": "blinds_control", "parameters": {"action": "close", "room": "cocina"}}
"gracias" -> {"response": "De nada! ¿Algo más?"}

Formato:
{"tool": "nombre_tool", "parameters": {...}}"""


def create_default_chain(
    backend: Backend,
    enable_embeddings: bool = True,
    enable_spacy: bool = True,
    enable_functiongemma: bool = False,
    functiongemma_model: str | None = None,
    enable_gemini: bool = False,
    gemini_api_key: str | None = None,
) -> ClassifierChain:
    """Create the default classifier chain for intent classification.

    Chain order (priority):
    1. ExactMatchClassifier (0ms, cached exact matches)
    2. EmbeddingClassifier (5-10ms, semantic similarity) [optional]
    3. SpaCySlotFiller (5-10ms, template + slot filling) [optional]
    4. FunctionGemmaClassifier (200-500ms, fine-tuned model) [optional]
    5. KeywordClassifier (<1ms, regex/keyword patterns)
    6. LLMClassifier (7s, Qwen fallback)
    7. GeminiClassifier (1-2s, API, "Yoda" final fallback) [optional]

    Args:
        backend: Backend instance for LLM classifier
        enable_embeddings: Whether to enable embedding classifier (requires sentence-transformers)
        enable_spacy: Whether to enable spaCy slot filler (requires spaCy)
        enable_functiongemma: Whether to enable FunctionGemma classifier
        functiongemma_model: Path to fine-tuned FunctionGemma model (or None for base)
        enable_gemini: Whether to enable Gemini as final fallback (requires API key)
        gemini_api_key: Google Gemini API key (or None to use GEMINI_API_KEY env var)

    Returns:
        Configured ClassifierChain
    """
    classifiers = [
        ExactMatchClassifier(),
    ]

    if enable_embeddings:
        try:
            classifiers.append(EmbeddingClassifier(similarity_threshold=0.85))
        except ImportError:
            # sentence-transformers not installed, skip
            pass

    if enable_spacy:
        try:
            classifiers.append(SpaCySlotFiller(confidence_boost=0.05))
        except ImportError:
            # spaCy not installed, skip
            pass

    # FunctionGemma classifier (if enabled and model available)
    if enable_functiongemma:
        try:
            model_path = functiongemma_model or "google/functiongemma-270m-it"
            classifiers.append(FunctionGemmaClassifier(model_path=model_path))
        except Exception as e:
            # FunctionGemma not available, skip
            import logging

            logging.warning(f"FunctionGemma classifier disabled: {e}")

    classifiers.extend(
        [
            KeywordClassifier(),
            LLMClassifier(backend, LLM_SYSTEM_PROMPT),
        ]
    )

    # Gemini classifier as final "Yoda" fallback (if enabled)
    if enable_gemini:
        try:
            classifiers.append(GeminiClassifier(api_key=gemini_api_key))
            import logging

            logging.info("Gemini 'Yoda' classifier enabled as final fallback")
        except Exception as e:
            # Gemini not available (likely no API key), skip
            import logging

            logging.warning(f"Gemini classifier disabled: {e}")

    return ClassifierChain(classifiers)


def create_policy_driven_chain(
    backend: Backend,
    policy: str = "threshold",
    enable_telemetry: bool = True,
    enable_learning: bool = True,
    store_path: str = "/var/halo",
    enable_embeddings: bool = True,
    enable_spacy: bool = True,
    enable_functiongemma: bool = False,
    functiongemma_model: str | None = None,
    enable_gemini: bool = False,
    gemini_api_key: str | None = None,
) -> PolicyDrivenChain:
    """Create a policy-driven classifier chain (next generation).

    Diferencias con create_default_chain:
    1. Usa PolicyDrivenChain con envelopes y métricas
    2. Policy configurable (threshold, care, consensus)
    3. Interceptors para observabilidad (telemetry, learning)
    4. File-based store para persistencia

    Args:
        backend: Backend instance for LLM classifier
        policy: Policy type ("threshold", "care", "consensus")
        enable_telemetry: Enable telemetry logging
        enable_learning: Enable learning from high-confidence classifications
        store_path: Path for file store (default: /var/halo)
        enable_embeddings: Whether to enable embedding classifier
        enable_spacy: Whether to enable spaCy slot filler
        enable_functiongemma: Whether to enable FunctionGemma classifier
        functiongemma_model: Path to fine-tuned FunctionGemma model
        enable_gemini: Whether to enable Gemini as final fallback
        gemini_api_key: Google Gemini API key

    Returns:
        Configured PolicyDrivenChain
    """
    # Create classifiers (same as default chain)
    classifiers = [
        ExactMatchClassifier(),
    ]

    if enable_embeddings:
        try:
            classifiers.append(EmbeddingClassifier(similarity_threshold=0.85))
        except ImportError:
            pass

    if enable_spacy:
        try:
            classifiers.append(SpaCySlotFiller(confidence_boost=0.05))
        except ImportError:
            pass

    if enable_functiongemma:
        try:
            model_path = functiongemma_model or "google/functiongemma-270m-it"
            classifiers.append(FunctionGemmaClassifier(model_path=model_path))
        except Exception as e:
            import logging
            logging.warning(f"FunctionGemma classifier disabled: {e}")

    classifiers.extend(
        [
            KeywordClassifier(),
            LLMClassifier(backend, LLM_SYSTEM_PROMPT),
        ]
    )

    if enable_gemini:
        try:
            classifiers.append(GeminiClassifier(api_key=gemini_api_key))
            import logging
            logging.info("Gemini 'Yoda' classifier enabled as final fallback")
        except Exception as e:
            import logging
            logging.warning(f"Gemini classifier disabled: {e}")

    # Create policy
    if policy == "threshold":
        chain_policy = ThresholdPolicy()
    elif policy == "care":
        chain_policy = CarePolicy()
    else:
        chain_policy = ThresholdPolicy()

    # Create chain
    chain = PolicyDrivenChain(classifiers, chain_policy)

    # Add interceptors
    if enable_telemetry or enable_learning:
        store = FileStore(store_path)

        if enable_telemetry:
            chain.add_interceptor(TelemetryInterceptor(store))
            chain.add_interceptor(ClassificationLogInterceptor(store))

        if enable_learning:
            chain.add_interceptor(LearningInterceptor(store, confidence_threshold=0.95))

    return chain
