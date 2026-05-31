"""Tests for the Java release_readiness checker."""

from pathlib import Path

from decipher.practices.checkers.java.release_readiness import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


class TestVersion:
    """Test JREL-001: version declaration detection."""

    def test_pom_version(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><version>1.0.0</version></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-001")
        assert f is not None
        assert f.severity == "pass"
        assert "1.0.0" in f.message

    def test_gradle_version(self, tmp_path: Path):
        (tmp_path / "build.gradle").write_text('version = "2.1.0"\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-001")
        assert f is not None
        assert f.severity == "pass"
        assert "2.1.0" in f.message

    def test_gradle_kts_version(self, tmp_path: Path):
        (tmp_path / "build.gradle.kts").write_text('version = "3.0.0"\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-001")
        assert f is not None
        assert f.severity == "pass"

    def test_no_version_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-001")
        assert f is not None
        assert f.severity == "fail"


class TestChangelog:
    """Test JREL-002: CHANGELOG.md detection."""

    def test_changelog_present(self, tmp_path: Path):
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n## [1.0.0]\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-002")
        assert f is not None
        assert f.severity == "pass"

    def test_no_changelog_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-002")
        assert f is not None
        assert f.severity == "warn"


class TestReleaseProfile:
    """Test JREL-003: release profile detection."""

    def test_maven_release_profile(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><profiles><profile>"
            "<id>release</id>"
            "</profile></profiles></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-003")
        assert f is not None
        assert f.severity == "pass"

    def test_maven_release_plugin(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><build><plugins>"
            "<plugin><artifactId>maven-release-plugin</artifactId></plugin>"
            "</plugins></build></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-003")
        assert f is not None
        assert f.severity == "pass"

    def test_gradle_release_plugin(self, tmp_path: Path):
        (tmp_path / "build.gradle").write_text(
            "plugins {\n    id 'net.researchgate.release' plugin\n}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-003")
        assert f is not None
        assert f.severity == "pass"

    def test_no_release_profile_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JREL-003")
        assert f is not None
        assert f.severity == "warn"


class TestReleaseReadinessAllPass:
    """Full release setup should produce all pass."""

    def test_all_pass(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><version>1.0.0</version>"
            "<profiles><profile><id>release</id></profile></profiles></project>"
        )
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n## [1.0.0]\n")
        result = Checker().run(tmp_path)
        assert result.status == "pass"
        assert result.score == 100
