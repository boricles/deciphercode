"""Checker for Java project structure best practices."""

from __future__ import annotations

import re
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

# Valid Java package directory pattern: lowercase letters, digits, underscores
_PACKAGE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_BUILD_FILES = ("pom.xml", "build.gradle", "build.gradle.kts")

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


class Checker:
    """Project Structure checker for Java repos.

    Finding IDs: JPROJ-001 through JPROJ-003.

    - JPROJ-001: src/main/java and src/test/java layout (or legacy src/ with .java files)
    - JPROJ-002: pom.xml or build.gradle exists (also checks immediate subdirectories)
    - JPROJ-003: Proper package naming conventions

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "project_structure"
    display_name = "Project Structure"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        self._check_maven_gradle_layout(repo_path, findings, recommendations)
        self._check_build_file(repo_path, findings, recommendations)
        self._check_package_naming(repo_path, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    def _check_maven_gradle_layout(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        main_java = repo_path / "src" / "main" / "java"
        test_java = repo_path / "src" / "test" / "java"

        has_main = main_java.is_dir()
        has_test = test_java.is_dir()

        if has_main and has_test:
            findings.append(
                Finding(
                    id="JPROJ-001",
                    message="Standard Maven/Gradle layout detected (src/main/java + src/test/java)",
                    severity="pass",
                    category=self.name,
                    file_path="src/main/java",
                )
            )
            return

        if has_main:
            findings.append(
                Finding(
                    id="JPROJ-001",
                    message="src/main/java found but src/test/java is missing",
                    severity="warn",
                    category=self.name,
                    file_path="src/main/java",
                )
            )
            recommendations.append("Add src/test/java directory for test sources")
            return

        # Check for legacy src/ layout (NetBeans, Ant-era): src/ with .java files
        # but no src/main/java structure
        src_dir = repo_path / "src"
        if src_dir.is_dir():
            has_java = any(src_dir.rglob("*.java"))
            if has_java:
                findings.append(
                    Finding(
                        id="JPROJ-001",
                        message="Legacy source layout detected (src/ without main/java)",
                        severity="warn",
                        category=self.name,
                        file_path="src",
                        detail="Consider migrating to standard Maven/Gradle layout "
                        "(src/main/java and src/test/java)",
                    )
                )
                recommendations.append(
                    "Migrate to standard Maven/Gradle directory layout "
                    "(src/main/java and src/test/java)"
                )
                return

        findings.append(
            Finding(
                id="JPROJ-001",
                message="No recognized source layout found",
                severity="fail",
                category=self.name,
            )
        )
        recommendations.append(
            "Adopt standard Maven/Gradle directory layout "
            "(src/main/java and src/test/java)"
        )

    def _check_build_file(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        # Check at repo root first
        for name in _BUILD_FILES:
            if (repo_path / name).exists():
                findings.append(
                    Finding(
                        id="JPROJ-002",
                        message=f"Build file found ({name})",
                        severity="pass",
                        category=self.name,
                        file_path=name,
                    )
                )
                return

        # Check immediate subdirectories (common for monorepos / nested projects)
        for child in sorted(repo_path.iterdir()):
            if not child.is_dir() or child.name.startswith(".") or child.name in _IGNORE_DIRS:
                continue
            for name in _BUILD_FILES:
                if (child / name).exists():
                    rel_path = f"{child.name}/{name}"
                    findings.append(
                        Finding(
                            id="JPROJ-002",
                            message=f"Build file found in subdirectory ({rel_path})",
                            severity="warn",
                            category=self.name,
                            file_path=rel_path,
                            detail="Build file should be at the repository root; "
                            "found in a subdirectory instead",
                        )
                    )
                    recommendations.append(
                        f"Move {name} to the repository root, or run the auditor "
                        f"against the {child.name}/ subdirectory"
                    )
                    return

        findings.append(
            Finding(
                id="JPROJ-002",
                message="No build file found (pom.xml, build.gradle, or build.gradle.kts)",
                severity="fail",
                category=self.name,
            )
        )
        recommendations.append("Add a pom.xml (Maven) or build.gradle (Gradle) build file")

    def _check_package_naming(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        # Check standard layout first, then fall back to legacy src/
        main_java = repo_path / "src" / "main" / "java"
        if not main_java.is_dir():
            # Try legacy src/ layout - look for .java files to infer package root
            src_dir = repo_path / "src"
            if src_dir.is_dir() and any(src_dir.rglob("*.java")):
                self._check_package_dirs(src_dir, "src", findings, recommendations)
            return

        self._check_package_dirs(main_java, "src/main/java", findings, recommendations)

    def _check_package_dirs(
        self,
        source_root: Path,
        source_root_display: str,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        bad_dirs: list[str] = []
        for d in source_root.rglob("*"):
            if not d.is_dir():
                continue
            rel = d.relative_to(source_root)
            for part in rel.parts:
                if not _PACKAGE_NAME_RE.match(part):
                    bad_dirs.append(str(rel))
                    break

        if bad_dirs:
            findings.append(
                Finding(
                    id="JPROJ-003",
                    message=f"{len(bad_dirs)} package(s) violate naming conventions",
                    severity="warn",
                    category=self.name,
                    file_path=source_root_display,
                    detail="Java packages should be all lowercase with no hyphens: "
                    + ", ".join(bad_dirs[:5]),
                )
            )
            recommendations.append(
                "Rename packages to follow Java conventions (all lowercase, no hyphens)"
            )
        else:
            # Only emit pass if there are actual packages
            pkg_dirs = [d for d in source_root.rglob("*") if d.is_dir()]
            if pkg_dirs:
                findings.append(
                    Finding(
                        id="JPROJ-003",
                        message="Package naming conventions followed",
                        severity="pass",
                        category=self.name,
                        file_path=source_root_display,
                    )
                )
