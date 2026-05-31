"""Tests for the Java quality_tooling checker."""

from pathlib import Path

from decipher.practices.checkers.java.quality_tooling import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


class TestStaticAnalysis:
    """Test JQUAL-001: static analysis tool detection."""

    def test_checkstyle_config_file(self, tmp_path: Path):
        (tmp_path / "checkstyle.xml").write_text("<module name='Checker'/>\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-001")
        assert f is not None
        assert f.severity == "pass"
        assert "Checkstyle" in f.message

    def test_checkstyle_in_config_dir(self, tmp_path: Path):
        config_dir = tmp_path / "config" / "checkstyle"
        config_dir.mkdir(parents=True)
        (config_dir / "checkstyle.xml").write_text("<module name='Checker'/>\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-001")
        assert f is not None
        assert f.severity == "pass"

    def test_spotbugs_config(self, tmp_path: Path):
        (tmp_path / "spotbugs-exclude.xml").write_text("<FindBugsFilter/>\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-001")
        assert f is not None
        assert f.severity == "pass"
        assert "SpotBugs" in f.message

    def test_pmd_config(self, tmp_path: Path):
        (tmp_path / "pmd-ruleset.xml").write_text("<ruleset/>\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-001")
        assert f is not None
        assert f.severity == "pass"
        assert "PMD" in f.message

    def test_checkstyle_in_pom(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><build><plugins>"
            "<plugin><artifactId>maven-checkstyle-plugin</artifactId></plugin>"
            "</plugins></build></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-001")
        assert f is not None
        assert f.severity == "pass"

    def test_no_static_analysis_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-001")
        assert f is not None
        assert f.severity == "warn"


class TestSonarQube:
    """Test JQUAL-002: SonarQube detection."""

    def test_sonar_properties(self, tmp_path: Path):
        (tmp_path / "sonar-project.properties").write_text("sonar.projectKey=myapp\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-002")
        assert f is not None
        assert f.severity == "pass"

    def test_sonar_in_pom(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><properties>"
            "<sonar.projectKey>myapp</sonar.projectKey>"
            "</properties></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-002")
        assert f is not None
        assert f.severity == "pass"

    def test_no_sonar_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-002")
        assert f is not None
        assert f.severity == "warn"


class TestEditorConfig:
    """Test JQUAL-003: EditorConfig detection."""

    def test_editorconfig_present(self, tmp_path: Path):
        (tmp_path / ".editorconfig").write_text("root = true\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-003")
        assert f is not None
        assert f.severity == "pass"

    def test_no_editorconfig_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JQUAL-003")
        assert f is not None
        assert f.severity == "warn"


class TestQualityToolingAllPass:
    """Full quality setup should produce all pass."""

    def test_all_pass(self, tmp_path: Path):
        (tmp_path / "checkstyle.xml").write_text("<module name='Checker'/>\n")
        (tmp_path / "sonar-project.properties").write_text("sonar.projectKey=x\n")
        (tmp_path / ".editorconfig").write_text("root = true\n")
        result = Checker().run(tmp_path)
        assert result.status == "pass"
        assert result.score == 100
        assert result.recommendations == []
