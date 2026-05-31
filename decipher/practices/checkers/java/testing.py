"""Checker for Java testing best practices."""

from __future__ import annotations

import re
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

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

_TEST_ANNOTATION_RE = re.compile(r"@Test\b")
_TESTNG_RE = re.compile(r"import\s+org\.testng\b")
_JUNIT_RE = re.compile(r"import\s+org\.junit\b")

_IT_NAME_PATTERNS = re.compile(
    r"(IT\.java$|IntegrationTest\.java$|/it/|/integration-test/|/integrationTest/)",
)


class Checker:
    """Testing checker for Java repos.

    Finding IDs: JTEST-001 through JTEST-003.

    - JTEST-001: JUnit or TestNG tests present
    - JTEST-002: Test directory structure (src/test/java exists)
    - JTEST-003: Integration tests separated from unit tests

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "testing"
    display_name = "Testing"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        test_files = self._find_test_files(repo_path)

        self._check_tests_present(test_files, findings, recommendations)
        self._check_test_directory(repo_path, findings, recommendations)
        self._check_integration_tests(repo_path, test_files, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    @staticmethod
    def _find_test_files(repo_path: Path) -> list[Path]:
        """Find Java test files (files containing @Test annotation)."""
        test_files: list[Path] = []
        for p in repo_path.rglob("*.java"):
            parts = p.relative_to(repo_path).parts
            if any(part in _IGNORE_DIRS for part in parts):
                continue
            try:
                content = p.read_text()
            except OSError:
                continue
            if _TEST_ANNOTATION_RE.search(content):
                test_files.append(p)
        return sorted(test_files)

    def _check_tests_present(
        self,
        test_files: list[Path],
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        if test_files:
            # Detect framework
            frameworks: set[str] = set()
            for f in test_files:
                try:
                    content = f.read_text()
                except OSError:
                    continue
                if _JUNIT_RE.search(content):
                    frameworks.add("JUnit")
                if _TESTNG_RE.search(content):
                    frameworks.add("TestNG")

            fw_str = " and ".join(sorted(frameworks)) if frameworks else "unknown framework"
            findings.append(
                Finding(
                    id="JTEST-001",
                    message=f"{len(test_files)} test file(s) found ({fw_str})",
                    severity="pass",
                    category=self.name,
                )
            )
        else:
            findings.append(
                Finding(
                    id="JTEST-001",
                    message="No test files found (no @Test annotations detected)",
                    severity="fail",
                    category=self.name,
                    detail="Expected Java files with @Test annotations "
                    "(JUnit or TestNG)",
                )
            )
            recommendations.append("Add JUnit or TestNG tests with @Test annotations")

    def _check_test_directory(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        test_java = repo_path / "src" / "test" / "java"
        if test_java.is_dir():
            findings.append(
                Finding(
                    id="JTEST-002",
                    message="Test directory found (src/test/java)",
                    severity="pass",
                    category=self.name,
                    file_path="src/test/java",
                )
            )
        else:
            findings.append(
                Finding(
                    id="JTEST-002",
                    message="No src/test/java directory found",
                    severity="fail",
                    category=self.name,
                )
            )
            recommendations.append(
                "Create src/test/java directory for test sources"
            )

    def _check_integration_tests(
        self,
        repo_path: Path,
        test_files: list[Path],
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        if not test_files:
            return

        # Check for integration test separation patterns
        has_it_dir = (
            (repo_path / "src" / "integration-test").is_dir()
            or (repo_path / "src" / "it").is_dir()
            or (repo_path / "src" / "integrationTest").is_dir()
        )

        has_it_files = any(
            _IT_NAME_PATTERNS.search(str(f.relative_to(repo_path)))
            for f in test_files
        )

        # Also check Maven Failsafe plugin in pom.xml
        has_failsafe = False
        pom = repo_path / "pom.xml"
        if pom.exists():
            try:
                content = pom.read_text()
                has_failsafe = "maven-failsafe-plugin" in content
            except OSError:
                pass

        if has_it_dir or has_it_files or has_failsafe:
            findings.append(
                Finding(
                    id="JTEST-003",
                    message="Integration tests separated from unit tests",
                    severity="pass",
                    category=self.name,
                )
            )
        else:
            findings.append(
                Finding(
                    id="JTEST-003",
                    message="No integration test separation detected",
                    severity="warn",
                    category=self.name,
                    detail="Expected separate IT directory, *IT.java naming, "
                    "or Maven Failsafe plugin",
                )
            )
            recommendations.append(
                "Separate integration tests using *IT.java naming or "
                "a dedicated src/integration-test directory"
            )
