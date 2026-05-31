"""Checker for Java release readiness best practices."""

from __future__ import annotations

import re
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

_CHANGELOG_VERSION_RE = re.compile(r"^##\s+\[", re.MULTILINE)

# Maven version in pom.xml: <version>1.0.0</version> (top-level, not dependency)
_POM_VERSION_RE = re.compile(r"<version>([^<]+)</version>")

# Gradle version: version = "1.0.0" or version '1.0.0'
_GRADLE_VERSION_RE = re.compile(r"""version\s*=?\s*['"]([^'"]+)['"]""")

# Maven release profile
_RELEASE_PROFILE_RE = re.compile(r"<id>\s*release\s*</id>", re.IGNORECASE)


class Checker:
    """Release Readiness checker for Java repos.

    Finding IDs: JREL-001 through JREL-003.

    - JREL-001: Version declared in pom.xml or build.gradle
    - JREL-002: CHANGELOG.md present
    - JREL-003: Release profile configured

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "release_readiness"
    display_name = "Release Readiness"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        self._check_version(repo_path, findings, recommendations)
        self._check_changelog(repo_path, findings, recommendations)
        self._check_release_profile(repo_path, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    def _check_version(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        # Check pom.xml
        pom = repo_path / "pom.xml"
        if pom.exists():
            try:
                content = pom.read_text()
            except OSError:
                content = ""
            match = _POM_VERSION_RE.search(content)
            if match:
                version = match.group(1)
                findings.append(
                    Finding(
                        id="JREL-001",
                        message=f"Version declared in pom.xml ({version})",
                        severity="pass",
                        category=self.name,
                        file_path="pom.xml",
                    )
                )
                return

        # Check build.gradle / build.gradle.kts
        for gradle_file in ("build.gradle", "build.gradle.kts"):
            path = repo_path / gradle_file
            if path.exists():
                try:
                    content = path.read_text()
                except OSError:
                    content = ""
                match = _GRADLE_VERSION_RE.search(content)
                if match:
                    version = match.group(1)
                    findings.append(
                        Finding(
                            id="JREL-001",
                            message=f"Version declared in {gradle_file} ({version})",
                            severity="pass",
                            category=self.name,
                            file_path=gradle_file,
                        )
                    )
                    return

        findings.append(
            Finding(
                id="JREL-001",
                message="No version declared in build file",
                severity="fail",
                category=self.name,
                detail="Expected <version> in pom.xml or version in build.gradle",
            )
        )
        recommendations.append("Declare a version in pom.xml or build.gradle")

    def _check_changelog(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        changelog = repo_path / "CHANGELOG.md"
        if changelog.exists():
            findings.append(
                Finding(
                    id="JREL-002",
                    message="CHANGELOG.md found",
                    severity="pass",
                    category=self.name,
                    file_path="CHANGELOG.md",
                )
            )
        else:
            findings.append(
                Finding(
                    id="JREL-002",
                    message="No CHANGELOG.md found",
                    severity="warn",
                    category=self.name,
                )
            )
            recommendations.append(
                "Add a CHANGELOG.md following Keep a Changelog format"
            )

    def _check_release_profile(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        # Maven release profile
        pom = repo_path / "pom.xml"
        if pom.exists():
            try:
                content = pom.read_text()
            except OSError:
                content = ""
            if _RELEASE_PROFILE_RE.search(content) or "maven-release-plugin" in content:
                findings.append(
                    Finding(
                        id="JREL-003",
                        message="Release profile configured in pom.xml",
                        severity="pass",
                        category=self.name,
                        file_path="pom.xml",
                    )
                )
                return

        # Gradle release plugin
        for gradle_file in ("build.gradle", "build.gradle.kts"):
            path = repo_path / gradle_file
            if path.exists():
                try:
                    content = path.read_text()
                except OSError:
                    content = ""
                if "release" in content.lower() and "plugin" in content.lower():
                    findings.append(
                        Finding(
                            id="JREL-003",
                            message=f"Release plugin configured in {gradle_file}",
                            severity="pass",
                            category=self.name,
                            file_path=gradle_file,
                        )
                    )
                    return

        findings.append(
            Finding(
                id="JREL-003",
                message="No release profile or plugin configured",
                severity="warn",
                category=self.name,
                detail="Configure a Maven release profile or Gradle release plugin",
            )
        )
        recommendations.append(
            "Configure a release profile (Maven) or release plugin (Gradle)"
        )
