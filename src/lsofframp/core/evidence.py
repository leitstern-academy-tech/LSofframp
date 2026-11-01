"""Exit Evidence Pack: the record of one rehearsal run.

The pack refers to the Manifest by its SHA-256 and never copies its content.
There is deliberately no overall score; each rule reports on its own.
"""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from lsofframp.core.manifest import (
    ChecksumError,
    ManifestError,
    ObjectId,
    Sha256Ref,
    ToolInfo,
    sha256_file,
    sha256_ref,
    write_text_atomic,
)

EVIDENCE_SCHEMA_VERSION = "0.1"
_CHECKSUM_SUFFIX = ".sha256"


class EvidenceError(ManifestError):
    """Base class for Evidence Pack problems."""


class EvidenceLoadError(EvidenceError):
    """An Evidence Pack file is missing, unreadable or invalid."""


class RuleStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    CANNOT_DETERMINE = "cannot_determine"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IssueRecord(_Model):
    """A problem met while reading the package."""

    code: str = Field(min_length=1)
    part: str = Field(min_length=1)
    path: str | None = None
    detail: str


class RuleResult(_Model):
    """Outcome of one rule; ``object_ids`` lists the objects that decided it."""

    rule_id: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
    status: RuleStatus
    summary: str = Field(min_length=1)
    count: int = Field(default=0, ge=0)
    object_ids: list[ObjectId] = Field(default_factory=list)

    @field_validator("object_ids")
    @classmethod
    def sort_unique(cls, value: list[str]) -> list[str]:
        return sorted(set(value))


class EvidencePack(_Model):
    schema_version: Literal["0.1"] = EVIDENCE_SCHEMA_VERSION
    generated_at: datetime
    tool: ToolInfo
    manifest_digest: Sha256Ref
    read_issues: list[IssueRecord] = Field(default_factory=list)
    results: list[RuleResult] = Field(default_factory=list)

    @field_validator("generated_at")
    @classmethod
    def normalise_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value.astimezone(timezone.utc).replace(microsecond=0)

    @model_validator(mode="after")
    def order_and_check(self) -> "EvidencePack":
        ids = [result.rule_id for result in self.results]
        repeated = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
        if repeated:
            raise ValueError(f"duplicate rule ids: {repeated}")
        self.results = sorted(self.results, key=lambda result: result.rule_id)
        self.read_issues = sorted(
            self.read_issues,
            key=lambda issue: (issue.part, issue.path or "", issue.code, issue.detail),
        )
        return self

    def to_json(self) -> str:
        return self.model_dump_json(indent=2) + "\n"

    def digest(self) -> str:
        return sha256_ref(self.to_json().encode("utf-8"))

    def write(self, path: Path) -> None:
        """Write the pack and, next to it, a ``sha256sum``-style checksum file."""
        path = Path(path)
        write_text_atomic(path, self.to_json())
        write_text_atomic(_checksum_path(path), f"{self.digest()[len('sha256:'):]}  {path.name}\n")

    @classmethod
    def load(cls, path: Path) -> "EvidencePack":
        path = Path(path)
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise EvidenceLoadError(f"cannot read {path.name}: {exc}") from exc
        try:
            return cls.model_validate_json(raw)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()[:5]
            )
            raise EvidenceLoadError(
                f"{path.name} is not a valid evidence pack "
                f"({exc.error_count()} error(s)): {problems}"
            ) from exc


def _checksum_path(path: Path) -> Path:
    return path.with_name(path.name + _CHECKSUM_SUFFIX)


def verify_checksum(path: Path) -> bool:
    """Compare the file with its checksum file; raise if the checksum file is unusable."""
    path = Path(path)
    sidecar = _checksum_path(path)
    try:
        recorded = sidecar.read_text(encoding="utf-8").split()[0]
    except (OSError, UnicodeDecodeError, IndexError) as exc:
        raise EvidenceLoadError(f"cannot read a checksum from {sidecar.name}") from exc
    try:
        actual = sha256_file(path)
    except ChecksumError as exc:
        raise EvidenceLoadError(str(exc)) from exc
    return actual == f"sha256:{recorded}"