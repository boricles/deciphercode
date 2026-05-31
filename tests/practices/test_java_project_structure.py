"""Tests for the Java project_structure checker."""

from pathlib import Path

from decipher.practices.checkers.java.project_structure import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


def _build_standard_layout(tmp_path: Path) -> Path:
    """Create a standard Maven/Gradle project layout."""
    (tmp_path / "pom.xml").write_text(
        "<project><groupId>com.example</groupId>"
        "<artifactId>myapp</artifactId><version>1.0.0</version></project>"
    )
    main = tmp_path / "src" / "main" / "java" / "com" / "example"
    main.mkdir(parents=True)
    (main / "App.java").write_text("package com.example;\npublic class App {}\n")
    test = tmp_path / "src" / "test" / "java" / "com" / "example"
    test.mkdir(parents=True)
    (test / "AppTest.java").write_text("package com.example;\npublic class AppTest {}\n")
    return tmp_path


class TestProjectStructurePass:
    """Complete project should produce all-pass findings."""

    def test_all_pass_status(self, tmp_path: Path):
        repo = _build_standard_layout(tmp_path)
        result = Checker().run(repo)
        assert result.status == "pass"
        assert result.score == 100

    def test_no_recommendations(self, tmp_path: Path):
        repo = _build_standard_layout(tmp_path)
        result = Checker().run(repo)
        assert result.recommendations == []

    def test_all_findings_pass(self, tmp_path: Path):
        repo = _build_standard_layout(tmp_path)
        result = Checker().run(repo)
        for f in result.findings:
            assert f.severity == "pass", f"Finding {f.id} has severity {f.severity}"


class TestProjectStructureFail:
    """Empty repo should produce fail findings for critical items."""

    def test_empty_repo_has_failures(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert result.status == "fail"

    def test_missing_layout_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-001")
        assert f is not None
        assert f.severity == "fail"

    def test_missing_build_file_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-002")
        assert f is not None
        assert f.severity == "fail"

    def test_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) >= 2


class TestProjectStructureWarn:
    """Project with partial layout."""

    def test_main_without_test_is_warn(self, tmp_path: Path):
        main = tmp_path / "src" / "main" / "java" / "com" / "example"
        main.mkdir(parents=True)
        (main / "App.java").write_text("package com.example;\npublic class App {}\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-001")
        assert f is not None
        assert f.severity == "warn"

    def test_bad_package_naming_is_warn(self, tmp_path: Path):
        bad_pkg = tmp_path / "src" / "main" / "java" / "com" / "My-Package"
        bad_pkg.mkdir(parents=True)
        (bad_pkg / "App.java").write_text("public class App {}\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-003")
        assert f is not None
        assert f.severity == "warn"


class TestBuildFileVariants:
    """Test detection of different build files."""

    def test_pom_xml(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-002")
        assert f is not None
        assert f.severity == "pass"
        assert f.file_path == "pom.xml"

    def test_build_gradle(self, tmp_path: Path):
        (tmp_path / "build.gradle").write_text("apply plugin: 'java'\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-002")
        assert f is not None
        assert f.severity == "pass"
        assert f.file_path == "build.gradle"

    def test_build_gradle_kts(self, tmp_path: Path):
        (tmp_path / "build.gradle.kts").write_text('plugins { java }\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-002")
        assert f is not None
        assert f.severity == "pass"
        assert f.file_path == "build.gradle.kts"

    def test_pom_preferred_over_gradle(self, tmp_path: Path):
        """When both exist, pom.xml is detected first."""
        (tmp_path / "pom.xml").write_text("<project></project>")
        (tmp_path / "build.gradle").write_text("apply plugin: 'java'\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-002")
        assert f is not None
        assert f.file_path == "pom.xml"


class TestBuildFileInSubdir:
    """Test detection of build files in immediate subdirectories."""

    def test_pom_in_subdir_is_warn(self, tmp_path: Path):
        sub = tmp_path / "myproject"
        sub.mkdir()
        (sub / "pom.xml").write_text("<project></project>")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-002")
        assert f is not None
        assert f.severity == "warn"
        assert "subdirectory" in f.message
        assert f.file_path == "myproject/pom.xml"

    def test_gradle_in_subdir_is_warn(self, tmp_path: Path):
        sub = tmp_path / "app"
        sub.mkdir()
        (sub / "build.gradle").write_text("apply plugin: 'java'\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-002")
        assert f is not None
        assert f.severity == "warn"

    def test_root_preferred_over_subdir(self, tmp_path: Path):
        """Build file at root takes precedence over subdirectory."""
        (tmp_path / "pom.xml").write_text("<project></project>")
        sub = tmp_path / "module"
        sub.mkdir()
        (sub / "pom.xml").write_text("<project></project>")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-002")
        assert f is not None
        assert f.severity == "pass"
        assert f.file_path == "pom.xml"


class TestLegacySrcLayout:
    """Test recognition of legacy src/ layout."""

    def test_legacy_src_with_java_is_warn(self, tmp_path: Path):
        pkg = tmp_path / "src" / "com" / "example"
        pkg.mkdir(parents=True)
        (pkg / "App.java").write_text("package com.example;\npublic class App {}\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-001")
        assert f is not None
        assert f.severity == "warn"
        assert "Legacy" in f.message

    def test_legacy_src_checks_packages(self, tmp_path: Path):
        """Package naming check works with legacy src/ layout."""
        pkg = tmp_path / "src" / "com" / "example"
        pkg.mkdir(parents=True)
        (pkg / "App.java").write_text("package com.example;\npublic class App {}\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-003")
        assert f is not None
        assert f.severity == "pass"

    def test_empty_src_is_fail(self, tmp_path: Path):
        """src/ without .java files is not recognized as legacy layout."""
        (tmp_path / "src").mkdir()
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-001")
        assert f is not None
        assert f.severity == "fail"


class TestPackageNaming:
    """Test package naming convention checks."""

    def test_valid_packages(self, tmp_path: Path):
        pkg = tmp_path / "src" / "main" / "java" / "com" / "example" / "myapp"
        pkg.mkdir(parents=True)
        (pkg / "Main.java").write_text("package com.example.myapp;\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-003")
        assert f is not None
        assert f.severity == "pass"

    def test_uppercase_package_is_warn(self, tmp_path: Path):
        pkg = tmp_path / "src" / "main" / "java" / "com" / "Example"
        pkg.mkdir(parents=True)
        (pkg / "Main.java").write_text("public class Main {}\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-003")
        assert f is not None
        assert f.severity == "warn"

    def test_no_packages_emits_no_finding(self, tmp_path: Path):
        """If src/main/java has no subdirs, JPROJ-003 is not emitted."""
        (tmp_path / "src" / "main" / "java").mkdir(parents=True)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JPROJ-003")
        assert f is None
