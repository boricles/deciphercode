"""Tests for the project_structure checker."""

from pathlib import Path

from decipher.practices.checkers.python.project_structure import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


class TestProjectStructurePass:
    """Complete project should produce all-pass findings."""

    @staticmethod
    def _build_complete(tmp_path: Path) -> Path:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "foo"\nversion = "0.1.0"\n')
        (tmp_path / "LICENSE").write_text("MIT License\n")
        (tmp_path / "README.md").write_text(
            "# Foo\n## Installation\npip install foo\n## Usage\nfoo run\n## License\nMIT\n"
        )
        (tmp_path / "CHANGELOG.md").write_text(
            "# Changelog\n## [0.1.0] - 2026-01-01\n### Added\n- Initial\n"
        )
        src = tmp_path / "src" / "foo"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        return tmp_path

    def test_all_pass_status(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        assert result.status == "pass"
        assert result.score == 100

    def test_no_recommendations(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        assert result.recommendations == []

    def test_all_findings_pass(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        for f in result.findings:
            assert f.severity == "pass", f"Finding {f.id} has severity {f.severity}"


class TestProjectStructureFail:
    """Empty repo should produce fail findings for critical items."""

    def test_empty_repo_score(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert result.status == "fail"
        # 3 fails (pyproject, LICENSE, README) + 1 warn (CHANGELOG) = 100 - 75 - 10 = 15
        assert result.score == 15

    def test_missing_pyproject_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-001")
        assert f is not None
        assert f.severity == "fail"

    def test_missing_license_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-005")
        assert f is not None
        assert f.severity == "fail"

    def test_missing_readme_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-006")
        assert f is not None
        assert f.severity == "fail"

    def test_missing_changelog_is_warn(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-010")
        assert f is not None
        assert f.severity == "warn"

    def test_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) >= 3


class TestProjectStructureWarn:
    """Project with pyproject.toml but missing optional items."""

    def test_missing_readme_sections_warn(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "LICENSE").write_text("MIT\n")
        (tmp_path / "README.md").write_text("# My Project\nSome text only.\n")
        result = Checker().run(tmp_path)
        # README sections (install, usage, license) should all be warn
        for fid in ("PROJ-007", "PROJ-008", "PROJ-009"):
            f = _finding_by_id(result, fid)
            assert f is not None
            assert f.severity == "warn", f"{fid} expected warn, got {f.severity}"

    def test_pyproject_no_project_table_warns(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-002")
        assert f is not None
        assert f.severity == "warn"

    def test_setup_py_only_warns(self, tmp_path: Path):
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-003")
        assert f is not None
        assert f.severity == "warn"

    def test_changelog_bad_format_warns(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "CHANGELOG.md").write_text("# Changes\n- did something\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-011")
        assert f is not None
        assert f.severity == "warn"


class TestProjectStructureMixed:
    """Project with a mix of pass, warn, and fail findings."""

    def test_mixed_score(self, tmp_path: Path):
        # Has pyproject.toml with [project] (pass), LICENSE (pass),
        # README with install only (2 warn: missing usage, license sections),
        # no CHANGELOG (1 warn)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "LICENSE").write_text("MIT\n")
        (tmp_path / "README.md").write_text("# X\n## Installation\npip install x\n")
        result = Checker().run(tmp_path)

        severities = {f.severity for f in result.findings}
        assert "pass" in severities
        assert "warn" in severities
        # 3 warns: missing usage, missing license section, missing changelog
        assert result.score == 70

    def test_mixed_has_both_pass_and_warn_findings(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "LICENSE").write_text("MIT\n")
        (tmp_path / "README.md").write_text("# X\n## Installation\npip install x\n")
        result = Checker().run(tmp_path)

        pass_count = sum(1 for f in result.findings if f.severity == "pass")
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert pass_count >= 3
        assert warn_count >= 2


class TestProjectStructureFilePath:
    """Validate that file_path is populated on findings."""

    def test_pyproject_findings_have_file_path(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-001")
        assert f is not None
        assert f.file_path == "pyproject.toml"

    def test_readme_findings_have_file_path(self, tmp_path: Path):
        (tmp_path / "README.md").write_text("# X\n## Installation\n## Usage\n## License\n")
        result = Checker().run(tmp_path)
        for fid in ("PROJ-006", "PROJ-007", "PROJ-008", "PROJ-009"):
            f = _finding_by_id(result, fid)
            assert f is not None
            assert f.file_path == "README.md", f"{fid} file_path should be README.md"

    def test_license_finding_has_file_path(self, tmp_path: Path):
        (tmp_path / "LICENSE.txt").write_text("MIT\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-005")
        assert f is not None
        assert f.file_path == "LICENSE.txt"

    def test_changelog_findings_have_file_path(self, tmp_path: Path):
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n## [1.0.0]\n### Added\n- stuff\n")
        result = Checker().run(tmp_path)
        for fid in ("PROJ-010", "PROJ-011"):
            f = _finding_by_id(result, fid)
            assert f is not None
            assert f.file_path == "CHANGELOG.md"

    def test_setup_py_finding_has_file_path(self, tmp_path: Path):
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-003")
        assert f is not None
        assert f.file_path == "setup.py"

    def test_src_layout_finding_has_file_path(self, tmp_path: Path):
        src = tmp_path / "src" / "pkg"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-004")
        assert f is not None
        assert f.file_path == "src"

    def test_missing_license_has_no_file_path(self, tmp_path: Path):
        """Missing files should have None file_path (repo-level finding)."""
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-005")
        assert f is not None
        assert f.file_path is None


class TestProjectStructureEdgeCases:
    def test_licence_british_spelling(self, tmp_path: Path):
        (tmp_path / "LICENCE").write_text("MIT\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-005")
        assert f is not None
        assert f.severity == "pass"

    def test_readme_rst(self, tmp_path: Path):
        (tmp_path / "README.rst").write_text(
            "Title\n=====\n\nInstallation\n------------\nUsage\n-----\n\nLicense\n-------\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-006")
        assert f is not None
        assert f.severity == "pass"
        assert f.file_path == "README.rst"

    def test_both_setup_py_and_pyproject(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-003")
        assert f is not None
        assert f.severity == "pass"

    def test_flat_package_layout(self, tmp_path: Path):
        pkg = tmp_path / "mypackage"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "PROJ-004")
        assert f is not None
        assert f.severity == "pass"
        assert f.message == "Flat package layout detected"
