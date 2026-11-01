"""Process definitions: what an organisation must still be able to do after an exit.

The organisation writes the file; the tool never guesses processes from the package.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from lsofframp.core.manifest import (
    SCHEMA_DIALECT,
    ManifestError,
    ObjectId,
    ObjectKind,
    UnsafePathError,
    validate_package_path,
)

PROCESS_SCHEMA_VERSION = "0.1"


class ProcessError(ManifestError):
    """Base class for process definition problems."""


class ProcessLoadError(ProcessError):
    """A process definition file is missing, unreadable or invalid."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Selector(_Model):
    """Picks objects from the Manifest by exactly one of kind, path prefix or identifier."""

    kind: ObjectKind | None = None
    path_prefix: str | None = None
    object_id: ObjectId | None = None

    @field_validator("path_prefix")
    @classmethod
    def normalise_prefix(cls, value: str | None) -> str | None:
        if value is None:
            return None
        prefix = value.rstrip("/")
        try:
            validate_package_path(prefix)
        except UnsafePathError as exc:
            raise ValueError(str(exc)) from exc
        return prefix

    @model_validator(mode="after")
    def exactly_one_criterion(self) -> "Selector":
        chosen = [self.kind, self.path_prefix, self.object_id]
        if sum(value is not None for value in chosen) != 1:
            raise ValueError("give exactly one of kind, path_prefix or object_id")
        return self


class ProcessItem(_Model):
    label: str = Field(min_length=1, max_length=200)
    select: Selector
    requires_shared_with: str | None = Field(default=None, min_length=1)


class Process(_Model):
    name: str = Field(min_length=1, max_length=200)
    items: list[ProcessItem] = Field(min_length=1)

    @model_validator(mode="after")
    def labels_are_unique(self) -> "Process":
        labels = [item.label for item in self.items]
        repeated = sorted({label for label in labels if labels.count(label) > 1})
        if repeated:
            raise ValueError(f"item labels must be unique within a process: {repeated}")
        return self


class ProcessFile(_Model):
    schema_version: Literal["0.1"] = PROCESS_SCHEMA_VERSION
    processes: list[Process] = Field(min_length=1)

    @model_validator(mode="after")
    def names_are_unique(self) -> "ProcessFile":
        names = [process.name for process in self.processes]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ValueError(f"process names must be unique: {repeated}")
        return self

    @classmethod
    def load(cls, path: Path) -> "ProcessFile":
        path = Path(path)
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise ProcessLoadError(f"cannot read {path.name}: {exc}") from exc
        try:
            return cls.model_validate_json(raw)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()[:5]
            )
            raise ProcessLoadError(
                f"{path.name} is not a valid process file "
                f"({exc.error_count()} error(s)): {problems}"
            ) from exc


def process_schema() -> dict:
    schema = ProcessFile.model_json_schema()
    schema["$schema"] = SCHEMA_DIALECT
    schema["title"] = "LSofframp Process Definition"
    return schema


def process_schema_text() -> str:
    return json.dumps(process_schema(), indent=2) + "\n"
