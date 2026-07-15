from gerbera_sdk.harness.agent.tool.rule_engine.condition import Condition, MatchMode, Operator
from gerbera_sdk.rule_engine.latest_value_store import LatestValueStore
from gerbera_sdk.rule_engine.rule_listener import RuleListener
from gerbera_sdk.rule_engine.ruleset import RuleSet


class FakeConnection:
    def __init__(self, event_name: str) -> None:
        self.event_name = event_name


class RecordingScript:
    def __init__(self) -> None:
        self.payloads: list[dict[str, str]] = []

    def __call__(self, payload: dict[str, str]) -> None:
        self.payloads.append(dict(payload))


def test_ruleset_evaluates_flat_all_conditions() -> None:
    obstacle_sensor = FakeConnection("obstacle_sensor")
    distance_sensor = FakeConnection("distance_sensor")
    script = RecordingScript()
    ruleset = RuleSet(
        conditions=[
            Condition(
                connection=obstacle_sensor,
                field="value",
                operator=Operator.EQUAL,
                expected="1",
            ),
            Condition(
                connection=distance_sensor,
                field="distance",
                operator=Operator.LESS_THAN,
                expected="10",
            ),
        ],
        script=script,
    )

    matched = ruleset.evaluate(
        {
            "obstacle_sensor": {"value": "1"},
            "distance_sensor": {"distance": "5"},
        }
    )

    assert matched is True
    assert script.payloads == [
        {
            "obstacle_sensor.value": "1",
            "distance_sensor.distance": "5",
        }
    ]


def test_ruleset_skips_events_when_flat_all_condition_fails() -> None:
    obstacle_sensor = FakeConnection("obstacle_sensor")
    distance_sensor = FakeConnection("distance_sensor")
    script = RecordingScript()
    ruleset = RuleSet(
        conditions=[
            Condition(
                connection=obstacle_sensor,
                field="value",
                operator=Operator.EQUAL,
                expected="1",
            ),
            Condition(
                connection=distance_sensor,
                field="distance",
                operator=Operator.LESS_THAN,
                expected="10",
            ),
        ],
        script=script,
    )

    matched = ruleset.evaluate(
        {
            "obstacle_sensor": {"value": "0"},
            "distance_sensor": {"distance": "5"},
        }
    )

    assert matched is False
    assert script.payloads == []


def test_ruleset_supports_flat_any_conditions() -> None:
    left_sensor = FakeConnection("left_sensor")
    right_sensor = FakeConnection("right_sensor")
    script = RecordingScript()
    ruleset = RuleSet(
        match_mode=MatchMode.ANY,
        conditions=[
            Condition(
                connection=left_sensor,
                field="value",
                operator=Operator.EQUAL,
                expected="1",
            ),
            Condition(
                connection=right_sensor,
                field="value",
                operator=Operator.EQUAL,
                expected="1",
            ),
        ],
        script=script,
    )

    matched = ruleset.evaluate(
        {
            "left_sensor": {"value": "0"},
            "right_sensor": {"value": "1"},
        }
    )

    assert matched is True
    assert script.payloads == [
        {
            "left_sensor.value": "0",
            "right_sensor.value": "1",
        }
    ]


def test_rule_listener_evaluates_rules_when_latest_values_change() -> None:
    obstacle_sensor = FakeConnection("obstacle_sensor")
    latest_values = LatestValueStore()
    script = RecordingScript()
    ruleset = RuleSet(
        conditions=[
            Condition(
                connection=obstacle_sensor,
                field="value",
                operator=Operator.EQUAL,
                expected="1",
            )
        ],
        script=script,
    )
    listener = RuleListener(
        rulesets=[ruleset],
        latest_values=latest_values,
    )

    latest_values.update(obstacle_sensor, {"value": "1"})
    listener.evaluate_once()
    listener.evaluate_once()

    assert script.payloads == [{"obstacle_sensor.value": "1"}]
