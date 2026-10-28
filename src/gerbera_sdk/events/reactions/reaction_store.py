import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from gerbera_sdk.configuration_io import decode_json

from gerbera_sdk.events.reactions.reaction_schema import (
    CreateReactionSchema,
    ReactionSchema,
)
from gerbera_sdk.paths import REACTIONS_PATH


@dataclass(frozen=True)
class ReactionStore:
    root: Path = REACTIONS_PATH

    def save(self, definition: ReactionSchema) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.definition_path(definition.reaction_id)
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(
                definition.model_dump(
                    mode="json",
                    include=set(CreateReactionSchema.model_fields) | {"schema_version", "reaction_id", "created_at"},
                ),
                indent=2,
                sort_keys=True,
            )
        )
        temporary_path.replace(path)

    def delete(self, reaction_id: UUID) -> None:
        self.definition_path(reaction_id).unlink(missing_ok=True)

    def load(self) -> tuple[ReactionSchema, ...]:
        if not self.root.exists():
            return ()

        definitions: list[ReactionSchema] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                definitions.append(
                    ReactionSchema.model_validate_json(
                        json.dumps(decode_json(path.read_text()))
                    )
                )
            except (OSError, ValidationError, json.JSONDecodeError):
                continue
        return tuple(definitions)

    def definition_path(self, reaction_id: UUID) -> Path:
        return self.root / f"{reaction_id}.json"
