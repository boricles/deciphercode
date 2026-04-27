"""Tests for decipher.cli."""

from click.testing import CliRunner

from decipher.cli import main


class TestCLI:
    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "decipher" in result.output
        assert "0.2.0" in result.output

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "legacy code" in result.output.lower() or "DecipherCode" in result.output

    def test_scan_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["scan", "--help"])
        assert result.exit_code == 0
        assert "TARGET" in result.output

    def test_readme_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["readme", "--help"])
        assert result.exit_code == 0

    def test_diagram_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["diagram", "--help"])
        assert result.exit_code == 0
        assert "mermaid" in result.output.lower() or "format" in result.output.lower()

    def test_history_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["history", "--help"])
        assert result.exit_code == 0

    def test_ask_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["ask", "--help"])
        assert result.exit_code == 0

    def test_scan_nonexistent_dir(self):
        runner = CliRunner()
        result = runner.invoke(main, ["scan", "/nonexistent/path/12345"])
        assert result.exit_code != 0
