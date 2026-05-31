"""Tests for the Java dependency_hygiene checker."""

from pathlib import Path

from decipher.practices.checkers.java.dependency_hygiene import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


class TestSnapshotDeps:
    """Test JDEP-001: SNAPSHOT dependency detection."""

    def test_no_snapshots_pass(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><dependencies>"
            "<dependency><version>1.0.0</version></dependency>"
            "</dependencies></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-001")
        assert f is not None
        assert f.severity == "pass"

    def test_snapshot_deps_warn(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><dependencies>"
            "<dependency><version>1.0.0-SNAPSHOT</version></dependency>"
            "</dependencies></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-001")
        assert f is not None
        assert f.severity == "warn"
        assert "SNAPSHOT" in f.message

    def test_gradle_snapshot_warn(self, tmp_path: Path):
        (tmp_path / "build.gradle").write_text(
            "dependencies {\n"
            "    implementation 'com.example:lib:1.0-SNAPSHOT'\n"
            "}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-001")
        assert f is not None
        assert f.severity == "warn"

class TestNoBuildFile:
    """No build file produces a gate-fail and suppresses all other checks."""

    def test_no_build_file_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-001")
        assert f is not None
        assert f.severity == "fail"
        assert "No build file" in f.message

    def test_no_build_file_suppresses_downstream(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "JDEP-002") is None
        assert _finding_by_id(result, "JDEP-003") is None

    def test_no_build_file_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) == 1

    def test_no_build_file_score(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert result.score == 75  # 1 fail = 100 - 25


class TestDepManagement:
    """Test JDEP-002: dependency management section detection."""

    def test_pom_dep_management(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><dependencyManagement>"
            "<dependencies></dependencies>"
            "</dependencyManagement></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-002")
        assert f is not None
        assert f.severity == "pass"

    def test_gradle_version_catalog(self, tmp_path: Path):
        (tmp_path / "build.gradle").write_text("apply plugin: 'java'\n")
        catalog = tmp_path / "gradle"
        catalog.mkdir()
        (catalog / "libs.versions.toml").write_text("[versions]\njunit = '5.10.0'\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-002")
        assert f is not None
        assert f.severity == "pass"

    def test_no_dep_management_warn(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-002")
        assert f is not None
        assert f.severity == "warn"


class TestBomUsage:
    """Test JDEP-003: BOM import detection."""

    def test_pom_bom_import(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><dependencyManagement><dependencies>"
            "<dependency><type>pom</type><scope>import</scope></dependency>"
            "</dependencies></dependencyManagement></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-003")
        assert f is not None
        assert f.severity == "pass"

    def test_gradle_platform(self, tmp_path: Path):
        (tmp_path / "build.gradle").write_text(
            "dependencies {\n"
            "    implementation platform('org.springframework.boot:spring-boot-dependencies:3.0.0')\n"
            "}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-003")
        assert f is not None
        assert f.severity == "pass"

    def test_no_bom_warn(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDEP-003")
        assert f is not None
        assert f.severity == "warn"

    def test_no_build_file_gate_fails(self, tmp_path: Path):
        """No build file triggers gate-fail at JDEP-001, suppressing JDEP-003."""
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "JDEP-003") is None
        assert _finding_by_id(result, "JDEP-001").severity == "fail"
