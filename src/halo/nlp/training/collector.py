"""Dataset collector for golden dataset generation.

Captures successful classifications with slot information for
incremental fine-tuning of spaCy NER model.
"""

import json
import hashlib
import time
import logging
from pathlib import Path
from typing import Optional
from ..provider import get_nlp
from ..slots import SlotExtractor, SlotInfo

logger = logging.getLogger(__name__)


class DatasetCollector:
    """Captures successful classifications for golden dataset.

    Inclusion criteria:
    - Execution successful (status == "completed")
    - Confidence >= threshold
    - Not duplicate (hash of normalized text)

    The golden dataset is used for incremental fine-tuning.
    """

    def __init__(
        self,
        dataset_path: str = "data/golden_dataset.jsonl",
        confidence_threshold: float = 0.85,
    ):
        self.dataset_path = Path(dataset_path)
        self.confidence_threshold = confidence_threshold
        self._seen_hashes = set()
        self._load_existing_hashes()

        # Ensure data directory exists
        self.dataset_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_existing_hashes(self):
        """Load hashes of existing examples to prevent duplicates."""
        if not self.dataset_path.exists():
            return

        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    text_hash = self._hash(record["text"])
                    self._seen_hashes.add(text_hash)
        except Exception as e:
            logger.error(f"Error loading existing hashes: {e}")

    def _hash(self, text: str) -> str:
        """Hash normalized text for deduplication.

        Args:
            text: Input text

        Returns:
            SHA256 hash hex string
        """
        normalized = text.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def collect(
        self,
        user_input: str,
        tool_name: str,
        parameters: dict,
        confidence: float,
        classifier_used: str,
        execution_status: str,
        synthetic: bool = False,
        slots_provided: Optional[dict] = None,
    ) -> bool:
        """Capture example if it meets criteria.

        Args:
            user_input: User's input text
            tool_name: Tool that was called
            parameters: Parameters used
            confidence: Classification confidence
            classifier_used: Which classifier was used
            execution_status: Execution status (e.g., "completed")
            synthetic: If True, example is synthetically generated (skip some checks)
            slots_provided: Pre-computed slots (for synthetic examples)

        Returns:
            True if captured, False otherwise
        """
        # Synthetic examples skip execution and confidence checks
        if not synthetic:
            # Check execution status
            if execution_status != "completed":
                logger.debug(f"Skipping collection: execution not completed ({execution_status})")
                return False

            # Check confidence
            if confidence < self.confidence_threshold:
                logger.debug(
                    f"Skipping collection: low confidence ({confidence:.2f} < {self.confidence_threshold})"
                )
                return False

        # Check for duplicates
        text_hash = self._hash(user_input)
        if text_hash in self._seen_hashes:
            logger.debug(f"Skipping collection: duplicate input")
            return False

        try:
            # Extract or use provided slots
            if slots_provided:
                slots = slots_provided
            else:
                # Extract slots using spaCy
                nlp = get_nlp()
                doc = nlp(user_input)
                slots = SlotExtractor.extract_slots(doc, parameters)

            # Create record
            record = {
                "text": user_input,
                "tool": tool_name,
                "params": parameters,
                "slots": {
                    k: {
                        "value": v.value,
                        "start": v.start,
                        "end": v.end,
                        "dep": v.dep,
                        "head": v.head,
                        "pos": v.pos,
                    }
                    for k, v in slots.items()
                },
                "confidence": confidence,
                "classifier": classifier_used,
                "timestamp": int(time.time()),
                "synthetic": synthetic,  # NEW: flag synthetic examples
            }

            # Append to dataset
            self._append_to_dataset(record)
            self._seen_hashes.add(text_hash)

            source = "synthetic" if synthetic else "real"
            logger.info(
                f"Collected {source} example: {user_input} -> {tool_name} (slots={len(slots)})"
            )
            return True

        except Exception as e:
            logger.error(f"Error collecting example: {e}")
            return False

    def _append_to_dataset(self, record: dict):
        """Append record to JSONL dataset.

        Args:
            record: Dataset record
        """
        with open(self.dataset_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def get_stats(self) -> dict:
        """Get dataset statistics.

        Returns:
            Dict with stats (count, tools, etc.)
        """
        if not self.dataset_path.exists():
            return {"count": 0, "tools": {}}

        tool_counts = {}
        total = 0

        try:
            with open(self.dataset_path, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    tool_name = record["tool"]
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                    total += 1
        except Exception as e:
            logger.error(f"Error getting stats: {e}")

        return {"count": total, "tools": tool_counts}
