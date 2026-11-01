# 0004: Process definitions and a member roster as optional local inputs



Status: Accepted

Date: 2026-11-01



## Context



The central question is whether working processes can be rebuilt, not only

whether files exist. A file-level result cannot say whether "member

administration" still works after an exit. It depends on a contact list, a

shared folder and a calendar together.



Stale ownership, such as a shared folder owned by a former administrator,

cannot be detected from the export alone. The export does not say who is still

a member of the organization.



Both facts are known only to the organization. Fetching them from the live

service would break ADR 0001.



## Decision



Two optional inputs are read from local files.



- **Process definition file (JSON).** Written by the organization. Each process

  has a name and a list of required items. An item is selected by object kind,

  path prefix or object identifier from the Manifest, and may require a

  relationship, for example that a folder is shared with a given group. The

  file is validated against a versioned schema.

- **Member roster (CSV).** Columns: `email`, `active`, and optionally `name`

  and `role`. The organization states the date the list is valid for.



Rules for both:



- Read-only. No credentials. No network access.

- The Evidence Pack records the hash, row count and as-of date, not the

  contents. With `--redact`, addresses are replaced by hashes in all outputs.

- Without a roster, checks that need it are reported as `unknown`, never as

  passed.

- A selector in a process file that matches nothing is reported as a finding,

  not silently ignored.

- For each process the report lists every required item with its state. A

  headline state is shown as well, taken as the least favourable state among

  the items, in this order: `not_usable`, `unknown`, `needs_conversion`,

  `usable`. `unknown` ranks above `needs_conversion` because it cannot be

  relied on. The headline never appears without the list behind it.



File formats: JSON for process definitions, because it can be read with the

standard library on Python 3.10 and later without a new dependency. CSV for

the roster, because organizations already keep member lists in spreadsheets.

A command that writes a starter process file with comments in an accompanying

guide is planned, since hand-writing JSON is hard for non-specialists.



## Consequences



- Users must put in some effort. If it proves too much in user interviews, the

  format or the workflow has to change.

- A badly defined process can give false comfort. Validation errors and

  unmatched selectors reduce this but do not remove it.

- The roster is personal data. It stays local, and the redaction option

  applies to it.

- A stale roster produces wrong ownership findings. The as-of date is shown in

  the report.



## Alternatives considered



- **Infer processes automatically:** would be a guess presented as a finding.

  Rejected.

- **Query the live directory:** needs credentials and a network connection.

  Rejected by ADR 0001.

- **YAML or TOML for process files:** friendlier to read, but YAML needs a

  third-party dependency and TOML is in the standard library only from Python

  3.11. May be reconsidered if the minimum Python version changes.



## Notes



CSV and JSON inputs are standard. Tying the reusability status to

organization-defined processes and a roster is specific to this project.

