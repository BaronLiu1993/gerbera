from abc import ABC, abstractmethod

from gerbera_harness.runtime.state_machine.builder import (
    CompiledWorkflow, WorkflowBuilder,
)


class StateMachine(ABC):
    @abstractmethod
    def define_workflow(self) -> WorkflowBuilder:
        """Supply nodes and transitions; ENTRY and EXIT remain engine-owned."""

    def compile(self) -> CompiledWorkflow:
        return self.define_workflow().build()
