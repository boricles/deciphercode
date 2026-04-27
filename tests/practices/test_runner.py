"""Tests for decipher.practices.runner."""

import tempfile
from pathlib import Path

from decipher.practices.runner import SUPPORTED_LANGUAGES, run_audit


class TestRunAudit:
    def test_returns_audit_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_audit(Path(tmpdir), language="python", show_progress=False)
            assert report.language == "python"
            assert report.schema_version == "1.0"
            assert report.deciphercode_version != ""
            assert len(report.checkers_run) == len(SUPPORTED_LANGUAGES["python"])

    def test_all_checkers_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_audit(Path(tmpdir), language="python", show_progress=False)
            assert report.checkers_run == SUPPORTED_LANGUAGES["python"]

    def test_overall_score_is_average(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_audit(Path(tmpdir), language="python", show_progress=False)
            if report.results:
                expected = sum(r.score for r in report.results) // len(report.results)
                assert report.overall_score == expected

    def test_timestamp_is_iso(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_audit(Path(tmpdir), language="python", show_progress=False)
            assert "T" in report.timestamp

    def test_repo_path_is_absolute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_audit(Path(tmpdir), language="python", show_progress=False)
            assert Path(report.repo_path).is_absolute()
