from dataclasses import dataclass

from mcp.types import ToolAnnotations

from gerbera_sdk.models.runtime.server.tool_registry import McpToolRegistry, ToolDefinition
from gerbera_sdk.events.reactions.reaction_service import ReactionService
from gerbera_sdk.events.reactions.reaction_schema import (
    CreateReactionSchema,
    DeleteReactionResultSchema,
    DeleteReactionSchema,
    ReactionSchema,
)


@dataclass
class ReactionTools:
    tools: McpToolRegistry
    reactions: ReactionService

    def register_reaction_tools(self) -> None:
        self.reactions.restore_reactions()

        def create_reaction(
            reaction: CreateReactionSchema,
        ) -> ReactionSchema:
            return self.reactions.create_reaction(reaction)

        def list_reactions() -> list[ReactionSchema]:
            return self.reactions.list_reactions()

        def delete_reaction(
            request: DeleteReactionSchema,
        ) -> DeleteReactionResultSchema:
            deleted = self.reactions.delete_reaction(
                request.reaction_id
            )
            return DeleteReactionResultSchema(deleted=deleted)

        self.tools.register(ToolDefinition(
            name="create_reaction",
            description=(
                "Create a persisted reaction that invokes a Gerbera tool "
                "when a hardware event condition matches."
            ),
            tool_function=create_reaction,
            annotations=ToolAnnotations(
                title="Create reaction",
                readOnlyHint=False,
                openWorldHint=False,
            ),
        ))
        self.tools.register(ToolDefinition(
            name="list_reactions",
            description="List active reactions and their runtime status.",
            tool_function=list_reactions,
            annotations=ToolAnnotations(
                title="List reactions",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        ))
        self.tools.register(ToolDefinition(
            name="delete_reaction",
            description="Permanently delete an active reaction.",
            tool_function=delete_reaction,
            annotations=ToolAnnotations(
                title="Delete reaction",
                readOnlyHint=False,
                destructiveHint=True,
                openWorldHint=False,
            ),
        ))

    def register_reaction_catalog_tool(self) -> None:
        def list_reaction_events() -> (
            dict[str, dict[str, dict[str, dict[str, object]]]]
        ):
            return self.reactions.event_catalog()

        self.tools.register(ToolDefinition(
            name="list_reaction_events",
            description=(
                "List the registered hardware events that can be used "
                "when creating reactions."
            ),
            tool_function=list_reaction_events,
            annotations=ToolAnnotations(
                title="List events available for reactions",
                readOnlyHint=True,
                openWorldHint=False,
            ),
        ))
