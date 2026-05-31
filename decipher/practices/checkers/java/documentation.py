"""Checker for Java documentation best practices."""

from __future__ import annotations

import re
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

_README_VARIANTS = [
    "README.md",
    "README.rst",
    "README.txt",
    "README",
]

_IGNORE_DIRS = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        "build",
        "target",
        ".gradle",
        ".idea",
        "node_modules",
        "bin",
        "out",
    }
)

_JAVADOC_RE = re.compile(r"/\*\*\s*\n(?:\s*\*.*\n)*?\s*\*/")

_MIN_README_LENGTH = 100  # non-whitespace characters


class Checker:
    """Documentation checker for Java repos.

    Finding IDs: JDOC-001 through JDOC-003.

    - JDOC-001: README.md present and non-trivial
    - JDOC-002: Javadoc comments in source files
    - JDOC-003: API documentation (javadoc plugin or docs dir)

    JDOC-002 and JDOC-003 are only emitted when JDOC-001 passes
    (conditional suppression).

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "documentation"
    display_name = "Documentation"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        has_readme = self._check_readme(repo_path, findings, recommendations)

        if has_readme:
            self._check_javadoc(repo_path, findings, recommendations)
            self._check_api_docs(repo_path, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    def _check_readme(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> bool:
        found = next(
            (n for n in _README_VARIANTS if (repo_path / n).exists()),
            None,
        )

        if found is None:
            findings.append(
                Finding(
                    id="JDOC-001",
                    message="No README file found",
                    severity="fail",
                    category=self.name,
                )
            )
            recommendations.append("Add a README.md to the repository root")
            return False

        try:
            content = (repo_path / found).read_text()
        except OSError:
            content = ""

        non_ws = sum(1 for c in content if not c.isspace())
        if non_ws < _MIN_README_LENGTH:
            findings.append(
                Finding(
                    id="JDOC-001",
                    message=f"README too short ({non_ws} non-whitespace chars, "
                    f"need {_MIN_README_LENGTH}+)",
                    severity="fail",
                    category=self.name,
                    file_path=found,
                )
            )
            recommendations.append(
                "Expand the README with project description, build instructions, and usage"
            )
            return False

        findings.append(
            Finding(
                id="JDOC-001",
                message=f"README found ({found})",
                severity="pass",
                category=self.name,
                file_path=found,
            )
        )
        return True

    def _check_javadoc(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        java_files = self._find_java_sources(repo_path)

        if not java_files:
            findings.append(
                Finding(
                    id="JDOC-002",
                    message="No Java source files found to check",
                    severity="pass",
                    category=self.name,
                )
            )
            return

        # Sample up to 20 files
        sample = java_files[:20]
        with_javadoc = 0
        for f in sample:
            try:
                content = f.read_text()
            except OSError:
                continue
            if _JAVADOC_RE.search(content):
                with_javadoc += 1

        total = len(sample)
        pct = (with_javadoc * 100) // total if total > 0 else 0

        if pct >= 50:
            findings.append(
                Finding(
                    id="JDOC-002",
                    message=f"Javadoc coverage: {pct}% of sampled files "
                    f"({with_javadoc}/{total})",
                    severity="pass",
                    category=self.name,
                )
            )
        else:
            findings.append(
                Finding(
                    id="JDOC-002",
                    message=f"Low Javadoc coverage: {pct}% of sampled files "
                    f"({with_javadoc}/{total})",
                    severity="warn",
                    category=self.name,
                    detail="Fewer than 50% of sampled Java files have Javadoc comments",
                )
            )
            recommendations.append(
                "Add Javadoc comments to public classes and methods"
            )

    def _check_api_docs(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        # Check for javadoc plugin in build files
        has_javadoc_plugin = False

        pom = repo_path / "pom.xml"
        if pom.exists():
            try:
                content = pom.read_text()
            except OSError:
                content = ""
            if "maven-javadoc-plugin" in content:
                has_javadoc_plugin = True

        if not has_javadoc_plugin:
            for gradle_file in ("build.gradle", "build.gradle.kts"):
                path = repo_path / gradle_file
                if path.exists():
                    try:
                        content = path.read_text()
                    except OSError:
                        continue
                    if "javadoc" in content.lower():
                        has_javadoc_plugin = True
                        break

        # Check for docs directory
        has_docs_dir = (repo_path / "docs").is_dir() or (repo_path / "doc").is_dir()

        if has_javadoc_plugin or has_docs_dir:
            if has_javadoc_plugin:
                msg = "Javadoc plugin configured in build file"
            else:
                msg = "Documentation directory found"
            findings.append(
                Finding(
                    id="JDOC-003",
                    message=msg,
                    severity="pass",
                    category=self.name,
                )
            )
        else:
            findings.append(
                Finding(
                    id="JDOC-003",
                    message="No API documentation setup found",
                    severity="warn",
                    category=self.name,
                    detail="Expected maven-javadoc-plugin, Gradle javadoc task, or docs/ directory",
                )
            )
            recommendations.append(
                "Configure Javadoc generation (maven-javadoc-plugin or Gradle javadoc task)"
            )

    @staticmethod
    def _find_java_sources(repo_path: Path) -> list[Path]:
        """Find .java source files (not test files)."""
        java_files: list[Path] = []
        main_java = repo_path / "src" / "main" / "java"
        search_root = main_java if main_java.is_dir() else repo_path

        for p in search_root.rglob("*.java"):
            parts = p.relative_to(repo_path).parts
            if any(part in _IGNORE_DIRS for part in parts):
                continue
            if "test" in parts or "tests" in parts:
                continue
            java_files.append(p)
        return sorted(java_files)
