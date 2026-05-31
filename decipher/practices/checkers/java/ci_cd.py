"""Checker for Java CI/CD best practices."""

from __future__ import annotations

from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status


class Checker:
    """CI/CD checker for Java repos.

    Finding IDs: JCICD-001 through JCICD-002.

    - JCICD-001: GitHub Actions, Jenkinsfile, or GitLab CI present
    - JCICD-002: Maven/Gradle wrapper committed

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "ci_cd"
    display_name = "CI/CD"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        self._check_ci_config(repo_path, findings, recommendations)
        self._check_build_wrapper(repo_path, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    def _check_ci_config(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        # GitHub Actions
        wf_dir = repo_path / ".github" / "workflows"
        if wf_dir.is_dir():
            wf_files = [
                p for p in wf_dir.iterdir()
                if p.suffix in (".yml", ".yaml") and p.is_file()
            ]
            if wf_files:
                findings.append(
                    Finding(
                        id="JCICD-001",
                        message=f"{len(wf_files)} GitHub Actions workflow(s) found",
                        severity="pass",
                        category=self.name,
                        file_path=".github/workflows",
                    )
                )
                return

        # Jenkinsfile
        jenkinsfile = repo_path / "Jenkinsfile"
        if jenkinsfile.exists():
            findings.append(
                Finding(
                    id="JCICD-001",
                    message="Jenkinsfile found",
                    severity="pass",
                    category=self.name,
                    file_path="Jenkinsfile",
                )
            )
            return

        # GitLab CI
        gitlab_ci = repo_path / ".gitlab-ci.yml"
        if gitlab_ci.exists():
            findings.append(
                Finding(
                    id="JCICD-001",
                    message="GitLab CI configuration found",
                    severity="pass",
                    category=self.name,
                    file_path=".gitlab-ci.yml",
                )
            )
            return

        findings.append(
            Finding(
                id="JCICD-001",
                message="No CI/CD configuration found",
                severity="fail",
                category=self.name,
                detail="Expected GitHub Actions, Jenkinsfile, or .gitlab-ci.yml",
            )
        )
        recommendations.append(
            "Add CI/CD configuration (GitHub Actions, Jenkinsfile, or .gitlab-ci.yml)"
        )

    def _check_build_wrapper(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        mvnw = repo_path / "mvnw"
        gradlew = repo_path / "gradlew"

        if mvnw.exists():
            findings.append(
                Finding(
                    id="JCICD-002",
                    message="Maven wrapper committed (mvnw)",
                    severity="pass",
                    category=self.name,
                    file_path="mvnw",
                )
            )
        elif gradlew.exists():
            findings.append(
                Finding(
                    id="JCICD-002",
                    message="Gradle wrapper committed (gradlew)",
                    severity="pass",
                    category=self.name,
                    file_path="gradlew",
                )
            )
        else:
            findings.append(
                Finding(
                    id="JCICD-002",
                    message="No build wrapper committed",
                    severity="warn",
                    category=self.name,
                    detail="Commit mvnw (Maven) or gradlew (Gradle) for reproducible builds",
                )
            )
            recommendations.append(
                "Commit a build wrapper (mvnw or gradlew) for reproducible builds"
            )
