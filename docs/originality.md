# Originality and sources

This document separates what is specific to this project from what is standard practice,
and lists what was reviewed. It is a statement of what was checked, not a guarantee: private
or unindexed work cannot be searched, so no claim of "nothing similar exists" is made.
Sources and the detailed comparison are in `docs/prior-art.md`.

Last reviewed: 2026-11-01. The review is repeated before a release and before any funding
application.

## What is specific to this project

These are design decisions of this project, taken from its own requirements
(`docs/requirements.md`, `docs/adr/`):

- **Evidence, not a score.** Every rule answers pass, fail, not_applicable or
  cannot_determine. A package that does not say something is reported as
  cannot_determine, never as pass or fail (ADR 0002).
- **Unknown is not empty.** `null` means "the package does not say", `[]` means "it says
  nobody". The distinction is kept in the Manifest and used by the rules.
- **Manifest and Evidence Pack are separate.** The Manifest is a deterministic inventory of
  the package; the Evidence Pack records one run and refers to the Manifest by SHA-256
  (ADR 0003).
- **Skip and record.** A damaged or unsafe entry becomes a recorded issue and the run
  continues; the issues are part of the evidence.
- **Open-standard classification** of file formats as an input to the rules.
- **Process and roster checks** (ADR 0004). The organisation describes in its own file what
  it must still be able to do. Each item gets a state of its own, the process shows the least
  favourable one together with its items, and a selector that matches nothing is reported,
  not passed. The roster is used locally; only its hash, row count and date are recorded.

## What is standard practice

- Streaming hashes, zip-slip and symbolic-link checks, and a compression-ratio limit when
  reading archives.
- A command line built with a common library, models validated with pydantic, tests with
  pytest.
- A JSON Schema published for the Manifest.
- Naming of `bytes`, `mediatype` and `hash` follows the Frictionless Data Package
  convention; the split between objects and events follows PREMIS. Only the conventions
  were used, no text or code.

## Reviewed projects and standards

| Name | What it is | Relation to this project |
| --- | --- | --- |
| ExitPreflight | Open-source (MIT) readiness check for exports; its report schema requires a readiness score; file records hold path, size and SHA-256; adapters for several services | Closest project found. Checked directly on 2026-11-01. Not reused: its required score conflicts with ADR 0002. Development continues independently (see below). |
| BagIt (RFC 8493) | Packaging format with checksums | Concept only. Not adopted: it describes how to package, not how to judge reuse. |
| Frictionless Data Package | Metadata format for datasets | Naming conventions followed. |
| PREMIS | Preservation metadata dictionary | Object/event separation followed. |
| Data Transfer Project | Moves data between providers | Different purpose: transfer, not assessment. |
| Google Migration Planner | Migration planning tool | Little public detail was found; no overlap established. |
| Tools around Google Takeout archives (for example TakePair, Takeout Inspector, Takeout Export Reconstructor) | Work with one provider's archive format | Provider-specific; this project is provider-independent. See `docs/prior-art.md`. |

## Similarity and license risk

- **Similarity:** medium. The general idea of checking an export before leaving a provider
  is shared with ExitPreflight. The distinguishing points are the list above. The funding
  application must not claim that no equivalent exists.
- **Code:** none was copied from any project. Dependencies and their licenses are in
  `docs/third-party.md`.
- **Licenses:** this project is Apache-2.0. ExitPreflight is MIT; reusing its code would be
  possible under that license, but no code was used.

## Decision on integration

Contributing to ExitPreflight or building on it was considered. It was not chosen because
its schema requires a single score, which this project rejects (ADR 0002), and because the
Manifest/Evidence separation and the planned process checks would change its core. The
decision was approved by the maintainer on 2026-11-01. It should be revisited if the
projects converge.

## Review of the process and roster stage (2026-11-01)

- **Specific to this project:** the four item states and the rule that a process shows its
  least favourable item together with the items; reporting an empty selector as unknown;
  requiring the organisation to state the roster's date; recording only fingerprint, row
  count and date of the roster.
- **Standard practice:** reading CSV with the standard library, validating a JSON file with
  pydantic models and a published schema, classifying file formats by extension.
- **Sources and code:** no new dependency, no code or text taken from other projects.
- **Similarity:** unchanged (medium). No new prior-art search was made at this stage; it is
  repeated before the funding application.
