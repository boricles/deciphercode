"""Click CLI commands for DecipherCode."""

from __future__ import annotations

import logging
import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from decipher import __version__

console = Console()

BANNER = r"""
[bold orange1]    ____            _       __              ______          __   [/bold orange1]
[bold orange1]   / __ \___  _____(_)___  / /_  ___  _____/ ____/___  ____/ /__ [/bold orange1]
[bold orange1]  / / / / _ \/ ___/ / __ \/ __ \/ _ \/ ___/ /   / __ \/ __  / _ \[/bold orange1]
[bold orange1] / /_/ /  __/ /__/ / /_/ / / / /  __/ /  / /___/ /_/ / /_/ /  __/[/bold orange1]
[bold orange1]/_____/\___/\___/_/ .___/_/ /_/\___/_/   \____/\____/\__,_/\___/ [/bold orange1]
[bold orange1]                 /_/                                              [/bold orange1]
[dim]Give your legacy code a voice.[/dim]
"""


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _get_llm() -> "LLMClient":
    from decipher.llm import LLMClient

    return LLMClient()


def _scan_and_analyze(target: str, show_progress: bool = True) -> "AnalysisResult":
    """Scan + full LLM analysis in one step."""
    from decipher.analyzer import analyze_codebase
    from decipher.scanner import resolve_path, scan_codebase

    root = resolve_path(target)
    scan = scan_codebase(root, show_progress=show_progress)

    if scan.total_files == 0:
        console.print("[red]No source files found. Check the path or ignore patterns.[/red]")
        sys.exit(1)

    llm = _get_llm()
    return analyze_codebase(scan, llm, show_progress=show_progress)


@click.group()
@click.version_option(__version__, prog_name="decipher")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def main(verbose: bool) -> None:
    """DecipherCode - Give your legacy code a voice.

    Analyze legacy codebases and generate documentation using LLMs.
    """
    _setup_logging(verbose)


@main.command()
@click.argument("target")
@click.option("-o", "--output", type=click.Path(), help="Save report to file.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON analysis.")
def scan(target: str, output: str | None, as_json: bool) -> None:
    """Scan and analyze a codebase.

    TARGET is a local directory path or a GitHub URL.
    """
    console.print(BANNER)
    analysis = _scan_and_analyze(target)

    if as_json:
        import json

        data = {
            "root": analysis.scan.root,
            "total_files": analysis.scan.total_files,
            "total_lines": analysis.scan.total_lines,
            "languages": analysis.scan.languages,
            "frameworks": analysis.scan.frameworks,
            "architecture": analysis.architecture,
            "components": analysis.components,
            "api_routes": analysis.api_routes,
            "db_models": analysis.db_models,
            "env_vars": analysis.env_vars,
            "dead_code_candidates": analysis.dead_code_candidates,
            "key_observations": analysis.key_observations,
        }
        text = json.dumps(data, indent=2)
        if output:
            with open(output, "w") as f:
                f.write(text)
            console.print(f"[green]Report saved to {output}[/green]")
        else:
            console.print(text)
        return

    # Pretty-print the analysis
    report = _format_scan_report(analysis)

    if output:
        with open(output, "w") as f:
            f.write(report)
        console.print(f"\n[green]Report saved to {output}[/green]")
    else:
        console.print()
        console.print(Markdown(report))


@main.command()
@click.argument("target")
@click.option("-o", "--output", type=click.Path(), default=None, help="Output file (default: stdout).")
def readme(target: str, output: str | None) -> None:
    """Generate a README.md for a codebase.

    TARGET is a local directory path or a GitHub URL.
    """
    console.print(BANNER)

    analysis = _scan_and_analyze(target)

    from decipher.readme_generator import generate_readme

    llm = _get_llm()
    readme_text = generate_readme(analysis, llm)

    if output:
        with open(output, "w") as f:
            f.write(readme_text)
        console.print(f"\n[green]README saved to {output}[/green]")
    else:
        console.print()
        console.print(Markdown(readme_text))


@main.command()
@click.argument("target")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["mermaid", "dot"]),
    default="mermaid",
    help="Diagram format.",
)
@click.option("-o", "--output", type=click.Path(), default=None, help="Output file.")
def diagram(target: str, fmt: str, output: str | None) -> None:
    """Generate architecture diagrams for a codebase.

    TARGET is a local directory path or a GitHub URL.
    """
    console.print(BANNER)

    analysis = _scan_and_analyze(target)

    from decipher.diagrammer import generate_diagrams

    llm = _get_llm()
    diagrams = generate_diagrams(analysis, llm, fmt=fmt)

    if output:
        with open(output, "w") as f:
            f.write(diagrams)
        console.print(f"\n[green]Diagrams saved to {output}[/green]")
    else:
        console.print()
        if fmt == "mermaid":
            console.print(Markdown(diagrams))
        else:
            console.print(diagrams)


@main.command()
@click.argument("target")
@click.option("-o", "--output", type=click.Path(), default=None, help="Output file.")
def history(target: str, output: str | None) -> None:
    """Generate an archaeology report from git history.

    TARGET is a local directory path or a GitHub URL.
    """
    console.print(BANNER)

    from decipher.archaeologist import format_report, generate_archaeology_report
    from decipher.scanner import resolve_path

    root = resolve_path(target)
    llm = _get_llm()
    report = generate_archaeology_report(root, llm)
    formatted = format_report(report)

    if output:
        with open(output, "w") as f:
            f.write(formatted)
        console.print(f"\n[green]Archaeology report saved to {output}[/green]")
    else:
        console.print()
        console.print(Markdown(formatted))


@main.command()
@click.argument("target")
@click.argument("question", required=False)
def ask(target: str, question: str | None) -> None:
    """Ask questions about a codebase.

    Without QUESTION, starts an interactive session.
    With QUESTION, answers it and exits.

    TARGET is a local directory path or a GitHub URL.
    """
    console.print(BANNER)

    analysis = _scan_and_analyze(target)
    llm = _get_llm()

    from decipher.interactive import ask_question, interactive_session

    if question:
        with console.status("[bold blue]Thinking...[/bold blue]"):
            answer, _ = ask_question(question, analysis, llm)
        console.print()
        console.print(Markdown(answer))
    else:
        interactive_session(analysis, llm)


def _format_scan_report(analysis: "AnalysisResult") -> str:
    """Format an AnalysisResult as a Markdown report."""
    scan = analysis.scan
    lines = [
        "# DecipherCode Analysis Report",
        "",
        f"**Target:** `{scan.root}`  ",
        f"**Files:** {scan.total_files}  ",
        f"**Lines of code:** {scan.total_lines:,}  ",
        "",
        "## Languages",
        "",
        "| Language | Files |",
        "|---|---|",
    ]
    for lang, count in sorted(scan.languages.items(), key=lambda x: -x[1]):
        lines.append(f"| {lang} | {count} |")

    lines.extend(["", "## Frameworks", ""])
    if scan.frameworks:
        for fw in scan.frameworks:
            lines.append(f"- {fw}")
    else:
        lines.append("None detected.")

    lines.extend(["", "## Architecture", "", analysis.architecture or "Not determined.", ""])

    if analysis.components:
        lines.extend(["## Components", ""])
        for comp in analysis.components:
            lines.append(f"- {comp}")
        lines.append("")

    if analysis.api_routes:
        lines.extend(["## API Routes", ""])
        for route in analysis.api_routes:
            lines.append(f"- {route}")
        lines.append("")

    if analysis.db_models:
        lines.extend(["## Database Models", ""])
        for model in analysis.db_models:
            lines.append(f"- {model}")
        lines.append("")

    if analysis.env_vars:
        lines.extend(["## Environment Variables", ""])
        for var in analysis.env_vars:
            lines.append(f"- `{var}`")
        lines.append("")

    if analysis.dead_code_candidates:
        lines.extend(["## Dead Code Candidates", ""])
        for dc in analysis.dead_code_candidates:
            lines.append(f"- {dc}")
        lines.append("")

    if analysis.key_observations:
        lines.extend(["## Key Observations", ""])
        for obs in analysis.key_observations:
            lines.append(f"- {obs}")
        lines.append("")

    if scan.entry_points:
        lines.extend(["## Entry Points", ""])
        for ep in scan.entry_points:
            lines.append(f"- `{ep}`")
        lines.append("")

    if scan.dependency_files:
        lines.extend(["## Dependency Files", ""])
        for dep, eco in scan.dependency_files.items():
            lines.append(f"- `{dep}` ({eco})")
        lines.append("")

    return "\n".join(lines)
