"""Checker for dependency hygiene best practices."""

from __future__ import annotations

import re
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

# Matches a PEP 508 version specifier (>=, <=, ==, !=, ~=, <, >)
_VERSION_SPEC_RE = re.compile(r"[><=!~]=?")

# Known lock files, ordered by preference
_LOCK_FILES = ["uv.lock", "poetry.lock", "requirements.lock", "pdm.lock"]

# requirements.txt counts as a lock proxy only when it contains pinned versions
_REQUIREMENTS_TXT = "requirements.txt"


def _parse_dep_name(dep: str) -> str:
    """Extract the normalized package name from a PEP 508 dependency string.

    'click>=8.1' -> 'click', 'PyYAML[extra]>=6.0' -> 'pyyaml'
    """
    # Strip extras, version specifiers, environment markers
    name = re.split(r"[\[;><=!~\s]", dep, maxsplit=1)[0]
    # PEP 503 normalization: lowercase, replace [-_.] with -
    return re.sub(r"[-_.]+", "-", name.lower())


def _has_version_specifier(dep: str) -> bool:
    """Return True if the dependency string contains a version constraint."""
    # Remove the package name and extras, check what remains
    remainder = re.split(r"^[A-Za-z0-9._-]+(?:\[[^\]]*\])?", dep, maxsplit=1)
    if len(remainder) < 2:
        return False
    after_name = remainder[1].split(";")[0]  # strip environment markers
    return bool(_VERSION_SPEC_RE.search(after_name))


def _is_pinned_requirements(path: Path) -> bool:
    """Check if a requirements.txt contains pinned versions (== specifiers)."""
    try:
        content = path.read_text()
    except OSError:
        return False
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if "==" in line:
            return True
    return False


class Checker:
    """Dependency Hygiene checker for Python repos.

    Finding IDs: DEP-001 through DEP-005.

    - DEP-001: Dependencies declared in [project.dependencies]
    - DEP-002: All dependencies have version constraints (no wildcard/unbounded)
    - DEP-003: Lock file present (uv.lock, poetry.lock, requirements.lock, pdm.lock,
               or requirements.txt with pinned versions)
    - DEP-004: No duplicate or conflicting dependencies
    - DEP-005: Optional dependencies properly grouped in
               [project.optional-dependencies]

    DEP-002 through DEP-005 are only emitted when DEP-001 passes
    (conditional suppression: no [project].dependencies means nothing to inspect).

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "dependency_hygiene"
    display_name = "Dependency Hygiene"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        project_data = self._load_pyproject(repo_path)
        has_deps = self._check_deps_declared(project_data, findings, recommendations)

        if has_deps:
            deps = project_data.get("dependencies", [])
            self._check_wildcard_versions(deps, findings, recommendations)
            self._check_lock_file(repo_path, findings, recommendations)
            self._check_duplicates(deps, findings, recommendations)
            self._check_optional_deps(project_data, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    @staticmethod
    def _load_pyproject(repo_path: Path) -> dict | None:
        """Load pyproject.toml and return the [project] table, or None."""
        pyproject = repo_path / "pyproject.toml"
        if not pyproject.exists():
            return None

        if tomllib is None:
            return None

        try:
            data = tomllib.loads(pyproject.read_text())
            return data.get("project")
        except Exception:
            return None

    def _check_deps_declared(
        self,
        project_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> bool:
        """DEP-001: Check that [project].dependencies exists and is non-empty."""
        if project_data is None:
            findings.append(
                Finding(
                    id="DEP-001",
                    message="No pyproject.toml with [project] table found",
                    severity="fail",
                    category=self.name,
                )
            )
            recommendations.append("Add a pyproject.toml with [project.dependencies]")
            return False

        deps = project_data.get("dependencies")
        if deps is None:
            findings.append(
                Finding(
                    id="DEP-001",
                    message="No dependencies field in [project]",
                    severity="fail",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append("Add a dependencies list to [project] in pyproject.toml")
            return False

        if not deps:
            findings.append(
                Finding(
                    id="DEP-001",
                    message="dependencies list is empty",
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                    detail="Empty dependencies list is valid for meta-packages",
                )
            )
            return True

        findings.append(
            Finding(
                id="DEP-001",
                message=f"{len(deps)} dependency(ies) declared",
                severity="pass",
                category=self.name,
                file_path="pyproject.toml",
            )
        )
        return True

    def _check_wildcard_versions(
        self,
        deps: list[str],
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        """DEP-002: Check that all deps have version constraints."""
        unbounded = [d for d in deps if not _has_version_specifier(d)]

        if not unbounded:
            findings.append(
                Finding(
                    id="DEP-002",
                    message="All dependencies have version constraints",
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            names = ", ".join(unbounded)
            findings.append(
                Finding(
                    id="DEP-002",
                    message=f"{len(unbounded)} unbounded dependency(ies): {names}",
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                    detail="Dependencies without version specifiers may break on "
                    "incompatible future releases",
                )
            )
            recommendations.append(f"Add version constraints to: {names}")

    def _check_lock_file(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        """DEP-003: Check that a lock file is present."""
        for lock_name in _LOCK_FILES:
            lock_path = repo_path / lock_name
            if lock_path.exists():
                findings.append(
                    Finding(
                        id="DEP-003",
                        message=f"Lock file found ({lock_name})",
                        severity="pass",
                        category=self.name,
                        file_path=lock_name,
                    )
                )
                return

        # Check requirements.txt as a lock proxy
        req_path = repo_path / _REQUIREMENTS_TXT
        if req_path.exists() and _is_pinned_requirements(req_path):
            findings.append(
                Finding(
                    id="DEP-003",
                    message="requirements.txt with pinned versions found (lock proxy)",
                    severity="pass",
                    category=self.name,
                    file_path=_REQUIREMENTS_TXT,
                )
            )
            return

        findings.append(
            Finding(
                id="DEP-003",
                message="No lock file found",
                severity="warn",
                category=self.name,
                detail="Checked: "
                + ", ".join(_LOCK_FILES)
                + ", requirements.txt (with pinned versions)",
            )
        )
        recommendations.append(
            "Add a lock file (uv lock, poetry lock, or pip freeze > requirements.txt)"
        )

    def _check_duplicates(
        self,
        deps: list[str],
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        """DEP-004: Check for duplicate or conflicting dependencies."""
        seen: dict[str, list[str]] = {}
        for dep in deps:
            name = _parse_dep_name(dep)
            seen.setdefault(name, []).append(dep)

        duplicates = {k: v for k, v in seen.items() if len(v) > 1}

        if not duplicates:
            findings.append(
                Finding(
                    id="DEP-004",
                    message="No duplicate dependencies",
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            dup_names = ", ".join(sorted(duplicates.keys()))
            findings.append(
                Finding(
                    id="DEP-004",
                    message=f"Duplicate dependency(ies): {dup_names}",
                    severity="fail",
                    category=self.name,
                    file_path="pyproject.toml",
                    detail="; ".join(f"{k}: {v}" for k, v in sorted(duplicates.items())),
                )
            )
            recommendations.append(f"Remove duplicate entries for: {dup_names}")

    def _check_optional_deps(
        self,
        project_data: dict,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        """DEP-005: Check that optional deps are in [project.optional-dependencies]."""
        opt_deps = project_data.get("optional-dependencies")

        if opt_deps is None:
            # No optional deps section — that's fine, not every project needs one
            findings.append(
                Finding(
                    id="DEP-005",
                    message="No optional dependency groups declared",
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                    detail="[project.optional-dependencies] not present (acceptable "
                    "if no optional features exist)",
                )
            )
            return

        if not opt_deps:
            findings.append(
                Finding(
                    id="DEP-005",
                    message="[project.optional-dependencies] is empty",
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                    detail="Empty optional-dependencies section is likely a leftover",
                )
            )
            recommendations.append(
                "Remove empty [project.optional-dependencies] or add dependency groups"
            )
            return

        # Check that each group is a non-empty list
        empty_groups = [g for g, entries in opt_deps.items() if not entries]
        group_names = sorted(opt_deps.keys())
        total = sum(len(v) for v in opt_deps.values())

        if empty_groups:
            findings.append(
                Finding(
                    id="DEP-005",
                    message=(
                        f"Empty optional dependency group(s): {', '.join(sorted(empty_groups))}"
                    ),
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append(
                f"Populate or remove empty groups: {', '.join(sorted(empty_groups))}"
            )
        else:
            findings.append(
                Finding(
                    id="DEP-005",
                    message=(
                        f"{len(group_names)} optional group(s) "
                        f"({', '.join(group_names)}) with {total} package(s)"
                    ),
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
