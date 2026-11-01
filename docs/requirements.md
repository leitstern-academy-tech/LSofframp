# Requirements

Status of each requirement is in `docs/acceptance.md`. "Planned" items are not built yet.

## Functional

| ID | Requirement |
| --- | --- |
| R-01 | The tool works locally. It uses no network, no credentials and uploads nothing (ADR 0001). |
| R-02 | It reads ZIP archives and plain directories without extracting them. |
| R-03 | An unsafe or unreadable entry (unsafe path, symbolic link, encryption, CRC error, duplicate, case collision) is recorded as an issue and skipped. Only an unreadable package as a whole stops the run. |
| R-04 | Entry count, entry size, total size and compression ratio are limited. A package over a limit is scanned only up to the limit and the limit is reported. |
| R-05 | The Manifest is deterministic: the same package gives the same content in the same order. |
| R-06 | The Manifest stores no file content, only paths, formats, sizes, hashes and addresses. URLs lose query strings and credentials. |
| R-07 | Unknown information (`null`) is never merged with "none" (`[]`). |
| R-08 | The Manifest and the Evidence Pack follow published, versioned JSON Schemas that are kept in sync with the code. |
| R-09 | The Evidence Pack refers to the Manifest by SHA-256 and does not copy its content (ADR 0003). |
| R-10 | Each rule reports pass, fail, not_applicable or cannot_determine. There is no overall score (ADR 0002). |
| R-11 | A rule that fails internally is reported as cannot_determine; the other rules still run. |
| R-12 | The Evidence Pack is written with a checksum file, and the tool can detect a changed file. |
| R-13 | Exports split over several archives are read together; repeated files are reported, repeated folders merged. |
| R-14 | A command line offers `inspect`, `manifest`, `rehearse`, `schema` and `version`. |
| R-15 | A process definition is a local JSON file validated against a published schema. Unknown fields are refused; a selector names exactly one of kind, path prefix or object identifier (ADR 0004). |
| R-16 | A member roster is a local CSV with the columns `email` and `active`; the organisation states the day it reflects. Only its SHA-256, row count and date are recorded; error messages never show cell values. An invalid row refuses the whole roster. |
| R-17 | Each process item gets one of `usable`, `needs_conversion`, `not_usable` or `unknown` with a reason. A selector that matches nothing is `unknown`. A process shows the least favourable item state together with its items; there is no score. |
| R-18 | Checks that need a roster report `unknown` without one. `--roster` needs `--roster-as-of` and `--process`; a date in the future or in the wrong form is refused. |
| R-19 | The `processes` section of the Evidence Pack is optional: `null` means the check was not run, and a pack without it stays valid. |

## Non-functional

| ID | Requirement |
| --- | --- |
| N-01 | Python 3.10 or newer, on Windows and Linux. |
| N-02 | Licensed under Apache-2.0. |
| N-03 | Every functional requirement above has automated tests where this is practical; gaps are listed in `docs/acceptance.md`. |
| N-04 | Third-party packages and their licenses are listed in `docs/third-party.md`. |

## Planned

| ID | Requirement |
| --- | --- |
| P-03 | Readers for ICS, VCF and MBOX content. |
| P-04 | Up to two provider modules that fill in sharing, ownership and relationships. |
| P-05 | Plain-language reports in German and English. |
| P-06 | `--redact`: replace names and addresses with keyed hashes (HMAC-SHA256, key held by the user). |
| P-08 | `compare`: show what changed between two runs. |
