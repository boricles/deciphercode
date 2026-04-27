"""Checker for Python project structure best practices."""

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

_CHANGELOG_VERSION_RE = re.compile(r"^##\s+\[", re.MULTILINE)
_CHANGELOG_TYPE_RE = re.compile(
    r"^###\s+(Added|Changed|Deprecated|Removed|Fixed|Security)",
    re.MULTILINE,
)

_README_SECTION_KEYWORDS: dict[str, list[str]] = {
    "install": ["install", "installation", "getting started", "setup", "quick start"],
    "usage": ["usage", "how to use", "examples"],
    "license": ["license", "licence"],
}


class Checker:
    """Project Structure checker for Python repos.

    Finding IDs: PROJ-001 through PROJ-011.

    - PROJ-001: pyproject.toml present
    - PROJ-002: pyproject.toml has [project] table
    - PROJ-003: setup.py-only legacy detection
    - PROJ-004: Recognized package layout (src/ or flat)
    - PROJ-005: LICENSE file at root
    - PROJ-006: README file present
    - PROJ-007: README has install/setup section
    - PROJ-008: README has usage section
    - PROJ-009: README has license section
    - PROJ-010: CHANGELOG.md present
    - PROJ-011: CHANGELOG follows Keep a Changelog format

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "project_structure"
    display_name = "Project Structure"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        self._check_pyproject(repo_path, findings, recommendations)
        self._check_setup_py_legacy(repo_path, findings, recommendations)
        self._check_layout(repo_path, findings)
        self._check_license(repo_path, findings, recommendations)
        self._check_readme(repo_path, findings, recommendations)
        self._check_changelog(repo_path, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    def _check_pyproject(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        pyproject = repo_path / "pyproject.toml"
        if not pyproject.exists():
            findings.append(
                Finding(
                    id="PROJ-001",
                    message="pyproject.toml not found",
                    severity="fail",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append("Add a pyproject.toml with [project] metadata (PEP 621)")
            return

        findings.append(
            Finding(
                id="PROJ-001",
                message="pyproject.toml found",
                severity="pass",
                category=self.name,
                file_path="pyproject.toml",
            )
        )

        # Parse and check for [project] table
        content = pyproject.read_text()
        if tomllib is not None:
            try:
                data = tomllib.loads(content)
                has_project = "project" in data
            except Exception:
                findings.append(
                    Finding(
                        id="PROJ-002",
                        message="pyproject.toml could not be parsed",
                        severity="warn",
                        category=self.name,
                        file_path="pyproject.toml",
                        detail="Ensure the file is valid TOML",
                    )
                )
                recommendations.append("Fix pyproject.toml syntax errors")
                return
        else:
            has_project = "[project]" in content

        if has_project:
            findings.append(
                Finding(
                    id="PROJ-002",
                    message="pyproject.toml has [project] table",
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            findings.append(
                Finding(
                    id="PROJ-002",
                    message="pyproject.toml missing [project] table",
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append("Add a [project] table to pyproject.toml (PEP 621)")

    def _check_setup_py_legacy(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        setup_py = repo_path / "setup.py"
        pyproject = repo_path / "pyproject.toml"

        if setup_py.exists() and not pyproject.exists():
            findings.append(
                Finding(
                    id="PROJ-003",
                    message="setup.py found without pyproject.toml (legacy)",
                    severity="warn",
                    category=self.name,
                    file_path="setup.py",
                )
            )
            recommendations.append("Migrate from setup.py to pyproject.toml (PEP 621)")
        elif setup_py.exists() and pyproject.exists():
            findings.append(
                Finding(
                    id="PROJ-003",
                    message="Both setup.py and pyproject.toml present",
                    severity="pass",
                    category=self.name,
                    file_path="setup.py",
                    detail="Consider removing setup.py if pyproject.toml is complete",
                )
            )

    def _check_layout(
        self,
        repo_path: Path,
        findings: list[Finding],
    ) -> None:
        src_dir = repo_path / "src"
        has_src = src_dir.is_dir() and any(src_dir.iterdir())

        has_flat_pkg = any(
            (d / "__init__.py").exists()
            for d in repo_path.iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and d.name not in ("tests", "test", "docs", "src")
        )

        if has_src:
            findings.append(
                Finding(
                    id="PROJ-004",
                    message="src/ layout detected",
                    severity="pass",
                    category=self.name,
                    file_path="src",
                )
            )
        elif has_flat_pkg:
            findings.append(
                Finding(
                    id="PROJ-004",
                    message="Flat package layout detected",
                    severity="pass",
                    category=self.name,
                )
            )

    def _check_license(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        variants = [
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
            "LICENCE",
            "LICENCE.txt",
            "LICENCE.md",
        ]
        found = next((n for n in variants if (repo_path / n).exists()), None)

        if found:
            findings.append(
                Finding(
                    id="PROJ-005",
                    message=f"License file found ({found})",
                    severity="pass",
                    category=self.name,
                    file_path=found,
                )
            )
        else:
            findings.append(
                Finding(
                    id="PROJ-005",
                    message="No LICENSE file found at repository root",
                    severity="fail",
                    category=self.name,
                )
            )
            recommendations.append("Add a LICENSE file to the repository root")

    def _check_readme(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        variants = ["README.md", "README.rst", "README.txt", "README"]
        found = next((n for n in variants if (repo_path / n).exists()), None)

        if not found:
            findings.append(
                Finding(
                    id="PROJ-006",
                    message="No README file found",
                    severity="fail",
                    category=self.name,
                )
            )
            recommendations.append("Add a README.md with install, usage, and license sections")
            return

        findings.append(
            Finding(
                id="PROJ-006",
                message=f"README found ({found})",
                severity="pass",
                category=self.name,
                file_path=found,
            )
        )

        content = (repo_path / found).read_text().lower()
        headings = re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)
        heading_text = " ".join(headings)

        id_map = {"install": "PROJ-007", "usage": "PROJ-008", "license": "PROJ-009"}

        for section_key, keywords in _README_SECTION_KEYWORDS.items():
            has_section = any(kw in heading_text for kw in keywords)
            finding_id = id_map[section_key]

            if has_section:
                findings.append(
                    Finding(
                        id=finding_id,
                        message=f"README has {section_key} section",
                        severity="pass",
                        category=self.name,
                        file_path=found,
                    )
                )
            else:
                findings.append(
                    Finding(
                        id=finding_id,
                        message=f"README missing {section_key} section",
                        severity="warn",
                        category=self.name,
                        file_path=found,
                    )
                )
                recommendations.append(f"Add a {section_key} section to {found}")

    def _check_changelog(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        changelog = repo_path / "CHANGELOG.md"
        if not changelog.exists():
            findings.append(
                Finding(
                    id="PROJ-010",
                    message="No CHANGELOG.md found",
                    severity="warn",
                    category=self.name,
                    file_path="CHANGELOG.md",
                )
            )
            recommendations.append(
                "Add a CHANGELOG.md following Keep a Changelog format (https://keepachangelog.com)"
            )
            return

        findings.append(
            Finding(
                id="PROJ-010",
                message="CHANGELOG.md found",
                severity="pass",
                category=self.name,
                file_path="CHANGELOG.md",
            )
        )

        content = changelog.read_text()
        has_versions = bool(_CHANGELOG_VERSION_RE.search(content))
        has_types = bool(_CHANGELOG_TYPE_RE.search(content))

        if has_versions and has_types:
            findings.append(
                Finding(
                    id="PROJ-011",
                    message="CHANGELOG follows Keep a Changelog format",
                    severity="pass",
                    category=self.name,
                    file_path="CHANGELOG.md",
                )
            )
        else:
            findings.append(
                Finding(
                    id="PROJ-011",
                    message="CHANGELOG does not follow Keep a Changelog format",
                    severity="warn",
                    category=self.name,
                    file_path="CHANGELOG.md",
                    detail="Expected version headers (## [x.y.z]) and change types "
                    "(### Added, ### Changed, etc.)",
                )
            )
            recommendations.append(
                "Format CHANGELOG.md following Keep a Changelog (https://keepachangelog.com)"
            )
