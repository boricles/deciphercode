"""Utility functions: file reading, language detection, token counting, helpers."""

from __future__ import annotations

import fnmatch
import logging
import os
from pathlib import Path

import tiktoken

logger = logging.getLogger(__name__)

# Language detection by extension
EXTENSION_MAP: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript (JSX)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (TSX)",
    ".java": "Java",
    ".kt": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".pl": "Perl",
    ".lua": "Lua",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".xml": "XML",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".tf": "Terraform",
    ".hcl": "HCL",
    ".proto": "Protocol Buffers",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".clj": "Clojure",
    ".vue": "Vue",
    ".svelte": "Svelte",
}

# Framework detection patterns: {framework_name: [(file_or_dir_pattern, weight), ...]}
FRAMEWORK_SIGNALS: dict[str, list[tuple[str, int]]] = {
    "Django": [("manage.py", 3), ("settings.py", 2), ("urls.py", 2), ("wsgi.py", 1)],
    "Flask": [("app.py", 1), ("wsgi.py", 1)],
    "FastAPI": [("main.py", 1)],
    "Rails": [("Gemfile", 1), ("Rakefile", 1), ("config/routes.rb", 3)],
    "Spring Boot": [("pom.xml", 1), ("build.gradle", 1)],
    "Express": [("package.json", 1), ("app.js", 1), ("server.js", 1)],
    "Next.js": [("next.config.js", 3), ("next.config.mjs", 3), ("next.config.ts", 3)],
    "React": [("package.json", 1)],
    "Angular": [("angular.json", 3)],
    "Vue": [("vue.config.js", 3), ("nuxt.config.js", 3), ("nuxt.config.ts", 3)],
    "Laravel": [("artisan", 3), ("composer.json", 1)],
    "ASP.NET": [("*.csproj", 2), ("Startup.cs", 3), ("Program.cs", 1)],
    "Terraform": [("*.tf", 2), ("terraform.tfstate", 2)],
    "Docker": [("Dockerfile", 2), ("docker-compose.yml", 2), ("docker-compose.yaml", 2)],
    "Kubernetes": [("*.yaml", 1)],
}

# Dependency file patterns
DEPENDENCY_FILES: dict[str, str] = {
    "requirements.txt": "Python (pip)",
    "Pipfile": "Python (pipenv)",
    "pyproject.toml": "Python (modern)",
    "setup.py": "Python (setuptools)",
    "setup.cfg": "Python (setuptools)",
    "poetry.lock": "Python (poetry)",
    "package.json": "Node.js (npm/yarn)",
    "yarn.lock": "Node.js (yarn)",
    "package-lock.json": "Node.js (npm)",
    "pnpm-lock.yaml": "Node.js (pnpm)",
    "Gemfile": "Ruby (bundler)",
    "Gemfile.lock": "Ruby (bundler)",
    "go.mod": "Go",
    "go.sum": "Go",
    "Cargo.toml": "Rust (cargo)",
    "Cargo.lock": "Rust (cargo)",
    "pom.xml": "Java (maven)",
    "build.gradle": "Java/Kotlin (gradle)",
    "build.gradle.kts": "Kotlin (gradle)",
    "composer.json": "PHP (composer)",
    "mix.exs": "Elixir (mix)",
    "pubspec.yaml": "Dart (pub)",
    "*.csproj": "C# (.NET)",
    "*.sln": "C# (.NET)",
}

# Default ignore patterns
DEFAULT_IGNORE: list[str] = [
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "*.egg-info",
    ".idea",
    ".vscode",
    ".DS_Store",
    "*.pyc",
    "*.pyo",
    "*.class",
    "*.o",
    "*.so",
    "*.dylib",
    "*.exe",
    "*.dll",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Cargo.lock",
]

# Config / env-related file patterns
CONFIG_PATTERNS: list[str] = [
    ".env",
    ".env.*",
    "*.env",
    ".envrc",
    "config.*",
    "settings.*",
    "*.config.js",
    "*.config.ts",
    "*.config.mjs",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
    "Makefile",
    "Procfile",
    "*.ini",
    "*.cfg",
    "*.toml",
    "*.yaml",
    "*.yml",
]


def should_ignore(path: str, ignore_patterns: list[str] | None = None) -> bool:
    """Check if a path should be ignored based on patterns."""
    patterns = ignore_patterns or DEFAULT_IGNORE
    name = os.path.basename(path)
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
        if pattern in path.split(os.sep):
            return True
    return False


def detect_language(filepath: str) -> str | None:
    """Detect programming language from file extension."""
    ext = Path(filepath).suffix.lower()
    return EXTENSION_MAP.get(ext)


def is_text_file(filepath: str, sample_size: int = 8192) -> bool:
    """Heuristic check for whether a file is text (not binary)."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(sample_size)
        if b"\x00" in chunk:
            return False
        return True
    except (OSError, PermissionError):
        return False


def read_file_safe(filepath: str, max_size: int = 512_000) -> str | None:
    """Read a file, returning None if it's too large, binary, or unreadable."""
    try:
        size = os.path.getsize(filepath)
        if size > max_size:
            logger.debug("Skipping %s: too large (%d bytes)", filepath, size)
            return None
        if not is_text_file(filepath):
            return None
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, PermissionError) as exc:
        logger.debug("Cannot read %s: %s", filepath, exc)
        return None


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Approximate token count using tiktoken. Falls back to word-based estimate."""
    try:
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except Exception:
        return len(text.split()) * 4 // 3


def chunk_text(text: str, max_tokens: int = 3000, model: str = "gpt-4") -> list[str]:
    """Split text into chunks that fit within a token budget."""
    lines = text.splitlines(keepends=True)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line, model)
        if current_tokens + line_tokens > max_tokens and current:
            chunks.append("".join(current))
            current = []
            current_tokens = 0
        current.append(line)
        current_tokens += line_tokens

    if current:
        chunks.append("".join(current))
    return chunks


def build_tree(root: str, files: list[str], max_depth: int = 4) -> str:
    """Build an ASCII directory tree from a list of file paths."""
    tree_lines: list[str] = []
    rel_paths = sorted(os.path.relpath(f, root) for f in files)

    dirs_seen: set[str] = set()
    for rp in rel_paths:
        parts = Path(rp).parts
        # Add directory entries
        for i in range(min(len(parts) - 1, max_depth)):
            dir_path = os.path.join(*parts[: i + 1])
            if dir_path not in dirs_seen:
                dirs_seen.add(dir_path)
                indent = "  " * i
                tree_lines.append(f"{indent}{parts[i]}/")
        # Add file entry
        if len(parts) <= max_depth + 1:
            indent = "  " * min(len(parts) - 1, max_depth)
            tree_lines.append(f"{indent}{parts[-1]}")

    return "\n".join(tree_lines)


def matches_config_pattern(filename: str) -> bool:
    """Check if a filename matches a known config/env pattern."""
    for pattern in CONFIG_PATTERNS:
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False
