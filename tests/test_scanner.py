"""Tests for decipher.scanner."""

import os
import tempfile

from decipher.scanner import ScanResult, scan_codebase


class TestScanCodebase:
    def test_scan_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = scan_codebase(tmpdir, show_progress=False)
            assert result.total_files == 0
            assert result.total_lines == 0

    def test_scan_simple_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal Python project
            with open(os.path.join(tmpdir, "main.py"), "w") as f:
                f.write("print('hello')\n")
            with open(os.path.join(tmpdir, "utils.py"), "w") as f:
                f.write("def helper():\n    pass\n")
            with open(os.path.join(tmpdir, "requirements.txt"), "w") as f:
                f.write("click\nrich\n")

            result = scan_codebase(tmpdir, show_progress=False)

            assert result.total_files >= 2
            assert result.total_lines >= 3
            assert "Python" in result.languages
            assert any("requirements.txt" in k for k in result.dependency_files)
            assert any("main.py" in ep for ep in result.entry_points)

    def test_ignores_pycache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = os.path.join(tmpdir, "__pycache__")
            os.makedirs(cache_dir)
            with open(os.path.join(cache_dir, "module.cpython-310.pyc"), "wb") as f:
                f.write(b"\x00")
            with open(os.path.join(tmpdir, "app.py"), "w") as f:
                f.write("x = 1\n")

            result = scan_codebase(tmpdir, show_progress=False)

            paths = [fi.relative_path for fi in result.files]
            assert not any("__pycache__" in p for p in paths)

    def test_detects_config_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "docker-compose.yml"), "w") as f:
                f.write("version: '3'\n")
            with open(os.path.join(tmpdir, "config.yaml"), "w") as f:
                f.write("debug: true\n")

            result = scan_codebase(tmpdir, show_progress=False)
            config_names = [os.path.basename(c) for c in result.config_files]
            assert "docker-compose.yml" in config_names
            assert "config.yaml" in config_names


class TestScanResult:
    def test_primary_language(self):
        r = ScanResult(root="/test", languages={"Python": 10, "JavaScript": 3})
        assert r.primary_language == "Python"

    def test_primary_language_empty(self):
        r = ScanResult(root="/test")
        assert r.primary_language is None

    def test_summary(self):
        r = ScanResult(
            root="/test",
            total_files=5,
            total_lines=100,
            languages={"Python": 5},
            frameworks=["Flask"],
        )
        summary = r.summary()
        assert "Python" in summary
        assert "Flask" in summary
