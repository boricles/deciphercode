"""Tests for the licensing checker."""

from pathlib import Path

from decipher.practices.checkers.python.licensing import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


_MIT_TEXT = """\
MIT License

Copyright (c) 2026 Test Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
"""

_APACHE2_TEXT = """\
Apache License Version 2.0, January 2004
http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION
"""


class TestLicensingPass:
    """Repo with LICENSE file, known license, and consistent pyproject.toml."""

    @staticmethod
    def _build_complete(tmp_path: Path) -> Path:
        (tmp_path / "LICENSE").write_text(_MIT_TEXT)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nlicense = {text = "MIT"}\n'
        )
        return tmp_path

    def test_all_pass_status(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        assert result.status == "pass"
        assert result.score == 100

    def test_all_findings_pass(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        for f in result.findings:
            assert f.severity == "pass", f"Finding {f.id} has severity {f.severity}"

    def test_no_recommendations(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        assert result.recommendations == []

    def test_license_identified_as_mit(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "LIC-002")
        assert f is not None
        assert "MIT" in f.message


class TestLicensingFail:
    """No LICENSE file at all."""

    def test_no_license_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-001")
        assert f is not None
        assert f.severity == "fail"

    def test_no_license_suppresses_other_checks(self, tmp_path: Path):
        """LIC-002 and LIC-003 should NOT be emitted when no LICENSE."""
        result = Checker().run(tmp_path)
        assert len(result.findings) == 1
        assert result.findings[0].id == "LIC-001"

    def test_no_license_score(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        # 1 fail = 100 - 25 = 75
        assert result.score == 75

    def test_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) >= 1


class TestLicensingWarn:
    """LICENSE exists but with issues."""

    def test_unknown_license_warns(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text("This is my custom license. Do whatever.\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-002")
        assert f is not None
        assert f.severity == "warn"

    def test_pyproject_no_license_field_warns(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text(_MIT_TEXT)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-003")
        assert f is not None
        assert f.severity == "warn"

    def test_pyproject_license_mismatch_warns(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text(_MIT_TEXT)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nlicense = {text = "Apache-2.0"}\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-003")
        assert f is not None
        assert f.severity == "warn"
        assert "MIT" in f.message
        assert "Apache" in f.message


class TestLicensingMixed:
    """Mix of pass and warn findings."""

    def test_license_present_unknown_no_pyproject(self, tmp_path: Path):
        """LIC-001 pass, LIC-002 warn, no LIC-003 (no pyproject)."""
        (tmp_path / "LICENSE").write_text("Custom license terms.\n")
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "LIC-001").severity == "pass"
        assert _finding_by_id(result, "LIC-002").severity == "warn"
        assert _finding_by_id(result, "LIC-003") is None
        assert result.status == "warn"
        assert result.score == 90

    def test_license_known_but_pyproject_mismatch(self, tmp_path: Path):
        """LIC-001 pass, LIC-002 pass, LIC-003 warn."""
        (tmp_path / "LICENSE").write_text(_MIT_TEXT)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nlicense = {text = "GPL-3.0"}\n'
        )
        result = Checker().run(tmp_path)
        pass_count = sum(1 for f in result.findings if f.severity == "pass")
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert pass_count == 2  # LIC-001, LIC-002
        assert warn_count == 1  # LIC-003
        assert result.score == 90


class TestLicensingFilePath:
    """Validate that file_path is populated on findings."""

    def test_license_present_has_file_path(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text(_MIT_TEXT)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-001")
        assert f.file_path == "LICENSE"

    def test_license_txt_variant_has_file_path(self, tmp_path: Path):
        (tmp_path / "LICENSE.txt").write_text(_MIT_TEXT)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-001")
        assert f.file_path == "LICENSE.txt"

    def test_licence_british_has_file_path(self, tmp_path: Path):
        (tmp_path / "LICENCE").write_text(_MIT_TEXT)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-001")
        assert f.file_path == "LICENCE"

    def test_known_license_points_to_file(self, tmp_path: Path):
        (tmp_path / "LICENSE.md").write_text(f"# MIT License\n\n{_MIT_TEXT}")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-002")
        assert f.file_path == "LICENSE.md"

    def test_consistency_points_to_pyproject(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text(_MIT_TEXT)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nlicense = {text = "MIT"}\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-003")
        assert f.file_path == "pyproject.toml"

    def test_missing_license_has_no_file_path(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-001")
        assert f.file_path is None


class TestLicensingEdgeCases:
    def test_apache2_detected(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text(_APACHE2_TEXT)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-002")
        assert f.severity == "pass"
        assert "Apache-2.0" in f.message

    def test_bsd3_detected(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text("BSD 3-Clause License\n\nCopyright (c) 2026\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-002")
        assert f.severity == "pass"
        assert "BSD-3-Clause" in f.message

    def test_gpl3_detected(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text("GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-002")
        assert f.severity == "pass"
        assert "GPL-3.0" in f.message

    def test_unlicense_detected(self, tmp_path: Path):
        (tmp_path / "LICENSE").write_text(
            "This is free and unencumbered software.\nThe Unlicense\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-002")
        assert f.severity == "pass"
        assert "Unlicense" in f.message

    def test_no_pyproject_skips_consistency(self, tmp_path: Path):
        """LIC-003 should not be emitted when there's no pyproject.toml."""
        (tmp_path / "LICENSE").write_text(_MIT_TEXT)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "LIC-003") is None

    def test_pyproject_license_as_string(self, tmp_path: Path):
        """PEP 639 style: license = 'MIT' as plain string."""
        (tmp_path / "LICENSE").write_text(_MIT_TEXT)
        # tomllib parses license = "MIT" as a string
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nlicense = "MIT"\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-003")
        assert f is not None
        assert f.severity == "pass"

    def test_pyproject_license_expression(self, tmp_path: Path):
        """PEP 639 license-expression field."""
        (tmp_path / "LICENSE").write_text(_MIT_TEXT)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nlicense-expression = "MIT"\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "LIC-003")
        assert f is not None
        assert f.severity == "pass"

    def test_empty_license_file(self, tmp_path: Path):
        """Empty LICENSE file: present but unknown license."""
        (tmp_path / "LICENSE").write_text("")
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "LIC-001").severity == "pass"
        assert _finding_by_id(result, "LIC-002").severity == "warn"
