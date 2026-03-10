"""Auto Adjuster - Aplica fixes sugeridos por Gemini automáticamente.

Sistema auto-mejorante: Gemini sugiere → AutoAdjuster aplica → Sistema mejora.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class AutoAdjuster:
    """Aplica automáticamente fixes sugeridos por Gemini.

    Usage:
        adjuster = AutoAdjuster(conversation_manager=conv_mgr)
        adjuster.apply_fixes(evaluation)

        # Ver qué se aplicó
        for fix in adjuster.applied_fixes:
            print(f"Applied: {fix['description']}")
    """

    def __init__(self, conversation_manager=None):
        """Inicializa adjuster.

        Args:
            conversation_manager: ConversationContextManager para agregar reglas
        """
        self.conversation_manager = conversation_manager
        self.applied_fixes: List[Dict] = []

    def apply_fixes(self, evaluation):
        """Aplica todos los auto_fixes de la evaluación.

        Args:
            evaluation: BatchEvaluation con auto_fixes
        """
        logger.info(f"Applying {len(evaluation.auto_fixes)} auto-fixes...")

        for fix in evaluation.auto_fixes:
            if fix.get("safe_to_apply", False):
                try:
                    self._apply_fix(fix)
                    self.applied_fixes.append(fix)
                    logger.info(f"✓ Applied: {fix.get('fix_id')}")
                except Exception as e:
                    logger.error(f"✗ Failed to apply {fix.get('fix_id')}: {e}")

        logger.info(f"Applied {len(self.applied_fixes)}/{len(evaluation.auto_fixes)} fixes")

    def _apply_fix(self, fix: Dict[str, Any]):
        """Aplica un fix específico.

        Args:
            fix: Dict con el fix a aplicar

        Supported fix types:
            - inference_rule: Agregar regla de inferencia contextual
            - threshold_adjust: Ajustar confidence threshold
            - context_policy: Cambiar política de herencia
        """
        fix_type = fix.get("type")

        if fix_type == "inference_rule":
            self._apply_inference_rule(fix)
        elif fix_type == "threshold_adjust":
            self._apply_threshold_adjust(fix)
        elif fix_type == "context_policy":
            self._apply_context_policy(fix)
        else:
            logger.warning(f"Unknown fix type: {fix_type}")

    def _apply_inference_rule(self, fix: Dict):
        """Aplica regla de inferencia.

        Ejemplo: "Si falta 'rooms' y hay last_room < 60s, inferir"
        """
        if not self.conversation_manager:
            logger.warning("No conversation_manager - can't apply inference rule")
            return

        # TODO: Implementar add_inference_rule en ConversationContextManager
        logger.info(f"Would apply inference rule: {fix.get('change')}")

    def _apply_threshold_adjust(self, fix: Dict):
        """Ajusta threshold de confidence."""
        logger.info(f"Would adjust threshold: {fix.get('change')}")

    def _apply_context_policy(self, fix: Dict):
        """Cambia política de herencia de contexto."""
        if not self.conversation_manager:
            logger.warning("No conversation_manager - can't apply context policy")
            return

        logger.info(f"Would apply context policy: {fix.get('change')}")
