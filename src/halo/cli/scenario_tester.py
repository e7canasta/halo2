"""CLI Tool for Scenario Testing.

Ejecuta el loop completo:
  run → evaluate → fix → re-run → report

Usage:
    python -m halo.cli.scenario_tester run scenarios/
    python -m halo.cli.scenario_tester auto-improve scenarios/
"""

import sys
import argparse
import logging
from pathlib import Path

from ..testing import ScenarioRunner
from ..agents.gemini_evaluator import GeminiEvaluator, GEMINI_AVAILABLE
from ..learning import AutoAdjuster

logger = logging.getLogger(__name__)


def run_scenarios(scenarios_dir: Path, endpoint_url: str):
    """Ejecuta scenarios.

    Args:
        scenarios_dir: Directorio con YAMLs
        endpoint_url: URL del endpoint
    """
    runner = ScenarioRunner(endpoint_url=endpoint_url)

    print(f"\n📊 Executing scenarios from {scenarios_dir}...")
    history = runner.run_all_scenarios(scenarios_dir)

    print(f"\n✅ Completed {len(history.runs)} scenarios")
    print(f"   Pass rate: {history.pass_rate:.1%}")
    print(f"   Total decisions: {history.total_decisions}")
    print(f"   Decisions by agent:")
    for agent, count in history.decisions_by_agent.items():
        print(f"     - {agent}: {count}")

    return history


def evaluate_with_gemini(history):
    """Evalúa con Gemini.

    Args:
        history: RunHistory

    Returns:
        BatchEvaluation
    """
    if not GEMINI_AVAILABLE:
        print("\n⚠️  Gemini not available - skipping evaluation")
        print("   Install with: pip install google-generativeai")
        return None

    print("\n🧠 Evaluating with Gemini...")
    evaluator = GeminiEvaluator()

    try:
        evaluation = evaluator.evaluate_run_history(history)

        print(f"\n✅ Evaluation complete")
        print(f"   Overall quality: {evaluation.summary.get('overall_quality')}")
        print(f"   Patterns found: {len(evaluation.patterns.get('systematic_errors', []))}")
        print(f"   Auto-fixes available: {len(evaluation.auto_fixes)}")

        return evaluation
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return None


def apply_auto_fixes(evaluation):
    """Aplica auto-fixes.

    Args:
        evaluation: BatchEvaluation
    """
    if not evaluation or not evaluation.auto_fixes:
        print("\n⚠️  No auto-fixes to apply")
        return

    print(f"\n🔧 Applying {len(evaluation.auto_fixes)} auto-fixes...")

    adjuster = AutoAdjuster()
    adjuster.apply_fixes(evaluation)

    print(f"\n✅ Applied {len(adjuster.applied_fixes)} fixes:")
    for fix in adjuster.applied_fixes:
        print(f"   - {fix.get('fix_id')}: {fix.get('change', '')[:60]}...")


def auto_improve(scenarios_dir: Path, endpoint_url: str):
    """Loop completo: run → evaluate → fix → re-run.

    Args:
        scenarios_dir: Directorio con scenarios
        endpoint_url: URL del endpoint
    """
    print("🚀 Auto-improvement loop starting...")

    # Run 1
    print("\n" + "="*60)
    print("RUN 1: Baseline")
    print("="*60)
    history1 = run_scenarios(scenarios_dir, endpoint_url)

    # Evaluate
    print("\n" + "="*60)
    print("EVALUATE: Finding patterns")
    print("="*60)
    evaluation = evaluate_with_gemini(history1)

    # Apply fixes
    if evaluation:
        print("\n" + "="*60)
        print("FIX: Applying improvements")
        print("="*60)
        apply_auto_fixes(evaluation)

        # Run 2
        print("\n" + "="*60)
        print("RUN 2: After fixes")
        print("="*60)
        history2 = run_scenarios(scenarios_dir, endpoint_url)

        # Compare
        improvement = history2.pass_rate - history1.pass_rate
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        print(f"   Before: {history1.pass_rate:.1%}")
        print(f"   After:  {history2.pass_rate:.1%}")
        print(f"   Improvement: {improvement:+.1%}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scenario Testing Tool"
    )

    parser.add_argument(
        "command",
        choices=["run", "auto-improve"],
        help="Command to execute"
    )

    parser.add_argument(
        "scenarios_dir",
        type=Path,
        help="Directory with scenario YAMLs"
    )

    parser.add_argument(
        "--endpoint",
        default="http://localhost:8000",
        help="Endpoint URL (default: http://localhost:8000)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    # Validate scenarios dir
    if not args.scenarios_dir.exists():
        print(f"❌ Error: {args.scenarios_dir} does not exist")
        sys.exit(1)

    # Execute command
    try:
        if args.command == "run":
            run_scenarios(args.scenarios_dir, args.endpoint)
        elif args.command == "auto-improve":
            auto_improve(args.scenarios_dir, args.endpoint)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
