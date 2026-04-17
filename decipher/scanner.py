"""Codebase scanning and file discovery."""

from __future__ import annotations

import fnmatch
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from decipher.utils import (
    DEPENDENCY_FILES,
    FRAMEWORK_SIGNALS,
    detect_language,
    matches_config_pattern,
    read_file_safe,
    should_ignore,
)

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Metadata about a single source file."""

    path: str
    relative_path: str
    language: str | None
    size: int
    lines: int


@dataclass
class ScanResult:
    """Aggregated results of scanning a codebase."""

    root: str
    files: list[FileInfo] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)  # language -> file count
    frameworks: list[str] = field(default_factory=list)
    dependency_files: dict[str, str] = field(default_factory=dict)  # filename -> ecosystem
    config_files: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    total_lines: int = 0
    total_files: int = 0

    @property
    def primary_language(self) -> str | None:
        if not self.languages:
            return None
        return max(self.languages, key=self.languages.get)

    def summary(self) -> str:
        parts = [
            f"Root: {self.root}",
            f"Files: {self.total_files}",
            f"Lines: {self.total_lines:,}",
            f"Languages: {', '.join(f'{k} ({v})' for k, v in sorted(self.languages.items(), key=lambda x: -x[1]))}",
        ]
        if self.frameworks:
            parts.append(f"Frameworks: {', '.join(self.frameworks)}")
        if self.dependency_files:
            parts.append(
                f"Dependencies: {', '.join(f'{k} [{v}]' for k, v in self.dependency_files.items())}"
            )
        if self.entry_points:
            parts.append(f"Entry points: {', '.join(self.entry_points)}")
        return "\n".join(parts)


# Common entry-point filenames
ENTRY_POINT_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "wsgi.py",
    "asgi.py",
    "manage.py",
    "index.js",
    "index.ts",
    "server.js",
    "server.ts",
    "app.js",
    "app.ts",
    "main.go",
    "main.rs",
    "Main.java",
    "Program.cs",
    "Startup.cs",
    "index.php",
    "artisan",
}


def clone_repo(url: str) -> str:
    """Clone a git repo to a temp directory and return the path."""
    tmpdir = tempfile.mkdtemp(prefix="decipher_")
    logger.info("Cloning %s into %s", url, tmpdir)
    subprocess.run(
        ["git", "clone", "--depth", "1", url, tmpdir],
        check=True,
        capture_output=True,
        text=True,
    )
    return tmpdir


def resolve_path(target: str) -> str:
    """Resolve a target that may be a local path or a GitHub URL."""
    if target.startswith(("http://", "https://", "git@")):
        return clone_repo(target)
    path = os.path.abspath(os.path.expanduser(target))
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Directory not found: {path}")
    return path


def scan_codebase(
    root: str,
    ignore_patterns: list[str] | None = None,
    show_progress: bool = True,
) -> ScanResult:
    """Walk a directory tree, catalogue every source file, and detect frameworks."""
    result = ScanResult(root=root)
    all_filenames: list[str] = []

    # Collect files
    file_paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if not should_ignore(d, ignore_patterns)]

        for fname in filenames:
            if should_ignore(fname, ignore_patterns):
                continue
            full = os.path.join(dirpath, fname)
            file_paths.append(full)
            all_filenames.append(fname)

    progress_ctx = (
        Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"))
        if show_progress
        else None
    )

    def _process() -> None:
        if progress_ctx:
            task = progress_ctx.add_task(f"Scanning {len(file_paths)} files...", total=None)

        for full in file_paths:
            rel = os.path.relpath(full, root)
            lang = detect_language(full)

            try:
                size = os.path.getsize(full)
            except OSError:
                continue

            # Count lines for text files
            lines = 0
            content = read_file_safe(full)
            if content is not None:
                lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)

            info = FileInfo(
                path=full,
                relative_path=rel,
                language=lang,
                size=size,
                lines=lines,
            )
            result.files.append(info)
            result.total_lines += lines

            if lang:
                result.languages[lang] = result.languages.get(lang, 0) + 1

            # Check for dependency files
            fname = os.path.basename(full)
            for pattern, ecosystem in DEPENDENCY_FILES.items():
                if fnmatch.fnmatch(fname, pattern):
                    result.dependency_files[rel] = ecosystem

            # Check for config files
            if matches_config_pattern(fname):
                result.config_files.append(rel)

            # Check for entry points
            if fname in ENTRY_POINT_NAMES:
                result.entry_points.append(rel)

            if progress_ctx:
                progress_ctx.update(task, description=f"Scanning... {rel}")

    if progress_ctx:
        with progress_ctx:
            _process()
    else:
        _process()

    result.total_files = len(result.files)

    # Detect frameworks
    result.frameworks = _detect_frameworks(all_filenames, root)

    logger.info("Scan complete: %d files, %d lines", result.total_files, result.total_lines)
    return result


def _detect_frameworks(filenames: list[str], root: str) -> list[str]:
    """Score frameworks based on signal files found in the repo."""
    scores: dict[str, int] = {}
    filename_set = set(filenames)

    for framework, signals in FRAMEWORK_SIGNALS.items():
        score = 0
        for pattern, weight in signals:
            if "/" in pattern:
                # Check full relative path existence
                if os.path.exists(os.path.join(root, pattern)):
                    score += weight
            elif "*" in pattern:
                if any(fnmatch.fnmatch(f, pattern) for f in filename_set):
                    score += weight
            elif pattern in filename_set:
                score += weight
        if score >= 2:
            scores[framework] = score

    # Extra detection from file contents
    _check_framework_imports(root, filenames, scores)

    return sorted(scores, key=scores.get, reverse=True)


def _check_framework_imports(root: str, filenames: list[str], scores: dict[str, int]) -> None:
    """Check file contents for framework import statements."""
    # Check package.json for React/Vue/Angular
    pkg_json = os.path.join(root, "package.json")
    if os.path.exists(pkg_json):
        content = read_file_safe(pkg_json) or ""
        if '"react"' in content:
            scores["React"] = scores.get("React", 0) + 3
        if '"vue"' in content:
            scores["Vue"] = scores.get("Vue", 0) + 3
        if '"@angular/core"' in content:
            scores["Angular"] = scores.get("Angular", 0) + 3
        if '"express"' in content:
            scores["Express"] = scores.get("Express", 0) + 3
        if '"next"' in content:
            scores["Next.js"] = scores.get("Next.js", 0) + 3

    # Check Python files for framework imports
    for fname in filenames:
        if not fname.endswith(".py"):
            continue
        full = os.path.join(root, fname)
        if not os.path.exists(full):
            continue
        content = read_file_safe(full, max_size=50_000)
        if content is None:
            continue
        if "from flask" in content or "import flask" in content:
            scores["Flask"] = scores.get("Flask", 0) + 3
        if "from fastapi" in content or "import fastapi" in content:
            scores["FastAPI"] = scores.get("FastAPI", 0) + 3
        if "from django" in content or "import django" in content:
            scores["Django"] = scores.get("Django", 0) + 3
        break  # Only check first Python file at root
