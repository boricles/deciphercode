"""Checker for CI/CD best practices."""

from __future__ import annotations

import re
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

_TEST_PATTERNS = re.compile(
    r"\b(pytest|py\.test|python\s+-m\s+pytest|tox\b|nox\b|make\s+test)",
    re.IGNORECASE,
)

_LINTER_PATTERNS = re.compile(
    r"\b(ruff\s+check|ruff\s+lint|flake8|pylint|mypy|pyright|make\s+lint)",
    re.IGNORECASE,
)

_USES_PATTERN = re.compile(r"uses:\s+(\S+@\S+)")

_UNPINNED_REFS = frozenset({"main", "master", "dev", "develop", "head"})


class Checker:
    """CI/CD checker for Python repos.

    Finding IDs: CICD-001 through CICD-006.

    - CICD-001: GitHub Actions workflow files present (.github/workflows/)
    - CICD-002: At least one workflow runs tests
    - CICD-003: At least one workflow runs a linter
    - CICD-004: At least one workflow triggers on pull_request
    - CICD-005: Actions use pinned versions (not @main/@master)
    - CICD-006: Python version matrix configured

    CICD-002 through CICD-006 are only emitted when CICD-001 passes
    (conditional suppression: no workflows means no further checks).

    Does NOT validate workflow YAML syntax.

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "ci_cd"
    display_name = "CI/CD"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        workflow_files = self._find_workflows(repo_path)
        workflow_contents = self._load_workflow_contents(repo_path, workflow_files)

        has_workflows = self._check_workflows_present(
            workflow_files,
            findings,
            recommendations,
        )

        if has_workflows:
            self._check_tests(workflow_contents, findings, recommendations)
            self._check_linter(workflow_contents, findings, recommendations)
            self._check_pr_trigger(workflow_contents, findings, recommendations)
            self._check_pinned_actions(workflow_contents, findings, recommendations)
            self._check_python_matrix(workflow_contents, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    @staticmethod
    def _find_workflows(repo_path: Path) -> list[str]:
        """Return workflow file paths relative to repo root."""
        wf_dir = repo_path / ".github" / "workflows"
        if not wf_dir.is_dir():
            return []
        return sorted(
            str(p.relative_to(repo_path))
            for p in wf_dir.iterdir()
            if p.suffix in (".yml", ".yaml") and p.is_file()
        )

    @staticmethod
    def _load_workflow_contents(
        repo_path: Path,
        workflow_files: list[str],
    ) -> dict[str, str]:
        """Load raw text content of each workflow file."""
        contents: dict[str, str] = {}
        for rel_path in workflow_files:
            try:
                contents[rel_path] = (repo_path / rel_path).read_text()
            except OSError:
                continue
        return contents

    def _check_workflows_present(
        self,
        workflow_files: list[str],
        findings: list[Finding],
        recommendations: list[str],
    ) -> bool:
        if workflow_files:
            findings.append(
                Finding(
                    id="CICD-001",
                    message=f"{len(workflow_files)} workflow file(s) found",
                    severity="pass",
                    category=self.name,
                    file_path=".github/workflows",
                )
            )
            return True

        findings.append(
            Finding(
                id="CICD-001",
                message="No GitHub Actions workflows found",
                severity="fail",
                category=self.name,
            )
        )
        recommendations.append("Add GitHub Actions workflows under .github/workflows/")
        return False

    def _check_tests(
        self,
        workflow_contents: dict[str, str],
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        for rel_path, content in workflow_contents.items():
            if _TEST_PATTERNS.search(content):
                findings.append(
                    Finding(
                        id="CICD-002",
                        message="Workflow runs tests",
                        severity="pass",
                        category=self.name,
                        file_path=rel_path,
                    )
                )
                return

        findings.append(
            Finding(
                id="CICD-002",
                message="No workflow runs tests",
                severity="fail",
                category=self.name,
            )
        )
        recommendations.append("Add a step that runs tests (e.g. pytest) to a CI workflow")

    def _check_linter(
        self,
        workflow_contents: dict[str, str],
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        for rel_path, content in workflow_contents.items():
            if _LINTER_PATTERNS.search(content):
                findings.append(
                    Finding(
                        id="CICD-003",
                        message="Workflow runs linter",
                        severity="pass",
                        category=self.name,
                        file_path=rel_path,
                    )
                )
                return

        findings.append(
            Finding(
                id="CICD-003",
                message="No workflow runs a linter",
                severity="warn",
                category=self.name,
            )
        )
        recommendations.append("Add a linter step (e.g. ruff check) to a CI workflow")

    def _check_pr_trigger(
        self,
        workflow_contents: dict[str, str],
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        for rel_path, content in workflow_contents.items():
            if "pull_request" in content:
                findings.append(
                    Finding(
                        id="CICD-004",
                        message="Workflow triggers on pull_request",
                        severity="pass",
                        category=self.name,
                        file_path=rel_path,
                    )
                )
                return

        findings.append(
            Finding(
                id="CICD-004",
                message="No workflow triggers on pull_request",
                severity="warn",
                category=self.name,
                detail="CI should run on PRs to catch issues before merge",
            )
        )
        recommendations.append("Add pull_request trigger to at least one CI workflow")

    def _check_pinned_actions(
        self,
        workflow_contents: dict[str, str],
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        all_content = "\n".join(workflow_contents.values())
        all_uses = _USES_PATTERN.findall(all_content)

        if not all_uses:
            # No uses: directives — nothing to check
            return

        unpinned = [ref for ref in all_uses if ref.rpartition("@")[2].lower() in _UNPINNED_REFS]

        if unpinned:
            # Find the first offending file for file_path
            offending_file: str | None = None
            for rel_path, content in workflow_contents.items():
                file_uses = _USES_PATTERN.findall(content)
                if any(ref.rpartition("@")[2].lower() in _UNPINNED_REFS for ref in file_uses):
                    offending_file = rel_path
                    break

            findings.append(
                Finding(
                    id="CICD-005",
                    message=(f"{len(unpinned)} action(s) use unpinned references (@main/@master)"),
                    severity="warn",
                    category=self.name,
                    file_path=offending_file,
                    detail="Pin actions to a version tag or SHA for reproducibility",
                )
            )
            recommendations.append(
                "Pin GitHub Actions to version tags (e.g. @v4) instead of branch refs"
            )
        else:
            findings.append(
                Finding(
                    id="CICD-005",
                    message="All actions use pinned versions",
                    severity="pass",
                    category=self.name,
                    file_path=".github/workflows",
                )
            )

    def _check_python_matrix(
        self,
        workflow_contents: dict[str, str],
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        for rel_path, content in workflow_contents.items():
            if "python-version" in content and "matrix" in content:
                findings.append(
                    Finding(
                        id="CICD-006",
                        message="Python version matrix configured",
                        severity="pass",
                        category=self.name,
                        file_path=rel_path,
                    )
                )
                return

        findings.append(
            Finding(
                id="CICD-006",
                message="No Python version matrix configured",
                severity="warn",
                category=self.name,
                detail="Test against multiple Python versions (e.g. 3.10, 3.11, 3.12)",
            )
        )
        recommendations.append("Add a Python version matrix to test against 3.10, 3.11, and 3.12")
