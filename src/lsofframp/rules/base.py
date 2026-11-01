"""Shared types for rehearsal rules and the loop that runs them."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from lsofframp.core.evidence import RuleResult, RuleStatus
from lsofframp.core.manifest import Manifest
from lsofframp.readers.package import ReadIssue


@dataclass(frozen=True)
class RuleContext:
    manifest: Manifest
    read_issues: Sequence[ReadIssue]


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    check: Callable[[RuleContext], RuleResult]


def run_rules(context: RuleContext, rules: Sequence[RuleSpec]) -> list[RuleResult]:
    """Run every rule; one that raises is reported as undetermined instead of ending the run."""
    results = []
    for spec in rules:
        try:
            results.append(spec.check(context))
        except Exception as exc:
            results.append(
                RuleResult(
                    rule_id=spec.rule_id,
                    status=RuleStatus.CANNOT_DETERMINE,
                    summary=f"The rule could not be evaluated ({type(exc).__name__}).",
                )
            )
    return results