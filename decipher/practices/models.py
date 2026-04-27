"""Data models for the best-practices auditor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Finding:
    """A single observation from a checker."""

    id: str
    message: str
    severity: Literal["pass", "warn", "fail"]
    category: str
    detail: str = ""
    file_path: str | None = None
    line: int | None = None


@dataclass
class CheckerResult:
    """Output of a single checker run."""

    name: str
    display_name: str
    status: Literal["pass", "warn", "fail"]
    score: int
    findings: list[Finding] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class AuditReport:
    """Aggregated report from all checkers."""

    language: str
    repo_path: str
    timestamp: str
    overall_score: int
    overall_status: Literal["pass", "warn", "fail"]
    deciphercode_version: str
    schema_version: str = "1.0"
    results: list[CheckerResult] = field(default_factory=list)
    checkers_run: list[str] = field(default_factory=list)
    top_recommendations: list[str] = field(default_factory=list)
    summary: str = ""


def compute_score(findings: list[Finding]) -> int:
    """Compute checker score from findings using the default formula.

    score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """
    warn_count = sum(1 for f in findings if f.severity == "warn")
    fail_count = sum(1 for f in findings if f.severity == "fail")
    return max(0, 100 - (warn_count * 10) - (fail_count * 25))


def worst_status(findings: list[Finding]) -> Literal["pass", "warn", "fail"]:
    """Return the worst severity across all findings."""
    severities = {f.severity for f in findings}
    if "fail" in severities:
        return "fail"
    if "warn" in severities:
        return "warn"
    return "pass"
