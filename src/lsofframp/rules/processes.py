"""Evaluate the organisation's process definitions against a Manifest.

Each item gets a state of its own and a process shows the least favourable one.
Nothing is averaged or scored, and a selector that matches nothing is a finding,
never a silent success.
"""

from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from lsofframp.core.evidence import (
    ITEM_STATE_ORDER,
    ItemResult,
    ItemState,
    ProcessEvidence,
    ProcessResult,
    least_favourable,
)
from lsofframp.core.manifest import (
    Manifest,
    ManifestObject,
    ObjectKind,
    OpenStandard,
    PrincipalKind,
    Sha256Ref,
)
from lsofframp.core.process import (
    Process,
    ProcessError,
    ProcessFile,
    ProcessItem,
    Selector,
)
from lsofframp.core.roster import Roster
from lsofframp.readers.package import ReadIssue

_UNREAD_KINDS = frozenset(ObjectKind) - {ObjectKind.FILE, ObjectKind.FOLDER}

_Finding = tuple[ItemState, str]


def select_objects(manifest: Manifest, selector: Selector) -> list[ManifestObject]:
    objects = manifest.objects
    if selector.kind is not None:
        return [item for item in objects if item.kind is selector.kind]
    if selector.object_id is not None:
        return [item for item in objects if item.id == selector.object_id]
    prefix = selector.path_prefix
    return [
        item
        for item in objects
        if item.path is not None and (item.path == prefix or item.path.startswith(prefix + "/"))
    ]


def _issues_for(
    selector: Selector, matched: Sequence[ManifestObject], read_issues: Sequence[ReadIssue]
) -> int:
    if selector.path_prefix is not None:
        prefix = selector.path_prefix
        return sum(
            1
            for issue in read_issues
            if issue.path is not None
            and (issue.path == prefix or issue.path.startswith(prefix + "/"))
        )
    paths = {item.path for item in matched if item.path is not None}
    return sum(1 for issue in read_issues if issue.path in paths)


def _assess_access(
    item: ManifestObject, required: str, roster: Roster | None
) -> list[_Finding]:
    if item.shared_with is None:
        return [(ItemState.UNKNOWN, "do not say who can access them")]
    target = required.strip().lower()
    if not any((entry.principal or "").lower() == target for entry in item.shared_with):
        indirect = any(
            entry.principal_kind in (PrincipalKind.GROUP, PrincipalKind.DOMAIN)
            for entry in item.shared_with
        )
        if indirect:
            return [
                (
                    ItemState.UNKNOWN,
                    "are shared through a group or domain whose members the package does not list",
                )
            ]
        return [(ItemState.NOT_USABLE, "are not shared with the required person")]
    if roster is None:
        return [
            (
                ItemState.UNKNOWN,
                "cannot be matched to an active person because no roster was given",
            )
        ]
    member = roster.find(target)
    if member is None:
        return [(ItemState.UNKNOWN, "are shared with a person who is not on the roster")]
    if not member.active:
        return [(ItemState.NOT_USABLE, "are shared with a person the roster marks as inactive")]
    return []


def _assess_object(
    item: ManifestObject, required: str | None, roster: Roster | None
) -> list[_Finding]:
    findings: list[_Finding] = []
    if item.kind is ObjectKind.FILE:
        if item.format.open_standard is OpenStandard.NO:
            findings.append(
                (ItemState.NEEDS_CONVERSION, "use a format that is not an open standard")
            )
        elif item.format.open_standard is OpenStandard.UNKNOWN:
            findings.append((ItemState.UNKNOWN, "have a format that could not be classified"))
    if required is not None:
        findings.extend(_assess_access(item, required, roster))
    return findings


def evaluate_item(
    manifest: Manifest,
    read_issues: Sequence[ReadIssue],
    item: ProcessItem,
    roster: Roster | None,
) -> ItemResult:
    selector = item.select
    matched = select_objects(manifest, selector)
    content = [entry for entry in matched if entry.kind is not ObjectKind.FOLDER]
    issue_count = _issues_for(selector, matched, read_issues)

    if not content and issue_count == 0:
        if selector.kind in _UNREAD_KINDS:
            reason = (
                "The package reader does not yet read this kind of object, "
                "so finding none proves nothing."
            )
        else:
            reason = "The selector matched nothing in the package."
        return ItemResult(label=item.label, state=ItemState.UNKNOWN, reason=reason)

    grouped: dict[_Finding, list[str]] = {}
    for entry in content:
        for finding in _assess_object(entry, item.requires_shared_with, roster):
            grouped.setdefault(finding, []).append(entry.id)

    states = [state for state, _ in grouped]
    parts: list[tuple[int, str]] = []
    if issue_count:
        states.append(ItemState.NOT_USABLE)
        parts.append((0, f"{issue_count} read problem(s) affect this selection"))
    for (state, cause), ids in grouped.items():
        parts.append((ITEM_STATE_ORDER.index(state), f"{len(ids)} object(s) {cause}"))

    if not parts:
        reason = f"{len(content)} object(s) matched; none of the checks found a problem."
    else:
        text = "; ".join(part for _, part in sorted(parts))
        reason = text[0].upper() + text[1:] + "."
    return ItemResult(
        label=item.label,
        state=least_favourable(states),
        reason=reason,
        matched=len(content),
        object_ids=[object_id for ids in grouped.values() for object_id in ids],
    )


def evaluate_process(
    manifest: Manifest,
    read_issues: Sequence[ReadIssue],
    process: Process,
    roster: Roster | None,
) -> ProcessResult:
    items = [evaluate_item(manifest, read_issues, item, roster) for item in process.items]
    return ProcessResult(
        name=process.name, state=least_favourable(item.state for item in items), items=items
    )


def evaluate_processes(
    manifest: Manifest,
    read_issues: Sequence[ReadIssue],
    definition: ProcessFile,
    definition_digest: Sha256Ref,
    roster: Roster | None = None,
) -> ProcessEvidence:
    return ProcessEvidence(
        definition_sha256=definition_digest,
        roster=roster.info if roster is not None else None,
        results=[
            evaluate_process(manifest, read_issues, process, roster)
            for process in definition.processes
        ],
    )


def _parse_as_of(text: str, today: date) -> date:
    try:
        value = date.fromisoformat(text.strip())
    except ValueError as exc:
        raise ProcessError("--roster-as-of must be a date written YYYY-MM-DD") from exc
    if value > today:
        raise ProcessError("--roster-as-of lies in the future")
    return value


def run_process_stage(
    manifest: Manifest,
    read_issues: Sequence[ReadIssue],
    process_path: Path | None,
    roster_path: Path | None,
    roster_as_of: str | None,
    today: date | None = None,
) -> ProcessEvidence | None:
    """Load the optional local inputs and evaluate; ``None`` when no process file was given."""
    if process_path is None:
        if roster_path is not None or roster_as_of is not None:
            raise ProcessError("--roster and --roster-as-of need --process")
        return None
    roster = None
    if roster_path is None:
        if roster_as_of is not None:
            raise ProcessError("--roster-as-of needs --roster")
    else:
        if roster_as_of is None:
            raise ProcessError(
                "--roster needs --roster-as-of YYYY-MM-DD: "
                "the organisation must state which day the roster reflects"
            )
        as_of = _parse_as_of(roster_as_of, today or datetime.now().astimezone().date())
        roster = Roster.load(roster_path, as_of)
    definition, digest = ProcessFile.load_with_digest(process_path)
    return evaluate_processes(manifest, read_issues, definition, digest, roster)
