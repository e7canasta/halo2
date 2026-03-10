"""Dataset statistics and validation."""

import json
from pathlib import Path
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class DatasetStats:
    """Analyze golden dataset statistics."""

    def __init__(self, dataset_path: str = "data/golden_dataset.jsonl"):
        self.dataset_path = Path(dataset_path)

    def get_stats(self) -> dict:
        """Get comprehensive dataset statistics.

        Returns:
            Dict with stats
        """
        if not self.dataset_path.exists():
            return {"error": "Dataset not found", "count": 0}

        stats = {
            "total_examples": 0,
            "tools": Counter(),
            "classifiers": Counter(),
            "avg_confidence": 0.0,
            "slots_distribution": Counter(),
            "params_distribution": Counter(),
            "synthetic_count": 0,  # NEW
            "real_count": 0,  # NEW
        }

        confidences = []

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                stats["total_examples"] += 1
                stats["tools"][record["tool"]] += 1
                stats["classifiers"][record["classifier"]] += 1
                confidences.append(record["confidence"])

                # Slot stats
                slot_count = len(record.get("slots", {}))
                stats["slots_distribution"][slot_count] += 1

                # Param stats
                for param in record.get("params", {}).keys():
                    stats["params_distribution"][param] += 1

                # Synthetic vs real
                if record.get("synthetic", False):
                    stats["synthetic_count"] += 1
                else:
                    stats["real_count"] += 1

        if confidences:
            stats["avg_confidence"] = sum(confidences) / len(confidences)

        return stats

    def print_stats(self):
        """Print formatted statistics."""
        stats = self.get_stats()

        if "error" in stats:
            print(f"Error: {stats['error']}")
            return

        print("\n=== Golden Dataset Statistics ===\n")
        print(f"Total examples: {stats['total_examples']}")
        print(f"  Real examples: {stats['real_count']} ({stats['real_count']/stats['total_examples']*100:.1f}%)")
        print(f"  Synthetic examples: {stats['synthetic_count']} ({stats['synthetic_count']/stats['total_examples']*100:.1f}%)")
        print(f"Average confidence: {stats['avg_confidence']:.4f}")

        print("\nTools distribution:")
        for tool, count in stats["tools"].most_common():
            pct = (count / stats["total_examples"]) * 100
            print(f"  {tool}: {count} ({pct:.1f}%)")

        print("\nClassifiers used:")
        for classifier, count in stats["classifiers"].most_common():
            pct = (count / stats["total_examples"]) * 100
            print(f"  {classifier}: {count} ({pct:.1f}%)")

        print("\nSlots per example:")
        for slot_count, freq in sorted(stats["slots_distribution"].items()):
            pct = (freq / stats["total_examples"]) * 100
            print(f"  {slot_count} slots: {freq} ({pct:.1f}%)")

        print("\nParameters extracted:")
        for param, count in stats["params_distribution"].most_common():
            print(f"  {param}: {count}")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Show dataset statistics")
    parser.add_argument(
        "--dataset",
        default="data/golden_dataset.jsonl",
        help="Path to golden dataset",
    )
    args = parser.parse_args()

    stats_analyzer = DatasetStats(args.dataset)
    stats_analyzer.print_stats()


if __name__ == "__main__":
    main()
