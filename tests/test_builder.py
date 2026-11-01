import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from lsofframp.core.manifest import Manifest, ObjectKind, OpenStandard, sha256_ref
from lsofframp.readers.builder import build_manifest
from lsofframp.readers.package import IssueCode, read_packages

FIXED_TIME = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def build(*archives: Path):
    return build_manifest(read_packages(archives), "0.0.1", FIXED_TIME)


def test_files_and_folders_become_objects(tmp_path):
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("docs/", b"")
        handle.writestr("docs/notes.docx", b"abc")
        handle.writestr("docs/old.doc", b"def")
    manifest, issues = build(archive)
    assert not issues
    by_path = {item.path: item for item in manifest.objects}
    assert by_path["docs"].kind is ObjectKind.FOLDER
    assert by_path["docs"].integrity is None
    notes = by_path["docs/notes.docx"]
    assert notes.kind is ObjectKind.FILE
    assert notes.part == "export.zip"
    assert notes.integrity.hash == sha256_ref(b"abc")
    assert notes.integrity.bytes == 3
    assert notes.format.open_standard is OpenStandard.YES
    assert by_path["docs/old.doc"].format.open_standard is OpenStandard.NO


def test_unknown_information_stays_unknown(tmp_path):
    manifest, _ = build(make_zip(tmp_path / "export.zip", {"a.txt": b"x"}))
    item = manifest.objects[0]
    assert item.shared_with is None
    assert item.owner is None
    assert manifest.provider.id == "unknown"


def test_same_input_gives_identical_manifest(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"b.txt": b"2", "a.txt": b"1"})
    first, _ = build(archive)
    second, _ = build(archive)
    assert first.to_json() == second.to_json()
    assert first.digest() == second.digest()


def test_manifest_survives_a_write_and_load(tmp_path):
    manifest, _ = build(make_zip(tmp_path / "export.zip", {"a.txt": b"1"}))
    target = tmp_path / "manifest.json"
    manifest.write(target)
    assert Manifest.load(target) == manifest
    assert json.loads(target.read_text(encoding="utf-8"))["schema_version"] == "0.1"


def test_repeated_file_across_parts_is_reported_once(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    first = make_zip(tmp_path / "one" / "part-1.zip", {"a.txt": b"1"})
    second = make_zip(tmp_path / "two" / "part-2.zip", {"a.txt": b"2", "b.txt": b"3"})
    manifest, issues = build(first, second)
    assert {item.path for item in manifest.objects} == {"a.txt", "b.txt"}
    assert [issue.code for issue in issues] == [IssueCode.DUPLICATE_PATH]
    kept = next(item for item in manifest.objects if item.path == "a.txt")
    assert kept.part == "part-1.zip"


def test_repeated_folder_across_parts_is_merged_silently(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    for folder, name in (("one", "part-1.zip"), ("two", "part-2.zip")):
        archive = tmp_path / folder / name
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("Takeout/", b"")
            handle.writestr(f"Takeout/{name}.txt", b"x")
    manifest, issues = build(tmp_path / "one" / "part-1.zip", tmp_path / "two" / "part-2.zip")
    assert not issues
    assert [item.kind for item in manifest.objects].count(ObjectKind.FOLDER) == 1
    assert len(manifest.objects) == 3