"""Tests for the Java testing checker."""

from pathlib import Path

from decipher.practices.checkers.java.testing import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


def _build_java_project_with_tests(tmp_path: Path) -> Path:
    """Create a Java project with proper test structure."""
    main = tmp_path / "src" / "main" / "java" / "com" / "example"
    main.mkdir(parents=True)
    (main / "App.java").write_text("package com.example;\npublic class App {}\n")

    test = tmp_path / "src" / "test" / "java" / "com" / "example"
    test.mkdir(parents=True)
    (test / "AppTest.java").write_text(
        "package com.example;\n"
        "import org.junit.jupiter.api.Test;\n"
        "public class AppTest {\n"
        "    @Test\n"
        "    void testApp() { }\n"
        "}\n"
    )
    return tmp_path


class TestTestingPass:
    """Project with tests should pass."""

    def test_all_pass(self, tmp_path: Path):
        repo = _build_java_project_with_tests(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "JTEST-001")
        assert f is not None
        assert f.severity == "pass"
        assert "JUnit" in f.message

    def test_test_dir_pass(self, tmp_path: Path):
        repo = _build_java_project_with_tests(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "JTEST-002")
        assert f is not None
        assert f.severity == "pass"


class TestTestingFail:
    """Project without tests should fail."""

    def test_no_tests_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JTEST-001")
        assert f is not None
        assert f.severity == "fail"

    def test_no_test_dir_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JTEST-002")
        assert f is not None
        assert f.severity == "fail"


class TestTestFrameworkDetection:
    """Detect JUnit vs TestNG."""

    def test_junit_detected(self, tmp_path: Path):
        test = tmp_path / "src" / "test" / "java"
        test.mkdir(parents=True)
        (test / "FooTest.java").write_text(
            "import org.junit.jupiter.api.Test;\n"
            "public class FooTest {\n"
            "    @Test void test() {}\n"
            "}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JTEST-001")
        assert f is not None
        assert "JUnit" in f.message

    def test_testng_detected(self, tmp_path: Path):
        test = tmp_path / "src" / "test" / "java"
        test.mkdir(parents=True)
        (test / "FooTest.java").write_text(
            "import org.testng.annotations.Test;\n"
            "public class FooTest {\n"
            "    @Test public void test() {}\n"
            "}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JTEST-001")
        assert f is not None
        assert "TestNG" in f.message


class TestIntegrationTestSeparation:
    """Test integration test detection."""

    def test_it_naming_convention(self, tmp_path: Path):
        test = tmp_path / "src" / "test" / "java"
        test.mkdir(parents=True)
        (test / "AppIT.java").write_text(
            "import org.junit.jupiter.api.Test;\n"
            "public class AppIT {\n"
            "    @Test void integrationTest() {}\n"
            "}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JTEST-003")
        assert f is not None
        assert f.severity == "pass"

    def test_failsafe_plugin_detected(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text(
            "<project><build><plugins>"
            "<plugin><artifactId>maven-failsafe-plugin</artifactId></plugin>"
            "</plugins></build></project>"
        )
        test = tmp_path / "src" / "test" / "java"
        test.mkdir(parents=True)
        (test / "AppTest.java").write_text(
            "import org.junit.jupiter.api.Test;\n"
            "public class AppTest { @Test void test() {} }\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JTEST-003")
        assert f is not None
        assert f.severity == "pass"

    def test_no_it_separation_is_warn(self, tmp_path: Path):
        repo = _build_java_project_with_tests(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "JTEST-003")
        assert f is not None
        assert f.severity == "warn"

    def test_no_tests_skips_it_check(self, tmp_path: Path):
        """If no test files, JTEST-003 is not emitted."""
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JTEST-003")
        assert f is None
