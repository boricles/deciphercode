"""Tests for the quality_gates checker."""

from pathlib import Path

from decipher.practices.checkers.python.quality_gates import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


class TestQualityGatesPass:
    """Complete project with all quality tools configured."""

    @staticmethod
    def _build_complete(tmp_path: Path) -> Path:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\n"
            'target-version = "py310"\n'
            "line-length = 100\n\n"
            "[tool.ruff.format]\n"
            'quote-style = "double"\n\n'
            "[tool.mypy]\n"
            "strict = true\n"
        )
        (tmp_path / ".pre-commit-config.yaml").write_text(
            "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        )
        return tmp_path

    def test_all_pass_status(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        assert result.status == "pass"
        assert result.score == 100

    def test_all_findings_pass(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        for f in result.findings:
            assert f.severity == "pass", f"Finding {f.id} has severity {f.severity}"

    def test_no_recommendations(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        assert result.recommendations == []


class TestQualityGatesFail:
    """Empty repo should produce fail for linter, warns for the rest."""

    def test_empty_repo_status(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert result.status == "fail"

    def test_missing_linter_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-001")
        assert f is not None
        assert f.severity == "fail"

    def test_missing_formatter_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-002")
        assert f is not None
        assert f.severity == "warn"

    def test_missing_type_checker_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-003")
        assert f is not None
        assert f.severity == "warn"

    def test_missing_pre_commit_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-004")
        assert f is not None
        assert f.severity == "warn"

    def test_no_strict_finding_when_no_type_checker(self, tmp_path: Path):
        """QUAL-005 should not be emitted if no type checker was found."""
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-005")
        assert f is None

    def test_empty_repo_score(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        # 1 fail (linter) + 3 warns (formatter, type checker, pre-commit)
        # 100 - 25 - 30 = 45
        assert result.score == 45

    def test_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) >= 3


class TestQualityGatesWarn:
    """Linter present but optional tools missing."""

    def test_ruff_only_no_explicit_formatter(self, tmp_path: Path):
        """Ruff configured without explicit [format] still counts as implicit formatter."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        result = Checker().run(tmp_path)
        # Linter: pass. Formatter: pass (ruff implicit).
        # Type checker: warn. Pre-commit: warn.
        assert _finding_by_id(result, "QUAL-001").severity == "pass"
        assert _finding_by_id(result, "QUAL-002").severity == "pass"
        assert _finding_by_id(result, "QUAL-003").severity == "warn"
        assert _finding_by_id(result, "QUAL-004").severity == "warn"

    def test_type_checker_not_strict_warns(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\nline-length = 100\n\n[tool.mypy]\nignore_missing_imports = true\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-005")
        assert f is not None
        assert f.severity == "warn"


class TestQualityGatesMixed:
    """Projects with a mix of pass and warn findings."""

    def test_ruff_and_mypy_no_precommit(self, tmp_path: Path):
        """Ruff + mypy strict = 4 pass (linter, formatter, type checker, strict).
        No pre-commit = 1 warn."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\nline-length = 100\n\n[tool.mypy]\nstrict = true\n"
        )
        result = Checker().run(tmp_path)
        pass_count = sum(1 for f in result.findings if f.severity == "pass")
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert pass_count == 4
        assert warn_count == 1
        assert result.score == 90
        assert result.status == "warn"

    def test_only_precommit_and_ruff_toml(self, tmp_path: Path):
        """ruff.toml + pre-commit = linter pass, formatter pass (implicit),
        pre-commit pass. Type checker warn, no strict check."""
        (tmp_path / "ruff.toml").write_text("line-length = 100\n")
        (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "QUAL-001").severity == "pass"
        assert _finding_by_id(result, "QUAL-002").severity == "pass"
        assert _finding_by_id(result, "QUAL-003").severity == "warn"
        assert _finding_by_id(result, "QUAL-004").severity == "pass"
        assert _finding_by_id(result, "QUAL-005") is None  # no type checker → no strict check


class TestQualityGatesFilePath:
    """Validate that file_path is populated on findings."""

    def test_ruff_in_pyproject_has_file_path(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-001")
        assert f is not None
        assert f.file_path == "pyproject.toml"

    def test_ruff_toml_has_file_path(self, tmp_path: Path):
        (tmp_path / "ruff.toml").write_text("line-length = 100\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-001")
        assert f is not None
        assert f.file_path == "ruff.toml"

    def test_dot_ruff_toml_has_file_path(self, tmp_path: Path):
        (tmp_path / ".ruff.toml").write_text("line-length = 100\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-001")
        assert f is not None
        assert f.file_path == ".ruff.toml"

    def test_mypy_in_pyproject_has_file_path(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\nx = 1\n\n[tool.mypy]\nstrict = true\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-003")
        assert f is not None
        assert f.file_path == "pyproject.toml"

    def test_mypy_ini_has_file_path(self, tmp_path: Path):
        (tmp_path / "mypy.ini").write_text("[mypy]\nstrict = True\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-003")
        assert f is not None
        assert f.file_path == "mypy.ini"

    def test_pre_commit_has_file_path(self, tmp_path: Path):
        (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-004")
        assert f is not None
        assert f.file_path == ".pre-commit-config.yaml"

    def test_missing_linter_has_no_file_path(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-001")
        assert f is not None
        assert f.file_path is None


class TestQualityGatesEdgeCases:
    def test_black_in_pyproject(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\nline-length = 100\n\n[tool.black]\nline-length = 100\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-002")
        assert f.severity == "pass"
        assert "black" in f.message.lower()

    def test_black_toml_standalone(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        (tmp_path / "black.toml").write_text("line-length = 100\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-002")
        assert f.severity == "pass"
        assert f.file_path == "black.toml"

    def test_ruff_format_section_in_ruff_toml(self, tmp_path: Path):
        (tmp_path / "ruff.toml").write_text(
            'line-length = 100\n\n[format]\nquote-style = "double"\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-002")
        assert f.severity == "pass"
        assert "ruff format" in f.message.lower()
        assert f.file_path == "ruff.toml"

    def test_pyright_in_pyproject(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\nline-length = 100\n\n[tool.pyright]\ntypeCheckingMode = 'basic'\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-003")
        assert f.severity == "pass"
        assert "pyright" in f.message.lower()

    def test_pyrightconfig_json(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        (tmp_path / "pyrightconfig.json").write_text('{"typeCheckingMode": "basic"}\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-003")
        assert f.severity == "pass"
        assert f.file_path == "pyrightconfig.json"

    def test_pyright_strict_mode(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.ruff]\nline-length = 100\n\n[tool.pyright]\ntypeCheckingMode = "strict"\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-005")
        assert f is not None
        assert f.severity == "pass"

    def test_mypy_in_setup_cfg(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        (tmp_path / "setup.cfg").write_text(
            "[mypy]\nstrict = True\nignore_missing_imports = True\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-003")
        assert f.severity == "pass"
        assert f.file_path == "setup.cfg"

    def test_dot_mypy_ini(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        (tmp_path / ".mypy.ini").write_text("[mypy]\nstrict = True\n")
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "QUAL-003").severity == "pass"
        assert _finding_by_id(result, "QUAL-003").file_path == ".mypy.ini"
        assert _finding_by_id(result, "QUAL-005").severity == "pass"

    def test_autopep8_in_pyproject(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[tool.ruff]\nline-length = 100\n\n[tool.autopep8]\nmax_line_length = 100\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "QUAL-002")
        assert f.severity == "pass"
        assert "autopep8" in f.message.lower()
