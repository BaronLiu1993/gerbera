from dataclasses import dataclass, field
import uuid

from gerbera_sdk.rule_engine.condition_node import ConditionNode, Operator
from gerbera_sdk.rule_engine.rule_event import RuleEvent


@dataclass
class RuleSet:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    root: ConditionNode | None = None

    def evaluate(self, payload: dict[str, str]) -> list[RuleEvent]:
        if self.root is None:
            return []

        return self.evaluate_node(self.root, payload)

    def evaluate_condition(
        self,
        condition_node: ConditionNode,
        payload: dict[str, str],
    ) -> bool:
        actual = payload.get(condition_node.field)
        expected = condition_node.expected

        if actual is None:
            return False

        if condition_node.operator == Operator.EQUAL:
            return actual == expected

        if condition_node.operator == Operator.NOT_EQUAL:
            return actual != expected

        try:
            actual_num = float(actual)
            expected_num = float(expected)
        except ValueError:
            return False

        if condition_node.operator == Operator.GREATER_THAN:
            return actual_num > expected_num

        if condition_node.operator == Operator.LESS_THAN:
            return actual_num < expected_num

        if condition_node.operator == Operator.GREATER_THAN_EQUAL:
            return actual_num >= expected_num

        if condition_node.operator == Operator.LESS_THAN_EQUAL:
            return actual_num <= expected_num

        raise ValueError(f"Unsupported operator: {condition_node.operator}")

    def evaluate_node(
        self,
        node: ConditionNode,
        payload: dict[str, str],
    ) -> list[RuleEvent]:
        if not self.evaluate_condition(node, payload):
            return []

        executed_events = []
        for event in node.rule_events:
            event.perform_work(payload)
            executed_events.append(event)

        for child in node.children:
            executed_events.extend(self.evaluate_node(child, payload))

        return executed_events
