"""Checker for Python quality gate best practices."""

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


class Checker:
    """Quality Gates checker for Python repos.

    Finding IDs: QUAL-001 through QUAL-005.

    - QUAL-001: Linter configured (ruff in pyproject.toml [tool.ruff] or ruff.toml)
    - QUAL-002: Formatter configured (ruff format, black, or autopep8)
    - QUAL-003: Type checker configured (mypy or pyright)
    - QUAL-004: Pre-commit hooks configured (.pre-commit-config.yaml)
    - QUAL-005: Type checker strict mode enabled

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "quality_gates"
    display_name = "Quality Gates"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        pyproject_data = self._load_pyproject(repo_path)

        self._check_linter(repo_path, pyproject_data, findings, recommendations)
        self._check_formatter(repo_path, pyproject_data, findings, recommendations)
        self._check_type_checker(repo_path, pyproject_data, findings, recommendations)
        self._check_pre_commit(repo_path, findings, recommendations)
        self._check_type_checker_strict(repo_path, pyproject_data, findings, recommendations)

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

    def _check_linter(
        self,
        repo_path: Path,
        pyproject_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        config_location = None

        # pyproject.toml [tool.ruff]
        if pyproject_data and "ruff" in pyproject_data.get("tool", {}):
            config_location = "pyproject.toml"

        # ruff.toml or .ruff.toml
        if not config_location and (repo_path / "ruff.toml").exists():
            config_location = "ruff.toml"
        if not config_location and (repo_path / ".ruff.toml").exists():
            config_location = ".ruff.toml"

        if config_location:
            findings.append(
                Finding(
                    id="QUAL-001",
                    message=f"Linter (ruff) configured in {config_location}",
                    severity="pass",
                    category=self.name,
                    file_path=config_location,
                )
            )
        else:
            findings.append(
                Finding(
                    id="QUAL-001",
                    message="No linter configuration found",
                    severity="fail",
                    category=self.name,
                    detail="Expected ruff config in pyproject.toml [tool.ruff] or ruff.toml",
                )
            )
            recommendations.append("Configure ruff as a linter in pyproject.toml under [tool.ruff]")

    def _check_formatter(
        self,
        repo_path: Path,
        pyproject_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        config_location = None
        formatter_name = None

        # ruff format: [tool.ruff.format] in pyproject.toml
        if pyproject_data:
            ruff_section = pyproject_data.get("tool", {}).get("ruff", {})
            if "format" in ruff_section:
                config_location = "pyproject.toml"
                formatter_name = "ruff format"

        # ruff.toml with [format]
        if not config_location:
            for ruff_file in ("ruff.toml", ".ruff.toml"):
                path = repo_path / ruff_file
                if path.exists():
                    content = path.read_text()
                    if "[format]" in content:
                        config_location = ruff_file
                        formatter_name = "ruff format"
                        break

        # black in pyproject.toml
        if not config_location and pyproject_data:
            if "black" in pyproject_data.get("tool", {}):
                config_location = "pyproject.toml"
                formatter_name = "black"

        # pyproject.toml or standalone black config
        if not config_location:
            for name in ("black.toml", ".black.toml"):
                if (repo_path / name).exists():
                    config_location = name
                    formatter_name = "black"
                    break

        # autopep8
        if not config_location and pyproject_data:
            if "autopep8" in pyproject_data.get("tool", {}):
                config_location = "pyproject.toml"
                formatter_name = "autopep8"

        # If ruff is configured as linter but no explicit [format] section,
        # ruff still acts as a formatter by default since v0.1.2. Count it.
        if not config_location and pyproject_data:
            if "ruff" in pyproject_data.get("tool", {}):
                config_location = "pyproject.toml"
                formatter_name = "ruff (implicit formatter)"
        if not config_location:
            for ruff_file in ("ruff.toml", ".ruff.toml"):
                if (repo_path / ruff_file).exists():
                    config_location = ruff_file
                    formatter_name = "ruff (implicit formatter)"
                    break

        if config_location:
            findings.append(
                Finding(
                    id="QUAL-002",
                    message=f"Formatter ({formatter_name}) configured in {config_location}",
                    severity="pass",
                    category=self.name,
                    file_path=config_location,
                )
            )
        else:
            findings.append(
                Finding(
                    id="QUAL-002",
                    message="No code formatter configured",
                    severity="warn",
                    category=self.name,
                    detail="Expected ruff format, black, or autopep8 configuration",
                )
            )
            recommendations.append("Configure a code formatter (ruff format or black)")

    def _check_type_checker(
        self,
        repo_path: Path,
        pyproject_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        config_location = None
        tool_name = None

        # mypy in pyproject.toml
        if pyproject_data and "mypy" in pyproject_data.get("tool", {}):
            config_location = "pyproject.toml"
            tool_name = "mypy"

        # mypy.ini
        if not config_location and (repo_path / "mypy.ini").exists():
            config_location = "mypy.ini"
            tool_name = "mypy"

        # .mypy.ini
        if not config_location and (repo_path / ".mypy.ini").exists():
            config_location = ".mypy.ini"
            tool_name = "mypy"

        # setup.cfg [mypy]
        if not config_location and (repo_path / "setup.cfg").exists():
            content = (repo_path / "setup.cfg").read_text()
            if "[mypy" in content:
                config_location = "setup.cfg"
                tool_name = "mypy"

        # pyright in pyproject.toml
        if not config_location and pyproject_data:
            if "pyright" in pyproject_data.get("tool", {}):
                config_location = "pyproject.toml"
                tool_name = "pyright"

        # pyrightconfig.json
        if not config_location and (repo_path / "pyrightconfig.json").exists():
            config_location = "pyrightconfig.json"
            tool_name = "pyright"

        if config_location:
            findings.append(
                Finding(
                    id="QUAL-003",
                    message=f"Type checker ({tool_name}) configured in {config_location}",
                    severity="pass",
                    category=self.name,
                    file_path=config_location,
                )
            )
        else:
            findings.append(
                Finding(
                    id="QUAL-003",
                    message="No type checker configured",
                    severity="warn",
                    category=self.name,
                    detail="Expected mypy or pyright configuration",
                )
            )
            recommendations.append("Configure a type checker (mypy or pyright)")

    def _check_pre_commit(
        self,
        repo_path: Path,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        config_file = repo_path / ".pre-commit-config.yaml"

        if config_file.exists():
            findings.append(
                Finding(
                    id="QUAL-004",
                    message="Pre-commit hooks configured",
                    severity="pass",
                    category=self.name,
                    file_path=".pre-commit-config.yaml",
                )
            )
        else:
            findings.append(
                Finding(
                    id="QUAL-004",
                    message="No pre-commit configuration found",
                    severity="warn",
                    category=self.name,
                    detail="Pre-commit hooks help enforce quality gates automatically",
                )
            )
            recommendations.append(
                "Add pre-commit hooks (.pre-commit-config.yaml) to automate linting"
            )

    def _check_type_checker_strict(
        self,
        repo_path: Path,
        pyproject_data: dict | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        # Only check if a type checker was detected (QUAL-003 passed)
        has_type_checker = any(f.id == "QUAL-003" and f.severity == "pass" for f in findings)
        if not has_type_checker:
            return

        is_strict = False

        # mypy strict in pyproject.toml
        if pyproject_data:
            mypy_section = pyproject_data.get("tool", {}).get("mypy", {})
            if mypy_section.get("strict") is True:
                is_strict = True

        # mypy.ini or .mypy.ini
        if not is_strict:
            for ini_file in ("mypy.ini", ".mypy.ini"):
                path = repo_path / ini_file
                if path.exists():
                    content = path.read_text()
                    if "strict = True" in content or "strict = true" in content:
                        is_strict = True
                        break

        # setup.cfg
        if not is_strict and (repo_path / "setup.cfg").exists():
            content = (repo_path / "setup.cfg").read_text()
            if "[mypy" in content and ("strict = True" in content or "strict = true" in content):
                is_strict = True

        # pyright strict
        if not is_strict and pyproject_data:
            pyright_section = pyproject_data.get("tool", {}).get("pyright", {})
            if pyright_section.get("typeCheckingMode") == "strict":
                is_strict = True

        # pyrightconfig.json
        if not is_strict and (repo_path / "pyrightconfig.json").exists():
            content = (repo_path / "pyrightconfig.json").read_text()
            if '"strict"' in content and "typeCheckingMode" in content:
                is_strict = True

        if is_strict:
            findings.append(
                Finding(
                    id="QUAL-005",
                    message="Type checker strict mode enabled",
                    severity="pass",
                    category=self.name,
                )
            )
        else:
            findings.append(
                Finding(
                    id="QUAL-005",
                    message="Type checker strict mode not enabled",
                    severity="warn",
                    category=self.name,
                    detail="Strict mode catches more type errors at the cost of verbosity",
                )
            )
            recommendations.append(
                "Consider enabling strict mode in your type checker configuration"
            )
