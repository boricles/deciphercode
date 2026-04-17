"""Architecture diagram generation using Mermaid and GraphViz DOT."""

from __future__ import annotations

import logging

from rich.progress import Progress, SpinnerColumn, TextColumn

from decipher.analyzer import AnalysisResult
from decipher.llm import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a software architect who creates clear, accurate architecture diagrams. \
You produce valid Mermaid or GraphViz DOT syntax. Only diagram what the analysis data supports; \
do not invent components."""

MERMAID_PROMPT = """\
Generate a Mermaid architecture diagram for this project.

## Architecture
{architecture}

## Components
{components}

## API routes
{api_routes}

## Database models
{db_models}

## Languages and frameworks
{languages}
{frameworks}

## Entry points
{entry_points}

---

Generate THREE Mermaid diagrams:

1. **Component diagram** - show the major components/modules and how they relate to each other. \
Use a `graph TD` or `graph LR` diagram.

2. **Data flow diagram** - show how data flows through the system (user request -> API -> \
service -> database, etc.). Use a `flowchart LR` diagram.

3. **Module dependency diagram** - show which modules/packages depend on which others. \
Use a `graph TD` diagram.

Format each diagram like this:

### Component Diagram
```mermaid
graph TD
    ...
```

### Data Flow
```mermaid
flowchart LR
    ...
```

### Module Dependencies
```mermaid
graph TD
    ...
```

Use clear node labels. Keep diagrams readable (not too many nodes). \
Output ONLY the three diagrams in Markdown, nothing else."""

DOT_PROMPT = """\
Generate a GraphViz DOT diagram showing the architecture of this project.

## Architecture
{architecture}

## Components
{components}

## API routes
{api_routes}

## Database models
{db_models}

## Languages and frameworks
{languages}
{frameworks}

---

Generate a single DOT digraph showing the major components, their relationships, \
and data flow. Use subgraphs to group related components. Use clear labels.

Output ONLY valid DOT syntax, starting with `digraph` and ending with `}}`. \
No markdown fences, no explanations."""


def generate_diagrams(
    analysis: AnalysisResult,
    llm: LLMClient,
    fmt: str = "mermaid",
    show_progress: bool = True,
) -> str:
    """Generate architecture diagrams from analysis results.

    Args:
        analysis: The codebase analysis result.
        llm: LLM client to use.
        fmt: Output format, either "mermaid" or "dot".
        show_progress: Whether to show a progress spinner.

    Returns:
        Diagram markup as a string (Mermaid markdown or DOT).
    """
    scan = analysis.scan
    languages_str = ", ".join(
        f"{lang} ({count})" for lang, count in sorted(scan.languages.items(), key=lambda x: -x[1])
    )

    template_vars = {
        "architecture": analysis.architecture or "not determined",
        "components": _format_list(analysis.components),
        "api_routes": _format_list(analysis.api_routes) or "none found",
        "db_models": _format_list(analysis.db_models) or "none found",
        "languages": languages_str,
        "frameworks": ", ".join(scan.frameworks) or "none detected",
        "entry_points": ", ".join(scan.entry_points) or "none detected",
    }

    if fmt == "dot":
        prompt = DOT_PROMPT.format(**template_vars)
    else:
        prompt = MERMAID_PROMPT.format(**template_vars)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        disable=not show_progress,
    ) as progress:
        progress.add_task(f"Generating {fmt} diagrams with LLM...", total=None)
        result = llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=4096)

    # Clean up DOT output
    if fmt == "dot":
        result = _clean_dot(result)

    return result.strip() + "\n"


def _format_list(items: list[str]) -> str:
    if not items:
        return "none"
    return "\n".join(f"- {item}" for item in items)


def _clean_dot(text: str) -> str:
    """Strip markdown fences from DOT output if the LLM added them."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text
