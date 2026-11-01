import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from lsofframp.core.manifest import ObjectKind
from lsofframp.core.process import (
    ProcessFile,
    ProcessLoadError,
    Selector,
    process_schema,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "schemas" / "process.v0.1.json"
EXAMPLE_FILE = ROOT / "examples" / "process.example.json"
OBJECT_ID = "obj_" + "a" * 16


def minimal(**changes) -> dict:
    data = {
        "schema_version": "0.1",
        "processes": [
            {"name": "Billing", "items": [{"label": "Invoices", "select": {"kind": "file"}}]}
        ],
    }
    data.update(changes)
    return data


def write_json(path: Path, data) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_minimal_file_is_valid():
    parsed = ProcessFile.model_validate(minimal())
    item = parsed.processes[0].items[0]
    assert item.select.kind is ObjectKind.FILE
    assert item.requires_shared_with is None


@pytest.mark.parametrize(
    "select",
    [{}, {"kind": "file", "path_prefix": "docs"}, {"path_prefix": "a", "object_id": OBJECT_ID}],
)
def test_selector_needs_exactly_one_criterion(select):
    with pytest.raises(ValidationError):
        Selector(**select)


def test_path_prefix_is_normalised_and_checked():
    assert Selector(path_prefix="Board/").path_prefix == "Board"
    for bad in ["../x", "/abs", "a\\b", "/", ""]:
        with pytest.raises(ValidationError):
            Selector(path_prefix=bad)


def test_object_id_must_have_the_manifest_format():
    assert Selector(object_id=OBJECT_ID).object_id == OBJECT_ID
    with pytest.raises(ValidationError):
        Selector(object_id="not-an-id")


def test_unknown_fields_are_rejected():
    data = minimal()
    data["processes"][0]["items"][0]["score"] = 5
    with pytest.raises(ValidationError):
        ProcessFile.model_validate(data)


def test_names_and_labels_must_be_unique():
    item = {"label": "Same", "select": {"kind": "file"}}
    with pytest.raises(ValidationError):
        ProcessFile.model_validate(minimal(processes=[{"name": "A", "items": [item, item]}]))
    process = {"name": "A", "items": [item]}
    with pytest.raises(ValidationError):
        ProcessFile.model_validate(minimal(processes=[process, process]))


def test_empty_lists_are_rejected():
    with pytest.raises(ValidationError):
        ProcessFile.model_validate(minimal(processes=[]))
    with pytest.raises(ValidationError):
        ProcessFile.model_validate(minimal(processes=[{"name": "A", "items": []}]))


def test_load_reads_a_valid_file(tmp_path):
    target = write_json(tmp_path / "process.json", minimal())
    assert ProcessFile.load(target).processes[0].name == "Billing"


def test_load_accepts_a_byte_order_mark(tmp_path):
    target = tmp_path / "process.json"
    target.write_bytes(b"\xef\xbb\xbf" + json.dumps(minimal()).encode("utf-8"))
    assert ProcessFile.load(target).processes[0].name == "Billing"


def test_load_reports_missing_broken_and_wrong_version_files(tmp_path):
    with pytest.raises(ProcessLoadError):
        ProcessFile.load(tmp_path / "missing.json")
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProcessLoadError):
        ProcessFile.load(broken)
    wrong = write_json(tmp_path / "wrong.json", minimal(schema_version="9.9"))
    with pytest.raises(ProcessLoadError) as caught:
        ProcessFile.load(wrong)
    assert "wrong.json" in str(caught.value)


def test_example_file_stays_valid():
    parsed = ProcessFile.load(EXAMPLE_FILE)
    assert [process.name for process in parsed.processes] == [
        "Member administration",
        "Event planning",
    ]


def test_process_schema_file_matches_models():
    stored = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert stored == process_schema()
