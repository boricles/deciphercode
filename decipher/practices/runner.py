"""Orchestrator that runs all checkers and produces an AuditReport."""

from __future__ import annotations

import importlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from decipher import __version__
from decipher.practices.models import AuditReport, CheckerResult

logger = logging.getLogger(__name__)
console = Console()

PYTHON_CHECKERS = [
    "project_structure",
    "testing",
    "quality_gates",
    "ci_cd",
    "dependency_hygiene",
    "documentation",
    "licensing",
    "release_readiness",
]

SUPPORTED_LANGUAGES = {"python": PYTHON_CHECKERS}


def _load_checker(language: str, checker_name: str) -> object:
    """Import and instantiate a Checker class from the given language module."""
    module_path = f"decipher.practices.checkers.{language}.{checker_name}"
    module = importlib.import_module(module_path)
    return module.Checker()


def run_audit(
    repo_path: Path,
    language: str = "python",
    show_progress: bool = True,
    checkers: list[str] | None = None,
) -> AuditReport:
    """Run all checkers for the given language and return the report."""
    checker_names = checkers if checkers is not None else SUPPORTED_LANGUAGES[language]
    results: list[CheckerResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        disable=not show_progress,
    ) as progress:
        for name in checker_names:
            progress.add_task(f"Running {name} checker...", total=None)
            checker = _load_checker(language, name)
            result = checker.run(repo_path)
            results.append(result)
            logger.debug("Checker %s: score=%d status=%s", name, result.score, result.status)

    # Compute aggregate score and status
    if results:
        overall_score = sum(r.score for r in results) // len(results)
        if any(r.status == "fail" for r in results):
            overall_status = "fail"
        elif any(r.status == "warn" for r in results):
            overall_status = "warn"
        else:
            overall_status = "pass"
    else:
        overall_score = 0
        overall_status = "pass"

    # Collect top recommendations: first recommendation from each checker,
    # ordered by checker score ascending (worst first), capped at 5
    sorted_results = sorted(results, key=lambda r: r.score)
    top_recommendations = []
    for r in sorted_results:
        for rec in r.recommendations:
            if rec not in top_recommendations:
                top_recommendations.append(rec)
            if len(top_recommendations) >= 5:
                break
        if len(top_recommendations) >= 5:
            break

    return AuditReport(
        language=language,
        repo_path=str(repo_path.resolve()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        overall_score=overall_score,
        overall_status=overall_status,
        deciphercode_version=__version__,
        checkers_run=[r.name for r in results],
        results=results,
        top_recommendations=top_recommendations,
        summary=_build_summary(overall_score, overall_status, results),
    )


def _build_summary(
    overall_score: int,
    overall_status: str,
    results: list[CheckerResult],
) -> str:
    """Build a one-sentence executive summary."""
    failing = [r.display_name for r in results if r.status == "fail"]
    warning = [r.display_name for r in results if r.status == "warn"]

    if overall_status == "pass":
        return "The repository meets all checked best practices."

    parts = []
    if failing:
        parts.append(f"failing checks in {', '.join(failing)}")
    if warning:
        parts.append(f"warnings in {', '.join(warning)}")

    return f"Overall score {overall_score}/100. The repository has {' and '.join(parts)}."
