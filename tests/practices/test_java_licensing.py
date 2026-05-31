"""Tests for the Java licensing checker."""

from pathlib import Path

from decipher.practices.checkers.java.licensing import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


class TestLicenseFile:
    """Test JLIC-001: LICENSE file detection."""

    def test_license_present(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text("MIT License\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JLIC-001")
        assert f is not None
        assert f.severity == "pass"
        assert f.file_path == "LICENSE"

    def test_license_txt(self, tmp_path: Path):
        (tmp_path / "LICENSE.txt").write_text("Apache License\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JLIC-001")
        assert f is not None
        assert f.severity == "pass"
        assert f.file_path == "LICENSE.txt"

    def test_licence_british(self, tmp_path: Path):
        (tmp_path / "LICENCE").write_text("MIT\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JLIC-001")
        assert f is not None
        assert f.severity == "pass"

    def test_no_license_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JLIC-001")
        assert f is not None
        assert f.severity == "fail"


class TestLicenseHeaders:
    """Test JLIC-002: license header detection."""

    def test_headers_present(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text("Apache License\n")
        main = tmp_path / "src" / "main" / "java" / "com" / "example"
        main.mkdir(parents=True)
        (main / "App.java").write_text(
            "/*\n"
            " * Copyright 2024 Example Inc.\n"
            " * Licensed under the Apache License\n"
            " */\n"
            "package com.example;\n"
            "public class App {}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JLIC-002")
        assert f is not None
        assert f.severity == "pass"

    def test_headers_missing_is_warn(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text("MIT License\n")
        main = tmp_path / "src" / "main" / "java" / "com" / "example"
        main.mkdir(parents=True)
        (main / "App.java").write_text(
            "package com.example;\npublic class App {}\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JLIC-002")
        assert f is not None
        assert f.severity == "warn"

    def test_no_license_suppresses_header_check(self, tmp_path: Path):
        """JLIC-002 is not emitted when JLIC-001 fails."""
        main = tmp_path / "src" / "main" / "java" / "com" / "example"
        main.mkdir(parents=True)
        (main / "App.java").write_text("public class App {}\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JLIC-002")
        assert f is None

    def test_no_java_files_passes(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text("MIT License\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "JLIC-002")
        assert f is not None
        assert f.severity == "pass"
