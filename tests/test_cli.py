import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from lsofframp import __version__
from lsofframp.cli import app
from lsofframp.core.evidence import EvidencePack, verify_checksum
from lsofframp.core.manifest import Manifest

runner = CliRunner()


def make_zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def run(*args):
    return runner.invoke(app, [str(arg) for arg in args])


def test_version_prints_the_package_version():
    result = run("version")
    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_schema_defaults_to_the_manifest():
    result = run("schema")
    assert result.exit_code == 0
    assert "Portability Manifest" in json.loads(result.output)["title"]


def test_schema_can_write_the_evidence_schema(tmp_path):
    target = tmp_path / "evidence.json"
    result = run("schema", "--kind", "evidence", "-o", target)
    assert result.exit_code == 0
    assert "Evidence Pack" in json.loads(target.read_text(encoding="utf-8"))["title"]


def test_schema_rejects_an_unknown_kind():
    assert run("schema", "--kind", "nonsense").exit_code == 2


def test_inspect_lists_parts_and_issues(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"a.txt": b"1", "../evil.txt": b"2"})
    result = run("inspect", archive)
    assert result.exit_code == 0
    assert "export.zip: zip, 1 entries" in result.output
    assert "Issues: 1" in result.output
    assert "[unsafe_path]" in result.output


def test_inspect_reports_a_file_that_is_not_a_zip(tmp_path):
    broken = tmp_path / "broken.zip"
    broken.write_text("plain text", encoding="utf-8")
    result = run("inspect", broken)
    assert result.exit_code == 2
    assert "broken.zip" in result.output


def test_inspect_needs_an_existing_path(tmp_path):
    assert run("inspect", tmp_path / "missing.zip").exit_code != 0


def test_manifest_prints_json_to_stdout(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"a.pdf": b"1"})
    result = run("manifest", archive)
    assert result.exit_code == 0
    assert json.loads(result.output)["objects"][0]["path"] == "a.pdf"


def test_manifest_writes_a_loadable_file(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"a.pdf": b"1"})
    target = tmp_path / "manifest.json"
    assert run("manifest", archive, "-o", target).exit_code == 0
    assert Manifest.load(target).objects[0].path == "a.pdf"


def test_rehearse_writes_manifest_and_evidence(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"a.pdf": b"1", "old.doc": b"2"})
    out = tmp_path / "out"
    out.mkdir()
    result = run("rehearse", archive, "-o", out)
    assert result.exit_code == 0
    assert "[pass] read.complete" in result.output
    assert "[fail] format.open" in result.output
    manifest = Manifest.load(out / "manifest.json")
    pack = EvidencePack.load(out / "evidence.json")
    assert pack.manifest_digest == manifest.digest()
    assert verify_checksum(out / "evidence.json") is True


def test_rehearse_reports_read_problems_as_a_failed_rule(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"ok.txt": b"1", "../evil.txt": b"2"})
    out = tmp_path / "out"
    out.mkdir()
    result = run("rehearse", archive, "-o", out)
    assert result.exit_code == 0
    assert "[fail] read.complete" in result.output


def test_rehearse_needs_an_existing_output_folder(tmp_path):
    archive = make_zip(tmp_path / "export.zip", {"a.txt": b"1"})
    assert run("rehearse", archive).exit_code != 0
    assert run("rehearse", archive, "-o", tmp_path / "missing").exit_code != 0
