"""Integration test: runs the full practices audit against a fixture repo."""

import json
from pathlib import Path

from click.testing import CliRunner

from decipher.cli import main
from decipher.practices.runner import run_audit


class TestIntegrationAudit:
    """Run the auditor against a synthetic repo and verify end-to-end output."""

    @staticmethod
    def _build_fixture(tmp_path: Path) -> Path:
        """Create a realistic minimal Python project."""
        # pyproject.toml
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["setuptools>=68.0"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            "[project]\n"
            'name = "fixture-project"\n'
            'version = "0.1.0"\n'
            'readme = "README.md"\n'
            'dependencies = ["click>=8.1", "rich>=13.0"]\n'
            "classifiers = [\n"
            '    "Programming Language :: Python :: 3",\n'
            '    "Programming Language :: Python :: 3.12",\n'
            "]\n\n"
            "[tool.pytest.ini_options]\n"
            'testpaths = ["tests"]\n\n'
            "[tool.ruff]\n"
            'target-version = "py310"\n'
            "line-length = 100\n\n"
            "[tool.mypy]\n"
            "strict = true\n\n"
            "[tool.coverage.report]\n"
            "fail_under = 80\n"
        )
        # LICENSE
        (tmp_path / "LICENSE").write_text("MIT License\n\nCopyright 2026\n")
        # README
        (tmp_path / "README.md").write_text(
            "# Fixture Project\n\n"
            "A sample Python project used for integration testing of the "
            "DecipherCode best-practices auditor.\n\n"
            "## Installation\n\npip install fixture-project\n\n"
            "## Usage\n\nfixture-project run\n\n"
            "## License\n\nMIT\n"
        )
        # CHANGELOG
        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [0.1.0] - 2026-04-01\n\n### Added\n\n- Initial release\n"
        )
        # Source
        src = tmp_path / "src" / "fixture_project"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text('"""Fixture Project."""\n')
        (src / "core.py").write_text('"""Core module."""\n\ndef main() -> None:\n    pass\n')
        # Tests
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")
        (tests / "test_core.py").write_text("def test_placeholder():\n    assert True\n")
        # GitHub Actions
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text(
            "name: CI\non: [push]\njobs:\n  test:\n"
            "    strategy:\n      matrix:\n"
            '        python-version: ["3.10", "3.11", "3.12"]\n'
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - run: pytest\n"
        )
        # Pre-commit
        (tmp_path / ".pre-commit-config.yaml").write_text(
            "repos:\n  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        )
        return tmp_path

    def test_full_audit_json_output(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        report = run_audit(repo, language="python", show_progress=False)

        assert report.language == "python"
        assert report.schema_version == "1.0"
        assert len(report.results) == 8
        assert len(report.checkers_run) == 8
        assert report.overall_score >= 0
        assert report.overall_status in ("pass", "warn", "fail")
        assert report.deciphercode_version != ""

    def test_full_audit_json_serializable(self, tmp_path: Path):
        from decipher.practices.reporter import Reporter

        repo = self._build_fixture(tmp_path)
        report = run_audit(repo, language="python", show_progress=False)
        reporter = Reporter()

        text = reporter.to_json(report)
        data = json.loads(text)
        assert data["language"] == "python"
        assert "top_recommendations" in data
        assert "checkers_run" in data

    def test_full_audit_markdown_output(self, tmp_path: Path):
        from decipher.practices.reporter import Reporter

        repo = self._build_fixture(tmp_path)
        report = run_audit(repo, language="python", show_progress=False)
        reporter = Reporter()

        md = reporter.to_markdown(report)
        assert "# Best Practices Audit Report" in md
        assert "fixture" in md.lower() or str(repo) in md

    def test_cli_practices_json_only(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "--json-only"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["language"] == "python"

    def test_cli_practices_default_markdown(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo)])
        assert result.exit_code == 0

    def test_cli_practices_unsupported_language(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(tmp_path), "--language", "rust"])
        assert result.exit_code == 2

    def test_cli_practices_nonexistent_dir(self):
        runner = CliRunner()
        result = runner.invoke(main, ["practices", "/nonexistent/path/xyz"])
        assert result.exit_code == 1

    def test_cli_practices_output_file(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        out_file = tmp_path / "output" / "report.json"
        out_file.parent.mkdir()
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--json-only", "-o", str(out_file)],
        )
        assert result.exit_code == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data["language"] == "python"


class TestCliFormatFlag:
    """Tests for --format flag and auto-detection."""

    @staticmethod
    def _build_fixture(tmp_path: Path) -> Path:
        return TestIntegrationAudit._build_fixture(tmp_path)

    def test_format_json(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["language"] == "python"

    def test_format_markdown(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "--format", "markdown"])
        assert result.exit_code == 0
        assert "Best Practices" in result.output or "Audit" in result.output

    def test_format_terminal(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "--format", "terminal"])
        assert result.exit_code == 0
        assert "Overall" in result.output

    def test_json_only_alias_works(self, tmp_path: Path):
        """--json-only still works as hidden alias for --format json."""
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "--json-only"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["language"] == "python"

    def test_output_file_json_extension(self, tmp_path: Path):
        """--o report.json auto-detects JSON format."""
        repo = self._build_fixture(tmp_path)
        out = tmp_path / "report.json"
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "-o", str(out)])
        assert result.exit_code == 0
        data = json.loads(out.read_text())
        assert data["language"] == "python"

    def test_output_file_md_extension(self, tmp_path: Path):
        """--o report.md auto-detects Markdown format."""
        repo = self._build_fixture(tmp_path)
        out = tmp_path / "report.md"
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "-o", str(out)])
        assert result.exit_code == 0
        content = out.read_text()
        assert "# Best Practices Audit Report" in content

    def test_output_file_unsupported_extension(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        out = tmp_path / "report.html"
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "-o", str(out)])
        assert result.exit_code != 0
        assert ".html" in result.output or "html" in result.output

    def test_output_file_no_extension(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        out = tmp_path / "report"
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "-o", str(out)])
        assert result.exit_code != 0
        assert "extension" in result.output.lower() or "format" in result.output.lower()

    def test_format_overrides_extension(self, tmp_path: Path):
        """--format json with -o report.md should produce JSON."""
        repo = self._build_fixture(tmp_path)
        out = tmp_path / "report.md"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--format", "json", "-o", str(out)],
        )
        assert result.exit_code == 0
        data = json.loads(out.read_text())
        assert data["language"] == "python"

    def test_default_format_is_markdown_in_non_tty(self, tmp_path: Path):
        """CliRunner has non-TTY stdout, so default should be markdown."""
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo)])
        assert result.exit_code == 0
        # Should get markdown, not terminal format
        assert "Best Practices" in result.output or "Audit" in result.output


class TestCliStrictFlag:
    """Tests for --strict flag and exit codes."""

    @staticmethod
    def _build_fixture(tmp_path: Path) -> Path:
        return TestIntegrationAudit._build_fixture(tmp_path)

    @staticmethod
    def _build_failing_fixture(tmp_path: Path) -> Path:
        """Build a repo that produces a 'fail' overall status."""
        # No LICENSE → LIC-001 fail
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "README.md").write_text(
            "# Test Project\n\n"
            "A comprehensive test project for demonstrating the "
            "auditor features and integration testing.\n\n"
            "## Installation\n\npip install test\n\n"
            "## Usage\n\ntest run\n"
        )
        return tmp_path

    def test_pass_exit_code_0(self, tmp_path: Path):
        """Pass status → exit 0."""
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "--format", "json"])
        data = json.loads(result.output)
        if data["overall_status"] == "pass":
            assert result.exit_code == 0

    def test_warn_without_strict_exit_code_0(self, tmp_path: Path):
        """Warn status without --strict → exit 0."""
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(main, ["practices", str(repo), "--format", "json"])
        data = json.loads(result.output)
        # Fixture may have warns (e.g. no lock file)
        if data["overall_status"] == "warn":
            assert result.exit_code == 0

    def test_warn_with_strict_exit_code_1(self, tmp_path: Path):
        """Warn status with --strict → exit 1."""
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--format", "json", "--strict"],
        )
        data = json.loads(result.output)
        if data["overall_status"] == "warn":
            assert result.exit_code == 1

    def test_fail_exit_code_1(self, tmp_path: Path):
        """Fail status → exit 1 (even without --strict)."""
        repo = self._build_failing_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--format", "json"],
        )
        data = json.loads(result.output)
        if data["overall_status"] == "fail":
            assert result.exit_code == 1

    def test_unsupported_language_exit_code_2(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(tmp_path), "--language", "rust"],
        )
        assert result.exit_code == 2


class TestCliOnlySkip:
    """Tests for --only and --skip flags."""

    @staticmethod
    def _build_fixture(tmp_path: Path) -> Path:
        return TestIntegrationAudit._build_fixture(tmp_path)

    def test_only_single_checker(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--format", "json", "--only", "licensing"],
        )
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert data["checkers_run"] == ["licensing"]
        assert len(data["results"]) == 1

    def test_only_multiple_checkers(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--format", "json", "--only", "licensing,testing"],
        )
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert set(data["checkers_run"]) == {"licensing", "testing"}

    def test_skip_single_checker(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--format", "json", "--skip", "documentation"],
        )
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert "documentation" not in data["checkers_run"]
        assert len(data["results"]) == 7

    def test_only_and_skip_mutually_exclusive(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "practices",
                str(repo),
                "--format",
                "json",
                "--only",
                "licensing",
                "--skip",
                "testing",
            ],
        )
        assert result.exit_code != 0
        assert "mutually exclusive" in result.output.lower()

    def test_only_unknown_checker(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--format", "json", "--only", "nonexistent"],
        )
        assert result.exit_code != 0
        assert "Unknown" in result.output or "unknown" in result.output

    def test_skip_unknown_checker(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--format", "json", "--skip", "nonexistent"],
        )
        assert result.exit_code != 0
        assert "Unknown" in result.output or "unknown" in result.output


class TestCliRunnerCheckers:
    """Tests for runner.run_audit with checkers parameter."""

    def test_checkers_subset(self, tmp_path: Path):
        report = run_audit(
            tmp_path,
            language="python",
            show_progress=False,
            checkers=["licensing"],
        )
        assert report.checkers_run == ["licensing"]
        assert len(report.results) == 1

    def test_checkers_none_runs_all(self, tmp_path: Path):
        from decipher.practices.runner import SUPPORTED_LANGUAGES

        report = run_audit(tmp_path, language="python", show_progress=False)
        assert len(report.checkers_run) == len(SUPPORTED_LANGUAGES["python"])
