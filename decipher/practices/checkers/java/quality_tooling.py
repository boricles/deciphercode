"""Checker for Java quality tooling best practices."""

from __future__ import annotations

from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status


class Checker:
    """Quality Tooling checker for Java repos.

    Finding IDs: JQUAL-001 through JQUAL-003.

    - JQUAL-001: Checkstyle, SpotBugs, or PMD config present
    - JQUAL-002: SonarQube properties file
    - JQUAL-003: EditorConfig present

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "quality_tooling"
    display_name = "Quality Tooling"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        self._check_static_analysis(repo_path, findings, recommendations)
        self._check_sonarqube(repo_path, findings, recommendations)
        self._check_editorconfig(repo_path, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    def _check_static_analysis(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        tools_found: list[tuple[str, str]] = []

        # Checkstyle config files
        checkstyle_files = [
            "checkstyle.xml",
            "config/checkstyle/checkstyle.xml",
        ]
        for f in checkstyle_files:
            if (repo_path / f).exists():
                tools_found.append(("Checkstyle", f))
                break

        # SpotBugs / FindBugs
        spotbugs_files = [
            "spotbugs-exclude.xml",
            "spotbugs-include.xml",
            "findbugs-exclude.xml",
            "config/spotbugs/exclude.xml",
        ]
        for f in spotbugs_files:
            if (repo_path / f).exists():
                tools_found.append(("SpotBugs", f))
                break

        # PMD
        pmd_files = [
            "pmd-ruleset.xml",
            "config/pmd/ruleset.xml",
            ".pmd",
        ]
        for f in pmd_files:
            if (repo_path / f).exists():
                tools_found.append(("PMD", f))
                break

        # Also check build file for plugin declarations
        if not tools_found:
            tools_found = self._check_build_plugins(repo_path)

        if tools_found:
            names = ", ".join(t[0] for t in tools_found)
            first_file = tools_found[0][1]
            findings.append(
                Finding(
                    id="JQUAL-001",
                    message=f"Static analysis tool(s) configured: {names}",
                    severity="pass",
                    category=self.name,
                    file_path=first_file,
                )
            )
        else:
            findings.append(
                Finding(
                    id="JQUAL-001",
                    message="No static analysis tools configured",
                    severity="warn",
                    category=self.name,
                    detail="Expected Checkstyle, SpotBugs, or PMD configuration",
                )
            )
            recommendations.append(
                "Configure a static analysis tool (Checkstyle, SpotBugs, or PMD)"
            )

    @staticmethod
    def _check_build_plugins(repo_path: Path) -> list[tuple[str, str]]:
        """Check pom.xml or build.gradle for analysis plugin declarations."""
        tools: list[tuple[str, str]] = []

        pom = repo_path / "pom.xml"
        if pom.exists():
            try:
                content = pom.read_text()
            except OSError:
                content = ""
            if "maven-checkstyle-plugin" in content:
                tools.append(("Checkstyle", "pom.xml"))
            if "spotbugs-maven-plugin" in content or "findbugs-maven-plugin" in content:
                tools.append(("SpotBugs", "pom.xml"))
            if "maven-pmd-plugin" in content:
                tools.append(("PMD", "pom.xml"))

        for gradle_file in ("build.gradle", "build.gradle.kts"):
            path = repo_path / gradle_file
            if path.exists():
                try:
                    content = path.read_text()
                except OSError:
                    content = ""
                if "checkstyle" in content.lower():
                    tools.append(("Checkstyle", gradle_file))
                if "spotbugs" in content.lower() or "findbugs" in content.lower():
                    tools.append(("SpotBugs", gradle_file))
                if "'pmd'" in content or '"pmd"' in content:
                    tools.append(("PMD", gradle_file))
                break

        return tools

    def _check_sonarqube(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        sonar_file = repo_path / "sonar-project.properties"

        if sonar_file.exists():
            findings.append(
                Finding(
                    id="JQUAL-002",
                    message="SonarQube configuration found",
                    severity="pass",
                    category=self.name,
                    file_path="sonar-project.properties",
                )
            )
        else:
            # Also check pom.xml for sonar properties
            pom = repo_path / "pom.xml"
            if pom.exists():
                try:
                    content = pom.read_text()
                except OSError:
                    content = ""
                if "sonar" in content.lower():
                    findings.append(
                        Finding(
                            id="JQUAL-002",
                            message="SonarQube configuration found in pom.xml",
                            severity="pass",
                            category=self.name,
                            file_path="pom.xml",
                        )
                    )
                    return

            findings.append(
                Finding(
                    id="JQUAL-002",
                    message="No SonarQube configuration found",
                    severity="warn",
                    category=self.name,
                    detail="Expected sonar-project.properties or Sonar config in pom.xml",
                )
            )
            recommendations.append(
                "Add SonarQube configuration (sonar-project.properties)"
            )

    def _check_editorconfig(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        editorconfig = repo_path / ".editorconfig"

        if editorconfig.exists():
            findings.append(
                Finding(
                    id="JQUAL-003",
                    message="EditorConfig found",
                    severity="pass",
                    category=self.name,
                    file_path=".editorconfig",
                )
            )
        else:
            findings.append(
                Finding(
                    id="JQUAL-003",
                    message="No .editorconfig found",
                    severity="warn",
                    category=self.name,
                    detail="EditorConfig helps maintain consistent coding styles across editors",
                )
            )
            recommendations.append(
                "Add an .editorconfig for consistent code style across editors"
            )
