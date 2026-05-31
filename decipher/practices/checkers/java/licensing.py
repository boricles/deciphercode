"""Checker for Java licensing best practices."""

from __future__ import annotations

import re
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

_LICENSE_VARIANTS = [
    "LICENSE",
    "LICENSE.txt",
    "LICENSE.md",
    "LICENCE",
    "LICENCE.txt",
    "LICENCE.md",
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

# Matches common license header patterns in Java source files
_LICENSE_HEADER_RE = re.compile(
    r"/\*\*?\s*\n"
    r"(?:\s*\*.*\n)*?"
    r"\s*\*.*(?:Copyright|License|Licensed|Apache|MIT|GPL|BSD)",
    re.IGNORECASE,
)


class Checker:
    """Licensing checker for Java repos.

    Finding IDs: JLIC-001 through JLIC-002.

    - JLIC-001: LICENSE file present at repository root
    - JLIC-002: License headers in source files

    JLIC-002 is only emitted when JLIC-001 passes
    (conditional suppression).

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "licensing"
    display_name = "Licensing"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        has_license = self._check_license_file(repo_path, findings, recommendations)

        if has_license:
            self._check_license_headers(repo_path, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    def _check_license_file(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> bool:
        found = next(
            (n for n in _LICENSE_VARIANTS if (repo_path / n).exists()),
            None,
        )

        if found:
            findings.append(
                Finding(
                    id="JLIC-001",
                    message=f"LICENSE file found ({found})",
                    severity="pass",
                    category=self.name,
                    file_path=found,
                )
            )
            return True

        findings.append(
            Finding(
                id="JLIC-001",
                message="No LICENSE file found at repository root",
                severity="fail",
                category=self.name,
            )
        )
        recommendations.append("Add a LICENSE file to the repository root")
        return False

    def _check_license_headers(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        java_files = self._find_java_sources(repo_path)

        if not java_files:
            findings.append(
                Finding(
                    id="JLIC-002",
                    message="No Java source files to check for license headers",
                    severity="pass",
                    category=self.name,
                )
            )
            return

        # Sample up to 20 files for header check
        sample = java_files[:20]
        with_header = 0
        for f in sample:
            try:
                # Read only the first 2KB to check for header
                content = f.read_text()[:2048]
            except OSError:
                continue
            if _LICENSE_HEADER_RE.search(content):
                with_header += 1

        total = len(sample)
        pct = (with_header * 100) // total if total > 0 else 0

        if pct >= 50:
            findings.append(
                Finding(
                    id="JLIC-002",
                    message=f"License headers found in {pct}% of sampled source files "
                    f"({with_header}/{total})",
                    severity="pass",
                    category=self.name,
                )
            )
        else:
            findings.append(
                Finding(
                    id="JLIC-002",
                    message=f"License headers missing in most source files "
                    f"({with_header}/{total} sampled)",
                    severity="warn",
                    category=self.name,
                    detail="Add license/copyright headers to Java source files",
                )
            )
            recommendations.append(
                "Add license headers to Java source files "
                "(use maven-license-plugin or Gradle license plugin)"
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
            # Skip test files
            if "test" in parts or "tests" in parts:
                continue
            java_files.append(p)
        return sorted(java_files)
