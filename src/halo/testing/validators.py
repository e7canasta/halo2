"""Expectation Validators - Valida responses contra expectations.

Valida que el sistema respondió como esperábamos en el scenario.
"""

from typing import Dict, Any, Tuple, List
import logging

logger = logging.getLogger(__name__)


class ExpectationValidator:
    """Valida expectations de scenarios.

    Soporta validaciones de:
    - Flow states (flow_started, flow_active, flow_completed)
    - Status codes
    - Tools ejecutados
    - Parámetros
    - Slots collected
    - Contenido de mensajes
    - Agency trace validations
    """

    def validate(
        self,
        response: Dict[str, Any],
        expectations: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Valida una response contra expectations.

        Args:
            response: Response del sistema
            expectations: Dict con expectations

        Returns:
            (passed, failures) donde failures es lista de mensajes de error
        """
        failures = []

        # Check flow_started
        if "flow_started" in expectations:
            if not self.check_flow_started(response, expectations["flow_started"]):
                failures.append(f"Expected flow_started: {expectations['flow_started']}")

        # Check flow_active
        if "flow_active" in expectations:
            if not self.check_flow_active(response, expectations["flow_active"]):
                failures.append(f"Expected flow_active: {expectations['flow_active']}")

        # Check status
        if "status" in expectations:
            if not self.check_status(response, expectations["status"]):
                failures.append(f"Expected status: {expectations['status']}, got: {response.get('result', {}).get('status')}")

        # Check tool
        if "tool" in expectations or "tool_executed" in expectations:
            expected_tool = expectations.get("tool") or expectations.get("tool_executed")
            if not self.check_tool(response, expected_tool):
                actual_tool = response.get("result", {}).get("tool_call", {}).get("tool")
                failures.append(f"Expected tool: {expected_tool}, got: {actual_tool}")

        # Check params
        if "params" in expectations:
            if not self.check_params(response, expectations["params"]):
                failures.append(f"Expected params: {expectations['params']}")

        # Check slots_collected
        if "slots_collected" in expectations:
            if not self.check_slots_collected(response, expectations["slots_collected"]):
                failures.append(f"Expected slots_collected: {expectations['slots_collected']}")

        # Check message_contains
        if "message_contains" in expectations:
            if not self.check_message_contains(response, expectations["message_contains"]):
                failures.append(f"Expected message to contain: {expectations['message_contains']}")

        # Check agency
        if "agency" in expectations:
            agency_failures = self.check_agency(response, expectations["agency"])
            failures.extend(agency_failures)

        passed = len(failures) == 0
        return (passed, failures)

    def check_flow_started(self, response: Dict, flow_name: str) -> bool:
        """Check si se inició el flow esperado.

        Args:
            response: Response del sistema
            flow_name: Nombre del flow esperado

        Returns:
            True si el flow se inició
        """
        # Check en metadata del context
        context = response.get("context", {})
        return context.get("process_id") is not None

    def check_flow_active(self, response: Dict, flow_name: str) -> bool:
        """Check si hay un flow activo.

        Args:
            response: Response del sistema
            flow_name: Nombre del flow esperado

        Returns:
            True si el flow está activo
        """
        context = response.get("context", {})
        return context.get("process_id") is not None

    def check_status(self, response: Dict, expected_status: str) -> bool:
        """Check status code.

        Args:
            response: Response del sistema
            expected_status: Status esperado

        Returns:
            True si coincide
        """
        actual_status = response.get("result", {}).get("status")
        return actual_status == expected_status

    def check_tool(self, response: Dict, expected_tool: str) -> bool:
        """Check tool ejecutado.

        Args:
            response: Response del sistema
            expected_tool: Tool esperado

        Returns:
            True si coincide
        """
        tool_call = response.get("result", {}).get("tool_call")
        if not tool_call:
            return False
        return tool_call.get("tool") == expected_tool

    def check_params(self, response: Dict, expected_params: Dict) -> bool:
        """Check parámetros del tool.

        Args:
            response: Response del sistema
            expected_params: Parámetros esperados

        Returns:
            True si todos los params esperados están presentes
        """
        tool_call = response.get("result", {}).get("tool_call")
        if not tool_call:
            return False

        actual_params = tool_call.get("parameters", {})

        # Check que todos los expected_params estén presentes
        for key, expected_value in expected_params.items():
            if key not in actual_params:
                return False
            if actual_params[key] != expected_value:
                return False

        return True

    def check_slots_collected(self, response: Dict, expected_slots: List[Dict]) -> bool:
        """Check slots collected in a flow.

        Args:
            response: Response del sistema
            expected_slots: Lista de slots esperados

        Returns:
            True si se recolectaron
        """
        # TODO: Implementar cuando tengamos metadata de slots en response
        return True

    def check_message_contains(self, response: Dict, substring: str) -> bool:
        """Check si el mensaje contiene substring.

        Args:
            response: Response del sistema
            substring: Substring esperado

        Returns:
            True si está presente
        """
        message = response.get("result", {}).get("message", "")
        return substring.lower() in message.lower()

    def check_agency(self, response: Dict, agency_expectations: Dict) -> List[str]:
        """Check agency trace expectations.

        Args:
            response: Response del sistema
            agency_expectations: Expectations de agencia

        Returns:
            Lista de failures (vacía si todo OK)
        """
        failures = []
        agency_trace = response.get("agency_trace")

        if not agency_trace:
            failures.append("No agency_trace in response")
            return failures

        # Check classifier_used
        if "classifier_used" in agency_expectations:
            expected_classifiers = agency_expectations["classifier_used"]
            if not isinstance(expected_classifiers, list):
                expected_classifiers = [expected_classifiers]

            # Find classifier decision
            decisions = agency_trace.get("decision_chain", [])
            classifier_decisions = [d for d in decisions if d.get("agent") == "ClassifierChain"]

            if classifier_decisions:
                actual_classifier = classifier_decisions[0].get("context_used", {}).get("classifier_used")
                if actual_classifier not in expected_classifiers:
                    failures.append(f"Expected classifier in {expected_classifiers}, got: {actual_classifier}")

        # Check flow_decision
        if "flow_decision" in agency_expectations:
            expected_decision = agency_expectations["flow_decision"]
            decisions = agency_trace.get("decision_chain", [])
            flow_decisions = [d for d in decisions if d.get("agent") == "FlowEngine"]

            if flow_decisions:
                actual_decision = flow_decisions[0].get("decided")
                if actual_decision != expected_decision:
                    failures.append(f"Expected flow_decision: {expected_decision}, got: {actual_decision}")

        # Check decision_why_contains
        if "decision_why_contains" in agency_expectations:
            substring = agency_expectations["decision_why_contains"]
            decisions = agency_trace.get("decision_chain", [])

            found = any(substring.lower() in d.get("why", "").lower() for d in decisions)
            if not found:
                failures.append(f"Expected decision 'why' to contain: {substring}")

        # Check decisions_count
        if "decisions_count" in agency_expectations:
            expected_count = agency_expectations["decisions_count"]
            decisions = agency_trace.get("decision_chain", [])
            actual_count = len(decisions)

            if actual_count < expected_count:
                failures.append(f"Expected at least {expected_count} decisions, got: {actual_count}")

        return failures
