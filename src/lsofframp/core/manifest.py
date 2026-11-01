"""Portability Manifest: provider-independent inventory of an export package."""

import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

SCHEMA_VERSION = "0.1"
SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

_CHUNK_SIZE = 1024 * 1024
_MAX_PATH_LENGTH = 4096
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_SHA256_REF = re.compile(r"sha256:[0-9a-f]{64}")
_QUERY_OR_FRAGMENT = re.compile(r"[?#]")

Sha256Ref = Annotated[str, StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$")]
HashRef = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+:[0-9a-f]{8,128}$")]
ObjectId = Annotated[str, StringConstraints(pattern=r"^obj_[0-9a-f]{16}$")]
MediaType = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$",
        to_lower=True,
    ),
]


class ManifestError(Exception):
    """Base class for failures raised by this package."""


class UnsafePathError(ManifestError, ValueError):
    """A package path is absolute, escapes the package root or is malformed."""


class ChecksumError(ManifestError):
    """A checksum could not be computed or an input digest is malformed."""


class ManifestLoadError(ManifestError):
    """A manifest file could not be read or does not match the schema."""


class PackageKind(str, Enum):
    ZIP = "zip"
    DIRECTORY = "directory"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class ObjectKind(str, Enum):
    FILE = "file"
    FOLDER = "folder"
    MAIL_MESSAGE = "mail_message"
    CALENDAR_EVENT = "calendar_event"
    CONTACT = "contact"
    LINK = "link"


class OpenStandard(str, Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class PrincipalKind(str, Enum):
    USER = "user"
    GROUP = "group"
    DOMAIN = "domain"
    ANYONE_WITH_LINK = "anyone_with_link"
    UNKNOWN = "unknown"


class ShareRole(str, Enum):
    VIEWER = "viewer"
    COMMENTER = "commenter"
    EDITOR = "editor"
    OWNER = "owner"
    UNKNOWN = "unknown"


class ReferenceScope(str, Enum):
    PROVIDER = "provider"
    PUBLIC_WEB = "public_web"
    UNKNOWN = "unknown"


def validate_package_path(path: str) -> str:
    """Return ``path`` unchanged if it is a safe, normalised, relative POSIX path."""
    if not path or len(path) > _MAX_PATH_LENGTH:
        raise UnsafePathError("path is empty or too long")
    if "\x00" in path or "\\" in path:
        raise UnsafePathError(f"path contains a forbidden character: {path!r}")
    if path.startswith("/") or _DRIVE_PREFIX.match(path):
        raise UnsafePathError(f"path is absolute: {path!r}")
    if any(segment in ("", ".", "..") for segment in path.split("/")):
        raise UnsafePathError(f"path is not normalised or escapes the package: {path!r}")
    return path


def derive_object_id(kind: ObjectKind, path: str | None, original_id: str | None) -> str:
    """Build a stable object identifier from what identifies the object in the package."""
    material = "\x00".join((kind.value, path or "", original_id or ""))
    digest = hashlib.sha256(material.encode("utf-8", "surrogatepass")).hexdigest()
    return f"obj_{digest[:16]}"


def sha256_ref(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def sha256_file(path: Path) -> str:
    """Hash a file in chunks; raise ChecksumError if it cannot be read."""
    path = Path(path)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ChecksumError(f"cannot read {path.name}: {exc.strerror or exc}") from exc
    return f"sha256:{digest.hexdigest()}"


def directory_digest(entries: Iterable[tuple[str, str]]) -> str:
    """Digest of a directory listing given as ``(relative path, sha256 ref)`` pairs.

    The digest covers lines of ``path NUL hex`` in path order, so it does not
    depend on the order in which the files were walked.
    """
    ordered = sorted(entries)
    paths = [path for path, _ in ordered]
    if len(paths) != len(set(paths)):
        raise ChecksumError("directory listing contains duplicate paths")
    digest = hashlib.sha256()
    for path, file_hash in ordered:
        validate_package_path(path)
        if not _SHA256_REF.fullmatch(file_hash):
            raise ChecksumError(f"malformed checksum for {path!r}")
        line = f"{path}\x00{file_hash.removeprefix('sha256:')}\n"
        digest.update(line.encode("utf-8", "surrogatepass"))
    return f"sha256:{digest.hexdigest()}"


def strip_url_secrets(target: str) -> str:
    """Drop credentials, query and fragment from http(s) URLs.

    Targets that are not http(s), or cannot be parsed, only lose their query
    and fragment.
    """
    fallback = _QUERY_OR_FRAGMENT.split(target, maxsplit=1)[0]
    try:
        parts = urlsplit(target)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return fallback
        host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
        port = parts.port
    except ValueError:
        return fallback
    netloc = f"{host}:{port}" if port else host
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def write_text_atomic(path: Path, text: str) -> None:
    """Write UTF-8 text with LF newlines by replacing the target in one step."""
    path = Path(path)
    try:
        descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            os.replace(temp_name, path)
        except BaseException:
            Path(temp_name).unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise ManifestError(f"cannot write {path.name}: {exc.strerror or exc}") from exc


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolInfo(_Model):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)


class PackagePart(_Model):
    """One archive or directory of an export; split exports have several."""

    name: str = Field(min_length=1, max_length=255)
    kind: PackageKind
    hash: Sha256Ref
    bytes: int = Field(ge=0)
    entry_count: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def validate_bare_name(cls, value: str) -> str:
        if "/" in value or "\\" in value or "\x00" in value:
            raise UnsafePathError(f"part name must not contain a path: {value!r}")
        return value


class SourcePackage(_Model):
    parts: list[PackagePart] = Field(min_length=1)

    @model_validator(mode="after")
    def check_unique_names(self) -> "SourcePackage":
        counts = Counter(part.name for part in self.parts)
        duplicates = sorted(name for name, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"duplicate part names: {duplicates}")
        return self


class ProviderInfo(_Model):
    """Detected provider. ``unknown`` is a valid and expected value."""

    id: str = Field(default="unknown", min_length=1)
    signals: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.NONE

    @model_validator(mode="after")
    def check_consistency(self) -> "ProviderInfo":
        detected = self.id != "unknown"
        if detected and self.confidence is Confidence.NONE:
            raise ValueError("a detected provider needs a confidence above 'none'")
        if not detected and self.confidence is not Confidence.NONE:
            raise ValueError("an unknown provider must have confidence 'none'")
        if detected and not self.signals:
            raise ValueError("a detected provider needs at least one signal")
        return self


class FormatInfo(_Model):
    """File format as seen in the package; ``mediatype`` carries no parameters."""

    mediatype: MediaType | None = None
    extension: str | None = None
    open_standard: OpenStandard = OpenStandard.UNKNOWN

    @field_validator("extension")
    @classmethod
    def normalise_extension(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.lower().lstrip(".") or None


class Owner(_Model):
    principal: str = Field(min_length=1)
    principal_kind: PrincipalKind = PrincipalKind.UNKNOWN


class ShareEntry(_Model):
    principal: str | None = Field(default=None, min_length=1)
    principal_kind: PrincipalKind = PrincipalKind.UNKNOWN
    role: ShareRole = ShareRole.UNKNOWN

    @model_validator(mode="after")
    def check_principal(self) -> "ShareEntry":
        if self.principal is None and self.principal_kind is not PrincipalKind.ANYONE_WITH_LINK:
            raise ValueError("principal is required unless the share is anyone-with-link")
        return self


class ExternalReference(_Model):
    """A target the package refers to but does not contain."""

    target: str = Field(min_length=1)
    scope: ReferenceScope = ReferenceScope.UNKNOWN

    @field_validator("target")
    @classmethod
    def remove_url_secrets(cls, value: str) -> str:
        stripped = strip_url_secrets(value)
        if not stripped:
            raise ValueError("target is empty once query and fragment are removed")
        return stripped


class IntegrityInfo(_Model):
    bytes: int | None = Field(default=None, ge=0)
    hash: Sha256Ref | None = None
    declared_hash: HashRef | None = None
    declared_matches: bool | None = None

    @model_validator(mode="after")
    def check_declaration(self) -> "IntegrityInfo":
        if self.declared_hash is None:
            if self.declared_matches is not None:
                raise ValueError("declared_matches needs a declared_hash")
            return self
        comparable = self.hash is not None and self.declared_hash.startswith("sha256:")
        if comparable and self.declared_matches is not None:
            if (self.declared_hash == self.hash) != self.declared_matches:
                raise ValueError("declared_matches contradicts the recorded hashes")
        return self


class MailInfo(_Model):
    labels: list[str] | None = None
    attachment_count: int | None = Field(default=None, ge=0)


class EventInfo(_Model):
    attendee_count: int | None = Field(default=None, ge=0)
    attachment_count: int | None = Field(default=None, ge=0)
    recurring: bool | None = None


class ContactInfo(_Model):
    has_email: bool | None = None
    has_phone: bool | None = None


_KIND_BLOCKS = {
    ObjectKind.MAIL_MESSAGE: "mail",
    ObjectKind.CALENDAR_EVENT: "event",
    ObjectKind.CONTACT: "contact",
}


class ManifestObject(_Model):
    """One thing found in the package.

    ``None`` means the package does not say; an empty list means it says
    there is nothing. The two are never merged.
    """

    id: ObjectId
    kind: ObjectKind
    part: str | None = None
    path: str | None = None
    source_service: str | None = None
    original_id: str | None = None
    format: FormatInfo = Field(default_factory=FormatInfo)
    owner: Owner | None = None
    shared_with: list[ShareEntry] | None = None
    depends_on: list[ObjectId] = Field(default_factory=list)
    external_references: list[ExternalReference] = Field(default_factory=list)
    integrity: IntegrityInfo | None = None
    unmapped_fields: list[str] = Field(default_factory=list)
    mail: MailInfo | None = None
    event: EventInfo | None = None
    contact: ContactInfo | None = None

    @field_validator("path")
    @classmethod
    def validate_path_field(cls, value: str | None) -> str | None:
        return None if value is None else validate_package_path(value)

    @field_validator("depends_on", "unmapped_fields")
    @classmethod
    def sort_unique(cls, value: list[str]) -> list[str]:
        return sorted(set(value))

    @field_validator("external_references")
    @classmethod
    def sort_references(cls, value: list[ExternalReference]) -> list[ExternalReference]:
        unique = {(ref.target, ref.scope.value): ref for ref in value}
        return [unique[key] for key in sorted(unique)]

    @field_validator("shared_with")
    @classmethod
    def sort_shares(cls, value: list[ShareEntry] | None) -> list[ShareEntry] | None:
        if value is None:
            return None
        return sorted(
            value,
            key=lambda entry: (entry.principal_kind.value, entry.principal or "", entry.role.value),
        )

    @model_validator(mode="after")
    def check_consistency(self) -> "ManifestObject":
        if self.kind in (ObjectKind.FILE, ObjectKind.FOLDER) and self.path is None:
            raise ValueError(f"a {self.kind.value} needs a path")
        expected = _KIND_BLOCKS.get(self.kind)
        for block in ("mail", "event", "contact"):
            if getattr(self, block) is not None and block != expected:
                raise ValueError(f"'{block}' is not allowed on a {self.kind.value}")
        if self.id in self.depends_on:
            raise ValueError("an object cannot depend on itself")
        return self


class Manifest(_Model):
    """Inventory derived from the package alone, independent of any check run."""

    schema_version: Literal["0.1"] = SCHEMA_VERSION
    generated_at: datetime
    tool: ToolInfo
    source_package: SourcePackage
    provider: ProviderInfo = Field(default_factory=ProviderInfo)
    objects: list[ManifestObject] = Field(default_factory=list)

    @field_validator("generated_at")
    @classmethod
    def normalise_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value.astimezone(timezone.utc).replace(microsecond=0)

    @model_validator(mode="after")
    def check_references(self) -> "Manifest":
        counts = Counter(obj.id for obj in self.objects)
        duplicates = sorted(key for key, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"duplicate object ids: {duplicates[:5]}")
        parts = {part.name for part in self.source_package.parts}
        for obj in self.objects:
            if obj.part is not None and obj.part not in parts:
                raise ValueError(f"{obj.id} refers to unknown part {obj.part!r}")
            missing = [target for target in obj.depends_on if target not in counts]
            if missing:
                raise ValueError(f"{obj.id} depends on unknown objects: {missing[:5]}")
        self.objects = sorted(self.objects, key=lambda obj: obj.id)
        return self

    def to_json(self) -> str:
        return self.model_dump_json(indent=2) + "\n"

    def digest(self) -> str:
        """SHA-256 of the exact serialised file, as referenced by an Evidence Pack."""
        return sha256_ref(self.to_json().encode("utf-8"))

    def write(self, path: Path) -> None:
        write_text_atomic(Path(path), self.to_json())

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        path = Path(path)
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ManifestLoadError(f"cannot read {path.name}: {exc}") from exc
        try:
            return cls.model_validate_json(raw)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()[:5]
            )
            raise ManifestLoadError(
                f"{path.name} is not a valid manifest ({exc.error_count()} error(s)): {problems}"
            ) from exc


def manifest_schema() -> dict:
    schema = Manifest.model_json_schema()
    schema["$schema"] = SCHEMA_DIALECT
    schema["title"] = "LSofframp Portability Manifest"
    return schema


def manifest_schema_text() -> str:
    return json.dumps(manifest_schema(), indent=2) + "\n"