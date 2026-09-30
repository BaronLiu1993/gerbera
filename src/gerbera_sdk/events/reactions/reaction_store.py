import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from gerbera_sdk.events.reactions.reaction_schema import (
    ReactionDefinitionSchema,
)
from gerbera_sdk.paths import REACTIONS_PATH


@dataclass(frozen=True)
class ReactionStore:
    root: Path = REACTIONS_PATH

    def save(self, definition: ReactionDefinitionSchema) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.definition_path(definition.reaction_id)
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(
                definition.model_dump(mode="json"),
                indent=2,
                sort_keys=True,
            )
        )
        temporary_path.replace(path)

    def delete(self, reaction_id: UUID) -> None:
        self.definition_path(reaction_id).unlink(missing_ok=True)

    def load(self) -> tuple[ReactionDefinitionSchema, ...]:
        if not self.root.exists():
            return ()

        definitions: list[ReactionDefinitionSchema] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                definitions.append(
                    ReactionDefinitionSchema.model_validate_json(
                        path.read_text()
                    )
                )
            except (OSError, ValidationError, json.JSONDecodeError):
                continue
        return tuple(definitions)

    def definition_path(self, reaction_id: UUID) -> Path:
        return self.root / f"{reaction_id}.json"
