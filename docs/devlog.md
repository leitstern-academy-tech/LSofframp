\# Development log



\## 2026-10-27

\- Repository created under the name LSofframp ("LS" = Leitstern).

\- Earlier working names, kept here for history only: Ausstiegsprobe

&#x20; (Exit Rehearsal), offramp, LS-offramp-exitcheck.

\- License: Apache-2.0. Copyright holder: Leitstern Academy \& Technology GmbH.

\- Hosted under the leitstern-academy-tech organization on GitHub.

\- Name check: no exact match for "lsofframp" found in web search.

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