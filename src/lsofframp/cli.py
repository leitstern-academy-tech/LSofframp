from pathlib import Path
from typing import Optional

import typer

from lsofframp import __version__
from lsofframp.core.manifest import ManifestError, manifest_schema_text, write_text_atomic

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
) -> None:
    """Print the JSON Schema of the Portability Manifest."""
    text = manifest_schema_text()
    if output is None:
        typer.echo(text, nl=False)
        return
    try:
        write_text_atomic(output, text)
    except ManifestError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc