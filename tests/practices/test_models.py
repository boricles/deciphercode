"""Tests for decipher.practices.models."""

from decipher.practices.models import (
    AuditReport,
    CheckerResult,
    Finding,
    compute_score,
    worst_status,
)


class TestFinding:
    def test_defaults(self):
        f = Finding(id="T-001", message="msg", severity="pass", category="test")
        assert f.file_path is None
        assert f.line is None
        assert f.detail == ""

    def test_with_file_and_line(self):
        f = Finding(
            id="T-002",
            message="missing docstring",
            severity="warn",
            category="documentation",
            file_path="src/main.py",
            line=42,
        )
        assert f.file_path == "src/main.py"
        assert f.line == 42


class TestCheckerResult:
    def test_defaults(self):
        r = CheckerResult(name="x", display_name="X", status="pass", score=100)
        assert r.findings == []
        assert r.recommendations == []


class TestAuditReport:
    def test_schema_version_default(self):
        r = AuditReport(
            language="python",
            repo_path="/tmp/repo",
            timestamp="2026-01-01T00:00:00+00:00",
            overall_score=80,
            overall_status="pass",
            deciphercode_version="0.2.0",
        )
        assert r.schema_version == "1.0"
        assert r.checkers_run == []
        assert r.top_recommendations == []


class TestComputeScore:
    def test_all_pass(self):
        findings = [
            Finding(id="A", message="ok", severity="pass", category="x"),
            Finding(id="B", message="ok", severity="pass", category="x"),
        ]
        assert compute_score(findings) == 100

    def test_warnings_deduct(self):
        findings = [
            Finding(id="A", message="ok", severity="pass", category="x"),
            Finding(id="B", message="meh", severity="warn", category="x"),
        ]
        assert compute_score(findings) == 90

    def test_failures_deduct(self):
        findings = [
            Finding(id="A", message="bad", severity="fail", category="x"),
        ]
        assert compute_score(findings) == 75

    def test_mixed(self):
        findings = [
            Finding(id="A", message="bad", severity="fail", category="x"),
            Finding(id="B", message="meh", severity="warn", category="x"),
            Finding(id="C", message="meh", severity="warn", category="x"),
        ]
        # 100 - 25 - 10 - 10 = 55
        assert compute_score(findings) == 55

    def test_floor_at_zero(self):
        findings = [
            Finding(id=f"F{i}", message="bad", severity="fail", category="x") for i in range(10)
        ]
        assert compute_score(findings) == 0

    def test_empty(self):
        assert compute_score([]) == 100


class TestWorstStatus:
    def test_all_pass(self):
        findings = [
            Finding(id="A", message="ok", severity="pass", category="x"),
        ]
        assert worst_status(findings) == "pass"

    def test_warn_beats_pass(self):
        findings = [
            Finding(id="A", message="ok", severity="pass", category="x"),
            Finding(id="B", message="meh", severity="warn", category="x"),
        ]
        assert worst_status(findings) == "warn"

    def test_fail_beats_all(self):
        findings = [
            Finding(id="A", message="ok", severity="pass", category="x"),
            Finding(id="B", message="meh", severity="warn", category="x"),
            Finding(id="C", message="bad", severity="fail", category="x"),
        ]
        assert worst_status(findings) == "fail"
