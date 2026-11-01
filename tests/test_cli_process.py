import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from lsofframp.cli import app

runner = CliRunner()


def prepare(tmp_path: Path):
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("Members/list.pdf", b"x")
    definition = tmp_path / "process.json"
    definition.write_text(
        '{"schema_version": "0.1", "processes": [{"name": "Members", "items": '
        '[{"label": "List", "select": {"path_prefix": "Members"}}]}]}',
        encoding="utf-8",
    )
    roster = tmp_path / "roster.csv"
    roster.write_text("email,active\na@example.org,true\n", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()
    return archive, definition, roster, out


def run(*args):
    return runner.invoke(app, [str(arg) for arg in args])


def test_rehearse_with_a_process_file_prints_and_records_it(tmp_path):
    archive, definition, roster, out = prepare(tmp_path)
    result = run(
        "rehearse", archive, "-o", out, "--process", definition,
        "--roster", roster, "--roster-as-of", "2026-10-01",
    )
    assert result.exit_code == 0, result.output
    assert "[process usable] Members" in result.output
    pack = json.loads((out / "evidence.json").read_text(encoding="utf-8"))
    assert pack["processes"]["roster"]["row_count"] == 1
    assert "a@example.org" not in (out / "evidence.json").read_text(encoding="utf-8")


def test_rehearse_without_a_process_file_records_none(tmp_path):
    archive, _, _, out = prepare(tmp_path)
    assert run("rehearse", archive, "-o", out).exit_code == 0
    assert json.loads((out / "evidence.json").read_text(encoding="utf-8"))["processes"] is None


def test_roster_without_a_date_is_refused(tmp_path):
    archive, definition, roster, out = prepare(tmp_path)
    result = run("rehearse", archive, "-o", out, "--process", definition, "--roster", roster)
    assert result.exit_code == 2
    assert not (out / "evidence.json").exists()
