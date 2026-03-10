"""Scenario Runner - Ejecuta scenarios y captura agencia.

Core del testing framework. Ejecuta scenarios YAML end-to-end
y captura la agencia completa para evaluación.
"""

import uuid
import yaml
import requests
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from .scenario_types import (
    Scenario,
    ScenarioTurn,
    ScenarioRun,
    TurnResult,
    RunHistory
)
from .validators import ExpectationValidator
from ..tracing import AgencyTrace

logger = logging.getLogger(__name__)


class ScenarioRunner:
    """Ejecuta scenarios y captura agencia completa.

    Usage:
        runner = ScenarioRunner(endpoint_url="http://localhost:8000")

        # Cargar y ejecutar scenario
        scenario = runner.load_scenario(Path("scenarios/flows/scene_setup.yaml"))
        run = runner.run_scenario(scenario)

        # Ejecutar todos los scenarios de un directorio
        history = runner.run_all_scenarios(Path("scenarios/"))

        # Ver resultados
        print(f"Pass rate: {history.pass_rate:.1%}")
    """

    def __init__(self, endpoint_url: str):
        """Inicializa runner.

        Args:
            endpoint_url: URL del endpoint /command (ej: http://localhost:8000)
        """
        self.endpoint = endpoint_url.rstrip("/") + "/command"
        self.run_history = RunHistory(runs=[])
        self.validator = ExpectationValidator()
        self.session = requests.Session()

    def load_scenario(self, yaml_path: Path) -> Scenario:
        """Carga scenario desde YAML.

        Args:
            yaml_path: Path al archivo YAML

        Returns:
            Scenario object

        Raises:
            ValueError: Si el YAML es inválido
        """
        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        scenario_data = data.get("scenario", {})
        turns_data = data.get("turns", [])

        turns = []
        for turn_data in turns_data:
            turn = ScenarioTurn(
                turn=turn_data["turn"],
                user_input=turn_data["user"],
                expectations=turn_data.get("expect", {})
            )
            turns.append(turn)

        scenario = Scenario(
            name=scenario_data.get("name", yaml_path.stem),
            description=scenario_data.get("description", ""),
            category=scenario_data.get("category", "general"),
            turns=turns
        )

        logger.info(f"Loaded scenario: {scenario.name} ({len(turns)} turns)")
        return scenario

    def run_scenario(self, scenario: Scenario) -> ScenarioRun:
        """Ejecuta scenario completo con captura de agencia.

        Args:
            scenario: Scenario a ejecutar

        Returns:
            ScenarioRun con resultados completos
        """
        run_id = str(uuid.uuid4())
        turns = []

        logger.info(f"Running scenario: {scenario.name}")

        for turn in scenario.turns:
            logger.debug(f"  Turn {turn.turn}: {turn.user_input}")

            # Ejecutar turn con trace de agencia
            response = self._execute_turn(
                turn.user_input,
                trace_agency=True
            )

            # Extraer agency trace
            agency_trace = None
            if response.get("agency_trace"):
                agency_trace = AgencyTrace.from_dict(response["agency_trace"])

            # Validar expectations
            expectations_met, failures = self.validator.validate(
                response,
                turn.expectations
            )

            if not expectations_met:
                logger.warning(f"  Turn {turn.turn} FAILED: {failures}")

            # Crear TurnResult
            turn_result = TurnResult(
                turn_number=turn.turn,
                user_input=turn.user_input,
                response=response,
                agency_trace=agency_trace,
                expectations_met=expectations_met,
                expectation_failures=failures
            )

            turns.append(turn_result)

        # Crear ScenarioRun
        run = ScenarioRun(
            run_id=run_id,
            scenario_name=scenario.name,
            timestamp=datetime.now(),
            turns=turns,
            passed=all(t.expectations_met for t in turns)
        )

        # Agregar al history
        self.run_history.runs.append(run)

        status = "PASSED" if run.passed else "FAILED"
        logger.info(f"Scenario {scenario.name}: {status} ({len(run.all_decisions)} decisions)")

        return run

    def run_all_scenarios(self, scenarios_dir: Path) -> RunHistory:
        """Ejecuta todos los scenarios de un directorio.

        Args:
            scenarios_dir: Directorio con archivos .yaml

        Returns:
            RunHistory con todas las corridas
        """
        yaml_files = list(scenarios_dir.glob("**/*.yaml"))
        logger.info(f"Found {len(yaml_files)} scenarios in {scenarios_dir}")

        for yaml_file in yaml_files:
            try:
                scenario = self.load_scenario(yaml_file)
                self.run_scenario(scenario)
            except Exception as e:
                logger.error(f"Failed to run scenario {yaml_file}: {e}")

        # Recalcular agregados
        self.run_history.__post_init__()

        logger.info(f"Completed {len(self.run_history.runs)} scenarios")
        logger.info(f"Pass rate: {self.run_history.pass_rate:.1%}")
        logger.info(f"Total decisions: {self.run_history.total_decisions}")

        return self.run_history

    def _execute_turn(
        self,
        user_input: str,
        trace_agency: bool = False
    ) -> Dict[str, Any]:
        """Ejecuta un turn contra el endpoint.

        Args:
            user_input: Input del usuario
            trace_agency: Si True, captura agency trace

        Returns:
            Response del endpoint

        Raises:
            requests.RequestException: Si falla la request
        """
        payload = {
            "message": user_input,
            "context": {
                "_trace_agency": trace_agency
            }
        }

        try:
            response = self.session.post(
                self.endpoint,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Request failed for '{user_input}': {e}")
            raise

    def reset_conversation(self):
        """Reset conversation context (nuevo session)."""
        self.session = requests.Session()
        logger.debug("Conversation reset (new session)")
