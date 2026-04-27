"""Tests for decipher.practices.reporter."""

import json
from io import StringIO

from rich.console import Console

from decipher.practices.models import AuditReport, CheckerResult, Finding
from decipher.practices.reporter import Reporter


def _render_terminal(report: AuditReport) -> str:
    """Render to_terminal() output to a plain string for testing."""
    reporter = Reporter()
    renderable = reporter.to_terminal(report)
    buf = StringIO()
    test_console = Console(file=buf, no_color=True, width=120)
    test_console.print(renderable)
    return buf.getvalue()


def _sample_report() -> AuditReport:
    """Build a minimal report for testing."""
    findings = [
        Finding(
            id="PROJ-001",
            message="pyproject.toml found",
            severity="pass",
            category="project_structure",
        ),
        Finding(
            id="PROJ-002",
            message="No CHANGELOG.md",
            severity="warn",
            category="project_structure",
            file_path="CHANGELOG.md",
        ),
    ]
    result = CheckerResult(
        name="project_structure",
        display_name="Project Structure",
        status="warn",
        score=90,
        findings=findings,
        recommendations=["Add a CHANGELOG.md"],
    )
    return AuditReport(
        language="python",
        repo_path="/tmp/test-repo",
        timestamp="2026-04-26T14:30:00+00:00",
        overall_score=90,
        overall_status="warn",
        deciphercode_version="0.2.0",
        results=[result],
        checkers_run=["project_structure"],
        top_recommendations=["Add a CHANGELOG.md"],
        summary="Overall score 90/100. The repository has warnings in Project Structure.",
    )


class TestReporterJson:
    def test_valid_json(self):
        report = _sample_report()
        reporter = Reporter()
        text = reporter.to_json(report)
        data = json.loads(text)
        assert data["language"] == "python"
        assert data["schema_version"] == "1.0"

    def test_json_contains_top_recommendations(self):
        report = _sample_report()
        reporter = Reporter()
        data = json.loads(reporter.to_json(report))
        assert "top_recommendations" in data
        assert len(data["top_recommendations"]) > 0

    def test_json_contains_checkers_run(self):
        report = _sample_report()
        reporter = Reporter()
        data = json.loads(reporter.to_json(report))
        assert data["checkers_run"] == ["project_structure"]

    def test_json_findings_have_file_path(self):
        report = _sample_report()
        reporter = Reporter()
        data = json.loads(reporter.to_json(report))
        finding = data["results"][0]["findings"][1]
        assert finding["file_path"] == "CHANGELOG.md"


class TestReporterMarkdown:
    def test_contains_header(self):
        report = _sample_report()
        reporter = Reporter()
        md = reporter.to_markdown(report)
        assert "# Best Practices Audit Report" in md

    def test_contains_overall_score(self):
        report = _sample_report()
        reporter = Reporter()
        md = reporter.to_markdown(report)
        assert "90 / 100" in md

    def test_contains_checker_section(self):
        report = _sample_report()
        reporter = Reporter()
        md = reporter.to_markdown(report)
        assert "## Project Structure" in md

    def test_contains_priority_actions(self):
        report = _sample_report()
        reporter = Reporter()
        md = reporter.to_markdown(report)
        assert "## Priority Actions" in md
        assert "Add a CHANGELOG.md" in md

    def test_contains_language(self):
        report = _sample_report()
        reporter = Reporter()
        md = reporter.to_markdown(report)
        assert "**Language:** Python" in md

    def test_finding_with_file_and_line(self):
        finding = Finding(
            id="DOC-001",
            message="missing docstring",
            severity="warn",
            category="documentation",
            file_path="src/main.py",
            line=10,
        )
        result = CheckerResult(
            name="documentation",
            display_name="Documentation",
            status="warn",
            score=90,
            findings=[finding],
        )
        report = AuditReport(
            language="python",
            repo_path="/tmp/repo",
            timestamp="2026-04-26T00:00:00+00:00",
            overall_score=90,
            overall_status="warn",
            deciphercode_version="0.2.0",
            results=[result],
            checkers_run=["documentation"],
        )
        reporter = Reporter()
        md = reporter.to_markdown(report)
        assert "src/main.py:10" in md


class TestReporterTerminal:
    def test_returns_group(self):
        from rich.console import Group

        report = _sample_report()
        reporter = Reporter()
        result = reporter.to_terminal(report)
        assert isinstance(result, Group)

    def test_contains_repo_path(self):
        report = _sample_report()
        output = _render_terminal(report)
        assert "/tmp/test-repo" in output

    def test_contains_language(self):
        report = _sample_report()
        output = _render_terminal(report)
        assert "Python" in output

    def test_contains_overall_score(self):
        report = _sample_report()
        output = _render_terminal(report)
        assert "90" in output
        assert "WARN" in output

    def test_contains_checker_name(self):
        report = _sample_report()
        output = _render_terminal(report)
        assert "Project Structure" in output

    def test_contains_priority_actions(self):
        report = _sample_report()
        output = _render_terminal(report)
        assert "Priority Actions" in output
        assert "Add a CHANGELOG.md" in output

    def test_contains_summary(self):
        report = _sample_report()
        output = _render_terminal(report)
        assert "warnings in Project Structure" in output

    def test_contains_overall_row(self):
        report = _sample_report()
        output = _render_terminal(report)
        assert "Overall" in output

    def test_multiple_checkers(self):
        results = [
            CheckerResult(
                name="licensing",
                display_name="Licensing",
                status="pass",
                score=100,
            ),
            CheckerResult(
                name="testing",
                display_name="Testing",
                status="warn",
                score=80,
            ),
        ]
        report = AuditReport(
            language="python",
            repo_path="/tmp/repo",
            timestamp="2026-04-26T00:00:00+00:00",
            overall_score=90,
            overall_status="warn",
            deciphercode_version="0.2.0",
            results=results,
            checkers_run=["licensing", "testing"],
        )
        output = _render_terminal(report)
        assert "Licensing" in output
        assert "Testing" in output
        assert "PASS" in output
        assert "WARN" in output

    def test_no_priority_actions_when_empty(self):
        report = AuditReport(
            language="python",
            repo_path="/tmp/repo",
            timestamp="2026-04-26T00:00:00+00:00",
            overall_score=100,
            overall_status="pass",
            deciphercode_version="0.2.0",
            top_recommendations=[],
        )
        output = _render_terminal(report)
        assert "Priority Actions" not in output
