"""Tests for the documentation checker."""

from pathlib import Path

from decipher.practices.checkers.python.documentation import Checker


def _finding_by_id(result, finding_id: str):
    """Return the first finding with the given ID, or None."""
    return next((f for f in result.findings if f.id == finding_id), None)


_GOOD_README = """\
# MyProject

A CLI tool for doing useful things with data.

MyProject analyzes input files, produces reports, and integrates
with external services. It supports JSON, CSV, and XML formats.

## Installation

```bash
pip install myproject
```

## Usage

```bash
myproject analyze ./data --format json
myproject report ./data -o report.html
```

## License

MIT
"""

_SHORT_README = "# MyProject\n\nA tool.\n"

_README_NO_SECTIONS = """\
# MyProject

This project is a comprehensive tool for analyzing and processing
large datasets. It supports multiple input formats and produces
detailed reports that can be exported to various output formats
for further analysis and visualization purposes.
"""

_DOCSTRING_PY = '"""Module with a docstring."""\n\ndef hello(): pass\n'
_NO_DOCSTRING_PY = "def hello(): pass\n"


class TestDocumentationPass:
    """Repo with README (install + usage), CHANGELOG, and docstrings."""

    @staticmethod
    def _build_complete(tmp_path: Path) -> Path:
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n## [0.1.0]\n- Init\n")
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Package."""\n')
        (pkg / "core.py").write_text(_DOCSTRING_PY)
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

    def test_readme_in_message(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "DOC-001")
        assert f is not None
        assert "README.md" in f.message

    def test_changelog_in_message(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "DOC-004")
        assert f is not None
        assert "CHANGELOG.md" in f.message

    def test_docstring_coverage_in_message(self, tmp_path: Path):
        repo = self._build_complete(tmp_path)
        result = Checker().run(repo)
        f = _finding_by_id(result, "DOC-005")
        assert f is not None
        assert "100%" in f.message


class TestDocumentationFail:
    """Scenarios that produce fail-severity findings."""

    def test_no_readme_is_fail(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert f is not None
        assert f.severity == "fail"

    def test_no_readme_suppresses_other_checks(self, tmp_path: Path):
        """DOC-002 through DOC-005 should NOT be emitted when no README."""
        result = Checker().run(tmp_path)
        assert len(result.findings) == 1
        assert result.findings[0].id == "DOC-001"

    def test_no_readme_score(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        # 1 fail = 100 - 25 = 75
        assert result.score == 75

    def test_has_recommendations(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        assert len(result.recommendations) >= 1

    def test_short_readme_is_fail(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_SHORT_README)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert f.severity == "fail"
        assert "too short" in f.message.lower()

    def test_short_readme_suppresses_other_checks(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_SHORT_README)
        result = Checker().run(tmp_path)
        assert len(result.findings) == 1
        assert result.findings[0].id == "DOC-001"

    def test_empty_readme_is_fail(self, tmp_path: Path):
        (tmp_path / "README.md").write_text("")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert f.severity == "fail"


class TestDocumentationWarn:
    """Scenarios that produce warn-severity findings."""

    def test_no_install_section_warns(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_README_NO_SECTIONS)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-002")
        assert f is not None
        assert f.severity == "warn"

    def test_no_usage_section_warns(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_README_NO_SECTIONS)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-003")
        assert f is not None
        assert f.severity == "warn"

    def test_no_changelog_warns(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-004")
        assert f is not None
        assert f.severity == "warn"

    def test_low_docstring_coverage_warns(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text(_NO_DOCSTRING_PY)
        (pkg / "b.py").write_text(_NO_DOCSTRING_PY)
        (pkg / "c.py").write_text(_DOCSTRING_PY)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-005")
        assert f is not None
        assert f.severity == "warn"

    def test_zero_docstrings_warns(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "core.py").write_text(_NO_DOCSTRING_PY)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-005")
        assert f.severity == "warn"
        assert "0%" in f.message


class TestDocumentationMixed:
    """Mix of pass and warn findings."""

    def test_readme_good_no_changelog_no_docstrings(self, tmp_path: Path):
        """DOC-001 pass, DOC-002 pass, DOC-003 pass, DOC-004 warn, DOC-005 warn."""
        (tmp_path / "README.md").write_text(_GOOD_README)
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "core.py").write_text(_NO_DOCSTRING_PY)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DOC-001").severity == "pass"
        assert _finding_by_id(result, "DOC-002").severity == "pass"
        assert _finding_by_id(result, "DOC-003").severity == "pass"
        assert _finding_by_id(result, "DOC-004").severity == "warn"
        assert _finding_by_id(result, "DOC-005").severity == "warn"
        assert result.status == "warn"

    def test_readme_no_sections_score(self, tmp_path: Path):
        """DOC-001 pass, DOC-002 warn, DOC-003 warn, DOC-004 warn, DOC-005 pass."""
        (tmp_path / "README.md").write_text(_README_NO_SECTIONS)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        result = Checker().run(tmp_path)
        # No packages → DOC-005 pass (nothing to check)
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        pass_count = sum(1 for f in result.findings if f.severity == "pass")
        assert warn_count == 2  # DOC-002, DOC-003
        assert pass_count == 3  # DOC-001, DOC-004, DOC-005
        # 2 warns = 100 - 20 = 80
        assert result.score == 80

    def test_all_warnings_score(self, tmp_path: Path):
        """DOC-001 pass, rest all warn: score = 60."""
        (tmp_path / "README.md").write_text(_README_NO_SECTIONS)
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "core.py").write_text(_NO_DOCSTRING_PY)
        result = Checker().run(tmp_path)
        warn_count = sum(1 for f in result.findings if f.severity == "warn")
        assert warn_count == 4  # DOC-002, DOC-003, DOC-004, DOC-005
        assert result.score == 60

    def test_readme_with_install_only(self, tmp_path: Path):
        """Has install section but no usage."""
        readme = (
            "# MyProject\n\n"
            "A comprehensive tool for data processing that supports "
            "multiple formats and produces detailed reports for analysis.\n\n"
            "## Installation\n\npip install myproject\n"
        )
        (tmp_path / "README.md").write_text(readme)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DOC-002").severity == "pass"
        assert _finding_by_id(result, "DOC-003").severity == "warn"

    def test_readme_with_usage_only(self, tmp_path: Path):
        """Has usage section but no install."""
        readme = (
            "# MyProject\n\n"
            "A comprehensive tool for data processing that supports "
            "multiple formats and produces detailed reports for analysis.\n\n"
            "## Usage\n\nmyproject analyze ./data\n"
        )
        (tmp_path / "README.md").write_text(readme)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DOC-002").severity == "warn"
        assert _finding_by_id(result, "DOC-003").severity == "pass"


class TestDocumentationFilePath:
    """Validate that file_path is populated on findings."""

    def test_readme_present_has_file_path(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert f.file_path == "README.md"

    def test_no_readme_has_no_file_path(self, tmp_path: Path):
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert f.file_path is None

    def test_short_readme_has_file_path(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_SHORT_README)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert f.file_path == "README.md"

    def test_install_finding_points_to_readme(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-002")
        assert f.file_path == "README.md"

    def test_changelog_finding_points_to_changelog(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-004")
        assert f.file_path == "CHANGELOG.md"

    def test_no_changelog_has_no_file_path(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-004")
        assert f.file_path is None

    def test_all_findings_have_file_path_complete_repo(self, tmp_path: Path):
        """In a complete repo, DOC-001 through DOC-004 reference files.
        DOC-005 may not (docstrings don't point to a single file)."""
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        result = Checker().run(tmp_path)
        for f in result.findings:
            if f.id != "DOC-005":
                assert f.file_path is not None, f"Finding {f.id} has file_path=None"


class TestDocumentationEdgeCases:
    def test_readme_rst_recognized(self, tmp_path: Path):
        rst = (
            "MyProject\n=========\n\n"
            "A comprehensive data analysis tool that processes various "
            "input formats and generates detailed reports for review.\n\n"
            "Installation\n------------\n\npip install myproject\n\n"
            "Usage\n-----\n\nmyproject run\n"
        )
        (tmp_path / "README.rst").write_text(rst)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert f.severity == "pass"
        assert "README.rst" in f.message

    def test_readme_txt_recognized(self, tmp_path: Path):
        txt = (
            "MyProject\n\n"
            "A data analysis tool that processes various input formats "
            "and generates detailed reports for review and analysis.\n\n"
            "Installation: pip install myproject\n\n"
            "Usage: myproject run ./data\n"
        )
        (tmp_path / "README.txt").write_text(txt)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert f.severity == "pass"

    def test_readme_no_extension_recognized(self, tmp_path: Path):
        txt = (
            "MyProject\n\n"
            "A data analysis tool that processes various input formats "
            "and generates detailed reports for review and analysis.\n\n"
            "Installation: pip install myproject\n\n"
            "Usage: myproject run ./data\n"
        )
        (tmp_path / "README").write_text(txt)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert f.severity == "pass"

    def test_install_keyword_setup(self, tmp_path: Path):
        """'setup' keyword triggers install detection."""
        readme = (
            "# MyProject\n\n"
            "A tool for data processing and analysis with support for "
            "multiple formats and detailed reporting capabilities.\n\n"
            "## Setup\n\npip install myproject\n"
        )
        (tmp_path / "README.md").write_text(readme)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DOC-002").severity == "pass"

    def test_install_keyword_getting_started(self, tmp_path: Path):
        """'Getting Started' triggers install detection."""
        readme = (
            "# MyProject\n\n"
            "A tool for data processing and analysis with support for "
            "multiple formats and detailed reporting capabilities.\n\n"
            "## Getting Started\n\npip install myproject\n"
        )
        (tmp_path / "README.md").write_text(readme)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DOC-002").severity == "pass"

    def test_install_keyword_prerequisites(self, tmp_path: Path):
        """'Prerequisites' triggers install detection."""
        readme = (
            "# MyProject\n\n"
            "A tool for data processing and analysis with support for "
            "multiple formats and detailed reporting capabilities.\n\n"
            "## Prerequisites\n\nPython 3.10+\n"
        )
        (tmp_path / "README.md").write_text(readme)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DOC-002").severity == "pass"

    def test_usage_keyword_examples(self, tmp_path: Path):
        """'Examples' triggers usage detection."""
        readme = (
            "# MyProject\n\n"
            "A tool for data processing and analysis with support for "
            "multiple formats and detailed reporting capabilities.\n\n"
            "## Examples\n\nmyproject run ./data\n"
        )
        (tmp_path / "README.md").write_text(readme)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DOC-003").severity == "pass"

    def test_usage_keyword_quickstart(self, tmp_path: Path):
        """'Quick Start' triggers usage detection."""
        readme = (
            "# MyProject\n\n"
            "A tool for data processing and analysis with support for "
            "multiple formats and detailed reporting capabilities.\n\n"
            "## Quick Start\n\nmyproject run ./data\n"
        )
        (tmp_path / "README.md").write_text(readme)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DOC-003").severity == "pass"

    def test_usage_keyword_tutorial(self, tmp_path: Path):
        """'Tutorial' triggers usage detection."""
        readme = (
            "# MyProject\n\n"
            "A tool for data processing and analysis with support for "
            "multiple formats and detailed reporting capabilities.\n\n"
            "## Tutorial\n\nStep 1: run myproject\n"
        )
        (tmp_path / "README.md").write_text(readme)
        result = Checker().run(tmp_path)
        assert _finding_by_id(result, "DOC-003").severity == "pass"

    def test_changelog_variant_changes_md(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGES.md").write_text("# Changes\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-004")
        assert f.severity == "pass"
        assert "CHANGES.md" in f.message

    def test_changelog_variant_history_md(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "HISTORY.md").write_text("# History\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-004")
        assert f.severity == "pass"
        assert "HISTORY.md" in f.message

    def test_no_packages_is_pass(self, tmp_path: Path):
        """No Python packages → DOC-005 pass (nothing to check)."""
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-005")
        assert f.severity == "pass"
        assert "No Python package" in f.message

    def test_docstring_syntax_error_skipped(self, tmp_path: Path):
        """Files with syntax errors should not crash the checker."""
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "broken.py").write_text("def foo(\n")  # syntax error
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-005")
        assert f is not None
        # 1 docstring (__init__), 1 broken (no docstring) → 50%
        assert f.severity == "pass"

    def test_docstring_exactly_50_percent(self, tmp_path: Path):
        """50% is the threshold — exactly 50% should pass."""
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "core.py").write_text(_NO_DOCSTRING_PY)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-005")
        assert f.severity == "pass"
        assert "50%" in f.message

    def test_docstring_100_percent(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        (pkg / "core.py").write_text(_DOCSTRING_PY)
        (pkg / "utils.py").write_text('"""Utils module."""\n')
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-005")
        assert f.severity == "pass"
        assert "100%" in f.message

    def test_test_dirs_excluded_from_docstrings(self, tmp_path: Path):
        """Files in tests/ directories should NOT be checked."""
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "__init__.py").write_text("")
        (tests / "test_core.py").write_text(_NO_DOCSTRING_PY)
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-005")
        # Only mypkg counted (1/1 = 100%), tests excluded
        assert f.severity == "pass"
        assert "1/1" in f.message

    def test_finding_count_complete(self, tmp_path: Path):
        """A complete repo should produce exactly 5 findings."""
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "CHANGELOG.md").write_text("# Changelog\n")
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Pkg."""\n')
        result = Checker().run(tmp_path)
        assert len(result.findings) == 5

    def test_checker_result_shape(self, tmp_path: Path):
        (tmp_path / "README.md").write_text(_GOOD_README)
        result = Checker().run(tmp_path)
        assert result.name == "documentation"
        assert result.display_name == "Documentation"
        assert isinstance(result.findings, list)
        assert isinstance(result.recommendations, list)
        assert 0 <= result.score <= 100

    def test_readme_md_takes_priority(self, tmp_path: Path):
        """When both README.md and README.rst exist, .md is preferred."""
        (tmp_path / "README.md").write_text(_GOOD_README)
        (tmp_path / "README.rst").write_text("fallback\n")
        result = Checker().run(tmp_path)
        f = _finding_by_id(result, "DOC-001")
        assert "README.md" in f.message
