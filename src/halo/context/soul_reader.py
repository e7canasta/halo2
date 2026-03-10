"""Soul Reader - carga el alma de Halo al iniciar.

El alma define quién es este Halo y persiste entre reinicios.
"""

import logging
from pathlib import Path

from ..storage import FileStore
from .levels import SoulContext

logger = logging.getLogger(__name__)


class SoulReader:
    """Lee el alma de Halo desde el file store.

    El alma incluye:
    - manifest.md: Quién es este Halo
    - personality.json: Voz, tono, límites
    - relationships/: Conocimiento de usuarios/operadores
    """

    def __init__(self, store: FileStore):
        self.store = store

    def load(self) -> SoulContext:
        """Carga el alma completa de Halo.

        Returns:
            SoulContext con manifest, personality y relationships
        """
        # Cargar manifest
        manifest = self.store.read_manifest()
        if not manifest:
            logger.warning("No manifest.md found. Using default empty manifest.")
            manifest = "# Halo\n\nNo manifest configured."

        # Cargar personality
        personality = self.store.read("soul", "personality")
        if not personality:
            logger.warning("No personality.json found. Using default personality.")
            personality = {
                "voice": {"tone": "neutral", "style": "direct"},
                "constraints": {},
            }

        # Cargar relaciones
        relationships = {}
        rel_keys = self.store.list_keys("soul/relationships")
        for rel_id in rel_keys:
            rel_data = self.store.read("soul/relationships", rel_id)
            if rel_data:
                relationships[rel_id] = rel_data
                logger.info(f"Loaded relationship: {rel_id}")

        # Cargar preferencias aprendidas
        learned = self.store.read("soul", "learned_preferences") or {}

        soul = SoulContext(
            manifest=manifest,
            personality=personality,
            relationships=relationships,
            learned_preferences=learned.get("preferences", {}),
            trust_score=learned.get("trust_score", 0.0),
            days_active=learned.get("days_active", 0),
        )

        logger.info(
            f"Soul loaded: {len(relationships)} relationships, "
            f"trust_score={soul.trust_score:.2f}, "
            f"days_active={soul.days_active}"
        )

        return soul

    def get_domain(self) -> str:
        """Intenta detectar el dominio de Halo basado en el manifest.

        Returns:
            "home", "care", o "unknown"
        """
        manifest = self.store.read_manifest().lower()

        if "home" in manifest or "casa" in manifest or "ernesto" in manifest:
            return "home"
        elif "care" in manifest or "carla" in manifest or "residencia" in manifest:
            return "care"
        else:
            return "unknown"

    def get_personality_trait(self, trait_path: str, default=None):
        """Obtiene un trait específico de personality.

        Args:
            trait_path: Path en formato "voice.tone" o "constraints.temperature.min"
            default: Valor por defecto si no existe

        Returns:
            Valor del trait o default
        """
        soul = self.load()
        parts = trait_path.split(".")

        value = soul.personality
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value
