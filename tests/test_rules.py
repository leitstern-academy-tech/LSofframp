import zipfile
from datetime import datetime, timezone
from pathlib import Path

from lsofframp.core.evidence import RuleResult, RuleStatus
from lsofframp.core.manifest import (
    Manifest,
    ManifestObject,
    ObjectKind,
    PackageKind,
    PackagePart,
    SourcePackage,
    ToolInfo,
    derive_object_id,
    sha256_file,
)
from lsofframp.readers.builder import build_manifest
from lsofframp.readers.package import IssueCode, ReadIssue, read_packages
from lsofframp.rules.base import RuleContext, RuleSpec, run_rules
from lsofframp.rules.builtin import (
    build_evidence,
    checksums,
    open_formats,
    read_complete,
    sharing_known,
)

STAMP = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def file_object(path: str, **fields) -> ManifestObject:
    return ManifestObject(
        id=derive_object_id(ObjectKind.FILE, path, None),
        kind=ObjectKind.FILE,
        path=path,
        **fields,
    )


def make_context(objects, issues=()) -> RuleContext:
    part = PackagePart(
        name="export.zip", kind=PackageKind.ZIP, hash=HASH_A, bytes=1, entry_count=len(objects)
    )
    manifest = Manifest(
        generated_at=STAMP,
        tool=ToolInfo(name="lsofframp", version="0.0.1"),
        source_package=SourcePackage(parts=[part]),
        objects=objects,
    )
    return RuleContext(manifest, list(issues))


def make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def test_read_complete_passes_without_issues():
    assert read_complete(make_context([file_object("a.txt")])).status is RuleStatus.PASS


def test_read_complete_fails_and_names_touched_objects():
    item = file_object("Report.txt")
    issue = ReadIssue(IssueCode.CASE_COLLISION, "export.zip", "Report.txt", "d")
    skipped = ReadIssue(IssueCode.UNSAFE_PATH, "export.zip", None, "d")
    result = read_complete(make_context([item], [issue, skipped]))
    assert result.status is RuleStatus.FAIL
    assert result.count == 2
    assert result.object_ids == [item.id]


def test_open_formats_fails_on_closed_formats_and_lists_them():
    closed = file_object("old.doc", format={"extension": "doc", "open_standard": "no"})
    fine = file_object("a.pdf", format={"open_standard": "yes"})
    result = open_formats(make_context([closed, fine]))
    assert result.status is RuleStatus.FAIL
    assert result.object_ids == [closed.id]


def test_open_formats_cannot_determine_for_unclassified_files():
    result = open_formats(make_context([file_object("blob.xyz")]))
    assert result.status is RuleStatus.CANNOT_DETERMINE


def test_open_formats_passes_when_everything_is_open():
    item = file_object("a.pdf", format={"open_standard": "yes"})
    assert open_formats(make_context([item])).status is RuleStatus.PASS


def test_open_formats_without_files_is_not_applicable():
    assert open_formats(make_context([])).status is RuleStatus.NOT_APPLICABLE


def test_checksums_cannot_be_judged_when_package_declares_none():
    item = file_object("a.txt", integrity={"bytes": 1, "hash": HASH_A})
    assert checksums(make_context([item])).status is RuleStatus.CANNOT_DETERMINE


def test_checksums_fail_on_missing_hash_or_mismatch():
    bare = file_object("a.txt")
    wrong = file_object(
        "b.txt",
        integrity={"hash": HASH_A, "declared_hash": HASH_B, "declared_matches": False},
    )
    result = checksums(make_context([bare, wrong]))
    assert result.status is RuleStatus.FAIL
    assert set(result.object_ids) == {bare.id, wrong.id}


def test_checksums_pass_when_declared_hashes_match():
    item = file_object(
        "a.txt",
        integrity={"hash": HASH_A, "declared_hash": HASH_A, "declared_matches": True},
    )
    assert checksums(make_context([item])).status is RuleStatus.PASS


def test_checksums_with_uncompared_declaration_stay_undetermined():
    item = file_object("a.txt", integrity={"hash": HASH_A, "declared_hash": "md5:" + "c" * 32})
    result = checksums(make_context([item]))
    assert result.status is RuleStatus.CANNOT_DETERMINE
    assert result.object_ids == [item.id]


def test_sharing_unknown_is_not_the_same_as_nobody():
    unknown = file_object("a.txt")
    private = file_object("b.txt", shared_with=[])
    result = sharing_known(make_context([unknown, private]))
    assert result.status is RuleStatus.CANNOT_DETERMINE
    assert result.object_ids == [unknown.id]
    assert sharing_known(make_context([private])).status is RuleStatus.PASS


def test_failing_rule_is_reported_not_raised():
    def broken(context):
        raise RuntimeError("boom")

    results = run_rules(make_context([]), [RuleSpec("test.broken", broken)])
    assert [(r.rule_id, r.status) for r in results] == [
        ("test.broken", RuleStatus.CANNOT_DETERMINE)
    ]
    assert "RuntimeError" in results[0].summary


def test_build_evidence_binds_manifest_and_issues(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"a.pdf": b"1", "old.doc": b"2"})
    reading = read_packages([archive])
    manifest, merge_issues = build_manifest(reading, "0.0.1", STAMP)
    pack = build_evidence(manifest, [*reading.issues, *merge_issues], "0.0.1", STAMP)
    assert pack.manifest_digest == manifest.digest()
    manifest_file = tmp_path / "manifest.json"
    manifest.write(manifest_file)
    assert sha256_file(manifest_file) == pack.manifest_digest
    statuses = {result.rule_id: result.status for result in pack.results}
    assert statuses == {
        "access.sharing_known": RuleStatus.CANNOT_DETERMINE,
        "format.open": RuleStatus.FAIL,
        "integrity.checksums": RuleStatus.CANNOT_DETERMINE,
        "read.complete": RuleStatus.PASS,
    }


def test_same_input_gives_identical_evidence(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"a.pdf": b"1"})

    def run() -> str:
        reading = read_packages([archive])
        manifest, extra = build_manifest(reading, "0.0.1", STAMP)
        return build_evidence(manifest, [*reading.issues, *extra], "0.0.1", STAMP).to_json()

    assert run() == run()


def test_rule_result_type_is_what_rules_return():
    assert isinstance(read_complete(make_context([])), RuleResult)