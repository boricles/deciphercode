"""Checker for PyPI release readiness best practices."""

from __future__ import annotations

import sys
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[import-not-found]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


class Checker:
    """Release Readiness checker for Python repos.

    Finding IDs: REL-001 through REL-007.

    - REL-001: pyproject.toml present with [project] table
    - REL-002: Version field declared (static or dynamic)
    - REL-003: Build backend declared ([build-system] requires + build-backend)
    - REL-004: Classifiers present
    - REL-005: README referenced in pyproject.toml
    - REL-006: Author/maintainer info present
    - REL-007: requires-python declared

    REL-002 through REL-007 are only emitted when REL-001 passes
    (conditional suppression: no pyproject.toml [project] means nothing to inspect).

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "release_readiness"
    display_name = "Release Readiness"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        project_data, build_data = self._load_pyproject(repo_path)

        has_project = self._check_pyproject_present(
            repo_path,
            project_data,
            findings,
            recommendations,
        )

        if has_project:
            self._check_version(project_data, findings, recommendations)
            self._check_build_backend(build_data, findings, recommendations)
            self._check_classifiers(project_data, findings, recommendations)
            self._check_readme_ref(project_data, findings, recommendations)
            self._check_author(project_data, findings, recommendations)
            self._check_python_requires(project_data, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    @staticmethod
    def _load_pyproject(repo_path: Path) -> tuple[dict | None, dict | None]:
        """Load pyproject.toml and return (project_data, build_system_data)."""
        pyproject = repo_path / "pyproject.toml"
        if not pyproject.exists():
            return None, None

        if tomllib is None:
            return None, None

        try:
            data = tomllib.loads(pyproject.read_text())
            return data.get("project"), data.get("build-system")
        except Exception:
            return None, None

    def _check_pyproject_present(
        self,
        repo_path: Path,
        project_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> bool:
        pyproject = repo_path / "pyproject.toml"

        if not pyproject.exists():
            findings.append(
                Finding(
                    id="REL-001",
                    message="No pyproject.toml found",
                    severity="fail",
                    category=self.name,
                )
            )
            recommendations.append("Add a pyproject.toml with a [project] table")
            return False

        if project_data is None:
            findings.append(
                Finding(
                    id="REL-001",
                    message="pyproject.toml has no [project] table",
                    severity="fail",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append("Add a [project] table to pyproject.toml")
            return False

        findings.append(
            Finding(
                id="REL-001",
                message="pyproject.toml found with [project] table",
                severity="pass",
                category=self.name,
                file_path="pyproject.toml",
            )
        )
        return True

    def _check_version(
        self,
        project_data: dict,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        has_version = "version" in project_data
        has_dynamic_version = "version" in project_data.get("dynamic", [])

        if has_version or has_dynamic_version:
            if has_dynamic_version:
                msg = "Version declared (dynamic)"
            else:
                msg = f"Version declared ({project_data['version']})"
            findings.append(
                Finding(
                    id="REL-002",
                    message=msg,
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            findings.append(
                Finding(
                    id="REL-002",
                    message="No version field in [project]",
                    severity="fail",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append('Add version = "x.y.z" to [project] in pyproject.toml')

    def _check_build_backend(
        self,
        build_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        if build_data and "build-backend" in build_data and "requires" in build_data:
            findings.append(
                Finding(
                    id="REL-003",
                    message=f"Build backend: {build_data['build-backend']}",
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            findings.append(
                Finding(
                    id="REL-003",
                    message="No build backend declared in [build-system]",
                    severity="fail",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append(
                "Add [build-system] with requires and build-backend to pyproject.toml"
            )

    def _check_classifiers(
        self,
        project_data: dict,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        classifiers = project_data.get("classifiers", [])
        if classifiers:
            findings.append(
                Finding(
                    id="REL-004",
                    message=f"{len(classifiers)} classifier(s) declared",
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            findings.append(
                Finding(
                    id="REL-004",
                    message="No classifiers declared in [project]",
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append("Add classifiers to [project] for PyPI discoverability")

    def _check_readme_ref(
        self,
        project_data: dict,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        readme = project_data.get("readme")
        if readme:
            if isinstance(readme, str):
                msg = f"README referenced ({readme})"
            elif isinstance(readme, dict):
                msg = f"README referenced ({readme.get('file', 'inline content')})"
            else:
                msg = "README referenced"
            findings.append(
                Finding(
                    id="REL-005",
                    message=msg,
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            findings.append(
                Finding(
                    id="REL-005",
                    message="No readme referenced in [project]",
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append(
                'Add readme = "README.md" to [project] for PyPI long description'
            )

    def _check_author(
        self,
        project_data: dict,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        has_authors = bool(project_data.get("authors"))
        has_maintainers = bool(project_data.get("maintainers"))

        if has_authors or has_maintainers:
            who = "authors" if has_authors else "maintainers"
            findings.append(
                Finding(
                    id="REL-006",
                    message=f"Project {who} declared",
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            findings.append(
                Finding(
                    id="REL-006",
                    message="No authors or maintainers declared in [project]",
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append("Add authors or maintainers to [project] in pyproject.toml")

    def _check_python_requires(
        self,
        project_data: dict,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        requires_python = project_data.get("requires-python")
        if requires_python:
            findings.append(
                Finding(
                    id="REL-007",
                    message=f"requires-python: {requires_python}",
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            findings.append(
                Finding(
                    id="REL-007",
                    message="No requires-python declared in [project]",
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append(
                "Add requires-python to [project] to prevent installation "
                "on incompatible Python versions"
            )
