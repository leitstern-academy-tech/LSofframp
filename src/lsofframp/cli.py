import typer

from lsofframp import __version__

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Check whether a cloud export package can be used without its provider."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)