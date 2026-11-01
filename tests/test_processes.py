from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from lsofframp.core.evidence import EvidencePack, ItemState, ProcessResult, least_favourable
from lsofframp.core.manifest import (
    Manifest,
    ManifestObject,
    ObjectKind,
    PackageKind,
    PackagePart,
    PrincipalKind,
    ShareEntry,
    SourcePackage,
    ToolInfo,
    derive_object_id,
)
from lsofframp.core.process import Process, ProcessError, ProcessFile, ProcessItem, Selector
from lsofframp.core.roster import Roster
from lsofframp.readers.builder import build_manifest
from lsofframp.readers.formats import describe_format
from lsofframp.readers.package import IssueCode, ReadIssue, read_packages
from lsofframp.rules.builtin import build_evidence
from lsofframp.rules.processes import (
    evaluate_item,
    evaluate_process,
    evaluate_processes,
    run_process_stage,
    select_objects,
)

STAMP = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
HASH = "sha256:" + "a" * 64
BOARD = "board@example.org"


def share(principal: str, kind: PrincipalKind = PrincipalKind.USER) -> ShareEntry:
    return ShareEntry(principal=principal, principal_kind=kind)


def file_object(path: str, shared=None) -> ManifestObject:
    return ManifestObject(
        id=derive_object_id(ObjectKind.FILE, path, None),
        kind=ObjectKind.FILE,
        path=path,
        format=describe_format(path),
        shared_with=shared,
    )


def folder_object(path: str) -> ManifestObject:
    return ManifestObject(
        id=derive_object_id(ObjectKind.FOLDER, path, None), kind=ObjectKind.FOLDER, path=path
    )


def make_manifest(objects) -> Manifest:
    part = PackagePart(
        name="export.zip", kind=PackageKind.ZIP, hash=HASH, bytes=1, entry_count=len(objects)
    )
    return Manifest(
        generated_at=STAMP,
        tool=ToolInfo(name="lsofframp", version="0.0.1"),
        source_package=SourcePackage(parts=[part]),
        objects=objects,
    )


def item(select: dict, requires: str | None = None, label: str = "Item") -> ProcessItem:
    return ProcessItem(label=label, select=Selector(**select), requires_shared_with=requires)


def make_roster(tmp_path, rows: str) -> Roster:
    target = tmp_path / "roster.csv"
    target.write_text("email,active\n" + rows, encoding="utf-8")
    return Roster.load(target, date(2026, 10, 1))


def test_least_favourable_order():
    assert least_favourable([ItemState.USABLE, ItemState.NEEDS_CONVERSION]) is (
        ItemState.NEEDS_CONVERSION
    )
    assert least_favourable([ItemState.NEEDS_CONVERSION, ItemState.UNKNOWN]) is ItemState.UNKNOWN
    assert least_favourable([ItemState.UNKNOWN, ItemState.NOT_USABLE]) is ItemState.NOT_USABLE
    assert least_favourable([ItemState.USABLE]) is ItemState.USABLE


def test_process_result_state_must_match_its_items():
    good = {"label": "A", "state": "usable", "reason": "ok"}
    with pytest.raises(ValueError):
        ProcessResult(name="P", state="not_usable", items=[good])


def test_selectors_pick_by_kind_prefix_and_id():
    manifest = make_manifest(
        [file_object("Members/a.pdf"), file_object("Membership.pdf"), folder_object("Members")]
    )
    assert len(select_objects(manifest, Selector(kind=ObjectKind.FILE))) == 2
    assert {o.path for o in select_objects(manifest, Selector(path_prefix="Members"))} == {
        "Members",
        "Members/a.pdf",
    }
    wanted = file_object("Membership.pdf").id
    assert [o.path for o in select_objects(manifest, Selector(object_id=wanted))] == [
        "Membership.pdf"
    ]


def test_open_files_are_usable_and_say_what_was_checked():
    manifest = make_manifest([file_object("Members/a.pdf"), file_object("Members/b.csv")])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}), None)
    assert result.state is ItemState.USABLE
    assert result.matched == 2
    assert result.object_ids == []
    assert "none of the checks found a problem" in result.reason


def test_closed_format_needs_conversion():
    manifest = make_manifest([file_object("Members/a.pdf"), file_object("Members/b.xls")])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}), None)
    assert result.state is ItemState.NEEDS_CONVERSION
    assert result.object_ids == [file_object("Members/b.xls").id]


def test_unclassified_format_is_unknown():
    manifest = make_manifest([file_object("Members/a.pdf"), file_object("Members/b.zzz")])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}), None)
    assert result.state is ItemState.UNKNOWN


def test_selector_matching_nothing_is_unknown_not_usable():
    manifest = make_manifest([file_object("Other/a.pdf")])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}), None)
    assert result.state is ItemState.UNKNOWN
    assert result.matched == 0
    assert "matched nothing" in result.reason


def test_folder_alone_does_not_count_as_content():
    manifest = make_manifest([folder_object("Members")])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}), None)
    assert result.state is ItemState.UNKNOWN


@pytest.mark.parametrize("kind", ["contact", "calendar_event", "mail_message"])
def test_kinds_without_reader_say_so(kind):
    manifest = make_manifest([file_object("a.pdf")])
    result = evaluate_item(manifest, [], item({"kind": kind}), None)
    assert result.state is ItemState.UNKNOWN
    assert "does not yet read" in result.reason


def test_read_problems_under_the_prefix_make_the_item_not_usable():
    manifest = make_manifest([file_object("Members/a.pdf")])
    problem = ReadIssue(IssueCode.CORRUPT_ENTRY, "export.zip", "Members/broken.pdf", "bad")
    result = evaluate_item(manifest, [problem], item({"path_prefix": "Members"}), None)
    assert result.state is ItemState.NOT_USABLE
    assert "1 read problem(s)" in result.reason


def test_read_problem_alone_is_not_reported_as_matched_nothing():
    manifest = make_manifest([file_object("Other/a.pdf")])
    problem = ReadIssue(IssueCode.CORRUPT_ENTRY, "export.zip", "Members/broken.pdf", "bad")
    result = evaluate_item(manifest, [problem], item({"path_prefix": "Members"}), None)
    assert result.state is ItemState.NOT_USABLE


def test_sharing_not_stated_is_unknown():
    manifest = make_manifest([file_object("Members/a.pdf")])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}, BOARD), None)
    assert result.state is ItemState.UNKNOWN
    assert "do not say who can access them" in result.reason


def test_stated_sharing_without_the_person_is_not_usable():
    manifest = make_manifest([file_object("Members/a.pdf", [share("someone@example.org")])])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}, BOARD), None)
    assert result.state is ItemState.NOT_USABLE


def test_empty_share_list_means_nobody_and_is_not_usable():
    manifest = make_manifest([file_object("Members/a.pdf", [])])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}, BOARD), None)
    assert result.state is ItemState.NOT_USABLE


def test_group_or_domain_sharing_cannot_be_resolved():
    shared = [share("example.org", PrincipalKind.DOMAIN)]
    manifest = make_manifest([file_object("Members/a.pdf", shared)])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}, BOARD), None)
    assert result.state is ItemState.UNKNOWN


def test_shared_with_person_but_no_roster_is_unknown():
    manifest = make_manifest([file_object("Members/a.pdf", [share(BOARD.upper())])])
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}, BOARD), None)
    assert result.state is ItemState.UNKNOWN
    assert "no roster was given" in result.reason


def test_roster_decides_active_inactive_and_missing(tmp_path):
    manifest = make_manifest([file_object("Members/a.pdf", [share(BOARD)])])
    wanted = item({"path_prefix": "Members"}, BOARD)
    active = make_roster(tmp_path, f"{BOARD},true\n")
    inactive = make_roster(tmp_path, f"{BOARD},false\n")
    absent = make_roster(tmp_path, "other@example.org,true\n")
    assert evaluate_item(manifest, [], wanted, active).state is ItemState.USABLE
    assert evaluate_item(manifest, [], wanted, inactive).state is ItemState.NOT_USABLE
    assert evaluate_item(manifest, [], wanted, absent).state is ItemState.UNKNOWN


def test_reasons_never_contain_the_required_address(tmp_path):
    manifest = make_manifest([file_object("Members/a.pdf", [share(BOARD)])])
    roster = make_roster(tmp_path, f"{BOARD},false\n")
    result = evaluate_item(manifest, [], item({"path_prefix": "Members"}, BOARD), roster)
    assert BOARD not in result.reason


def test_process_state_is_the_least_favourable_item(tmp_path):
    manifest = make_manifest([file_object("A/a.pdf"), file_object("B/b.xls")])
    process = Process(
        name="Both",
        items=[
            item({"path_prefix": "A"}, label="First"),
            item({"path_prefix": "B"}, label="Second"),
        ],
    )
    result = evaluate_process(manifest, [], process, None)
    assert result.state is ItemState.NEEDS_CONVERSION
    assert [entry.state for entry in result.items] == [
        ItemState.USABLE,
        ItemState.NEEDS_CONVERSION,
    ]


def test_evidence_records_roster_fingerprint_not_content(tmp_path):
    manifest = make_manifest([file_object("Members/a.pdf", [share(BOARD)])])
    roster = make_roster(tmp_path, f"{BOARD},true\nsecret-person@example.org,true\n")
    definition = ProcessFile(
        processes=[Process(name="P", items=[item({"path_prefix": "Members"}, BOARD)])]
    )
    processes = evaluate_processes(manifest, [], definition, HASH, roster)
    pack = build_evidence(manifest, [], "0.0.1", generated_at=STAMP, processes=processes)
    text = pack.to_json()
    assert "secret-person" not in text
    assert BOARD not in text
    assert '"row_count": 2' in text
    assert '"as_of": "2026-10-01"' in text
    target = tmp_path / "evidence.json"
    pack.write(target)
    assert EvidencePack.load(target).processes == pack.processes


def test_pack_without_processes_stays_valid():
    pack = build_evidence(make_manifest([file_object("a.pdf")]), [], "0.0.1", generated_at=STAMP)
    assert pack.processes is None
    assert EvidencePack.model_validate_json(pack.to_json()).processes is None


def write_definition(tmp_path: Path) -> Path:
    target = tmp_path / "process.json"
    target.write_text(
        '{"schema_version": "0.1", "processes": [{"name": "P", "items": '
        '[{"label": "L", "select": {"path_prefix": "Members"}}]}]}',
        encoding="utf-8",
    )
    return target


def write_csv(tmp_path: Path) -> Path:
    target = tmp_path / "roster.csv"
    target.write_text("email,active\na@example.org,true\n", encoding="utf-8")
    return target


def test_stage_without_inputs_returns_nothing():
    assert run_process_stage(make_manifest([]), [], None, None, None) is None


def test_stage_runs_with_a_definition(tmp_path):
    manifest = make_manifest([file_object("Members/a.pdf")])
    outcome = run_process_stage(manifest, [], write_definition(tmp_path), None, None)
    assert outcome is not None
    assert outcome.roster is None
    assert outcome.results[0].state is ItemState.USABLE
    assert outcome.definition_sha256.startswith("sha256:")


def test_stage_runs_with_a_roster_and_date(tmp_path):
    manifest = make_manifest([file_object("Members/a.pdf")])
    outcome = run_process_stage(
        manifest,
        [],
        write_definition(tmp_path),
        write_csv(tmp_path),
        "2026-10-01",
        today=date(2026, 11, 1),
    )
    assert outcome.roster.row_count == 1
    assert outcome.roster.as_of == date(2026, 10, 1)


@pytest.mark.parametrize(
    "use_process, use_roster, as_of",
    [
        (False, True, "2026-10-01"),
        (False, False, "2026-10-01"),
        (True, True, None),
        (True, False, "2026-10-01"),
        (True, True, "01.10.2026"),
        (True, True, "2026-12-31"),
    ],
)
def test_stage_rejects_incomplete_or_wrong_inputs(tmp_path, use_process, use_roster, as_of):
    with pytest.raises(ProcessError):
        run_process_stage(
            make_manifest([]),
            [],
            write_definition(tmp_path) if use_process else None,
            write_csv(tmp_path) if use_roster else None,
            as_of,
            today=date(2026, 11, 1),
        )


def test_end_to_end_with_a_real_package(tmp_path):
    import zipfile

    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("Members/list.xls", b"x")
        handle.writestr("Members/notes.pdf", b"y")
    manifest, issues = build_manifest(read_packages([archive]), "0.0.1")
    outcome = run_process_stage(manifest, issues, write_definition(tmp_path), None, None)
    assert outcome.results[0].state is ItemState.NEEDS_CONVERSION
