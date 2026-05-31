"""Tests for the Java documentation checker."""

from pathlib import Path

from decipher.practices.checkers.java.documentation import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


class TestReadme:
    """Test JDOC-001: README detection."""

    def test_readme_present(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(
            "# My Java Project\n\n"
            "A comprehensive Java application that demonstrates best practices "
            "for building enterprise software with Spring Boot and Maven.\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDOC-001")
        assert f is not None
        assert f.severity == "pass"

    def test_no_readme_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDOC-001")
        assert f is not None
        assert f.severity == "fail"

    def test_short_readme_is_fail(self, tmp_path: Path):
        (tmp_path / "README.md").write_text("# Foo\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDOC-001")
        assert f is not None
        assert f.severity == "fail"

    def test_no_readme_suppresses_other_checks(self, tmp_path: Path):
        """JDOC-002 and JDOC-003 not emitted when JDOC-001 fails."""
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "JDOC-002") is None
        assert _finding_by_id(result, "JDOC-003") is None


class TestJavadoc:
    """Test JDOC-002: Javadoc comment detection."""

    def test_javadoc_present(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(
            "# My Java Project\n\n"
            "A comprehensive Java project with extensive Javadoc documentation "
            "covering all public APIs, data models, and service interfaces for production use.\n"
        )
        main = tmp_path / "src" / "main" / "java" / "com" / "example"
        main.mkdir(parents=True)
        (main / "App.java").write_text(
            "package com.example;\n\n"
            "/**\n"
            " * Main application class.\n"
            " */\n"
            "public class App {\n"
            "    /**\n"
            "     * Entry point.\n"
            "     */\n"
            "    public static void main(String[] args) {}\n"
            "}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDOC-002")
        assert f is not None
        assert f.severity == "pass"

    def test_no_javadoc_is_warn(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(
            "# My Java Project\n\n"
            "A comprehensive Java project that needs some documentation work done "
            "to bring it up to enterprise-grade standards and ensure full API coverage.\n"
        )
        main = tmp_path / "src" / "main" / "java" / "com" / "example"
        main.mkdir(parents=True)
        (main / "App.java").write_text(
            "package com.example;\n"
            "public class App {\n"
            "    public static void main(String[] args) {}\n"
            "}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDOC-002")
        assert f is not None
        assert f.severity == "warn"

    def test_no_java_files_passes(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(
            "# My Java Project\n\n"
            "A comprehensive project with no source files yet but a solid README "
            "that describes the planned architecture, modules, and deployment strategy.\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDOC-002")
        assert f is not None
        assert f.severity == "pass"


class TestApiDocs:
    """Test JDOC-003: API documentation setup detection."""

    def test_javadoc_plugin_in_pom(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(
            "# My Java Project\n\n"
            "A comprehensive project with automated Javadoc generation "
            "configured via the Maven Javadoc plugin for continuous documentation builds.\n"
        )
        (tmp_path / "pom.xml").write_text(
            "<project><build><plugins>"
            "<plugin><artifactId>maven-javadoc-plugin</artifactId></plugin>"
            "</plugins></build></project>"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDOC-003")
        assert f is not None
        assert f.severity == "pass"

    def test_docs_directory(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(
            "# My Java Project\n\n"
            "A comprehensive project with a dedicated documentation directory "
            "containing API guides, architecture diagrams, and detailed deployment docs.\n"
        )
        (tmp_path / "docs").mkdir()
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDOC-003")
        assert f is not None
        assert f.severity == "pass"

    def test_no_api_docs_is_warn(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(
            "# My Java Project\n\n"
            "A comprehensive project that would benefit from automated API documentation "
            "generation using Maven Javadoc plugin and a dedicated docs directory.\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JDOC-003")
        assert f is not None
        assert f.severity == "warn"


class TestDocumentationAllPass:
    """Full documentation setup should produce all pass."""

    def test_all_pass(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(
            "# My Java Project\n\n"
            "A comprehensive Java application built with Maven that "
            "demonstrates best practices for enterprise development.\n"
        )
        main = tmp_path / "src" / "main" / "java" / "com" / "example"
        main.mkdir(parents=True)
        (main / "App.java").write_text(
            "package com.example;\n\n"
            "/**\n"
            " * Main app.\n"
            " */\n"
            "public class App {}\n"
        )
        (tmp_path / "docs").mkdir()
        result = Checker().run(tmp_path)
        assert result.status == "pass"
        assert result.score == 100
