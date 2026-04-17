"""LLM-powered code analysis: architecture, APIs, dead code, env vars."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from rich.progress import Progress, SpinnerColumn, TextColumn

from decipher.llm import LLMClient
from decipher.scanner import ScanResult
from decipher.utils import build_tree, chunk_text, read_file_safe

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Full analysis of a codebase."""

    scan: ScanResult
    architecture: str = ""
    components: list[str] = field(default_factory=list)
    api_routes: list[str] = field(default_factory=list)
    db_models: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    dead_code_candidates: list[str] = field(default_factory=list)
    key_observations: list[str] = field(default_factory=list)
    raw_analysis: str = ""


SYSTEM_PROMPT = """\
You are a senior software architect analyzing a legacy codebase. You provide precise, \
structured analysis. When listing items, be specific (include file paths and names). \
Respond only in the requested format."""

ANALYSIS_PROMPT_TEMPLATE = """\
Analyze this codebase and provide a structured report.

## Project metadata
- Root: {root}
- Total files: {total_files}
- Total lines: {total_lines}
- Languages: {languages}
- Detected frameworks: {frameworks}
- Dependency files: {dep_files}
- Entry points: {entry_points}

## Directory structure
```
{tree}
```

## Source file samples
{file_samples}

Provide your analysis as JSON with these keys:
- "architecture": string describing the architecture pattern (e.g. "Monolithic MVC", \
"Microservices", "Serverless", "Modular monolith", etc.) with a brief explanation
- "components": list of strings, each naming a major component/module and its purpose
- "api_routes": list of strings, each describing an API endpoint or route found \
(format: "METHOD /path - description" or "file:line - description")
- "db_models": list of strings, each naming a database model/table/schema found
- "env_vars": list of strings, each naming an environment variable referenced in the code
- "dead_code_candidates": list of strings, each naming a file or function that appears \
unused or orphaned, with brief reasoning
- "key_observations": list of strings, each a notable finding about the codebase \
(tech debt, patterns, risks, strengths)

Return ONLY valid JSON, no markdown fences."""


def analyze_codebase(
    scan: ScanResult,
    llm: LLMClient,
    max_sample_files: int = 30,
    show_progress: bool = True,
) -> AnalysisResult:
    """Run a full LLM-powered analysis of a scanned codebase."""
    result = AnalysisResult(scan=scan)

    # Build file tree
    tree = build_tree(scan.root, [f.path for f in scan.files])

    # Select representative files to sample
    sampled = _select_sample_files(scan, max_sample_files)

    # Read and format file samples
    file_samples = _format_file_samples(sampled, scan.root)

    # Build the prompt
    languages_str = ", ".join(
        f"{lang} ({count})" for lang, count in sorted(scan.languages.items(), key=lambda x: -x[1])
    )
    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        root=scan.root,
        total_files=scan.total_files,
        total_lines=f"{scan.total_lines:,}",
        languages=languages_str,
        frameworks=", ".join(scan.frameworks) or "none detected",
        dep_files=", ".join(f"{k} [{v}]" for k, v in scan.dependency_files.items()) or "none",
        entry_points=", ".join(scan.entry_points) or "none detected",
        tree=tree,
        file_samples=file_samples,
    )

    # If prompt is too large, chunk file samples and do multiple passes
    chunks = chunk_text(prompt, max_tokens=12000)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        disable=not show_progress,
    ) as progress:
        if len(chunks) == 1:
            progress.add_task("Analyzing codebase with LLM...", total=None)
            raw = llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=4096)
        else:
            # Multi-pass: send structure first, then file samples
            task = progress.add_task(
                f"Analyzing codebase ({len(chunks)} passes)...", total=len(chunks)
            )
            partial_results: list[str] = []
            for i, chunk in enumerate(chunks):
                sub_prompt = (
                    f"This is part {i + 1} of {len(chunks)} of a codebase analysis.\n\n{chunk}"
                )
                if i < len(chunks) - 1:
                    sub_prompt += (
                        "\n\nAcknowledge this partial context. "
                        "Reply with a brief summary of what you see so far."
                    )
                else:
                    sub_prompt += (
                        "\n\nNow provide the full analysis as JSON "
                        "(using the schema described in part 1)."
                    )
                partial = llm.chat(sub_prompt, system=SYSTEM_PROMPT, max_tokens=4096)
                partial_results.append(partial)
                progress.update(task, advance=1)
            raw = partial_results[-1]

    result.raw_analysis = raw

    # Parse JSON response
    parsed = _parse_json_response(raw)
    if parsed:
        result.architecture = parsed.get("architecture", "")
        result.components = parsed.get("components", [])
        result.api_routes = parsed.get("api_routes", [])
        result.db_models = parsed.get("db_models", [])
        result.env_vars = parsed.get("env_vars", [])
        result.dead_code_candidates = parsed.get("dead_code_candidates", [])
        result.key_observations = parsed.get("key_observations", [])
    else:
        logger.warning("Could not parse LLM response as JSON; storing raw text")
        result.key_observations = [raw]

    return result


def _select_sample_files(scan: ScanResult, max_files: int) -> list[str]:
    """Pick the most representative files to send to the LLM."""
    # Prioritise: entry points, then largest files per language, then config
    selected: list[str] = []
    selected_set: set[str] = set()

    def _add(path: str) -> None:
        if path not in selected_set and len(selected) < max_files:
            selected.append(path)
            selected_set.add(path)

    # Entry points first
    for ep in scan.entry_points:
        import os

        _add(os.path.join(scan.root, ep))

    # Largest file per language (most likely to be substantive)
    by_lang: dict[str, list] = {}
    for f in scan.files:
        if f.language:
            by_lang.setdefault(f.language, []).append(f)

    for lang in sorted(by_lang, key=lambda l: -scan.languages.get(l, 0)):
        files = sorted(by_lang[lang], key=lambda f: -f.lines)
        for f in files[:3]:
            _add(f.path)

    # Config files
    for cfg in scan.config_files[:5]:
        import os

        _add(os.path.join(scan.root, cfg))

    return selected


def _format_file_samples(paths: list[str], root: str) -> str:
    """Read files and format them for inclusion in a prompt."""
    import os

    parts: list[str] = []
    for path in paths:
        content = read_file_safe(path, max_size=100_000)
        if content is None:
            continue
        # Truncate very long files
        lines = content.splitlines()
        if len(lines) > 150:
            content = "\n".join(lines[:150]) + f"\n... ({len(lines) - 150} more lines)"
        rel = os.path.relpath(path, root)
        parts.append(f"### {rel}\n```\n{content}\n```")
    return "\n\n".join(parts)


def _parse_json_response(text: str) -> dict | None:
    """Extract and parse JSON from an LLM response, handling markdown fences."""
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass
    return None
