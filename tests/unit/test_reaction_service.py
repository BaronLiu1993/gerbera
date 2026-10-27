from types import SimpleNamespace

import pytest

from gerbera_sdk.events.event_bus import EventBus
from gerbera_sdk.events.event_registration import EventRegistration
from gerbera_sdk.events.reactions.reaction_bus import ReactionBus
from gerbera_sdk.events.reactions.reaction_executor import ActionPolicy, ReactionActionRegistry
from gerbera_sdk.events.reactions.reaction_schema import (
    CreateReactionSchema, ReactionActionSchema, ReactionConditionSchema,
    ReactionEventSchema, ReactionOperator, ReactionTriggerMode,
)
from gerbera_sdk.events.reactions.reaction_service import ReactionService
from gerbera_sdk.events.reactions.reaction_store import ReactionStore
from gerbera_sdk.gerbera_runtime import GerberaRuntime
from gerbera_sdk.models.hardware.connection import Connection
from gerbera_sdk.models.hardware.hardware_system import HardwareSystem
from gerbera_sdk.models.hardware.microcontroller import Microcontroller, RuntimeTransportConfig


@pytest.fixture
def service_setup(tmp_path):
    sensor = Connection(name="sensor", component_type="hw201", pins={"out": "7"}, description="Sensor", stream=True)
    hardware = HardwareSystem(name="robot", microcontrollers=[Microcontroller(
        runtime_transport=RuntimeTransportConfig.usb_serial("/dev/test"),
        name="board", device_id="board-1", upload_port="/dev/test", fqbn="arduino:avr:uno", connections=[sensor],
    )])
    GerberaRuntime.bind_connection_microcontroller_ids(hardware)
    plan = GerberaRuntime.validate_hardware(hardware)
    events = EventBus()
    EventRegistration(plan, events, SimpleNamespace()).register()
    actions = ReactionActionRegistry()
    actions.register("stop", lambda: {"success": True}, ActionPolicy(modifies_state=True))
    store = ReactionStore(tmp_path)
    bus = ReactionBus(action_executor=actions, store=store)
    service = ReactionService(plan, events, bus, actions)
    request = CreateReactionSchema(
        event=ReactionEventSchema(
            event_type="STREAM", microcontroller_id="board-1", event_name=sensor.event_name,
            payload_field="obstacle_detected",
        ),
        condition=ReactionConditionSchema(operator=ReactionOperator.EQUAL, expected_value=1),
        action=ReactionActionSchema(tool_name="stop", arguments={}),
        trigger_mode=ReactionTriggerMode.CONTINUOUS,
    )
    return SimpleNamespace(service=service, request=request, store=store)


def test_service_restores_persisted_reaction_without_mcp(service_setup) -> None:
    original = service_setup.service.create_reaction(service_setup.request)
    old = service_setup.service
    restored = ReactionService(
        old.hardware_plan, old.event_bus, ReactionBus(store=service_setup.store), old.actions,
    )

    restored.restore_reactions()

    assert [reaction.definition.reaction_id for reaction in restored.list_reactions()] == [original.definition.reaction_id]


def test_service_rejects_unknown_payload_field_before_persisting(service_setup) -> None:
    request = service_setup.request.model_copy(update={
        "event": service_setup.request.event.model_copy(update={"payload_field": "unknown"}),
    })

    with pytest.raises(ValueError, match="Unknown reaction payload field"):
        service_setup.service.create_reaction(request)

    assert not service_setup.store.load()


def test_service_rejects_unknown_action_before_persisting(service_setup) -> None:
    request = service_setup.request.model_copy(update={
        "action": service_setup.request.action.model_copy(update={"tool_name": "missing"}),
    })

    with pytest.raises(ValueError, match="Unknown reaction action"):
        service_setup.service.create_reaction(request)

    assert not service_setup.store.load()
