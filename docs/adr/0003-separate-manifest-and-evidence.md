\# 0003: Keep the Manifest and the Evidence Pack as separate files



Status: Accepted

Date: 2026-11-01



\## Context



Two kinds of information come out of a run. One describes what the package

contains: objects, owners, sharing, dependencies, formats and checksums. The

other records what the checks found at a point in time: which rules ran, which

did not, the findings and the unknowns.



Putting both in one report mixes facts that belong to the package with results

that belong to a run. It also makes redaction and comparison harder, because

the two parts change for different reasons.



\## Decision



The tool writes two files.



\- \*\*Portability Manifest:\*\* the object inventory, derived only from the

&#x20; package. For the same package and tool version it is deterministic apart

&#x20; from the generation header.

\- \*\*Exit Evidence Pack:\*\* the record of one run. It contains the date, tool

&#x20; version, the SHA-256 of the Manifest it refers to, the rules applied and not

&#x20; applied, findings, conversion needs and unknowns. It also records the hash

&#x20; and row count of optional inputs (roster, process file), not their contents.



Both carry their own schema version. The Evidence Pack refers to the Manifest

by its SHA-256, so a mismatch can be detected.



Field names follow the Frictionless Data Resource naming where an equivalent

exists: `bytes`, `mediatype`, and `hash` written as `sha256:<hex>`. This is a

naming choice for later interoperability. Conformance to that specification is

not claimed.



\## Consequences



\- Two files must be kept together. A verify command checks that they match.

\- Comparing two runs works per object on Manifests and per finding on Evidence

&#x20; Packs, so progress is visible where it happened.

\- Redaction can be applied to each file separately. The Manifest holds paths

&#x20; and addresses; the Evidence Pack is designed to be shareable.

\- The two schemas can evolve at different speeds and need independent

&#x20; versioning and tests.



\## Alternatives considered



\- \*\*One combined report:\*\* simpler to ship, but mixes package facts with run

&#x20; results. Rejected.

\- \*\*Adopting BagIt or PREMIS as the format:\*\* both are built for preservation

&#x20; and transfer, not for judging reusability. Only ideas are borrowed. Rejected

&#x20; as a format.



\## Notes



Separating objects from events is a standard idea in preservation metadata

(PREMIS). Frictionless naming is borrowed. Neither is claimed as original. The

use of the split to carry a four-state reusability status per object, with

unknowns reported, is specific to this project.

