"""Checker for documentation best practices."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

_README_VARIANTS = [
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "readme.md",
    "readme.rst",
    "readme.txt",
    "readme",
]

_CHANGELOG_VARIANTS = [
    "CHANGELOG.md",
    "CHANGELOG.rst",
    "CHANGELOG.txt",
    "CHANGELOG",
    "CHANGES.md",
    "CHANGES.rst",
    "CHANGES.txt",
    "CHANGES",
    "HISTORY.md",
    "HISTORY.rst",
    "HISTORY.txt",
    "HISTORY",
    "changelog.md",
    "changelog.rst",
    "changelog.txt",
    "changelog",
    "changes.md",
    "changes.rst",
    "changes.txt",
    "changes",
    "history.md",
    "history.rst",
    "history.txt",
    "history",
]

# Directories to skip when scanning for Python packages
_SKIP_DIRS = frozenset(
    {
        ".venv",
        "venv",
        ".env",
        "env",
        "node_modules",
        "__pycache__",
        "build",
        "dist",
        ".eggs",
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".nox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)

_INSTALL_RE = re.compile(
    r"\b(install(ation)?|setup|getting\s+started|prerequisites)\b",
    re.IGNORECASE,
)

_USAGE_RE = re.compile(
    r"\b(usage|quick\s*start|example[s]?|how\s+to\s+use|tutorial|demo|basic\s+usage)\b",
    re.IGNORECASE,
)

_MIN_README_LENGTH = 100  # non-whitespace characters


class Checker:
    """Documentation checker for Python repos.

    Finding IDs: DOC-001 through DOC-005.

    - DOC-001: README file present and non-trivial (>100 non-whitespace chars)
    - DOC-002: README contains installation/setup guidance
    - DOC-003: README contains usage/quickstart guidance
    - DOC-004: CHANGELOG or equivalent release notes file present
    - DOC-005: Public module docstring coverage (>=50% of .py files in packages)

    DOC-002 through DOC-005 are only emitted when DOC-001 passes
    (conditional suppression: no usable README means documentation is
    fundamentally missing — fix that first).

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "documentation"
    display_name = "Documentation"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        readme_path, readme_text = self._find_readme(repo_path)
        has_readme = self._check_readme_present(
            readme_path,
            readme_text,
            findings,
            recommendations,
        )

        if has_readme:
            self._check_install_section(
                readme_path,
                readme_text,
                findings,
                recommendations,
            )
            self._check_usage_section(
                readme_path,
                readme_text,
                findings,
                recommendations,
            )
            self._check_changelog(repo_path, findings, recommendations)
            self._check_docstrings(repo_path, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    @staticmethod
    def _find_readme(repo_path: Path) -> tuple[str | None, str]:
        """Return (relative_path, text) for the first README variant found."""
        for name in _README_VARIANTS:
            path = repo_path / name
            if path.exists():
                try:
                    return name, path.read_text()
                except OSError:
                    return name, ""
        return None, ""

    def _check_readme_present(
        self,
        readme_path: str | None,
        readme_text: str,
        findings: list[Finding],
        recommendations: list[str],
    ) -> bool:
        """DOC-001: README present and non-trivial."""
        if readme_path is None:
            findings.append(
                Finding(
                    id="DOC-001",
                    message="No README file found",
                    severity="fail",
                    category=self.name,
                )
            )
            recommendations.append("Add a README.md to the repository root")
            return False

        non_ws = sum(1 for c in readme_text if not c.isspace())
        if non_ws < _MIN_README_LENGTH:
            findings.append(
                Finding(
                    id="DOC-001",
                    message=(
                        f"README too short ({non_ws} non-whitespace chars, "
                        f"need {_MIN_README_LENGTH}+)"
                    ),
                    severity="fail",
                    category=self.name,
                    file_path=readme_path,
                )
            )
            recommendations.append(
                "Expand the README with project description, installation, and usage sections"
            )
            return False

        findings.append(
            Finding(
                id="DOC-001",
                message=f"README found ({readme_path})",
                severity="pass",
                category=self.name,
                file_path=readme_path,
            )
        )
        return True

    def _check_install_section(
        self,
        readme_path: str | None,
        readme_text: str,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        """DOC-002: README contains installation guidance."""
        if _INSTALL_RE.search(readme_text):
            findings.append(
                Finding(
                    id="DOC-002",
                    message="Installation/setup section found in README",
                    severity="pass",
                    category=self.name,
                    file_path=readme_path,
                )
            )
        else:
            findings.append(
                Finding(
                    id="DOC-002",
                    message="No installation/setup section found in README",
                    severity="warn",
                    category=self.name,
                    file_path=readme_path,
                )
            )
            recommendations.append("Add an installation section to the README")

    def _check_usage_section(
        self,
        readme_path: str | None,
        readme_text: str,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        """DOC-003: README contains usage guidance."""
        if _USAGE_RE.search(readme_text):
            findings.append(
                Finding(
                    id="DOC-003",
                    message="Usage/quickstart section found in README",
                    severity="pass",
                    category=self.name,
                    file_path=readme_path,
                )
            )
        else:
            findings.append(
                Finding(
                    id="DOC-003",
                    message="No usage/quickstart section found in README",
                    severity="warn",
                    category=self.name,
                    file_path=readme_path,
                )
            )
            recommendations.append("Add a usage or quickstart section to the README")

    @staticmethod
    def _find_changelog(repo_path: Path) -> str | None:
        """Return the relative path of the first CHANGELOG variant found."""
        for name in _CHANGELOG_VARIANTS:
            if (repo_path / name).exists():
                return name
        return None

    def _check_changelog(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        """DOC-004: CHANGELOG or equivalent present."""
        changelog = self._find_changelog(repo_path)
        if changelog:
            findings.append(
                Finding(
                    id="DOC-004",
                    message=f"Changelog found ({changelog})",
                    severity="pass",
                    category=self.name,
                    file_path=changelog,
                )
            )
        else:
            findings.append(
                Finding(
                    id="DOC-004",
                    message="No changelog file found",
                    severity="warn",
                    category=self.name,
                    detail="Checked: CHANGELOG, CHANGES, HISTORY (with .md/.rst/.txt extensions)",
                )
            )
            recommendations.append("Add a CHANGELOG.md to track release history")

    def _check_docstrings(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        """DOC-005: Module docstring coverage in Python packages."""
        py_files = self._find_package_py_files(repo_path)

        if not py_files:
            findings.append(
                Finding(
                    id="DOC-005",
                    message="No Python package files found to check",
                    severity="pass",
                    category=self.name,
                    detail="No directories with __init__.py detected",
                )
            )
            return

        with_docstring = sum(1 for f in py_files if self._has_module_docstring(f))
        total = len(py_files)
        pct = (with_docstring * 100) // total if total > 0 else 0

        if pct >= 50:
            findings.append(
                Finding(
                    id="DOC-005",
                    message=(f"Module docstring coverage: {pct}% ({with_docstring}/{total} files)"),
                    severity="pass",
                    category=self.name,
                )
            )
        else:
            findings.append(
                Finding(
                    id="DOC-005",
                    message=(
                        f"Low module docstring coverage: {pct}% ({with_docstring}/{total} files)"
                    ),
                    severity="warn",
                    category=self.name,
                    detail="Fewer than 50% of Python package files have module docstrings",
                )
            )
            recommendations.append(
                f"Add module docstrings to Python files "
                f"({with_docstring}/{total} currently have them)"
            )

    @staticmethod
    def _find_package_py_files(repo_path: Path) -> list[Path]:
        """Find .py files in Python packages (dirs with __init__.py).

        Excludes test directories, virtual environments, and build artifacts.
        """
        py_files: list[Path] = []
        for init in repo_path.rglob("__init__.py"):
            parts = init.relative_to(repo_path).parts
            if any(p in _SKIP_DIRS or p.endswith(".egg-info") for p in parts):
                continue
            if any(p in ("test", "tests") for p in parts):
                continue
            pkg_dir = init.parent
            for py in pkg_dir.glob("*.py"):
                py_files.append(py)
        return py_files

    @staticmethod
    def _has_module_docstring(py_file: Path) -> bool:
        """Check if a Python file has a module-level docstring via AST."""
        try:
            source = py_file.read_text()
            tree = ast.parse(source)
            return ast.get_docstring(tree) is not None
        except (OSError, SyntaxError, ValueError):
            return False
