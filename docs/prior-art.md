## Verified comparison with ExitPreflight



Date: 2026-11-01

Based on: report.schema.json (report schema 1.0) and docs/ARCHITECTURE.md in

the public repository, plus its README and release notes. Source code beyond

these documents was not inspected. The project is young and may change.



| Question | Finding |

|---|---|

| Object-level ownership, sharing, dependency | Not in the schema. File records carry path, size and SHA-256 only. Findings have a free-form metadata object. |

| Calendar, contact, office-document parsing | Not present. Adapters: generic audit, Slack, Gmail MBOX, Notion. |

| Result without a score; "unknown" as a state | A 0-100 readiness score is a required field. Status values: ready, review, needs-attention, blocked. No unknown state. The architecture notes describe the score as an explanation aid. |

| Roster cross-check or process definition | Not present. |



Practices shared with ExitPreflight and therefore treated as standard, not as

original: archive inspection without extraction, path and link refusal, CRC and

compression-ratio limits, per-file SHA-256, comparison of two runs, hashed

paths for shareable reports, capping of repeated findings.



Consequence: LSofframp is developed as an independent project with its own

schema. Contribution as an adapter is not a good fit because the report schema

is closed at the root, requires a score, and has no relationship fields.



Re-check before any public release and before any funding application.

