#!/usr/bin/env python3
"""Scenario-based bulk tester for conversational flows.

Tests multi-turn conversations with context inheritance and parameter merging.

Usage:
    uv run python test/scenario_tester.py test/scenarios/
    uv run python test/scenario_tester.py test/scenarios/conversation_flows.yaml
"""

import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import yaml
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.halo.context.conversation_manager import ConversationContextManager
from src.halo.intent.factory import create_default_chain
from src.halo.backend.qwen.backend import QwenBackend

logger = logging.getLogger(__name__)


@dataclass
class TurnExpectation:
    """Expected result for a conversation turn."""

    tool: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    confidence_min: Optional[float] = None
    confidence_max: Optional[float] = None
    classifier: Optional[str] = None


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    user: str
    expect: TurnExpectation
    context: Optional[Dict] = None


@dataclass
class Scenario:
    """A test scenario with conversation sequence."""

    name: str
    description: str
    conversation: List[ConversationTurn]


@dataclass
class TurnResult:
    """Result of a single turn."""

    turn: ConversationTurn
    classification: Any  # ClassificationResult
    passed: bool
    failures: List[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Result of running a scenario."""

    scenario: Scenario
    turn_results: List[TurnResult]
    passed: bool
    total_turns: int
    passed_turns: int


class ScenarioTester:
    """Bulk tester for conversational scenarios.

    Loads scenarios from YAML files and tests multi-turn conversations
    with context tracking and parameter inheritance.
    """

    def __init__(self, backend=None, context_manager=None):
        """Initialize scenario tester.

        Args:
            backend: Backend instance (defaults to QwenBackend)
            context_manager: ConversationContextManager instance
        """
        # Initialize backend
        if backend is None:
            backend = QwenBackend()

        self.backend = backend

        # Initialize classifier chain
        self.chain = create_default_chain(backend, enable_embeddings=True)

        # Initialize context manager
        self.context_manager = context_manager or ConversationContextManager(max_turns=5)

    def load_scenarios(self, yaml_path: str) -> List[Scenario]:
        """Load scenarios from YAML file.

        Args:
            yaml_path: Path to YAML file

        Returns:
            List of Scenario objects
        """
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        scenarios = []

        for scenario_data in data.get("scenarios", []):
            conversation_turns = []

            for turn_data in scenario_data.get("conversation", []):
                # Parse expectation
                expect_data = turn_data.get("expect", {})
                expectation = TurnExpectation(
                    tool=expect_data.get("tool"),
                    params=expect_data.get("params"),
                    confidence_min=expect_data.get("confidence_min"),
                    confidence_max=expect_data.get("confidence_max"),
                    classifier=expect_data.get("classifier"),
                )

                # Create turn
                turn = ConversationTurn(
                    user=turn_data.get("user"),
                    expect=expectation,
                    context=turn_data.get("context"),
                )

                conversation_turns.append(turn)

            scenario = Scenario(
                name=scenario_data.get("name"),
                description=scenario_data.get("description", ""),
                conversation=conversation_turns,
            )

            scenarios.append(scenario)

        return scenarios

    def run_scenario(self, scenario: Scenario, verbose: bool = False) -> ScenarioResult:
        """Run a single scenario with context accumulation.

        Args:
            scenario: Scenario to run
            verbose: Print detailed output

        Returns:
            ScenarioResult
        """
        if verbose:
            print(f"\n{'=' * 70}")
            print(f"Scenario: {scenario.name}")
            print(f"{'=' * 70}")
            print(f"Description: {scenario.description}\n")

        # Reset context manager
        self.context_manager.reset()

        turn_results = []
        context = {}

        for i, turn in enumerate(scenario.conversation, 1):
            if verbose:
                print(f"Turn {i}: \"{turn.user}\"")

            # Merge turn-specific context
            if turn.context:
                context.update(turn.context)

            # Classify with context
            classification = self.chain.classify(turn.user, context)

            # Merge missing parameters from conversational context
            if classification:
                classification = self.context_manager.merge_context(classification, turn.user)

            # Validate expectations
            passed, failures = self._validate_turn(classification, turn.expect)

            if verbose:
                if classification:
                    print(f"  → {classification.tool_name} {classification.parameters}")
                    print(f"  → confidence: {classification.confidence:.2f}")
                    print(f"  → classifier: {classification.classifier_used}")

                if passed:
                    print(f"  ✅ PASSED")
                else:
                    print(f"  ❌ FAILED")
                    for failure in failures:
                        print(f"     - {failure}")

                print()

            turn_results.append(TurnResult(turn, classification, passed, failures))

            # Update context manager for next turn
            if classification:
                self.context_manager.add_turn(turn.user, classification)

        # Calculate summary
        passed_turns = sum(1 for r in turn_results if r.passed)
        scenario_passed = passed_turns == len(turn_results)

        return ScenarioResult(
            scenario=scenario,
            turn_results=turn_results,
            passed=scenario_passed,
            total_turns=len(turn_results),
            passed_turns=passed_turns,
        )

    def _validate_turn(self, classification, expect: TurnExpectation) -> tuple[bool, List[str]]:
        """Validate classification against expectations.

        Args:
            classification: ClassificationResult
            expect: TurnExpectation

        Returns:
            (passed, list of failure messages)
        """
        failures = []

        if classification is None:
            failures.append("No classification result (chain returned None)")
            return (False, failures)

        # Validate tool
        if expect.tool and classification.tool_name != expect.tool:
            failures.append(
                f"tool: expected '{expect.tool}', got '{classification.tool_name}'"
            )

        # Validate parameters
        if expect.params:
            for key, expected_value in expect.params.items():
                actual_value = classification.parameters.get(key)
                if actual_value != expected_value:
                    failures.append(
                        f"params.{key}: expected '{expected_value}', got '{actual_value}'"
                    )

        # Validate confidence range
        if expect.confidence_min and classification.confidence < expect.confidence_min:
            failures.append(
                f"confidence: {classification.confidence:.2f} < min {expect.confidence_min}"
            )

        if expect.confidence_max and classification.confidence > expect.confidence_max:
            failures.append(
                f"confidence: {classification.confidence:.2f} > max {expect.confidence_max}"
            )

        # Validate classifier
        if expect.classifier and classification.classifier_used != expect.classifier:
            failures.append(
                f"classifier: expected '{expect.classifier}', got '{classification.classifier_used}'"
            )

        return (len(failures) == 0, failures)

    def run_all(self, scenarios_path: str, verbose: bool = False) -> List[ScenarioResult]:
        """Run all scenarios in a directory or file.

        Args:
            scenarios_path: Path to YAML file or directory
            verbose: Print detailed output

        Returns:
            List of ScenarioResult
        """
        path = Path(scenarios_path)
        results = []

        if path.is_dir():
            # Run all YAML files in directory
            yaml_files = list(path.glob("*.yaml")) + list(path.glob("*.yml"))
            for yaml_file in sorted(yaml_files):
                print(f"\n{'=' * 70}")
                print(f"Loading scenarios from: {yaml_file.name}")
                print(f"{'=' * 70}")

                scenarios = self.load_scenarios(str(yaml_file))
                for scenario in scenarios:
                    result = self.run_scenario(scenario, verbose=verbose)
                    results.append(result)
        else:
            # Run single file
            scenarios = self.load_scenarios(str(path))
            for scenario in scenarios:
                result = self.run_scenario(scenario, verbose=verbose)
                results.append(result)

        return results

    def generate_report(self, results: List[ScenarioResult]) -> str:
        """Generate summary report.

        Args:
            results: List of ScenarioResult

        Returns:
            Report string
        """
        total_scenarios = len(results)
        passed_scenarios = sum(1 for r in results if r.passed)
        total_turns = sum(r.total_turns for r in results)
        passed_turns = sum(r.passed_turns for r in results)

        report = f"\n{'=' * 70}\n"
        report += "SUMMARY\n"
        report += f"{'=' * 70}\n\n"

        report += f"Scenarios: {passed_scenarios}/{total_scenarios} passed "
        report += f"({passed_scenarios/total_scenarios*100:.1f}%)\n"

        report += f"Turns: {passed_turns}/{total_turns} passed "
        report += f"({passed_turns/total_turns*100 if total_turns > 0 else 0:.1f}%)\n\n"

        # Detailed results
        for result in results:
            status = "✅ PASSED" if result.passed else "❌ FAILED"
            report += f"{status} - {result.scenario.name} "
            report += f"({result.passed_turns}/{result.total_turns} turns)\n"

            if not result.passed:
                for turn_result in result.turn_results:
                    if not turn_result.passed:
                        report += f"  Turn: \"{turn_result.turn.user}\"\n"
                        for failure in turn_result.failures:
                            report += f"    - {failure}\n"

        return report


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run scenario-based tests")
    parser.add_argument(
        "path",
        help="Path to YAML scenario file or directory",
        default="test/scenarios/",
        nargs="?",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output (show each turn)"
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s"
    )

    print("\n🧪 Running Scenario Tests\n")

    # Create tester
    tester = ScenarioTester()

    # Run scenarios
    results = tester.run_all(args.path, verbose=args.verbose)

    # Generate report
    report = tester.generate_report(results)
    print(report)

    # Exit code
    all_passed = all(r.passed for r in results)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
