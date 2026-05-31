"""Tests for the Java ci_cd checker."""

from pathlib import Path

from decipher.practices.checkers.java.ci_cd import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


class TestCiConfig:
    """Test JCICD-001: CI/CD configuration detection."""

    def test_github_actions(self, tmp_path: Path):
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text("name: CI\non: [push]\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JCICD-001")
        assert f is not None
        assert f.severity == "pass"
        assert "GitHub Actions" in f.message

    def test_jenkinsfile(self, tmp_path: Path):
        (tmp_path / "Jenkinsfile").write_text("pipeline { agent any }\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JCICD-001")
        assert f is not None
        assert f.severity == "pass"
        assert "Jenkinsfile" in f.message

    def test_gitlab_ci(self, tmp_path: Path):
        (tmp_path / ".gitlab-ci.yml").write_text("stages:\n  - build\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JCICD-001")
        assert f is not None
        assert f.severity == "pass"
        assert "GitLab" in f.message

    def test_no_ci_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JCICD-001")
        assert f is not None
        assert f.severity == "fail"


class TestBuildWrapper:
    """Test JCICD-002: build wrapper detection."""

    def test_mvnw(self, tmp_path: Path):
        (tmp_path / "mvnw").write_text("#!/bin/sh\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JCICD-002")
        assert f is not None
        assert f.severity == "pass"
        assert "Maven" in f.message
        assert f.file_path == "mvnw"

    def test_gradlew(self, tmp_path: Path):
        (tmp_path / "gradlew").write_text("#!/bin/sh\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JCICD-002")
        assert f is not None
        assert f.severity == "pass"
        assert "Gradle" in f.message
        assert f.file_path == "gradlew"

    def test_no_wrapper_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JCICD-002")
        assert f is not None
        assert f.severity == "warn"


class TestCiCdAllPass:
    """Full CI/CD setup should produce all pass."""

    def test_all_pass(self, tmp_path: Path):
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text("name: CI\non: [push]\n")
        (tmp_path / "mvnw").write_text("#!/bin/sh\n")
        result = Checker().run(tmp_path)
        assert result.status == "pass"
        assert result.score == 100
