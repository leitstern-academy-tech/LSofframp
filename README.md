# LSofframp

LSofframp checks, on your own machine, whether an organisation could really reuse the data,
relationships and processes in a cloud export if it left its provider.

It reads an export package (a ZIP archive or a folder), writes a provider-independent
inventory, and records what each check found. It needs no credentials and sends nothing
anywhere.

> **Status: early prototype (v0.0.1).** The core works and is tested, but only a few checks
> exist and only generic ZIP/folder packages are read. Expect changes to file formats.

PS:"With Leitstern as your guiding star, failure was simply never compiled."

## What it produces

- **Portability Manifest** (`manifest.json`): a versioned, deterministic inventory of what
  the package contains. It holds paths, formats, sizes and hashes, never file content. What
  the package does not say stays `null`; an empty list means the package says "nobody".
- **Exit Evidence Pack** (`evidence.json` plus `evidence.json.sha256`): the record of one
  run. It refers to the Manifest by its SHA-256 and lists each rule's result.

Each rule answers on its own as `pass`, `fail`, `not_applicable` or `cannot_determine`.
There is deliberately **no single portability score**: "the package does not tell us" is not
the same as "fine", and a number would hide that.

## Quick start

Requires Python 3.10 or newer. Not yet published on PyPI; install from a clone:

    git clone https://github.com/leitstern-academy-tech/LSofframp.git
    cd LSofframp
    python -m venv .venv
    .venv\Scripts\activate          (Windows)   or   source .venv/bin/activate
    pip install -e ".[dev]"

Run the rehearsal on an export (the output folder must exist and should be outside the
package):

    mkdir out
    lsofframp rehearse path\to\export.zip -o out

Example output:

    [cannot_determine] access.sharing_known: The package does not say who can access 9 of 9 object(s).
    [pass] format.open: All files use open standard formats.
    [cannot_determine] integrity.checksums: The package declares no checksums, so damage before the export cannot be excluded.
    [pass] read.complete: The package was read completely.

Split exports: pass every part, for example `lsofframp rehearse part-1.zip part-2.zip -o out`.

## Commands

| Command | Purpose |
| --- | --- |
| `lsofframp inspect PACKAGE...` | Scan packages and list what was found and what could not be read |
| `lsofframp manifest PACKAGE... [-o FILE]` | Write the Portability Manifest |
| `lsofframp rehearse PACKAGE... -o DIR` | Write the Manifest and the Evidence Pack and print the rule results |
| `lsofframp schema [-o FILE]` | Print the JSON Schema of the Manifest |
| `lsofframp version` | Print the version |

## Current rules

| Rule | Asks |
| --- | --- |
| `read.complete` | Could the whole package be read? |
| `format.open` | Are the files in open standard formats? |
| `integrity.checksums` | Does the package declare checksums, and do they match? |
| `access.sharing_known` | Does the package say who can access each object? |

Not yet implemented: process continuity and roster checks, ICS/VCF/MBOX readers, provider
modules, plain-language reports (DE/EN), `--redact`.

## Safety

- Packages are never extracted. Entries are streamed through SHA-256.
- Unsafe paths (`..`, absolute paths, backslashes), symbolic links, encrypted entries and
  suspicious compression ratios are recorded as issues and skipped.
- Size and entry-count limits apply to every package.
- URLs found in a package lose their query strings and credentials.

See `docs/threat-model.md` for the full list.

## Documentation

- `docs/scope.md` - what the tool is and is not
- `docs/prior-art.md` - related projects and how this one differs
- `docs/adr/` - design decisions
- `docs/devlog.md` - development log

## Development

    python -m pytest -q

## License

Apache License 2.0. Copyright 2026 Leitstern Academy & Technology GmbH. See `LICENSE` and
`NOTICE`.
