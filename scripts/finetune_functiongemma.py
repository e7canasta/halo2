#!/usr/bin/env python3
"""
Fine-tune FunctionGemma 270M with Halo golden dataset.

Based on: functionGemma/finetuning_with_functiongemma.ipynb

Usage:
    python scripts/finetune_functiongemma.py [--epochs EPOCHS] [--batch-size BATCH_SIZE]
"""

import argparse
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

from halo.nlp.functiongemma.converter import HaloToFunctionGemmaConverter


def main():
    parser = argparse.ArgumentParser(description="Fine-tune FunctionGemma for Halo")
    parser.add_argument(
        "--golden",
        type=Path,
        default=Path("data/golden_dataset.jsonl"),
        help="Path to golden dataset",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/functiongemma-halo"),
        help="Output directory for fine-tuned model",
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default="google/functiongemma-270m-it",
        help="Base FunctionGemma model to fine-tune",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs (default: 3)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Batch size per device (default: 4)",
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-5,
        help="Learning rate (default: 1e-5)",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Test set size (default: 0.2 = 20%%)",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=512,
        help="Max sequence length (default: 512)",
    )

    args = parser.parse_args()

    # Validate input
    if not args.golden.exists():
        print(f"❌ Golden dataset not found: {args.golden}")
        return 1

    print("=" * 70)
    print("🚀 Fine-tuning FunctionGemma for Halo")
    print("=" * 70)
    print(f"   Base model: {args.base_model}")
    print(f"   Golden dataset: {args.golden}")
    print(f"   Output: {args.output}")
    print(f"   Epochs: {args.epochs}")
    print(f"   Batch size: {args.batch_size}")
    print(f"   Learning rate: {args.learning_rate}")
    print("=" * 70)

    # Load and convert dataset
    print("\n📚 Loading and converting dataset...")
    converter = HaloToFunctionGemmaConverter()
    dataset = converter.golden_to_training(args.golden)
    print(f"   Loaded {len(dataset)} examples")

    # Split train/eval
    dataset = dataset.train_test_split(test_size=args.test_size, shuffle=True)
    print(f"   Train: {len(dataset['train'])} examples")
    print(f"   Eval: {len(dataset['test'])} examples")

    # Load model and tokenizer
    print(f"\n🤖 Loading {args.base_model}...")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        device_map="auto",
        dtype=torch.bfloat16,
        attn_implementation="eager",
    )
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)

    print(f"   Device: {model.device}")
    print(f"   DType: {model.dtype}")

    # Configure training
    training_args = SFTConfig(
        output_dir=str(args.output),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=args.learning_rate,
        lr_scheduler_type="cosine",
        max_length=args.max_length,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        bf16=True,
        gradient_checkpointing=True,
        optim="adamw_torch_fused",
        completion_only_loss=True,  # Only train on assistant response
        report_to="none",
    )

    # Create trainer
    print("\n🏋️ Setting up trainer...")
    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        processing_class=tokenizer,
    )

    # Train
    print("\n🔥 Starting training...")
    print("=" * 70)
    trainer.train()

    # Save
    print("\n💾 Saving fine-tuned model...")
    trainer.save_model(str(args.output))
    tokenizer.save_pretrained(str(args.output))

    print("\n✅ Fine-tuning complete!")
    print(f"   Model saved to: {args.output}")
    print("\n📊 To evaluate:")
    print(f"   python scripts/eval_functiongemma.py --model {args.output}")

    return 0


if __name__ == "__main__":
    exit(main())
