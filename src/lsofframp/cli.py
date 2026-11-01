from pathlib import Path
from typing import Optional

import typer

from lsofframp import __version__
from lsofframp.core.evidence import evidence_schema_text
from lsofframp.core.manifest import ManifestError, manifest_schema_text, write_text_atomic
from lsofframp.core.process import process_schema_text
from lsofframp.readers.builder import build_manifest
from lsofframp.readers.package import read_packages
from lsofframp.rules.builtin import build_evidence

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Check whether a cloud export package can be used without its provider."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def schema(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write the schema to this file instead of stdout."
    ),
    kind: str = typer.Option("manifest", "--kind", "-k", help="manifest, evidence or process."),
) -> None:
    """Print a JSON Schema: the Manifest, the Evidence Pack or a process definition."""
    builders = {
        "manifest": manifest_schema_text,
        "evidence": evidence_schema_text,
        "process": process_schema_text,
    }
    if kind not in builders:
        typer.echo(f"unknown schema kind {kind!r}; use manifest, evidence or process", err=True)
        raise typer.Exit(code=2)
    text = builders[kind]()
    if output is None:
        typer.echo(text, nl=False)
        return
    try:
        write_text_atomic(output, text)
    except ManifestError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


@app.command()
def inspect(
    packages: list[Path] = typer.Argument(
        ..., exists=True, help="Export ZIP archives or directories (all parts of one export)."
    ),
) -> None:
    """Scan export packages locally and list what was found and what could not be read."""
    try:
        reading = read_packages(packages)
    except ManifestError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    for scan in reading.scans:
        part = scan.part
        typer.echo(
            f"{part.name}: {part.kind.value}, {part.entry_count} entries, "
            f"{part.bytes} bytes, {part.hash}"
        )
    issues = reading.issues
    typer.echo(f"Issues: {len(issues)}")
    for issue in issues:
        location = issue.path or "-"
        typer.echo(f"  [{issue.code.value}] {issue.part}: {location} - {issue.detail}")


@app.command("manifest")
def make_manifest(
    packages: list[Path] = typer.Argument(
        ..., exists=True, help="Export ZIP archives or directories (all parts of one export)."
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write the manifest to this file instead of stdout."
    ),
) -> None:
    """Write the Portability Manifest of an export package."""
    try:
        reading = read_packages(packages)
        manifest, merge_issues = build_manifest(reading, __version__)
        if output is None:
            typer.echo(manifest.to_json(), nl=False)
        else:
            manifest.write(output)
    except ManifestError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    problems = len(reading.issues) + len(merge_issues)
    if problems:
        typer.echo(f"{problems} issue(s) found; run 'inspect' to list them.", err=True)


@app.command()
def rehearse(
    packages: list[Path] = typer.Argument(
        ..., exists=True, help="Export ZIP archives or directories (all parts of one export)."
    ),
    out_dir: Path = typer.Option(
        ...,
        "--out-dir",
        "-o",
        exists=True,
        file_okay=False,
        writable=True,
        help="Existing folder for manifest.json and evidence.json (keep it outside the package).",
    ),
) -> None:
    """Run the rehearsal rules and write the Manifest and the Exit Evidence Pack."""
    try:
        reading = read_packages(packages)
        manifest, merge_issues = build_manifest(reading, __version__)
        pack = build_evidence(manifest, [*reading.issues, *merge_issues], __version__)
        manifest.write(out_dir / "manifest.json")
        pack.write(out_dir / "evidence.json")
    except ManifestError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    for result in pack.results:
        typer.echo(f"[{result.status.value}] {result.rule_id}: {result.summary}")
    typer.echo(f"Written: {out_dir / 'manifest.json'}, {out_dir / 'evidence.json'}")
