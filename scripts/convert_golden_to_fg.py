#!/usr/bin/env python3
"""
Convert Halo golden dataset to FunctionGemma training format.

Usage:
    python scripts/convert_golden_to_fg.py [--output OUTPUT_DIR]
"""

import argparse
import json
from pathlib import Path

from halo.nlp.functiongemma.converter import HaloToFunctionGemmaConverter


def main():
    parser = argparse.ArgumentParser(
        description="Convert Halo golden dataset to FunctionGemma format"
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=Path("data/golden_dataset.jsonl"),
        help="Path to golden dataset (default: data/golden_dataset.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/functiongemma_training.jsonl"),
        help="Output path for FunctionGemma training data",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print statistics about the conversion",
    )

    args = parser.parse_args()

    # Validate input
    if not args.golden.exists():
        print(f"❌ Golden dataset not found: {args.golden}")
        return 1

    # Convert
    print(f"📚 Converting {args.golden} to FunctionGemma format...")
    converter = HaloToFunctionGemmaConverter()

    try:
        dataset = converter.golden_to_training(args.golden)
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return 1

    # Save as JSONL
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for record in dataset:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✅ Converted {len(dataset)} examples to {args.output}")

    # Print stats if requested
    if args.stats:
        print("\n📊 Statistics:")
        print(f"   Total examples: {len(dataset)}")

        # Count tools
        tool_counts = {}
        for record in dataset:
            tool_name = record["messages"][2]["tool_calls"][0]["function"]["name"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        print("\n   Tool distribution:")
        for tool, count in sorted(
            tool_counts.items(), key=lambda x: x[1], reverse=True
        ):
            pct = count / len(dataset) * 100
            print(f"   - {tool}: {count} ({pct:.1f}%)")

        # Sample
        print("\n   Sample (first example):")
        sample = dataset[0]
        print(f"   User: {sample['messages'][1]['content']}")
        tool_call = sample["messages"][2]["tool_calls"][0]["function"]
        print(f"   Tool: {tool_call['name']}")
        print(f"   Args: {tool_call['arguments']}")

    return 0


if __name__ == "__main__":
    exit(main())
