"""Member roster: the organisation's own list of people and whether they are active.

The roster is a local CSV supplied by the organisation, together with the date it
reflects. Only its hash, row count and date are meant to reach the Evidence Pack,
never its contents. Error messages therefore name rows and columns, not cell values.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from lsofframp.core.manifest import ManifestError, Sha256Ref, sha256_ref

MAX_ROSTER_BYTES = 20 * 1024 * 1024
MAX_ROSTER_ROWS = 100_000

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TRUE = frozenset({"true", "yes", "y", "1", "ja", "j"})
_FALSE = frozenset({"false", "no", "n", "0", "nein"})
_REQUIRED = ("email", "active")


class RosterError(ManifestError):
    """Base class for roster problems."""


class RosterLoadError(RosterError):
    """The roster file is missing, unreadable or invalid."""


class RosterInfo(BaseModel):
    """What may be recorded about a roster: its fingerprint, size and date."""

    model_config = ConfigDict(extra="forbid")

    sha256: Sha256Ref
    row_count: int = Field(ge=0)
    as_of: date


@dataclass(frozen=True)
class Member:
    email: str
    active: bool
    name: str | None = None
    role: str | None = None


@dataclass(frozen=True)
class Roster:
    members: tuple[Member, ...]
    info: RosterInfo

    def find(self, email: str) -> Member | None:
        wanted = email.strip().lower()
        return next((member for member in self.members if member.email == wanted), None)

    @classmethod
    def load(cls, path: Path, as_of: date) -> "Roster":
        path = Path(path)
        try:
            if path.stat().st_size > MAX_ROSTER_BYTES:
                raise RosterLoadError(f"{path.name} is larger than {MAX_ROSTER_BYTES} bytes")
            data = path.read_bytes()
        except OSError as exc:
            raise RosterLoadError(f"cannot read {path.name}: {exc.strerror or exc}") from exc
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise RosterLoadError(f"{path.name} is not valid UTF-8 text") from exc
        members = _parse(path.name, text)
        info = RosterInfo(sha256=sha256_ref(data), row_count=len(members), as_of=as_of)
        return cls(members=tuple(members), info=info)


def _parse(name: str, text: str) -> list[Member]:
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise RosterLoadError(f"{name} is empty")
    delimiter = ";" if lines[0].count(";") > lines[0].count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = [cell.strip().lower() for cell in next(reader)]
    missing = [column for column in _REQUIRED if column not in header]
    if missing:
        raise RosterLoadError(f"{name} lacks the required column(s): {', '.join(missing)}")
    if len(set(header)) != len(header):
        raise RosterLoadError(f"{name} has repeated column names")
    position = {column: header.index(column) for column in header}

    members: list[Member] = []
    seen: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(members) >= MAX_ROSTER_ROWS:
            raise RosterLoadError(f"{name} has more than {MAX_ROSTER_ROWS} rows")
        if len(row) != len(header):
            raise RosterLoadError(f"{name}, row {row_number}: expected {len(header)} columns")
        email = row[position["email"]].strip().lower()
        if not _EMAIL.match(email):
            raise RosterLoadError(f"{name}, row {row_number}: the email address is not valid")
        if email in seen:
            raise RosterLoadError(f"{name}, row {row_number}: the email address appears twice")
        seen.add(email)
        members.append(
            Member(
                email=email,
                active=_parse_active(name, row_number, row[position["active"]]),
                name=_optional(row, position, "name"),
                role=_optional(row, position, "role"),
            )
        )
    return members


def _parse_active(name: str, row_number: int, cell: str) -> bool:
    value = cell.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise RosterLoadError(
        f"{name}, row {row_number}: 'active' must be one of true/false, yes/no, ja/nein, 1/0"
    )


def _optional(row: list[str], position: dict[str, int], column: str) -> str | None:
    if column not in position:
        return None
    return row[position[column]].strip() or None
