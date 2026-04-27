"""Tests for the testing checker."""

from pathlib import Path

from decipher.practices.checkers.python.testing import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


class TestTestingPass:
    """Complete project with tests, pytest config, coverage, and threshold."""

    @staticmethod
    def _build_complete(tmp_path: Path) -> Path:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\n"
            'testpaths = ["tests"]\n\n'
            "[tool.coverage.run]\n"
            'source = ["mypackage"]\n\n'
            "[tool.coverage.report]\n"
            "fail_under = 80\n"
        )
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")
        (tests / "test_core.py").write_text("def test_one(): pass\n")
        (tests / "test_utils.py").write_text("def test_two(): pass\n")
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

    def test_test_count_reported(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "TEST-002")
        assert f is not None
        assert "2 test file(s)" in f.message


class TestTestingFail:
    """Empty repo should produce fail findings for critical items."""

    def test_empty_repo_score(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert result.status == "fail"
        # 2 fails (tests dir, test files) + 3 warns (pytest, coverage, threshold)
        # 100 - 50 - 30 = 20
        assert result.score == 20

    def test_missing_tests_dir_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-001")
        assert f is not None
        assert f.severity == "fail"

    def test_no_test_files_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-002")
        assert f is not None
        assert f.severity == "fail"

    def test_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) >= 3

    def test_tests_dir_exists_but_empty(self, tmp_path: Path):
        """tests/ present but no test files → TEST-001 pass, TEST-002 fail."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "__init__.py").write_text("")
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "TEST-001").severity == "pass"
        assert _finding_by_id(result, "TEST-002").severity == "fail"


class TestTestingWarn:
    """Tests exist but optional config is missing."""

    def test_no_pytest_config_warns(self, tmp_path: Path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_a(): pass\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-003")
        assert f is not None
        assert f.severity == "warn"

    def test_no_coverage_config_warns(self, tmp_path: Path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_a(): pass\n")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-004")
        assert f is not None
        assert f.severity == "warn"

    def test_no_coverage_threshold_warns(self, tmp_path: Path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_a(): pass\n")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
            "\n[tool.coverage.run]\nsource = ['pkg']\n"
        )
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "TEST-004").severity == "pass"
        f = _finding_by_id(result, "TEST-005")
        assert f is not None
        assert f.severity == "warn"


class TestTestingMixed:
    """Project with a mix of pass and warn findings."""

    def test_tests_exist_but_no_coverage(self, tmp_path: Path):
        """Tests dir + files + pytest config = 3 pass; no coverage = 2 warn."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("def test_main(): pass\n")
        result = Checker().run(tmp_path)

        pass_count = sum(1 for f in result.findings if f.severity == "pass")
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert pass_count == 3  # TEST-001, TEST-002, TEST-003
        assert warn_count == 2  # TEST-004, TEST-005
        assert result.score == 80
        assert result.status == "warn"

    def test_coverage_configured_but_no_threshold(self, tmp_path: Path):
        """4 pass (dir, files, pytest, coverage) + 1 warn (threshold)."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n\n'
            "[tool.coverage.run]\nsource = ['pkg']\n"
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("def test_a(): pass\n")
        result = Checker().run(tmp_path)

        pass_count = sum(1 for f in result.findings if f.severity == "pass")
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert pass_count == 4
        assert warn_count == 1
        assert result.score == 90


class TestTestingFilePath:
    """Validate that file_path is populated on findings."""

    def test_tests_dir_finding_has_file_path(self, tmp_path: Path):
        (tmp_path / "tests").mkdir()
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-001")
        assert f is not None
        assert f.file_path == "tests"

    def test_test_dir_singular_has_file_path(self, tmp_path: Path):
        (tmp_path / "test").mkdir()
        (tmp_path / "test" / "test_a.py").write_text("def test_a(): pass\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-001")
        assert f is not None
        assert f.file_path == "test"

    def test_pytest_config_finding_has_file_path(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
        )
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-003")
        assert f is not None
        assert f.file_path == "pyproject.toml"

    def test_pytest_ini_finding_has_file_path(self, tmp_path: Path):
        (tmp_path / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-003")
        assert f is not None
        assert f.file_path == "pytest.ini"

    def test_coverage_config_finding_has_file_path(self, tmp_path: Path):
        (tmp_path / ".coveragerc").write_text("[run]\nsource = mypackage\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-004")
        assert f is not None
        assert f.file_path == ".coveragerc"

    def test_missing_tests_dir_has_no_file_path(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-001")
        assert f is not None
        assert f.file_path is None


class TestTestingEdgeCases:
    def test_test_dir_singular(self, tmp_path: Path):
        """test/ (singular) should be accepted."""
        (tmp_path / "test").mkdir()
        (tmp_path / "test" / "test_a.py").write_text("def test_a(): pass\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-001")
        assert f.severity == "pass"
        assert f.message == "test/ directory found"

    def test_setup_cfg_pytest_config(self, tmp_path: Path):
        (tmp_path / "setup.cfg").write_text("[tool:pytest]\ntestpaths = tests\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-003")
        assert f.severity == "pass"
        assert f.file_path == "setup.cfg"

    def test_setup_cfg_coverage(self, tmp_path: Path):
        (tmp_path / "setup.cfg").write_text("[coverage:run]\nsource = mypackage\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-004")
        assert f.severity == "pass"
        assert f.file_path == "setup.cfg"

    def test_addopts_cov(self, tmp_path: Path):
        """--cov in addopts should count as coverage configured."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\naddopts = "--cov=mypackage"\n'
        )
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "TEST-004").severity == "pass"

    def test_addopts_cov_fail_under(self, tmp_path: Path):
        """--cov-fail-under in addopts should count as threshold set."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\naddopts = "--cov=pkg --cov-fail-under=80"\n'
        )
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "TEST-005").severity == "pass"

    def test_coveragerc_fail_under(self, tmp_path: Path):
        (tmp_path / ".coveragerc").write_text(
            "[run]\nsource = mypackage\n\n[report]\nfail_under = 80\n"
        )
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "TEST-004").severity == "pass"
        assert _finding_by_id(result, "TEST-005").severity == "pass"

    def test_ignores_venv_test_files(self, tmp_path: Path):
        """Test files inside .venv should not be counted."""
        venv = tmp_path / ".venv" / "lib" / "site-packages" / "somepkg"
        venv.mkdir(parents=True)
        (venv / "test_internal.py").write_text("def test_x(): pass\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-002")
        assert f.severity == "fail"  # should be 0 test files

    def test_nested_test_files_counted(self, tmp_path: Path):
        """Test files in subdirectories of tests/ should be counted."""
        sub = tmp_path / "tests" / "unit"
        sub.mkdir(parents=True)
        (sub / "test_a.py").write_text("def test_a(): pass\n")
        (sub / "test_b.py").write_text("def test_b(): pass\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-002")
        assert f.severity == "pass"
        assert "2 test file(s)" in f.message

    def test_suffix_test_pattern(self, tmp_path: Path):
        """Files ending with _test.py should be counted."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "core_test.py").write_text("def test_core(): pass\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "TEST-002")
        assert f.severity == "pass"
        assert "1 test file(s)" in f.message
