"""Incremental spaCy NER trainer for home automation entities.

Trains custom NER model on golden dataset with incremental updates.
"""

import json
import random
import spacy
from spacy.training import Example
from pathlib import Path
import logging
from typing import List, Tuple
from ..entities import CUSTOM_ENTITY_LABELS

logger = logging.getLogger(__name__)


class SpaCyNERTrainer:
    """Incremental NER trainer for custom entities.

    Trains spaCy NER on golden dataset with checkpoint support
    for incremental learning.

    Usage:
        trainer = SpaCyNERTrainer()
        metrics = trainer.train(epochs=10)
    """

    def __init__(
        self,
        base_model: str = "es_core_news_md",
        custom_model_path: str = "models/ner_custom",
        dataset_path: str = "data/golden_dataset.jsonl",
        checkpoint_path: str = "models/.checkpoint",
    ):
        self.base_model = base_model
        self.custom_model_path = Path(custom_model_path)
        self.dataset_path = Path(dataset_path)
        self.checkpoint_path = Path(checkpoint_path)
        self._last_trained_count = self._load_checkpoint()

    def _load_checkpoint(self) -> int:
        """Load last training checkpoint.

        Returns:
            Number of examples trained on previously
        """
        if not self.checkpoint_path.exists():
            return 0

        try:
            with open(self.checkpoint_path, "r") as f:
                data = json.load(f)
                return data.get("examples_trained", 0)
        except Exception as e:
            logger.warning(f"Could not load checkpoint: {e}")
            return 0

    def _save_checkpoint(self, examples_trained: int):
        """Save training checkpoint.

        Args:
            examples_trained: Total number of examples trained
        """
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.checkpoint_path, "w") as f:
            json.dump({"examples_trained": examples_trained}, f)

    def _load_model(self) -> spacy.Language:
        """Load model (custom if exists, base otherwise).

        Returns:
            spaCy Language model
        """
        if self.custom_model_path.exists():
            logger.info(f"Loading custom model from {self.custom_model_path}")
            return spacy.load(self.custom_model_path)
        else:
            logger.info(f"Loading base model: {self.base_model}")
            return spacy.load(self.base_model)

    def _load_new_examples(self) -> List[dict]:
        """Load only new examples since last checkpoint.

        Returns:
            List of new example records
        """
        if not self.dataset_path.exists():
            logger.warning(f"Dataset not found: {self.dataset_path}")
            return []

        all_examples = []
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                all_examples.append(json.loads(line))

        # Get only new examples
        new_examples = all_examples[self._last_trained_count :]
        logger.info(
            f"Loaded {len(new_examples)} new examples "
            f"(total: {len(all_examples)}, trained: {self._last_trained_count})"
        )
        return new_examples

    def _prepare_training_data(
        self, examples: List[dict]
    ) -> Tuple[List[Example], List[Example]]:
        """Convert golden dataset to spaCy training format.

        Args:
            examples: List of dataset records

        Returns:
            Tuple of (train_examples, test_examples)
        """
        nlp = self._load_model()
        spacy_examples = []

        for record in examples:
            text = record["text"]
            slots = record.get("slots", {})

            # Convert slots to entities format
            entities = []
            for param_name, slot_info in slots.items():
                # Map param to entity label
                label = self._param_to_label(param_name)
                if label:
                    entities.append((slot_info["start"], slot_info["end"], label))

            # Create spaCy Example
            doc = nlp.make_doc(text)
            example = Example.from_dict(doc, {"entities": entities})
            spacy_examples.append(example)

        # Split train/test (80/20)
        random.shuffle(spacy_examples)
        split_idx = int(len(spacy_examples) * 0.8)
        train_data = spacy_examples[:split_idx]
        test_data = spacy_examples[split_idx:]

        logger.info(f"Prepared {len(train_data)} train, {len(test_data)} test examples")
        return train_data, test_data

    def _param_to_label(self, param_name: str) -> str | None:
        """Map parameter name to NER label.

        Args:
            param_name: Parameter name (e.g., "room", "temperature")

        Returns:
            NER label or None
        """
        mapping = {
            "room": "ROOM",
            "temperature": "NUMBER",
            "level": "NUMBER",
            "position": "NUMBER",
            "action": "ACTION",
            "device": "DEVICE",
        }
        return mapping.get(param_name)

    def train(self, epochs: int = 10, batch_size: int = 8, drop: float = 0.3) -> dict:
        """Train model on new examples.

        Args:
            epochs: Number of training epochs
            batch_size: Batch size for training
            drop: Dropout rate

        Returns:
            Dict with training metrics
        """
        # Load new examples
        new_examples = self._load_new_examples()
        if not new_examples:
            return {"status": "no_new_data", "examples": 0}

        # Load model
        nlp = self._load_model()

        # Prepare data
        train_data, test_data = self._prepare_training_data(new_examples)
        if not train_data:
            return {"status": "no_training_data", "examples": 0}

        # Configure NER pipeline
        if "ner" not in nlp.pipe_names:
            ner = nlp.add_pipe("ner", last=True)
        else:
            ner = nlp.get_pipe("ner")

        # Add custom labels
        for label in CUSTOM_ENTITY_LABELS:
            ner.add_label(label)

        # Train
        logger.info(f"Training for {epochs} epochs on {len(train_data)} examples")
        optimizer = nlp.initialize()

        for epoch in range(epochs):
            random.shuffle(train_data)
            losses = {}

            # Batch training
            for i in range(0, len(train_data), batch_size):
                batch = train_data[i : i + batch_size]
                nlp.update(batch, drop=drop, sgd=optimizer, losses=losses)

            logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {losses.get('ner', 0):.4f}")

        # Evaluate on test set
        metrics = self._evaluate(nlp, test_data)

        # Save model
        self.custom_model_path.parent.mkdir(parents=True, exist_ok=True)
        nlp.to_disk(self.custom_model_path)
        logger.info(f"Model saved to {self.custom_model_path}")

        # Save checkpoint
        total_trained = self._last_trained_count + len(new_examples)
        self._save_checkpoint(total_trained)

        return {
            "status": "trained",
            "examples": len(new_examples),
            "total_examples": total_trained,
            "metrics": metrics,
        }

    def _evaluate(self, nlp: spacy.Language, test_data: List[Example]) -> dict:
        """Evaluate model on test data.

        Args:
            nlp: Trained spaCy model
            test_data: Test examples

        Returns:
            Dict with evaluation metrics
        """
        if not test_data:
            return {}

        scorer = nlp.evaluate(test_data)
        return {
            "precision": scorer.get("ents_p", 0),
            "recall": scorer.get("ents_r", 0),
            "f1": scorer.get("ents_f", 0),
        }


def main():
    """CLI entry point for training."""
    import argparse

    parser = argparse.ArgumentParser(description="Train spaCy NER model")
    parser.add_argument("--epochs", type=int, default=10, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    args = parser.parse_args()

    trainer = SpaCyNERTrainer()
    result = trainer.train(epochs=args.epochs, batch_size=args.batch_size)

    print(f"\nTraining complete:")
    print(f"  Status: {result['status']}")
    print(f"  New examples: {result.get('examples', 0)}")
    print(f"  Total examples: {result.get('total_examples', 0)}")

    if "metrics" in result and result["metrics"]:
        metrics = result["metrics"]
        print(f"\nMetrics:")
        print(f"  Precision: {metrics.get('precision', 0):.4f}")
        print(f"  Recall: {metrics.get('recall', 0):.4f}")
        print(f"  F1: {metrics.get('f1', 0):.4f}")


if __name__ == "__main__":
    main()
