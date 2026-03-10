"""End-to-end tests for scenario testing framework.

Tests the complete loop: load → run → evaluate → fix
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from halo.testing import ScenarioRunner, Scenario
from halo.tracing import DecisionTracer, AgencyTrace


class TestScenarioLoading:
    """Test scenario loading from YAML."""

    def test_load_scenario_from_yaml(self):
        """Should load scenario from YAML file."""
        yaml_path = Path("scenarios/flows/scene_setup_complete.yaml")

        if not yaml_path.exists():
            pytest.skip(f"Scenario file not found: {yaml_path}")

        runner = ScenarioRunner(endpoint_url="http://localhost:8000")
        scenario = runner.load_scenario(yaml_path)

        assert scenario.name == "Scene Setup - Complete Flow"
        assert scenario.category == "flows"
        assert len(scenario.turns) == 2
        assert scenario.turns[0].user_input == "configura escena nocturno"


class TestDecisionTracer:
    """Test decision tracing."""

    def test_tracer_captures_decisions(self):
        """Should capture decision points."""
        tracer = DecisionTracer(user_input="test input")

        tracer.decision_point(
            agent="TestAgent",
            question="What to do?",
            context={"key": "value"},
            options=[{"option": "A"}, {"option": "B"}],
            decided="A",
            why="Because A is better"
        )

        trace = tracer.finish(final_result="Done")

        assert trace.user_input == "test input"
        assert len(trace.decisions) == 1
        assert trace.decisions[0].agent == "TestAgent"
        assert trace.decisions[0].decided == "A"
        assert "test input" in trace.narrative

    def test_tracer_serialization(self):
        """Should serialize to dict."""
        tracer = DecisionTracer(user_input="test")
        tracer.decision_point(
            agent="Agent1",
            question="Q?",
            context={},
            options=[],
            decided="X",
            why="Reason"
        )

        trace = tracer.finish("Result")
        trace_dict = trace.to_dict()

        assert "trace_id" in trace_dict
        assert "decision_chain" in trace_dict
        assert len(trace_dict["decision_chain"]) == 1

    def test_tracer_deserialization(self):
        """Should deserialize from dict."""
        trace_dict = {
            "trace_id": "abc-123",
            "user_input": "test input",
            "final_result": "done",
            "decision_chain": [
                {
                    "agent": "TestAgent",
                    "question": "What?",
                    "context_used": {},
                    "options_considered": [],
                    "decided": "X",
                    "why": "Because",
                    "alternative_paths": []
                }
            ],
            "narrative": "Test narrative"
        }

        trace = AgencyTrace.from_dict(trace_dict)

        assert trace.trace_id == "abc-123"
        assert trace.user_input == "test input"
        assert len(trace.decisions) == 1
        assert trace.decisions[0].agent == "TestAgent"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
