from gerbera_harness.runtime.state_machine.bindings import (
    pointer_tokens, validate_json_schema,
)
from gerbera_harness.runtime.state_machine.schemas import (
    ReservedNode, RunStatus, Transition, WorkflowDefinition,
)


def validate_workflow(definition: WorkflowDefinition) -> None:
    validate_json_schema(definition.interface.input_schema)
    validate_json_schema(definition.interface.output_schema)
    validate_nodes(definition)
    validate_transitions(definition)
    validate_reachability(definition)


def validate_nodes(definition: WorkflowDefinition) -> None:
    for name, node in definition.nodes.items():
        if not name or name.startswith("__"):
            raise ValueError(f"Reserved or empty node name: {name}")
        if len(set(node.outcomes)) != len(node.outcomes):
            raise ValueError(f"Duplicate outcomes on node: {name}")
        if any(not outcome for outcome in node.outcomes):
            raise ValueError(f"Empty outcome on node: {name}")
        for pointer in node.inputs.values():
            tokens = pointer_tokens(pointer)
            if not tokens or tokens[0] not in {"input", "values", "nodes"}:
                raise ValueError(f"Invalid node input binding: {pointer}")
        written: list[tuple[str, ...]] = []
        for source, destination in node.outputs.items():
            pointer_tokens(source)
            tokens = pointer_tokens(destination)
            if len(tokens) < 2 or tokens[0] != "values":
                raise ValueError("Node outputs may only write below /values/")
            if any(tokens[:len(old)] == old or old[:len(tokens)] == tokens
                   for old in written):
                raise ValueError(f"Overlapping output bindings on node: {name}")
            written.append(tokens)


def validate_transitions(definition: WorkflowDefinition) -> None:
    names = {*definition.nodes, ReservedNode.ENTRY, ReservedNode.EXIT}
    seen: set[tuple[str, str]] = set()
    entry_count = 0
    for transition in definition.transitions:
        if transition.source not in names or transition.destination not in names:
            raise ValueError("Transition references an unknown node")
        if transition.destination == ReservedNode.ENTRY:
            raise ValueError("ENTRY cannot have incoming transitions")
        if transition.source == ReservedNode.EXIT:
            raise ValueError("EXIT cannot have outgoing transitions")
        key = (transition.source, transition.outcome)
        if key in seen:
            raise ValueError(f"Duplicate transition: {key}")
        seen.add(key)
        if transition.source == ReservedNode.ENTRY:
            entry_count += 1
            if transition.outcome != "start":
                raise ValueError("ENTRY must use the start outcome")
        elif transition.outcome not in definition.nodes[transition.source].outcomes:
            raise ValueError(f"Undeclared outcome: {key}")
        validate_terminal(transition)
    if entry_count != 1:
        raise ValueError("Workflow requires exactly one ENTRY transition")
    for name, node in definition.nodes.items():
        for outcome in node.outcomes:
            if (name, outcome) not in seen:
                raise ValueError(f"Unmapped outcome: {name}.{outcome}")


def validate_terminal(transition: Transition) -> None:
    terminal = transition.terminal
    if transition.destination != ReservedNode.EXIT:
        if terminal is not None:
            raise ValueError("Only EXIT transitions may specify terminal data")
        return
    if terminal is None:
        raise ValueError("EXIT transitions require a terminal status")
    if terminal.status == RunStatus.SUCCEEDED and terminal.error is not None:
        raise ValueError("Successful exits cannot include an error")
    if terminal.status != RunStatus.SUCCEEDED and terminal.error is None:
        raise ValueError("Unsuccessful exits require an error")
    for pointer in terminal.output.values():
        tokens = pointer_tokens(pointer)
        if not tokens or tokens[0] not in {"input", "values", "nodes"}:
            raise ValueError(f"Invalid terminal output binding: {pointer}")


def reachable(start: str, edges: dict[str, set[str]]) -> set[str]:
    visited: set[str] = set()
    pending = [start]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(edges.get(current, ()))
    return visited


def validate_reachability(definition: WorkflowDefinition) -> None:
    forward: dict[str, set[str]] = {}
    reverse: dict[str, set[str]] = {}
    for transition in definition.transitions:
        forward.setdefault(transition.source, set()).add(transition.destination)
        reverse.setdefault(transition.destination, set()).add(transition.source)
    expected = {*definition.nodes, ReservedNode.ENTRY, ReservedNode.EXIT}
    if reachable(ReservedNode.ENTRY, forward) != expected:
        raise ValueError("Every node and EXIT must be reachable from ENTRY")
    if reachable(ReservedNode.EXIT, reverse) != expected:
        raise ValueError("Every node must have a path to EXIT")
