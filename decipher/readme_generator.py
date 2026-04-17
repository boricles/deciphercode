"""README.md generation from codebase analysis."""

from __future__ import annotations

import logging

from rich.progress import Progress, SpinnerColumn, TextColumn

from decipher.analyzer import AnalysisResult
from decipher.llm import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a technical writer who creates clear, professional README.md files for software projects. \
Write in a direct, helpful style. Use proper Markdown formatting. Do not invent features that \
are not supported by the analysis data provided."""

README_PROMPT_TEMPLATE = """\
Generate a comprehensive README.md for this project based on the following analysis.

## Project info
- Root directory: {root}
- Total files: {total_files}
- Total lines of code: {total_lines}
- Primary language: {primary_language}
- All languages: {languages}
- Detected frameworks: {frameworks}
- Dependency files: {dep_files}
- Entry points: {entry_points}

## Architecture
{architecture}

## Components
{components}

## API routes / endpoints
{api_routes}

## Database models
{db_models}

## Environment variables
{env_vars}

## Key observations
{observations}

---

Generate a README.md that includes:

1. **Title and badges** - project name (infer from directory name), badges for primary language, \
license (MIT if found, otherwise omit), and main framework
2. **Description** - 2-3 sentence project description based on the analysis
3. **Architecture overview** - brief explanation of the architecture pattern
4. **Project structure** - directory tree of the main components
5. **Getting started** - prerequisites, installation, and setup instructions \
(infer from dependency files)
6. **Configuration** - environment variables and config files
7. **API documentation** - table or list of endpoints if any were found
8. **Tech stack** - languages, frameworks, and key dependencies
9. **Contributing** - brief contributing guide

Use real Markdown. Start with the title as an H1. Do not wrap the output in code fences.
Output ONLY the README content, nothing else."""


def generate_readme(
    analysis: AnalysisResult,
    llm: LLMClient,
    show_progress: bool = True,
) -> str:
    """Generate a README.md from analysis results."""
    scan = analysis.scan

    languages_str = ", ".join(
        f"{lang} ({count})" for lang, count in sorted(scan.languages.items(), key=lambda x: -x[1])
    )

    prompt = README_PROMPT_TEMPLATE.format(
        root=scan.root,
        total_files=scan.total_files,
        total_lines=f"{scan.total_lines:,}",
        primary_language=scan.primary_language or "unknown",
        languages=languages_str,
        frameworks=", ".join(scan.frameworks) or "none detected",
        dep_files=", ".join(f"{k} [{v}]" for k, v in scan.dependency_files.items()) or "none",
        entry_points=", ".join(scan.entry_points) or "none detected",
        architecture=analysis.architecture or "not determined",
        components=_format_list(analysis.components),
        api_routes=_format_list(analysis.api_routes) or "none found",
        db_models=_format_list(analysis.db_models) or "none found",
        env_vars=_format_list(analysis.env_vars) or "none found",
        observations=_format_list(analysis.key_observations),
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        disable=not show_progress,
    ) as progress:
        progress.add_task("Generating README with LLM...", total=None)
        readme = llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=4096)

    # Clean up any accidental wrapping
    readme = readme.strip()
    if readme.startswith("```markdown"):
        readme = readme[len("```markdown") :].strip()
    if readme.startswith("```md"):
        readme = readme[len("```md") :].strip()
    if readme.startswith("```"):
        readme = readme[3:].strip()
    if readme.endswith("```"):
        readme = readme[:-3].strip()

    return readme + "\n"


def _format_list(items: list[str]) -> str:
    """Format a list as bullet points."""
    if not items:
        return "none"
    return "\n".join(f"- {item}" for item in items)
