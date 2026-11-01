import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from lsofframp.core.evidence import (
    EvidenceLoadError,
    EvidencePack,
    IssueRecord,
    RuleResult,
    RuleStatus,
    verify_checksum,
)
from lsofframp.core.manifest import ToolInfo

DIGEST = "sha256:" + "a" * 64
OBJECT_A = "obj_" + "a" * 16
OBJECT_B = "obj_" + "b" * 16
STAMP = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_result(rule_id: str = "format.open", **fields) -> RuleResult:
    values = {"rule_id": rule_id, "status": RuleStatus.PASS, "summary": "ok"}
    values.update(fields)
    return RuleResult(**values)


def make_pack(**fields) -> EvidencePack:
    values = {
        "generated_at": STAMP,
        "tool": ToolInfo(name="lsofframp", version="0.0.1"),
        "manifest_digest": DIGEST,
        "results": [make_result()],
    }
    values.update(fields)
    return EvidencePack(**values)


@pytest.mark.parametrize("rule_id", ["Format.open", "open", "format.", "1a.b", "a b.c"])
def test_rule_ids_must_be_dotted_lowercase_names(rule_id):
    with pytest.raises(ValidationError):
        make_result(rule_id)


def test_object_ids_are_sorted_and_unique():
    result = make_result(object_ids=[OBJECT_B, OBJECT_A, OBJECT_B])
    assert result.object_ids == [OBJECT_A, OBJECT_B]


def test_results_are_ordered_and_rule_ids_must_be_unique():
    pack = make_pack(results=[make_result("z.last"), make_result("a.first")])
    assert [result.rule_id for result in pack.results] == ["a.first", "z.last"]
    with pytest.raises(ValidationError):
        make_pack(results=[make_result("a.same"), make_result("a.same")])


def test_pack_has_no_overall_score():
    assert "score" not in " ".join(EvidencePack.model_fields)


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        RuleResult(rule_id="a.b", status=RuleStatus.PASS, summary="ok", score=1)


def test_timestamps_must_be_aware_and_become_utc():
    with pytest.raises(ValidationError):
        make_pack(generated_at=datetime(2026, 11, 1, 12, 0, 0))
    local = datetime(2026, 11, 1, 13, 0, 0, tzinfo=timezone(timedelta(hours=1)))
    assert '"generated_at": "2026-11-01T12:00:00Z"' in make_pack(generated_at=local).to_json()


def test_issues_are_kept_in_a_stable_order():
    first = IssueRecord(code="symlink", part="b.zip", path="x", detail="d")
    second = IssueRecord(code="symlink", part="a.zip", path="y", detail="d")
    pack = make_pack(read_issues=[first, second])
    assert [issue.part for issue in pack.read_issues] == ["a.zip", "b.zip"]


def test_write_load_roundtrip_with_checksum_file(tmp_path):
    pack = make_pack(read_issues=[IssueRecord(code="symlink", part="a.zip", detail="d")])
    target = tmp_path / "evidence.json"
    pack.write(target)
    assert EvidencePack.load(target) == pack
    sidecar = tmp_path / "evidence.json.sha256"
    assert sidecar.read_text(encoding="utf-8") == f"{pack.digest()[7:]}  evidence.json\n"
    assert verify_checksum(target) is True


def test_changed_file_fails_verification(tmp_path):
    target = tmp_path / "evidence.json"
    make_pack().write(target)
    data = json.loads(target.read_text(encoding="utf-8"))
    data["results"][0]["status"] = "fail"
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assert verify_checksum(target) is False


def test_missing_checksum_file_is_an_error(tmp_path):
    target = tmp_path / "evidence.json"
    make_pack().write(target)
    (tmp_path / "evidence.json.sha256").unlink()
    with pytest.raises(EvidenceLoadError):
        verify_checksum(target)


def test_load_reports_missing_and_invalid_files(tmp_path):
    with pytest.raises(EvidenceLoadError):
        EvidencePack.load(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(EvidenceLoadError):
        EvidencePack.load(broken)
    wrong = tmp_path / "wrong.json"
    data = json.loads(make_pack().to_json())
    data["schema_version"] = "9.9"
    wrong.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(EvidenceLoadError):
        EvidencePack.load(wrong)