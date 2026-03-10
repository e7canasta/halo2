"""Gemini Evaluator - Analiza batch de corridas para encontrar patterns.

Similar a ML evaluation: analiza el "dataset" de corridas y encuentra:
- Patterns de error sistemáticos
- Confusion matrix (qué se confunde con qué)
- Context handling (cuándo usa/pierde contexto)
- Recomendaciones globales
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from ..testing.scenario_types import RunHistory

logger = logging.getLogger(__name__)


@dataclass
class DecisionEvaluation:
    """Evaluación de una decisión específica."""
    decision_id: str
    verdict: str  # "correct", "suboptimal", "incorrect"
    confidence: float
    reasoning: str
    suggestion: Optional[Dict[str, Any]] = None


@dataclass
class BatchEvaluation:
    """Evaluación de batch de corridas (como ML evaluation)."""
    summary: Dict[str, Any]
    patterns: Dict[str, List[Dict]]
    confusion_matrix: Dict[str, Dict]
    context_analysis: Dict[str, Any]
    global_recommendations: List[Dict]
    auto_fixes: List[Dict]


class GeminiEvaluator:
    """Evalúa batch de corridas para encontrar patterns (como ML evaluation).

    Usage:
        evaluator = GeminiEvaluator()
        evaluation = evaluator.evaluate_run_history(run_history)

        print(f"Quality: {evaluation.summary['overall_quality']}")
        print(f"Auto-fixes: {len(evaluation.auto_fixes)}")
    """

    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        """Inicializa evaluator.

        Args:
            model_name: Nombre del modelo Gemini a usar
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai not available. Install with: pip install google-generativeai")

        self.model = genai.GenerativeModel(model_name)

    def evaluate_run_history(self, history: RunHistory) -> BatchEvaluation:
        """Evalúa dataset completo de corridas (big picture analysis).

        Args:
            history: RunHistory con todas las corridas

        Returns:
            BatchEvaluation con patterns y recomendaciones
        """
        logger.info(f"Evaluating {len(history.runs)} runs with Gemini...")

        prompt = self._build_batch_evaluation_prompt(history)

        try:
            response = self.model.generate_content(prompt)
            evaluation = self._parse_evaluation(response.text)
            logger.info(f"Evaluation complete: {evaluation.summary['overall_quality']}")
            return evaluation
        except Exception as e:
            logger.error(f"Gemini evaluation failed: {e}")
            raise

    def _build_batch_evaluation_prompt(self, history: RunHistory) -> str:
        """Construye prompt para evaluación batch.

        Args:
            history: RunHistory

        Returns:
            Prompt string
        """
        eval_data = history.to_evaluation_format()

        return f"""
# ROL: ML Engineer / System Evaluator
Sos un experto evaluando sistemas de IA. Tenés un dataset de {len(history.runs)} corridas
con {history.total_decisions} decisiones totales.

## MÉTRICAS GENERALES
- Total corridas: {len(history.runs)}
- Pass rate: {history.pass_rate:.1%}
- Total decisiones: {history.total_decisions}
- Decisiones por agente: {history.decisions_by_agent}

## DATOS DE CORRIDAS
{self._format_runs_summary(history)}

---

# TU TAREA

Analizá el dataset completo como si fuera un training set de ML:

## 1. ANÁLISIS DE PATTERNS
- ¿Qué decisiones se repiten?
- ¿Hay errores sistemáticos?
- ¿Qué classifiers fallan más?

## 2. CONFUSION MATRIX (Clasificación)
- ¿Qué tools se confunden entre sí?

## 3. CONTEXT HANDLING
- ¿El sistema usa bien el contexto conversacional?
- ¿Pierde información entre turnos?

## 4. RECOMENDACIONES GLOBALES
- Fixes que aplican a TODO el sistema
- Patterns que aprender

---

# OUTPUT (JSON)

{{
  "summary": {{
    "overall_quality": "good|acceptable|poor",
    "pass_rate": {history.pass_rate:.2f},
    "main_issues": ["..."],
    "main_strengths": ["..."]
  }},

  "patterns": {{
    "systematic_errors": [
      {{
        "pattern": "Cuando X siempre falla en Y",
        "frequency": 0.7,
        "fix": "..."
      }}
    ],
    "successful_patterns": [...]
  }},

  "confusion_matrix": {{}},

  "context_analysis": {{
    "inheritance_rate": 0.8,
    "missed_opportunities": [...]
  }},

  "global_recommendations": [
    {{
      "type": "training_data|rule|context_policy",
      "action": "...",
      "impact": "high|medium|low"
    }}
  ],

  "auto_fixes": [
    {{
      "fix_id": "fix_001",
      "type": "inference_rule|threshold_adjust|...",
      "safe_to_apply": true,
      "change": "..."
    }}
  ]
}}
"""

    def _format_runs_summary(self, history: RunHistory) -> str:
        """Formatea resumen de corridas para el prompt."""
        lines = []
        for run in history.runs[:10]:  # Primeras 10 corridas
            status = "✓" if run.passed else "✗"
            lines.append(f"- [{status}] {run.scenario_name} ({len(run.all_decisions)} decisions)")

        if len(history.runs) > 10:
            lines.append(f"... y {len(history.runs) - 10} más")

        return "\n".join(lines)

    def _parse_evaluation(self, response_text: str) -> BatchEvaluation:
        """Parse respuesta de Gemini."""
        # Extract JSON from markdown if present
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            # Return empty evaluation
            return BatchEvaluation(
                summary={"overall_quality": "unknown", "pass_rate": 0},
                patterns={},
                confusion_matrix={},
                context_analysis={},
                global_recommendations=[],
                auto_fixes=[]
            )

        return BatchEvaluation(
            summary=data.get("summary", {}),
            patterns=data.get("patterns", {}),
            confusion_matrix=data.get("confusion_matrix", {}),
            context_analysis=data.get("context_analysis", {}),
            global_recommendations=data.get("global_recommendations", []),
            auto_fixes=data.get("auto_fixes", [])
        )
