from gerbera_sdk.rule_engine.condition_node import ConditionNode, Operator
from gerbera_sdk.rule_engine.rule_event import RuleEvent
from gerbera_sdk.rule_engine.ruleset import RuleSet


class RecordingHandler:
    def __init__(self) -> None:
        self.payloads: list[dict[str, str]] = []

    def perform_work(self, payload: dict[str, str]) -> None:
        self.payloads.append(dict(payload))


def test_ruleset_evaluates_matching_nested_conditions() -> None:
    root_handler = RecordingHandler()
    child_handler = RecordingHandler()

    ruleset = RuleSet(
        root=ConditionNode(
            field="value",
            operator=Operator.EQUAL,
            expected="1",
            rule_events=[
                RuleEvent(
                    name="root",
                    handler=root_handler,
                )
            ],
            children=[
                ConditionNode(
                    field="distance",
                    operator=Operator.LESS_THAN,
                    expected="10",
                    rule_events=[
                        RuleEvent(
                            name="child",
                            handler=child_handler,
                        )
                    ],
                )
            ],
        )
    )

    executed_events = ruleset.evaluate({"value": "1", "distance": "5"})

    assert [event.name for event in executed_events] == ["root", "child"]
    assert root_handler.payloads == [{"value": "1", "distance": "5"}]
    assert child_handler.payloads == [{"value": "1", "distance": "5"}]


def test_ruleset_skips_children_when_parent_condition_fails() -> None:
    child_handler = RecordingHandler()

    ruleset = RuleSet(
        root=ConditionNode(
            field="value",
            operator=Operator.EQUAL,
            expected="1",
            children=[
                ConditionNode(
                    field="distance",
                    operator=Operator.LESS_THAN,
                    expected="10",
                    rule_events=[
                        RuleEvent(
                            name="child",
                            handler=child_handler,
                        )
                    ],
                )
            ],
        )
    )

    executed_events = ruleset.evaluate({"value": "0", "distance": "5"})

    assert executed_events == []
    assert child_handler.payloads == []
