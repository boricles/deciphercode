"""Checker for Java dependency hygiene best practices."""

from __future__ import annotations

import re
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

_SNAPSHOT_RE = re.compile(r"<version>[^<]*-SNAPSHOT[^<]*</version>")

# Match <dependencyManagement> section in pom.xml
_DEP_MGMT_RE = re.compile(r"<dependencyManagement>", re.IGNORECASE)

# Match BOM import pattern:
#   <type>pom</type> + <scope>import</scope> inside dependencyManagement
_BOM_IMPORT_RE = re.compile(
    r"<type>\s*pom\s*</type>.*?<scope>\s*import\s*</scope>",
    re.DOTALL | re.IGNORECASE,
)

# Gradle platform/BOM usage
_GRADLE_PLATFORM_RE = re.compile(r"\bplatform\s*\(|enforcedPlatform\s*\(")
_GRADLE_BOM_RE = re.compile(r"dependencyManagement\b")

_BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")


def _find_build_file(repo_path: Path) -> str | None:
    """Return the relative path of the first build file found, or None."""
    for name in _BUILD_FILES:
        if (repo_path / name).exists():
            return name
    return None


class Checker:
    """Dependency Hygiene checker for Java repos.

    Finding IDs: JDEP-001 through JDEP-003.

    - JDEP-001: No SNAPSHOT dependencies in releases
    - JDEP-002: Dependency management section present
    - JDEP-003: BOM usage for version control

    All findings require a build file to be present.  When no
    pom.xml / build.gradle / build.gradle.kts exists, a single
    gate-fail is emitted and downstream checks are suppressed.

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "dependency_hygiene"
    display_name = "Dependency Hygiene"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        build_file = _find_build_file(repo_path)
        if build_file is None:
            findings.append(
                Finding(
                    id="JDEP-001",
                    message="No build file found (pom.xml, build.gradle, or build.gradle.kts)",
                    severity="fail",
                    category=self.name,
                )
            )
            recommendations.append(
                "Add a build file (pom.xml or build.gradle) to manage dependencies"
            )
            return CheckerResult(
                name=self.name,
                display_name=self.display_name,
                status=worst_status(findings),
                score=compute_score(findings),
                findings=findings,
                recommendations=recommendations,
            )

        self._check_snapshot_deps(repo_path, build_file, findings, recommendations)
        self._check_dep_management(repo_path, build_file, findings, recommendations)
        self._check_bom_usage(repo_path, build_file, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    def _check_snapshot_deps(
        self,
        repo_path: Path,
        build_file: str,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        path = repo_path / build_file
        try:
            content = path.read_text()
        except OSError:
            return

        if build_file == "pom.xml":
            snapshots = _SNAPSHOT_RE.findall(content)
            if snapshots:
                findings.append(
                    Finding(
                        id="JDEP-001",
                        message=f"{len(snapshots)} SNAPSHOT dependency(ies) found in pom.xml",
                        severity="warn",
                        category=self.name,
                        file_path="pom.xml",
                        detail="SNAPSHOT dependencies should be removed before release",
                    )
                )
                recommendations.append("Remove SNAPSHOT dependencies before releasing")
            else:
                findings.append(
                    Finding(
                        id="JDEP-001",
                        message="No SNAPSHOT dependencies found",
                        severity="pass",
                        category=self.name,
                        file_path="pom.xml",
                    )
                )
        else:
            snapshot_count = content.lower().count("-snapshot")
            if snapshot_count > 0:
                findings.append(
                    Finding(
                        id="JDEP-001",
                        message=f"{snapshot_count} SNAPSHOT reference(s) found",
                        severity="warn",
                        category=self.name,
                        file_path=build_file,
                        detail="SNAPSHOT dependencies should be removed before release",
                    )
                )
                recommendations.append(
                    "Remove SNAPSHOT dependencies before releasing"
                )
            else:
                findings.append(
                    Finding(
                        id="JDEP-001",
                        message="No SNAPSHOT dependencies found",
                        severity="pass",
                        category=self.name,
                        file_path=build_file,
                    )
                )

    def _check_dep_management(
        self,
        repo_path: Path,
        build_file: str,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        path = repo_path / build_file
        try:
            content = path.read_text()
        except OSError:
            content = ""

        if build_file == "pom.xml":
            if _DEP_MGMT_RE.search(content):
                findings.append(
                    Finding(
                        id="JDEP-002",
                        message="Dependency management section found in pom.xml",
                        severity="pass",
                        category=self.name,
                        file_path="pom.xml",
                    )
                )
                return
        else:
            # Gradle: check for constraints, dependencyManagement, or version catalog ref
            if (
                "constraints" in content
                or _GRADLE_BOM_RE.search(content)
                or "libs.versions.toml" in content
            ):
                findings.append(
                    Finding(
                        id="JDEP-002",
                        message=f"Dependency management configured in {build_file}",
                        severity="pass",
                        category=self.name,
                        file_path=build_file,
                    )
                )
                return

        # Check for Gradle version catalog
        version_catalog = repo_path / "gradle" / "libs.versions.toml"
        if version_catalog.exists():
            findings.append(
                Finding(
                    id="JDEP-002",
                    message="Gradle version catalog found (libs.versions.toml)",
                    severity="pass",
                    category=self.name,
                    file_path="gradle/libs.versions.toml",
                )
            )
            return

        findings.append(
            Finding(
                id="JDEP-002",
                message="No dependency management section found",
                severity="warn",
                category=self.name,
                file_path=build_file,
                detail="Use <dependencyManagement> in pom.xml or "
                "Gradle version catalog for centralized version control",
            )
        )
        recommendations.append(
            "Add a <dependencyManagement> section (Maven) or "
            "version catalog (Gradle) for centralized dependency versions"
        )

    def _check_bom_usage(
        self,
        repo_path: Path,
        build_file: str,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        path = repo_path / build_file
        try:
            content = path.read_text()
        except OSError:
            content = ""

        if build_file == "pom.xml":
            if _BOM_IMPORT_RE.search(content):
                findings.append(
                    Finding(
                        id="JDEP-003",
                        message="BOM import found in pom.xml",
                        severity="pass",
                        category=self.name,
                        file_path="pom.xml",
                    )
                )
                return
        else:
            if _GRADLE_PLATFORM_RE.search(content):
                findings.append(
                    Finding(
                        id="JDEP-003",
                        message=f"BOM/platform usage found in {build_file}",
                        severity="pass",
                        category=self.name,
                        file_path=build_file,
                    )
                )
                return

        findings.append(
            Finding(
                id="JDEP-003",
                message="No BOM usage detected",
                severity="warn",
                category=self.name,
                file_path=build_file,
                detail="Use BOMs (Bill of Materials) to manage dependency versions consistently",
            )
        )
        recommendations.append(
            "Import BOMs for dependency version management "
            "(e.g. Spring Boot BOM, JUnit BOM)"
        )
