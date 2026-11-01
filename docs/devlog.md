\# Development log



## 2026-10-27

- Repository created under the name LSofframp ("LS" = Leitstern).

- Earlier working names, kept here for history only: Ausstiegsprobe

&#x20; (Exit Rehearsal), offramp, LS-offramp-exitcheck.

- License: Apache-2.0. Copyright holder: Leitstern Academy \& Technology GmbH.
- Hosted under the leitstern-academy-tech organization on GitHub.

- Name check: no exact match for "lsofframp" found in web search.

&#x20; Visual similarity to the Unix command `lsof` acknowledged and accepted.



## 2026-11-01
- Prior-art survey added. Closest project found: ExitPreflight (MIT).
- Compared against its report schema and architecture notes: no object-level
  ownership or sharing, no calendar, contact or office parsing, a required
  numeric score, no unknown state.
- Decision: continue as an independent project with its own schema.
- Core scope extended: process continuity check, roster check, plain-language
  reports in German and English.
- ADR 0003 (separate Manifest and Evidence Pack) and ADR 0004 (process and
  roster inputs) accepted.


## 2026-11-01 (later) - Package reader

Added the ZIP/directory reader (`readers/package.py`), the extension table
(`readers/formats.py`) and the `inspect` command.

Decisions (approved by the maintainer):
- Packages are scanned without extracting. Entries are streamed through SHA-256;
  the ZIP CRC is verified by `zipfile` while reading.
- A problem in one entry (unsafe path, duplicate, case collision, symlink,
  encryption, CRC error, size limit, suspicious compression ratio) is recorded as
  an issue and the entry is skipped. Only an unreadable package raises an error.
- Issues are returned separately from entries; they will be bound to the
  Evidence Pack later, not to the Manifest.
- Default limits: 200,000 entries, 4 GiB per entry, 100 GiB in total, ratio above
  1000:1 flagged for entries of at least 1 MiB. All are adjustable via `Limits`.
- TAR is deferred. Formats are detected by extension only; the table marks
  proprietary formats (doc, xls, ppt, gdoc, gsheet, gslides) as not open.

Standard techniques: streaming hash, zip-slip and symlink checks, ratio limit.
Original to this project: issue codes, skip-and-record behaviour, the open-standard
classification used later by the rehearsal rules.

Tests: 79 passing (48 manifest, 31 reader).