"""Tests for the dependency_hygiene checker."""

from pathlib import Path

from decipher.practices.checkers.python.dependency_hygiene import Checker


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
dependencies = [
    "click>=8.1",
    "rich>=13.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff>=0.4",
]
"""

_MINIMAL_PROJECT = """\
[project]
name = "x"
"""


class TestDependencyHygienePass:
    """Repo with proper deps, lock file, no duplicates, grouped optionals."""

    @staticmethod
    def _build_complete(tmp_path: Path) -> Path:
        (tmp_path / "pyproject.toml").write_text(_COMPLETE_PYPROJECT)
        (tmp_path / "uv.lock").write_text("# lock\n")
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

    def test_dep_count_in_message(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "DEP-001")
        assert f is not None
        assert "3 dependency" in f.message

    def test_lock_file_in_message(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "DEP-003")
        assert f is not None
        assert "uv.lock" in f.message

    def test_optional_groups_in_message(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "DEP-005")
        assert f is not None
        assert "dev" in f.message
        assert "2 package" in f.message


class TestDependencyHygieneFail:
    """Scenarios that produce fail-severity findings."""

    def test_no_pyproject_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-001")
        assert f is not None
        assert f.severity == "fail"

    def test_no_pyproject_suppresses_other_checks(self, tmp_path: Path):
        """DEP-002 through DEP-005 should NOT be emitted when no pyproject.toml."""
        result = Checker().run(tmp_path)
        assert len(result.findings) == 1
        assert result.findings[0].id == "DEP-001"

    def test_no_pyproject_score(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        # 1 fail = 100 - 25 = 75
        assert result.score == 75

    def test_no_deps_field_is_fail(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(_MINIMAL_PROJECT)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-001")
        assert f.severity == "fail"

    def test_no_deps_field_suppresses_other_checks(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(_MINIMAL_PROJECT)
        result = Checker().run(tmp_path)
        assert len(result.findings) == 1
        assert result.findings[0].id == "DEP-001"

    def test_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) >= 1

    def test_duplicate_deps_is_fail(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = [\n    "click>=8.1",\n    "click>=9.0",\n]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-004")
        assert f is not None
        assert f.severity == "fail"
        assert "click" in f.message

    def test_duplicate_with_normalization(self, tmp_path: Path):
        """PyYAML and pyyaml are the same package."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = [\n    "PyYAML>=6.0",\n    "pyyaml>=6.0.1",\n]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-004")
        assert f.severity == "fail"


class TestDependencyHygieneWarn:
    """Scenarios that produce warn-severity findings."""

    def test_unbounded_dep_warns(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-002")
        assert f is not None
        assert f.severity == "warn"
        assert "click" in f.message

    def test_multiple_unbounded_warns(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click", "rich"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-002")
        assert f.severity == "warn"
        assert "2 unbounded" in f.message

    def test_no_lock_file_warns(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-003")
        assert f is not None
        assert f.severity == "warn"

    def test_empty_optional_deps_warns(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n\n'
            "[project.optional-dependencies]\n"
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-005")
        assert f is not None
        assert f.severity == "warn"

    def test_empty_group_in_optional_deps_warns(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n\n'
            "[project.optional-dependencies]\n"
            "dev = []\n"
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-005")
        assert f.severity == "warn"
        assert "dev" in f.message


class TestDependencyHygieneMixed:
    """Mix of pass, warn, and fail findings."""

    def test_deps_present_but_unbounded_and_no_lock(self, tmp_path: Path):
        """DEP-001 pass, DEP-002 warn, DEP-003 warn, DEP-004 pass, DEP-005 pass."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click"]\n'
        )
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DEP-001").severity == "pass"
        assert _finding_by_id(result, "DEP-002").severity == "warn"
        assert _finding_by_id(result, "DEP-003").severity == "warn"
        assert result.status == "warn"

    def test_mixed_score(self, tmp_path: Path):
        """2 warns = 100 - 20 = 80."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click"]\n'
        )
        result = Checker().run(tmp_path)
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert warn_count == 2  # DEP-002, DEP-003
        assert result.score == 80

    def test_duplicates_and_no_lock(self, tmp_path: Path):
        """DEP-001 pass, DEP-002 pass, DEP-003 warn, DEP-004 fail, DEP-005 pass."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = [\n    "click>=8.1",\n    "click>=9.0",\n]\n'
        )
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DEP-003").severity == "warn"
        assert _finding_by_id(result, "DEP-004").severity == "fail"
        assert result.status == "fail"
        # 1 warn + 1 fail = 100 - 10 - 25 = 65
        assert result.score == 65

    def test_all_good_except_no_lock(self, tmp_path: Path):
        """Only DEP-003 warns; everything else passes."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        result = Checker().run(tmp_path)
        pass_count = sum(1 for f in result.findings if f.severity == "pass")
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert pass_count == 4  # DEP-001, DEP-002, DEP-004, DEP-005
        assert warn_count == 1  # DEP-003
        assert result.score == 90

    def test_perfect_except_empty_optional_group(self, tmp_path: Path):
        """Lock present, versions bounded, but an empty optional group."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n\n'
            "[project.optional-dependencies]\n"
            "dev = []\n"
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DEP-005").severity == "warn"
        assert result.status == "warn"
        assert result.score == 90


class TestDependencyHygieneFilePath:
    """Validate that file_path is populated on findings."""

    def test_deps_present_has_file_path(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-001")
        assert f.file_path == "pyproject.toml"

    def test_no_pyproject_has_no_file_path(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-001")
        assert f.file_path is None

    def test_no_deps_field_has_file_path(self, tmp_path: Path):
        """pyproject.toml exists but missing dependencies — still points to file."""
        (tmp_path / "pyproject.toml").write_text(_MINIMAL_PROJECT)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-001")
        assert f.file_path == "pyproject.toml"

    def test_lock_file_finding_points_to_lock(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "poetry.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-003")
        assert f.file_path == "poetry.lock"

    def test_no_lock_has_no_file_path(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-003")
        assert f.file_path is None

    def test_all_findings_point_to_pyproject(self, tmp_path: Path):
        """When deps declared with lock, all findings should reference a file."""
        (tmp_path / "pyproject.toml").write_text(_COMPLETE_PYPROJECT)
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        for f in result.findings:
            assert f.file_path is not None, f"Finding {f.id} has file_path=None"

    def test_requirements_txt_lock_proxy_file_path(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "requirements.txt").write_text("click==8.1.7\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-003")
        assert f.file_path == "requirements.txt"


class TestDependencyHygieneEdgeCases:
    def test_empty_deps_list(self, tmp_path: Path):
        """Empty dependencies = [] is valid (meta-package)."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\ndependencies = []\n')
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-001")
        assert f.severity == "pass"
        assert "empty" in f.message

    def test_dep_with_extras_has_version(self, tmp_path: Path):
        """'uvicorn[standard]>=0.20' should count as versioned."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["uvicorn[standard]>=0.20"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-002")
        assert f.severity == "pass"

    def test_dep_with_extras_no_version(self, tmp_path: Path):
        """'uvicorn[standard]' without version should be flagged."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["uvicorn[standard]"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-002")
        assert f.severity == "warn"

    def test_dep_with_env_marker_has_version(self, tmp_path: Path):
        """'pywin32>=300; sys_platform == \"win32\"' should count as versioned."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = [\n'
            '    "pywin32>=300; sys_platform == \\"win32\\"",\n'
            "]\n"
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-002")
        assert f.severity == "pass"

    def test_dep_with_env_marker_no_version(self, tmp_path: Path):
        """'pywin32; sys_platform == \"win32\"' should be flagged."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = [\n'
            '    "pywin32; sys_platform == \\"win32\\"",\n'
            "]\n"
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-002")
        assert f.severity == "warn"

    def test_exact_pin_is_versioned(self, tmp_path: Path):
        """'click==8.1.7' counts as versioned."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click==8.1.7"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-002")
        assert f.severity == "pass"

    def test_compatible_release_is_versioned(self, tmp_path: Path):
        """'click~=8.1' counts as versioned."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click~=8.1"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-002")
        assert f.severity == "pass"

    def test_poetry_lock_recognized(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "poetry.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-003")
        assert f.severity == "pass"
        assert "poetry.lock" in f.message

    def test_pdm_lock_recognized(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "pdm.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-003")
        assert f.severity == "pass"
        assert "pdm.lock" in f.message

    def test_requirements_txt_without_pins_not_lock(self, tmp_path: Path):
        """requirements.txt with only >= specifiers is NOT a lock proxy."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "requirements.txt").write_text("click>=8.1\nrich>=13.0\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-003")
        assert f.severity == "warn"

    def test_requirements_txt_with_pins_is_lock(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "requirements.txt").write_text("click==8.1.7\nrich==13.7.0\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-003")
        assert f.severity == "pass"

    def test_duplicate_with_underscores_vs_dashes(self, tmp_path: Path):
        """my_pkg and my-pkg are the same package per PEP 503."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = [\n    "my_pkg>=1.0",\n    "my-pkg>=2.0",\n]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-004")
        assert f.severity == "fail"

    def test_multiple_optional_groups(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n\n'
            "[project.optional-dependencies]\n"
            'dev = ["pytest>=7.0"]\n'
            'docs = ["sphinx>=7.0"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-005")
        assert f.severity == "pass"
        assert "dev" in f.message
        assert "docs" in f.message
        assert "2 optional group" in f.message

    def test_finding_count_complete(self, tmp_path: Path):
        """A complete repo should produce exactly 5 findings."""
        (tmp_path / "pyproject.toml").write_text(_COMPLETE_PYPROJECT)
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        assert len(result.findings) == 5

    def test_no_optional_deps_is_pass(self, tmp_path: Path):
        """Omitting optional-dependencies entirely is not a warning."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-005")
        assert f.severity == "pass"

    def test_uv_lock_takes_priority_over_poetry(self, tmp_path: Path):
        """When both uv.lock and poetry.lock exist, uv.lock is preferred."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\ndependencies = ["click>=8.1"]\n'
        )
        (tmp_path / "uv.lock").write_text("# lock\n")
        (tmp_path / "poetry.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DEP-003")
        assert "uv.lock" in f.message

    def test_checker_result_shape(self, tmp_path: Path):
        """CheckerResult has all expected fields."""
        (tmp_path / "pyproject.toml").write_text(_COMPLETE_PYPROJECT)
        (tmp_path / "uv.lock").write_text("# lock\n")
        result = Checker().run(tmp_path)
        assert result.name == "dependency_hygiene"
        assert result.display_name == "Dependency Hygiene"
        assert isinstance(result.findings, list)
        assert isinstance(result.recommendations, list)
        assert 0 <= result.score <= 100
