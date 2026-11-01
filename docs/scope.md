# Scope

## Purpose

Organizations that use a cloud service often assume they can export their data
whenever they want. An export package that exists is not the same as an export
package that can be used. LSofframp tests the second claim.

The question it answers:

> If this platform became unavailable tomorrow, which data, relationships and
> working processes could we actually rebuild from the export package we hold?

LSofframp does not migrate data. It produces evidence about portability.

## Maintainer

Leitstern Academy & Technology GmbH, Düsseldorf, Germany.
Website: https://lsacademytech.com/

The maintainer is a small technology and training company working with
small and medium-sized organizations and associations in Germany. The tool is
designed for that audience: people who are not IT specialists and need results
they can understand and verify.

## Target users

Small organizations such as associations, schools and small businesses in
Germany and the EU that rely on a hosted service and have no dedicated IT
department.

## Problems it looks for

- Files are present but sharing permissions are lost.
- Mail is exported but folder or label structure is broken.
- Calendars are exported without attendees or attachments.
- Documents exist only as provider-specific links.
- Ownership is tied to the account of a former administrator.
- Files use non-open or proprietary formats.
- Completeness of the archive cannot be verified.
- The data can be obtained but not used in another system.
- A working process (for example member administration) depends on several
  objects, and the export keeps only some of them in usable form.

## How it works

The organization opens an export package that the provider issued, locally.
No account access, password or token is given to the tool.

1. Turn the package contents into an inventory.
2. Check file formats and readability.
3. Classify file, mail, calendar, contact and permission metadata.
4. Identify provider-specific elements that cannot be carried over.
5. Report broken files, missing attachments and unresolvable links.
6. Explain what can be moved directly and what needs conversion.
7. Optionally compare owners and shared-with people against a member roster
   supplied by the organization.
8. Optionally check user-defined processes against the inventory.
9. Write a machine-readable Portability Manifest.
10. Write an Exit Evidence Pack with check results, checksums and the checks
    used, and a plain-language summary in German or English.
11. Allow the same check to be run again later and the results compared.

All processing happens on the user's machine. No content is uploaded to a
central server.

## Prior work

Local, credential-free auditing of export packages is an existing practice.
The closest project found is ExitPreflight. The comparison, its date and its
limits are in `prior-art.md`. LSofframp is an independent project with its own
schema.

## What is distinctive

1. **Portability Manifest.** A versioned, provider-independent JSON schema at
   object level: ownership, sharing, dependencies, format, integrity and a
   four-state reusability status (usable, needs_conversion, not_usable,
   unknown).
2. **Rehearsal Rules.** Deterministic checks of whether a package is
   independently usable, not merely present.
3. **Exit Evidence Pack.** A record of one run, kept separate from the
   Manifest: check date, tool version, source package fingerprint, rules
   applied and not applied, findings, conversion needs, unknowns and what is
   needed to re-run (ADR 0003).
4. **Findings and unknowns instead of a score** (ADR 0002).
5. **Process continuity check.** The organization lists its own critical
   processes; the tool reports per process what can be rebuilt (ADR 0004).
6. **Roster check.** Ownership and sharing are compared with a local list of
   current members (ADR 0004).
7. **Plain-language reports** in German and English for non-specialists.

Archive safety checks, SHA-256 checksums, local processing and comparison of
runs are standard practice and are not claimed as original.

## First prototype

Open formats only: ZIP and folder packages, MBOX and EML, ICS, VCF, CSV and
JSON metadata, PDF, ODF and Microsoft Office documents, provider-specific
online document links, file checksums and export manifests.

Optional inputs: a member roster (CSV) and a process definition file (JSON).

At most two provider ecosystems. Which two is decided after real sample
packages and user interviews have been seen.

## Out of scope

- Logging in to accounts on the user's behalf.
- Storing passwords or access keys.
- Automatically migrating production data to another provider.
- Legal compliance guarantees.
- Supporting all providers.
- AI-based interpretation of file contents.
- A single "portability score".
- Rebuilding the data in another system (considered for a later version).

## Open decisions

- Which two provider ecosystems come first.
- Final names for the manifest schema and rule format.
- Whether users can write process definitions without help; to be tested in
  user interviews.
- Third-party licence review before any code is reused.