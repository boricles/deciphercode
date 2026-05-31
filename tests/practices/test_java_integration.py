"""Integration test: runs the full Java practices audit against a fixture repo."""

import json
from pathlib import Path

from click.testing import CliRunner

from decipher.cli import main
from decipher.practices.runner import run_audit


class TestJavaIntegrationAudit:
    """Run the auditor against a synthetic Java repo and verify end-to-end output."""

    @staticmethod
    def _build_fixture(tmp_path: Path) -> Path:
        """Create a realistic minimal Java/Maven project."""
        # pom.xml
        (tmp_path / "pom.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<project>\n"
            "  <modelVersion>4.0.0</modelVersion>\n"
            "  <groupId>com.example</groupId>\n"
            "  <artifactId>myapp</artifactId>\n"
            "  <version>1.0.0</version>\n"
            "  <dependencyManagement>\n"
            "    <dependencies>\n"
            "      <dependency>\n"
            "        <groupId>org.springframework.boot</groupId>\n"
            "        <artifactId>spring-boot-dependencies</artifactId>\n"
            "        <version>3.2.0</version>\n"
            "        <type>pom</type>\n"
            "        <scope>import</scope>\n"
            "      </dependency>\n"
            "    </dependencies>\n"
            "  </dependencyManagement>\n"
            "  <build>\n"
            "    <plugins>\n"
            "      <plugin>\n"
            "        <artifactId>maven-checkstyle-plugin</artifactId>\n"
            "      </plugin>\n"
            "      <plugin>\n"
            "        <artifactId>maven-javadoc-plugin</artifactId>\n"
            "      </plugin>\n"
            "      <plugin>\n"
            "        <artifactId>maven-failsafe-plugin</artifactId>\n"
            "      </plugin>\n"
            "    </plugins>\n"
            "  </build>\n"
            "  <profiles>\n"
            "    <profile>\n"
            "      <id>release</id>\n"
            "    </profile>\n"
            "  </profiles>\n"
            "</project>\n"
        )
        # LICENSE
        (tmp_path / "LICENSE").write_text("Apache License Version 2.0\n\nCopyright 2024\n")
        # README
        (tmp_path / "README.md").write_text(
            "# My Java App\n\n"
            "A sample Java project used for integration testing of the "
            "DecipherCode best-practices auditor for Java projects.\n\n"
            "## Build\n\nmvn clean install\n\n"
            "## Usage\n\njava -jar target/myapp.jar\n"
        )
        # CHANGELOG
        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [1.0.0] - 2024-01-01\n\n### Added\n\n- Initial release\n"
        )
        # Source
        main = tmp_path / "src" / "main" / "java" / "com" / "example"
        main.mkdir(parents=True)
        (main / "App.java").write_text(
            "/*\n"
            " * Copyright 2024 Example Inc.\n"
            " * Licensed under the Apache License\n"
            " */\n"
            "package com.example;\n\n"
            "/**\n"
            " * Main application class.\n"
            " */\n"
            "public class App {\n"
            "    public static void main(String[] args) {}\n"
            "}\n"
        )
        # Tests
        test = tmp_path / "src" / "test" / "java" / "com" / "example"
        test.mkdir(parents=True)
        (test / "AppTest.java").write_text(
            "package com.example;\n"
            "import org.junit.jupiter.api.Test;\n"
            "public class AppTest {\n"
            "    @Test void testApp() {}\n"
            "}\n"
        )
        # GitHub Actions
        wf = tmp_path / ".github" / "workflows"
        wf.mkdir(parents=True)
        (wf / "ci.yml").write_text(
            "name: CI\non: [push]\njobs:\n  build:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - run: mvn verify\n"
        )
        # Maven wrapper
        (tmp_path / "mvnw").write_text("#!/bin/sh\n")
        # SonarQube
        (tmp_path / "sonar-project.properties").write_text(
            "sonar.projectKey=com.example:myapp\n"
        )
        # EditorConfig
        (tmp_path / ".editorconfig").write_text("root = true\n")
        return tmp_path

    def test_full_audit_all_checkers_run(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        report = run_audit(repo, language="java", show_progress=False)

        assert report.language == "java"
        assert report.schema_version == "1.0"
        assert len(report.results) == 8
        assert len(report.checkers_run) == 8
        assert report.overall_score >= 0
        assert report.overall_status in ("pass", "warn", "fail")

    def test_full_audit_high_score(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        report = run_audit(repo, language="java", show_progress=False)
        # The fixture project should score well
        assert report.overall_score >= 80

    def test_full_audit_json_serializable(self, tmp_path: Path):
        from decipher.practices.reporter import Reporter

        repo = self._build_fixture(tmp_path)
        report = run_audit(repo, language="java", show_progress=False)
        reporter = Reporter()

        text = reporter.to_json(report)
        data = json.loads(text)
        assert data["language"] == "java"
        assert "top_recommendations" in data
        assert "checkers_run" in data

    def test_cli_practices_java_explicit(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--language", "java", "--format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["language"] == "java"
        assert len(data["results"]) == 8

    def test_cli_auto_detect_java(self, tmp_path: Path):
        """Auto-detect Java when pom.xml is present."""
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(repo), "--format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["language"] == "java"

    def test_cli_auto_detect_gradle(self, tmp_path: Path):
        """Auto-detect Java when build.gradle is present."""
        (tmp_path / "build.gradle").write_text("apply plugin: 'java'\n")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(tmp_path), "--format", "json"],
        )
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert data["language"] == "java"

    def test_cli_auto_detect_python_default(self, tmp_path: Path):
        """Auto-detect defaults to Python when no Java build file exists."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["practices", str(tmp_path), "--format", "json"],
        )
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert data["language"] == "python"

    def test_cli_only_flag_java(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "practices",
                str(repo),
                "--language",
                "java",
                "--format",
                "json",
                "--only",
                "licensing",
            ],
        )
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert data["checkers_run"] == ["licensing"]
        assert len(data["results"]) == 1

    def test_cli_skip_flag_java(self, tmp_path: Path):
        repo = self._build_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "practices",
                str(repo),
                "--language",
                "java",
                "--format",
                "json",
                "--skip",
                "documentation",
            ],
        )
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert "documentation" not in data["checkers_run"]
        assert len(data["results"]) == 7


class TestJavaEmptyRepo:
    """Run audit on empty directory with Java language flag."""

    def test_empty_repo_has_failures(self, tmp_path: Path):
        report = run_audit(tmp_path, language="java", show_progress=False)
        assert report.overall_status == "fail"
        assert report.overall_score < 80
