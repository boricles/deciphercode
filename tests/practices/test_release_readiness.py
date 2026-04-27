"""Tests for the release_readiness checker."""

from pathlib import Path

from decipher.practices.checkers.python.release_readiness import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


_COMPLETE_PYPROJECT = """\
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "mypkg"
version = "1.0.0"
readme = "README.md"
requires-python = ">=3.10"
authors = [{name = "Test Author"}]
classifiers = [
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
]
"""

_MINIMAL_PROJECT = """\
[project]
name = "x"
"""


class TestReleaseReadinessPass:
    """Repo with a complete pyproject.toml."""

    @staticmethod
    def _build_complete(tmp_path: Path) -> Path:
        (tmp_path / "pyproject.toml").write_text(_COMPLETE_PYPROJECT)
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

    def test_version_in_message(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "REL-002")
        assert f is not None
        assert "1.0.0" in f.message

    def test_build_backend_in_message(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "REL-003")
        assert f is not None
        assert "setuptools" in f.message


class TestReleaseReadinessFail:
    """No pyproject.toml at all."""

    def test_no_pyproject_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-001")
        assert f is not None
        assert f.severity == "fail"

    def test_no_pyproject_suppresses_other_checks(self, tmp_path: Path):
        """REL-002 through REL-007 should NOT be emitted when no pyproject.toml."""
        result = Checker().run(tmp_path)
        assert len(result.findings) == 1
        assert result.findings[0].id == "REL-001"

    def test_no_pyproject_score(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        # 1 fail = 100 - 25 = 75
        assert result.score == 75

    def test_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) >= 1

    def test_no_project_table_is_fail(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 80\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-001")
        assert f.severity == "fail"
        assert "no [project]" in f.message

    def test_no_project_table_suppresses_other_checks(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 80\n")
        result = Checker().run(tmp_path)
        assert len(result.findings) == 1

    def test_missing_version_is_fail(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(_MINIMAL_PROJECT)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-002")
        assert f is not None
        assert f.severity == "fail"

    def test_missing_build_backend_is_fail(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.1.0"\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-003")
        assert f is not None
        assert f.severity == "fail"


class TestReleaseReadinessWarn:
    """pyproject.toml present but with missing optional fields."""

    @staticmethod
    def _write_versioned(tmp_path: Path, extra: str = "") -> Path:
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["setuptools"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            "[project]\n"
            'name = "x"\n'
            'version = "0.1.0"\n' + extra
        )
        return tmp_path

    def test_no_classifiers_warns(self, tmp_path: Path):
        self._write_versioned(tmp_path)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-004")
        assert f is not None
        assert f.severity == "warn"

    def test_no_readme_warns(self, tmp_path: Path):
        self._write_versioned(tmp_path)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-005")
        assert f is not None
        assert f.severity == "warn"

    def test_no_authors_warns(self, tmp_path: Path):
        self._write_versioned(tmp_path)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-006")
        assert f is not None
        assert f.severity == "warn"

    def test_no_python_requires_warns(self, tmp_path: Path):
        self._write_versioned(tmp_path)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-007")
        assert f is not None
        assert f.severity == "warn"


class TestReleaseReadinessMixed:
    """Mix of pass and warn/fail findings."""

    def test_minimal_project_no_build(self, tmp_path: Path):
        """REL-001 pass, REL-002 fail (no version), REL-003 fail, rest warn."""
        (tmp_path / "pyproject.toml").write_text(_MINIMAL_PROJECT)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "REL-001").severity == "pass"
        assert _finding_by_id(result, "REL-002").severity == "fail"
        assert _finding_by_id(result, "REL-003").severity == "fail"
        assert result.status == "fail"

    def test_versioned_no_extras(self, tmp_path: Path):
        """Version + build present, no classifiers/readme/author/python-requires."""
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["setuptools"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            "[project]\n"
            'name = "x"\n'
            'version = "0.1.0"\n'
        )
        result = Checker().run(tmp_path)
        pass_count = sum(1 for f in result.findings if f.severity == "pass")
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert pass_count == 3  # REL-001, REL-002, REL-003
        assert warn_count == 4  # REL-004, REL-005, REL-006, REL-007
        assert result.status == "warn"
        # 4 warn = 100 - 40 = 60
        assert result.score == 60

    def test_almost_complete(self, tmp_path: Path):
        """Everything except classifiers."""
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["setuptools"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            "[project]\n"
            'name = "x"\n'
            'version = "0.1.0"\n'
            'readme = "README.md"\n'
            'requires-python = ">=3.10"\n'
            'authors = [{name = "A"}]\n'
        )
        result = Checker().run(tmp_path)
        assert result.status == "warn"
        assert result.score == 90  # 1 warn


class TestReleaseReadinessFilePath:
    """Validate that file_path is populated on findings."""

    def test_pyproject_present_has_file_path(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(_COMPLETE_PYPROJECT)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-001")
        assert f.file_path == "pyproject.toml"

    def test_no_pyproject_has_no_file_path(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-001")
        assert f.file_path is None

    def test_no_project_table_has_file_path(self, tmp_path: Path):
        """pyproject.toml exists but missing [project] — still points to file."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-001")
        assert f.file_path == "pyproject.toml"

    def test_version_finding_points_to_pyproject(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(_COMPLETE_PYPROJECT)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-002")
        assert f.file_path == "pyproject.toml"

    def test_all_findings_point_to_pyproject(self, tmp_path: Path):
        """When pyproject.toml exists, all findings should reference it."""
        (tmp_path / "pyproject.toml").write_text(_COMPLETE_PYPROJECT)
        result = Checker().run(tmp_path)
        for f in result.findings:
            assert f.file_path == "pyproject.toml", f"Finding {f.id} has file_path={f.file_path}"


class TestReleaseReadinessEdgeCases:
    def test_dynamic_version(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\ndynamic = ["version"]\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-002")
        assert f.severity == "pass"
        assert "dynamic" in f.message

    def test_build_system_missing_requires(self, tmp_path: Path):
        """build-backend without requires is incomplete."""
        (tmp_path / "pyproject.toml").write_text(
            '[build-system]\nbuild-backend = "setuptools.build_meta"\n\n'
            '[project]\nname = "x"\nversion = "0.1.0"\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-003")
        assert f.severity == "fail"

    def test_build_system_missing_backend(self, tmp_path: Path):
        """requires without build-backend is incomplete."""
        (tmp_path / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["setuptools"]\n\n'
            '[project]\nname = "x"\nversion = "0.1.0"\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-003")
        assert f.severity == "fail"

    def test_readme_as_dict(self, tmp_path: Path):
        """PEP 621: readme = {file = "README.md", content-type = "text/markdown"}."""
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "x"\n'
            'version = "0.1.0"\n'
            "\n[project.readme]\n"
            'file = "README.md"\n'
            'content-type = "text/markdown"\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-005")
        assert f.severity == "pass"
        assert "README.md" in f.message

    def test_maintainers_instead_of_authors(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\nmaintainers = [{name = "M"}]\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-006")
        assert f.severity == "pass"
        assert "maintainers" in f.message

    def test_empty_classifiers_list(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\nclassifiers = []\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-004")
        assert f.severity == "warn"

    def test_empty_authors_list(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\nauthors = []\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-006")
        assert f.severity == "warn"

    def test_hatchling_backend(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["hatchling"]\n'
            'build-backend = "hatchling.build"\n\n'
            "[project]\n"
            'name = "x"\n'
            'version = "0.1.0"\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-003")
        assert f.severity == "pass"
        assert "hatchling" in f.message

    def test_flit_backend(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["flit_core>=3.2"]\n'
            'build-backend = "flit_core.buildapi"\n\n'
            "[project]\n"
            'name = "x"\n'
            'version = "0.1.0"\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-003")
        assert f.severity == "pass"
        assert "flit" in f.message

    def test_finding_count_complete(self, tmp_path: Path):
        """A complete pyproject.toml should produce exactly 7 findings."""
        (tmp_path / "pyproject.toml").write_text(_COMPLETE_PYPROJECT)
        result = Checker().run(tmp_path)
        assert len(result.findings) == 7

    def test_classifier_count_in_message(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "x"\n'
            'version = "0.1.0"\n'
            "classifiers = [\n"
            '    "Development Status :: 3 - Alpha",\n'
            '    "Programming Language :: Python :: 3",\n'
            '    "License :: OSI Approved :: MIT License",\n'
            "]\n"
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-004")
        assert "3 classifier(s)" in f.message

    def test_requires_python_in_message(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\nrequires-python = ">=3.10"\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "REL-007")
        assert ">=3.10" in f.message
