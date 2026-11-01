# 0002: Report findings, not a single portability score



Status: Accepted

Date: 2026-10-28



## Context



A one-number result such as "78% portable" is easy to read and easy to quote.

For export packages it is also misleading. A package can score well on file

count while the three shared folders that matter most have lost their

ownership, or while a large part of the data could not be checked at all.

A percentage hides which checks were skipped, which items are unknown and

which findings are serious.



## Decision



LSofframp does not produce a single portability score. Each check reports its

own result. The Exit Evidence Pack lists findings by category, the checks that

were applied, the checks that could not be run, and the items whose status is

unknown.



Where a count or share is shown, it is always given together with what it

covers and what it leaves out.



## Consequences



- Results are longer and need more explanation than one number.

- Users cannot rank two providers by a single figure. This is intended.

- Re-running a rehearsal and comparing two runs is done per finding, not per

  score, so progress is visible where it actually happened.

- "Unknown" is a first-class result and must not be folded into "pass" or

  "fail".

- The report format needs a clear plain-language summary so that

  non-specialists can still act on it.



## Alternatives considered



- **Weighted overall score:** simple, but the weights would be arbitrary and

  would encode judgements about what matters to every organization. Rejected.

- **Traffic-light rating per data type:** closer to the intended behavior but

  still hides the detail. May be used as a presentation aid on top of the

  findings, never as a replacement.



## Notes



Reporting findings instead of scores is a common practice in audit and

assessment tools. The combination with a re-runnable evidence pack is specific

to this project.

