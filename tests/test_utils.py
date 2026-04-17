"""Tests for decipher.utils."""

import os
import tempfile

from decipher.utils import (
    build_tree,
    chunk_text,
    count_tokens,
    detect_language,
    is_text_file,
    matches_config_pattern,
    read_file_safe,
    should_ignore,
)


class TestDetectLanguage:
    def test_python(self):
        assert detect_language("app.py") == "Python"

    def test_javascript(self):
        assert detect_language("index.js") == "JavaScript"

    def test_typescript(self):
        assert detect_language("main.ts") == "TypeScript"

    def test_tsx(self):
        assert detect_language("Component.tsx") == "TypeScript (TSX)"

    def test_go(self):
        assert detect_language("main.go") == "Go"

    def test_rust(self):
        assert detect_language("lib.rs") == "Rust"

    def test_unknown(self):
        assert detect_language("file.xyz") is None

    def test_case_insensitive(self):
        assert detect_language("FILE.PY") == "Python"


class TestShouldIgnore:
    def test_git_dir(self):
        assert should_ignore(".git")

    def test_node_modules(self):
        assert should_ignore("node_modules")

    def test_pycache(self):
        assert should_ignore("__pycache__")

    def test_normal_file(self):
        assert not should_ignore("app.py")

    def test_pyc(self):
        assert should_ignore("module.pyc")

    def test_custom_patterns(self):
        assert should_ignore("vendor", ["vendor", "*.log"])
        assert not should_ignore("app.py", ["vendor", "*.log"])


class TestIsTextFile:
    def test_text_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("print('hello')\n")
            f.flush()
            assert is_text_file(f.name)
        os.unlink(f.name)

    def test_binary_file(self):
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(b"\x00\x01\x02\x03\xff")
            f.flush()
            assert not is_text_file(f.name)
        os.unlink(f.name)


class TestReadFileSafe:
    def test_reads_text(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("hello world")
            f.flush()
            content = read_file_safe(f.name)
            assert content == "hello world"
        os.unlink(f.name)

    def test_skips_large(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x" * 1_000_000)
            f.flush()
            assert read_file_safe(f.name, max_size=100) is None
        os.unlink(f.name)

    def test_nonexistent(self):
        assert read_file_safe("/nonexistent/path/file.py") is None


class TestCountTokens:
    def test_short_text(self):
        count = count_tokens("Hello, world!")
        assert count > 0

    def test_empty_string(self):
        assert count_tokens("") == 0


class TestChunkText:
    def test_single_chunk(self):
        text = "line1\nline2\nline3\n"
        chunks = chunk_text(text, max_tokens=1000)
        assert len(chunks) == 1

    def test_multiple_chunks(self):
        text = "\n".join(f"line {i}" * 20 for i in range(100))
        chunks = chunk_text(text, max_tokens=50)
        assert len(chunks) > 1
        # All content should be preserved
        assert "".join(chunks) == text


class TestBuildTree:
    def test_simple(self):
        root = "/project"
        files = ["/project/src/main.py", "/project/src/utils.py", "/project/README.md"]
        tree = build_tree(root, files)
        assert "src/" in tree
        assert "main.py" in tree
        assert "README.md" in tree


class TestMatchesConfigPattern:
    def test_env(self):
        assert matches_config_pattern(".env")

    def test_env_local(self):
        assert matches_config_pattern(".env.local")

    def test_dockerfile(self):
        assert matches_config_pattern("Dockerfile")

    def test_yaml(self):
        assert matches_config_pattern("config.yaml")

    def test_source_file(self):
        assert not matches_config_pattern("app.py")
