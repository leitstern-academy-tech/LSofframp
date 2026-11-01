# Third-party software

LSofframp contains no code copied from other projects. It depends on the packages below,
which are installed from PyPI and are not bundled in this repository.

Licenses were read from the installed package metadata on 2026-11-01 (Windows, Python
virtual environment). They are the packages' own statements, not legal advice. All are
permissive licenses that are compatible with Apache-2.0.

## Runtime dependencies

Direct (declared in `pyproject.toml`):

| Package | Version seen | License | Use |
| --- | --- | --- | --- |
| pydantic | 2.14.1 | MIT | Data models and validation |
| typer | 0.27.3 | MIT | Command line interface |
| rich | 15.0.0 | MIT | Terminal output (used through typer) |

Installed as transitive dependencies:

| Package | Version seen | License |
| --- | --- | --- |
| pydantic_core | 2.50.1 | MIT |
| annotated-types | 0.8.0 | MIT |
| annotated-doc | 0.0.5 | MIT |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| markdown-it-py | 4.2.0 | MIT |
| mdurl | 0.1.2 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| shellingham | 1.5.4 | ISC |
| colorama | 0.4.6 | BSD (Windows only) |

## Development dependencies

| Package | Version seen | License | Use |
| --- | --- | --- | --- |
| pytest | 9.2.0 | MIT | Tests |
| ruff | 0.17.3 | MIT | Linting |
| pluggy | 1.7.0 | MIT | pytest dependency |
| iniconfig | 2.3.1 | MIT | pytest dependency |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | pytest dependency |

## Build backend

`hatchling` builds the package (`pyproject.toml`). It is installed in a temporary build
environment, so it was not part of the metadata check above. Its license has not been
verified for this document yet.

## Specifications and ideas

No code or text was taken from these; they are cited because the design follows their
conventions. See `docs/prior-art.md` for the comparison.

- BagIt File Packaging Format, RFC 8493
- Frictionless Data Package (naming of `bytes`, `mediatype`, `hash`)
- PREMIS Data Dictionary (separation of objects and events)
- JSON Schema 2020-12

## Keeping this list current

Run a license check of the installed packages before every release and update the
versions and licenses above.
