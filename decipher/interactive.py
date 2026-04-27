"""Interactive Q&A mode for asking questions about a codebase."""

from __future__ import annotations

import logging
import os

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from decipher.analyzer import AnalysisResult
from decipher.llm import LLMClient
from decipher.scanner import ScanResult
from decipher.utils import build_tree, read_file_safe

logger = logging.getLogger(__name__)

console = Console()

SYSTEM_PROMPT = """\
You are a senior engineer who has been given full context about a codebase. Answer questions \
about the code precisely and helpfully. Reference specific files, functions, and line numbers \
when relevant. If you're not sure about something, say so rather than guessing.

Here is the codebase context:

## Project metadata
- Root: {root}
- Total files: {total_files}
- Languages: {languages}
- Frameworks: {frameworks}
- Entry points: {entry_points}

## Architecture
{architecture}

## Components
{components}

## API routes
{api_routes}

## Directory structure
```
{tree}
```

## Key source files
{file_contents}
"""


def build_context(analysis: AnalysisResult) -> str:
    """Build the system prompt with full codebase context."""
    scan = analysis.scan
    tree = build_tree(scan.root, [f.path for f in scan.files])

    # Include the most important source files
    file_contents = _gather_key_files(scan)

    languages_str = ", ".join(
        f"{lang} ({count})" for lang, count in sorted(scan.languages.items(), key=lambda x: -x[1])
    )

    return SYSTEM_PROMPT.format(
        root=scan.root,
        total_files=scan.total_files,
        languages=languages_str,
        frameworks=", ".join(scan.frameworks) or "none",
        entry_points=", ".join(scan.entry_points) or "none",
        architecture=analysis.architecture or "not determined",
        components="\n".join(f"- {c}" for c in analysis.components) or "none",
        api_routes="\n".join(f"- {r}" for r in analysis.api_routes) or "none",
        tree=tree,
        file_contents=file_contents,
    )


def _gather_key_files(scan: ScanResult, max_files: int = 20, max_lines: int = 100) -> str:
    """Read key source files and format them for the context window."""
    # Prioritise entry points and largest files per language
    selected: list[str] = []

    for ep in scan.entry_points:
        full = os.path.join(scan.root, ep)
        if os.path.exists(full):
            selected.append(full)

    by_lang: dict[str, list] = {}
    for f in scan.files:
        if f.language and f.language not in ("JSON", "YAML", "TOML", "Markdown"):
            by_lang.setdefault(f.language, []).append(f)

    for lang in sorted(by_lang, key=lambda ln: -scan.languages.get(ln, 0)):
        files = sorted(by_lang[lang], key=lambda f: -f.lines)
        for f in files[:3]:
            if f.path not in selected:
                selected.append(f.path)
            if len(selected) >= max_files:
                break
        if len(selected) >= max_files:
            break

    parts: list[str] = []
    for path in selected:
        content = read_file_safe(path, max_size=100_000)
        if content is None:
            continue
        lines = content.splitlines()
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
        rel = os.path.relpath(path, scan.root)
        parts.append(f"### {rel}\n```\n{content}\n```")

    return "\n\n".join(parts)


def ask_question(
    question: str,
    analysis: AnalysisResult,
    llm: LLMClient,
    history: list[dict[str, str]] | None = None,
) -> tuple[str, list[dict[str, str]]]:
    """Ask a single question about the codebase.

    Returns the answer and the updated message history.
    """
    if history is None:
        system_content = build_context(analysis)
        history = [{"role": "system", "content": system_content}]

    history.append({"role": "user", "content": question})

    answer = llm.chat_with_history(history, max_tokens=4096)
    history.append({"role": "assistant", "content": answer})

    return answer, history


def interactive_session(analysis: AnalysisResult, llm: LLMClient) -> None:
    """Run an interactive REPL for asking questions about the codebase."""
    console.print(
        Panel(
            "[bold]DecipherCode Interactive Mode[/bold]\n"
            f"Codebase: [cyan]{analysis.scan.root}[/cyan]\n"
            f"Files: {analysis.scan.total_files} | "
            f"Lines: {analysis.scan.total_lines:,} | "
            f"Architecture: {analysis.architecture or 'unknown'}\n\n"
            "Ask anything about this codebase. Type [bold]quit[/bold] or [bold]exit[/bold] "
            "to leave.",
            title="[orange1]decipher ask[/orange1]",
            border_style="blue",
        )
    )

    history: list[dict[str, str]] | None = None

    while True:
        console.print()
        try:
            question = console.input("[bold green]> [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break
        if question.lower() == "clear":
            history = None
            console.print("[dim]Context cleared.[/dim]")
            continue

        with console.status("[bold blue]Thinking...[/bold blue]"):
            answer, history = ask_question(question, analysis, llm, history)

        console.print()
        console.print(Markdown(answer))
