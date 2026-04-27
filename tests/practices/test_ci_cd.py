"""Tests for the ci_cd checker."""

from pathlib import Path

from decipher.practices.checkers.python.ci_cd import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


def _write_workflow(tmp_path: Path, filename: str, content: str) -> Path:
    """Create a workflow file under .github/workflows/."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    wf = wf_dir / filename
    wf.write_text(content)
    return wf


# -- Reusable workflow content snippets --

_FULL_CI = """\
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e .[dev]
      - run: ruff check .
      - run: pytest
"""

_MINIMAL_PUSH_ONLY = """\
name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest
"""

_DEPLOY_NO_TESTS = """\
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "deploying"
"""

_UNPINNED_ACTIONS = """\
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@main
      - uses: actions/setup-python@master
      - run: pytest
"""


class TestCiCdPass:
    """Complete CI setup with all best practices."""

    def test_all_pass_status(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        result = Checker().run(tmp_path)
        assert result.status == "pass"
        assert result.score == 100

    def test_all_findings_pass(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        result = Checker().run(tmp_path)
        for f in result.findings:
            assert f.severity == "pass", f"Finding {f.id} has severity {f.severity}"

    def test_no_recommendations(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        result = Checker().run(tmp_path)
        assert result.recommendations == []

    def test_workflow_count(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        _write_workflow(tmp_path, "release.yml", _DEPLOY_NO_TESTS)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-001")
        assert "2 workflow file(s)" in f.message


class TestCiCdFail:
    """No workflows or workflows without tests."""

    def test_no_workflows_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert result.status == "fail"
        f = _finding_by_id(result, "CICD-001")
        assert f is not None
        assert f.severity == "fail"

    def test_no_workflows_suppresses_other_checks(self, tmp_path: Path):
        """CICD-002 through CICD-006 should NOT be emitted when no workflows."""
        result = Checker().run(tmp_path)
        assert len(result.findings) == 1
        assert result.findings[0].id == "CICD-001"

    def test_no_workflows_score(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        # 1 fail = 100 - 25 = 75
        assert result.score == 75

    def test_workflow_without_tests_is_fail(self, tmp_path: Path):
        _write_workflow(tmp_path, "deploy.yml", _DEPLOY_NO_TESTS)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-002")
        assert f is not None
        assert f.severity == "fail"

    def test_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) >= 1


class TestCiCdWarn:
    """Workflows exist but missing optional items."""

    def test_no_linter_warns(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _MINIMAL_PUSH_ONLY)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-003")
        assert f is not None
        assert f.severity == "warn"

    def test_no_pr_trigger_warns(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _MINIMAL_PUSH_ONLY)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-004")
        assert f is not None
        assert f.severity == "warn"

    def test_unpinned_actions_warns(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _UNPINNED_ACTIONS)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-005")
        assert f is not None
        assert f.severity == "warn"
        assert "2 action(s)" in f.message

    def test_no_python_matrix_warns(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _MINIMAL_PUSH_ONLY)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-006")
        assert f is not None
        assert f.severity == "warn"


class TestCiCdMixed:
    """Workflows with a mix of pass and warn/fail findings."""

    def test_push_only_with_tests_no_linter(self, tmp_path: Path):
        """Tests pass, but no linter, no PR trigger, no matrix = 3 warn."""
        _write_workflow(tmp_path, "ci.yml", _MINIMAL_PUSH_ONLY)
        result = Checker().run(tmp_path)
        pass_count = sum(1 for f in result.findings if f.severity == "pass")
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert pass_count >= 2  # CICD-001 (workflows), CICD-002 (tests), CICD-005 (pinned)
        assert warn_count >= 2  # CICD-003 (linter), CICD-004 (PR), CICD-006 (matrix)
        assert result.status == "warn"

    def test_deploy_only_score(self, tmp_path: Path):
        """Deploy workflow without tests: CICD-001 pass, CICD-002 fail, rest warn."""
        _write_workflow(tmp_path, "deploy.yml", _DEPLOY_NO_TESTS)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "CICD-001").severity == "pass"
        assert _finding_by_id(result, "CICD-002").severity == "fail"
        assert result.status == "fail"

    def test_full_ci_plus_deploy(self, tmp_path: Path):
        """Full CI + deploy workflow: all should pass because CI covers everything."""
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        _write_workflow(tmp_path, "deploy.yml", _DEPLOY_NO_TESTS)
        result = Checker().run(tmp_path)
        assert result.status == "pass"
        assert result.score == 100


class TestCiCdFilePath:
    """Validate that file_path is populated on findings."""

    def test_workflows_present_has_dir_path(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-001")
        assert f.file_path == ".github/workflows"

    def test_no_workflows_has_no_file_path(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-001")
        assert f.file_path is None

    def test_tests_finding_points_to_workflow(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-002")
        assert f.file_path == ".github/workflows/ci.yml"

    def test_linter_finding_points_to_workflow(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-003")
        assert f.file_path == ".github/workflows/ci.yml"

    def test_pr_trigger_finding_points_to_workflow(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-004")
        assert f.file_path == ".github/workflows/ci.yml"

    def test_matrix_finding_points_to_workflow(self, tmp_path: Path):
        _write_workflow(tmp_path, "ci.yml", _FULL_CI)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-006")
        assert f.file_path == ".github/workflows/ci.yml"

    def test_unpinned_action_points_to_offending_file(self, tmp_path: Path):
        _write_workflow(tmp_path, "good.yml", _FULL_CI)
        _write_workflow(tmp_path, "bad.yml", _UNPINNED_ACTIONS)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-005")
        assert f is not None
        assert f.severity == "warn"
        assert f.file_path == ".github/workflows/bad.yml"

    def test_missing_tests_has_no_file_path(self, tmp_path: Path):
        _write_workflow(tmp_path, "deploy.yml", _DEPLOY_NO_TESTS)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-002")
        assert f.file_path is None


class TestCiCdEdgeCases:
    def test_yaml_extension(self, tmp_path: Path):
        """Workflow files with .yaml extension should be found."""
        _write_workflow(tmp_path, "ci.yaml", _FULL_CI)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-001")
        assert f.severity == "pass"

    def test_tox_as_test_runner(self, tmp_path: Path):
        wf = (
            "name: CI\non: [push]\njobs:\n  test:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - run: tox\n"
        )
        _write_workflow(tmp_path, "ci.yml", wf)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "CICD-002").severity == "pass"

    def test_nox_as_test_runner(self, tmp_path: Path):
        wf = (
            "name: CI\non: [push]\njobs:\n  test:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - run: nox\n"
        )
        _write_workflow(tmp_path, "ci.yml", wf)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "CICD-002").severity == "pass"

    def test_make_test_as_test_runner(self, tmp_path: Path):
        wf = (
            "name: CI\non: [push]\njobs:\n  test:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: make test\n"
        )
        _write_workflow(tmp_path, "ci.yml", wf)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "CICD-002").severity == "pass"

    def test_flake8_as_linter(self, tmp_path: Path):
        wf = (
            "name: CI\non: [push]\njobs:\n  lint:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - run: flake8 .\n"
            "      - run: pytest\n"
        )
        _write_workflow(tmp_path, "ci.yml", wf)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "CICD-003").severity == "pass"

    def test_ruff_check_as_linter(self, tmp_path: Path):
        wf = (
            "name: CI\non: [push]\njobs:\n  lint:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: ruff check .\n"
            "      - run: pytest\n"
        )
        _write_workflow(tmp_path, "ci.yml", wf)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "CICD-003").severity == "pass"

    def test_sha_pinned_actions(self, tmp_path: Path):
        wf = (
            "name: CI\non: [push, pull_request]\njobs:\n  test:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11\n"
            "      - run: pytest\n"
        )
        _write_workflow(tmp_path, "ci.yml", wf)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-005")
        assert f is not None
        assert f.severity == "pass"

    def test_no_uses_directives_skips_pin_check(self, tmp_path: Path):
        """Workflow with only run: steps and no uses: should skip CICD-005."""
        wf = (
            "name: CI\non: [push]\njobs:\n  test:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: pytest\n"
        )
        _write_workflow(tmp_path, "ci.yml", wf)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-005")
        assert f is None

    def test_test_found_across_multiple_workflows(self, tmp_path: Path):
        """Tests in one workflow, linter in another — both should pass."""
        wf_test = (
            "name: Test\non: [push]\njobs:\n  test:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - run: pytest\n"
        )
        wf_lint = (
            "name: Lint\non: [push]\njobs:\n  lint:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - run: ruff check .\n"
        )
        _write_workflow(tmp_path, "test.yml", wf_test)
        _write_workflow(tmp_path, "lint.yml", wf_lint)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "CICD-002").severity == "pass"
        assert _finding_by_id(result, "CICD-003").severity == "pass"

    def test_python_m_pytest(self, tmp_path: Path):
        wf = (
            "name: CI\non: [push]\njobs:\n  test:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: python -m pytest\n"
        )
        _write_workflow(tmp_path, "ci.yml", wf)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "CICD-002").severity == "pass"

    def test_dev_branch_ref_is_unpinned(self, tmp_path: Path):
        wf = (
            "name: CI\non: [push]\njobs:\n  test:\n"
            "    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@dev\n"
            "      - run: pytest\n"
        )
        _write_workflow(tmp_path, "ci.yml", wf)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "CICD-005")
        assert f is not None
        assert f.severity == "warn"
