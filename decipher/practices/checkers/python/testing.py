"""Checker for Python testing best practices."""

from __future__ import annotations

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

_IGNORE_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".tox",
        ".nox",
        ".eggs",
        "build",
        "dist",
        ".mypy_cache",
        ".ruff_cache",
    }
)


class Checker:
    """Testing checker for Python repos.

    Finding IDs: TEST-001 through TEST-005.

    - TEST-001: tests/ (or test/) directory present
    - TEST-002: Test files found (count of test_*.py and *_test.py)
    - TEST-003: pytest configured (pyproject.toml, pytest.ini, or setup.cfg)
    - TEST-004: Coverage measurement configured (pytest-cov, coverage.py, .coveragerc)
    - TEST-005: Coverage threshold set (fail_under or --cov-fail-under)

    conftest.py is NOT checked: it is entirely optional and its absence
    does not indicate a testing problem.

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "testing"
    display_name = "Testing"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        pyproject_data = self._load_pyproject(repo_path)

        self._check_tests_dir(repo_path, findings, recommendations)
        self._check_test_files(repo_path, findings, recommendations)
        self._check_pytest_config(repo_path, pyproject_data, findings, recommendations)
        self._check_coverage_config(repo_path, pyproject_data, findings, recommendations)
        self._check_coverage_threshold(repo_path, pyproject_data, findings, recommendations)

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    @staticmethod
    def _load_pyproject(repo_path: Path) -> dict | None:
        pyproject = repo_path / "pyproject.toml"
        if not pyproject.exists() or tomllib is None:
            return None
        try:
            return tomllib.loads(pyproject.read_text())
        except Exception:
            return None

    @staticmethod
    def _find_test_files(repo_path: Path) -> list[Path]:
        test_files = []
        for p in repo_path.rglob("*.py"):
            parts = p.relative_to(repo_path).parts
            if any(part in _IGNORE_DIRS or part.endswith(".egg-info") for part in parts):
                continue
            if p.name.startswith("test_") or p.name.endswith("_test.py"):
                test_files.append(p)
        return sorted(test_files)

    def _check_tests_dir(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        tests_dir = repo_path / "tests"
        test_dir = repo_path / "test"

        if tests_dir.is_dir():
            findings.append(
                Finding(
                    id="TEST-001",
                    message="tests/ directory found",
                    severity="pass",
                    category=self.name,
                    file_path="tests",
                )
            )
        elif test_dir.is_dir():
            findings.append(
                Finding(
                    id="TEST-001",
                    message="test/ directory found",
                    severity="pass",
                    category=self.name,
                    file_path="test",
                )
            )
        else:
            findings.append(
                Finding(
                    id="TEST-001",
                    message="No tests/ directory found",
                    severity="fail",
                    category=self.name,
                )
            )
            recommendations.append("Create a tests/ directory for your test suite")

    def _check_test_files(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        test_files = self._find_test_files(repo_path)
        count = len(test_files)

        if count > 0:
            findings.append(
                Finding(
                    id="TEST-002",
                    message=f"{count} test file(s) found",
                    severity="pass",
                    category=self.name,
                )
            )
        else:
            findings.append(
                Finding(
                    id="TEST-002",
                    message="No test files found",
                    severity="fail",
                    category=self.name,
                    detail="Expected files matching test_*.py or *_test.py",
                )
            )
            recommendations.append("Add test files (test_*.py or *_test.py)")

    def _check_pytest_config(
        self,
        repo_path: Path,
        pyproject_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        config_location = None

        # pyproject.toml [tool.pytest.ini_options]
        if pyproject_data and "pytest" in pyproject_data.get("tool", {}):
            config_location = "pyproject.toml"

        # pytest.ini
        if not config_location and (repo_path / "pytest.ini").exists():
            config_location = "pytest.ini"

        # setup.cfg [tool:pytest]
        if not config_location and (repo_path / "setup.cfg").exists():
            content = (repo_path / "setup.cfg").read_text()
            if "[tool:pytest]" in content:
                config_location = "setup.cfg"

        if config_location:
            findings.append(
                Finding(
                    id="TEST-003",
                    message=f"pytest configured in {config_location}",
                    severity="pass",
                    category=self.name,
                    file_path=config_location,
                )
            )
        else:
            findings.append(
                Finding(
                    id="TEST-003",
                    message="No pytest configuration found",
                    severity="warn",
                    category=self.name,
                    detail="Expected [tool.pytest.ini_options] in pyproject.toml, "
                    "pytest.ini, or [tool:pytest] in setup.cfg",
                )
            )
            recommendations.append(
                "Configure pytest in pyproject.toml under [tool.pytest.ini_options]"
            )

    def _check_coverage_config(
        self,
        repo_path: Path,
        pyproject_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        config_location = None

        # pyproject.toml [tool.coverage]
        if pyproject_data and "coverage" in pyproject_data.get("tool", {}):
            config_location = "pyproject.toml"

        # pytest addopts --cov
        if not config_location and pyproject_data:
            addopts = (
                pyproject_data.get("tool", {})
                .get("pytest", {})
                .get("ini_options", {})
                .get("addopts", "")
            )
            if "--cov" in addopts:
                config_location = "pyproject.toml"

        # .coveragerc
        if not config_location and (repo_path / ".coveragerc").exists():
            config_location = ".coveragerc"

        # setup.cfg [coverage:run]
        if not config_location and (repo_path / "setup.cfg").exists():
            content = (repo_path / "setup.cfg").read_text()
            if "[coverage:" in content:
                config_location = "setup.cfg"

        if config_location:
            findings.append(
                Finding(
                    id="TEST-004",
                    message=f"Coverage measurement configured in {config_location}",
                    severity="pass",
                    category=self.name,
                    file_path=config_location,
                )
            )
        else:
            findings.append(
                Finding(
                    id="TEST-004",
                    message="No coverage configuration found",
                    severity="warn",
                    category=self.name,
                    detail="Neither pytest-cov nor coverage.py configuration detected",
                )
            )
            recommendations.append("Add coverage measurement with pytest-cov or coverage.py")

    def _check_coverage_threshold(
        self,
        repo_path: Path,
        pyproject_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        has_threshold = False

        # pyproject.toml [tool.coverage.report] fail_under
        if pyproject_data:
            fail_under = (
                pyproject_data.get("tool", {})
                .get("coverage", {})
                .get("report", {})
                .get("fail_under")
            )
            if fail_under is not None:
                has_threshold = True

        # pytest addopts --cov-fail-under
        if not has_threshold and pyproject_data:
            addopts = (
                pyproject_data.get("tool", {})
                .get("pytest", {})
                .get("ini_options", {})
                .get("addopts", "")
            )
            if "--cov-fail-under" in addopts:
                has_threshold = True

        # .coveragerc
        if not has_threshold and (repo_path / ".coveragerc").exists():
            content = (repo_path / ".coveragerc").read_text()
            if "fail_under" in content:
                has_threshold = True

        # setup.cfg [coverage:report]
        if not has_threshold and (repo_path / "setup.cfg").exists():
            content = (repo_path / "setup.cfg").read_text()
            if "fail_under" in content and "[coverage:" in content:
                has_threshold = True

        if has_threshold:
            findings.append(
                Finding(
                    id="TEST-005",
                    message="Coverage threshold configured",
                    severity="pass",
                    category=self.name,
                )
            )
        else:
            findings.append(
                Finding(
                    id="TEST-005",
                    message="No coverage threshold set",
                    severity="warn",
                    category=self.name,
                    detail="Set fail_under in coverage config to enforce minimum coverage",
                )
            )
            recommendations.append(
                "Set a coverage threshold (e.g. fail_under = 80) in coverage config"
            )
