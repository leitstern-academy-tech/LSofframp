"""The first rehearsal rules; each needs only the file inventory."""

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

from lsofframp.core.evidence import EvidencePack, IssueRecord, RuleResult, RuleStatus
from lsofframp.core.manifest import Manifest, ManifestObject, ObjectKind, OpenStandard, ToolInfo
from lsofframp.readers.package import ReadIssue
from lsofframp.rules.base import RuleContext, RuleSpec, run_rules


def _result(
    rule_id: str, status: RuleStatus, summary: str, objects: Iterable[ManifestObject] = ()
) -> RuleResult:
    ids = [item.id for item in objects]
    return RuleResult(
        rule_id=rule_id, status=status, summary=summary, count=len(ids), object_ids=ids
    )


def _files(manifest: Manifest) -> list[ManifestObject]:
    return [item for item in manifest.objects if item.kind is ObjectKind.FILE]


def read_complete(context: RuleContext) -> RuleResult:
    rule_id = "read.complete"
    issues = context.read_issues
    if not issues:
        return _result(rule_id, RuleStatus.PASS, "The package was read completely.")
    by_path = {item.path: item for item in context.manifest.objects if item.path}
    touched = [by_path[issue.path] for issue in issues if issue.path in by_path]
    codes = ", ".join(sorted({issue.code.value for issue in issues}))
    result = _result(
        rule_id,
        RuleStatus.FAIL,
        f"{len(issues)} problem(s) while reading the package ({codes}).",
        touched,
    )
    return result.model_copy(update={"count": len(issues)})


def open_formats(context: RuleContext) -> RuleResult:
    rule_id = "format.open"
    files = _files(context.manifest)
    if not files:
        return _result(rule_id, RuleStatus.NOT_APPLICABLE, "The package contains no files.")
    closed = [item for item in files if item.format.open_standard is OpenStandard.NO]
    unknown = [item for item in files if item.format.open_standard is OpenStandard.UNKNOWN]
    if closed:
        summary = f"{len(closed)} file(s) use formats that are not open standards"
        if unknown:
            summary += f"; {len(unknown)} more could not be classified"
        return _result(rule_id, RuleStatus.FAIL, summary + ".", closed)
    if unknown:
        return _result(
            rule_id,
            RuleStatus.CANNOT_DETERMINE,
            f"{len(unknown)} file(s) have a format that could not be classified.",
            unknown,
        )
    return _result(rule_id, RuleStatus.PASS, "All files use open standard formats.")


def checksums(context: RuleContext) -> RuleResult:
    rule_id = "integrity.checksums"
    files = _files(context.manifest)
    if not files:
        return _result(rule_id, RuleStatus.NOT_APPLICABLE, "The package contains no files.")
    missing = [item for item in files if item.integrity is None or item.integrity.hash is None]
    mismatched = [
        item for item in files if item.integrity and item.integrity.declared_matches is False
    ]
    declared = [item for item in files if item.integrity and item.integrity.declared_hash]
    undecided = [item for item in declared if item.integrity.declared_matches is None]
    if missing or mismatched:
        return _result(
            rule_id,
            RuleStatus.FAIL,
            f"{len(missing)} file(s) have no checksum and {len(mismatched)} do not match "
            "the checksum the package declares.",
            missing + mismatched,
        )
    if not declared:
        return _result(
            rule_id,
            RuleStatus.CANNOT_DETERMINE,
            "The package declares no checksums, so damage before the export cannot be excluded.",
        )
    if undecided:
        return _result(
            rule_id,
            RuleStatus.CANNOT_DETERMINE,
            f"{len(undecided)} declared checksum(s) could not be compared.",
            undecided,
        )
    return _result(rule_id, RuleStatus.PASS, "Every declared checksum matches.")


def sharing_known(context: RuleContext) -> RuleResult:
    rule_id = "access.sharing_known"
    objects = context.manifest.objects
    if not objects:
        return _result(rule_id, RuleStatus.NOT_APPLICABLE, "The package contains no objects.")
    unknown = [item for item in objects if item.shared_with is None]
    if unknown:
        return _result(
            rule_id,
            RuleStatus.CANNOT_DETERMINE,
            f"The package does not say who can access {len(unknown)} of {len(objects)} object(s).",
            unknown,
        )
    return _result(rule_id, RuleStatus.PASS, "The package states the sharing of every object.")


BUILTIN_RULES: tuple[RuleSpec, ...] = (
    RuleSpec("read.complete", read_complete),
    RuleSpec("format.open", open_formats),
    RuleSpec("integrity.checksums", checksums),
    RuleSpec("access.sharing_known", sharing_known),
)


def build_evidence(
    manifest: Manifest,
    read_issues: Sequence[ReadIssue],
    tool_version: str,
    generated_at: datetime | None = None,
    rules: Sequence[RuleSpec] = BUILTIN_RULES,
) -> EvidencePack:
    """Run the rules against ``manifest`` and record the outcome."""
    results = run_rules(RuleContext(manifest, read_issues), rules)
    return EvidencePack(
        generated_at=generated_at or datetime.now(timezone.utc),
        tool=ToolInfo(name="lsofframp", version=tool_version),
        manifest_digest=manifest.digest(),
        read_issues=[
            IssueRecord(
                code=issue.code.value, part=issue.part, path=issue.path, detail=issue.detail
            )
            for issue in read_issues
        ],
        results=results,
    )