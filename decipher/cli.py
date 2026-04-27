"""Click CLI commands for DecipherCode."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.markdown import Markdown

from decipher import __version__

if TYPE_CHECKING:
    from decipher.analyzer import AnalysisResult
    from decipher.llm import LLMClient

console = Console()

BANNER = (
    "[bold green3]"
    "    ____            _       __              ______          __   \n"
    "   / __ \\___  _____(_)___  / /_  ___  _____/ ____/___  ____/ /__ \n"
    "  / / / / _ \\/ ___/ / __ \\/ __ \\/ _ \\/ ___/ /   / __ \\/ __  / _ \\\n"
    " / /_/ /  __/ /__/ / /_/ / / / /  __/ /  / /___/ /_/ / /_/ /  __/\n"
    "/_____/\\___/\\___/_/ .___/_/ /_/\\___/_/   \\____/\\____/\\__,_/\\___/ \n"
    "                 /_/                                              \n"
    "[/bold green3]\n"
    "[dim]Give your legacy code a voice.[/dim]"
)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _get_llm() -> LLMClient:
    from decipher.llm import LLMClient

    return LLMClient()


def _scan_and_analyze(target: str, show_progress: bool = True) -> AnalysisResult:
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
@click.option(
    "-o", "--output", type=click.Path(), default=None, help="Output file (default: stdout)."
)
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


def _is_ci_env() -> bool:
    """Detect common CI environment variables."""
    import os

    ci_vars = [
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "CIRCLECI",
        "TRAVIS",
        "BUILDKITE",
        "TF_BUILD",
    ]
    return any(os.environ.get(v) for v in ci_vars)


_FORMAT_FROM_EXT = {
    ".json": "json",
    ".md": "markdown",
    ".markdown": "markdown",
}


def _resolve_format(
    fmt: str | None,
    json_only: bool,
    output: str | None,
) -> str:
    """Determine the output format from flags, file extension, or environment."""
    from pathlib import Path as _Path

    if fmt is not None:
        return fmt

    if json_only:
        return "json"

    if output is not None:
        ext = _Path(output).suffix.lower()
        if ext in _FORMAT_FROM_EXT:
            return _FORMAT_FROM_EXT[ext]
        if ext:
            raise click.UsageError(
                f"Cannot determine format from extension '{ext}'. "
                f"Supported: .json, .md. Use --format to specify explicitly."
            )
        raise click.UsageError(
            "Cannot determine format (no file extension). Use --format to specify explicitly."
        )

    if sys.stdout.isatty() and not _is_ci_env():
        return "terminal"
    return "markdown"


def _resolve_checkers(
    only: str | None,
    skip: str | None,
    available: list[str],
) -> list[str]:
    """Resolve checker list from --only/--skip flags."""
    if only and skip:
        raise click.UsageError("--only and --skip are mutually exclusive.")

    if only:
        names = [n.strip() for n in only.split(",")]
        unknown = [n for n in names if n not in available]
        if unknown:
            raise click.UsageError(
                f"Unknown checker(s): {', '.join(unknown)}. Available: {', '.join(available)}"
            )
        return names

    if skip:
        names = [n.strip() for n in skip.split(",")]
        unknown = [n for n in names if n not in available]
        if unknown:
            raise click.UsageError(
                f"Unknown checker(s): {', '.join(unknown)}. Available: {', '.join(available)}"
            )
        return [c for c in available if c not in names]

    return available


@main.command()
@click.argument("target")
@click.option(
    "--language",
    default="python",
    show_default=True,
    help=(
        "Language to audit. Only Python is supported in v0.2; "
        "passing any other value exits with error code 2."
    ),
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["terminal", "markdown", "json"]),
    default=None,
    help="Output format (default: auto-detect from TTY/CI/extension).",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Exit with code 1 on warnings (not just failures).",
)
@click.option(
    "--only",
    default=None,
    help="Run only these checkers (comma-separated names).",
)
@click.option(
    "--skip",
    default=None,
    help="Skip these checkers (comma-separated names).",
)
@click.option("-o", "--output", type=click.Path(), default=None, help="Write report to file.")
@click.option("--json-only", is_flag=True, hidden=True, help="Deprecated. Use --format json.")
def practices(
    target: str,
    language: str,
    fmt: str | None,
    strict: bool,
    only: str | None,
    skip: str | None,
    output: str | None,
    json_only: bool,
) -> None:
    """Audit a repository against software-development best practices.

    Produces a structured report with per-category scores and prioritised
    recommendations.  Format defaults to a Rich terminal table when stdout
    is a TTY, Markdown in CI environments, or auto-detected from the -o
    file extension.

    TARGET is a local directory path.
    """
    from io import StringIO
    from pathlib import Path

    from rich.console import Console as RichConsole

    from decipher.practices.reporter import Reporter
    from decipher.practices.runner import SUPPORTED_LANGUAGES, run_audit

    if language not in SUPPORTED_LANGUAGES:
        console.print(
            f'[red]Unsupported language "{language}". '
            f"Supported: {', '.join(sorted(SUPPORTED_LANGUAGES))}.[/red]"
        )
        sys.exit(2)

    repo_path = Path(target).resolve()
    if not repo_path.is_dir():
        console.print(f"[red]Directory not found: {target}[/red]")
        sys.exit(1)

    resolved_fmt = _resolve_format(fmt, json_only, output)
    checker_list = _resolve_checkers(
        only,
        skip,
        SUPPORTED_LANGUAGES[language],
    )
    show_banner = resolved_fmt == "terminal"

    if show_banner:
        console.print(BANNER)

    report = run_audit(
        repo_path,
        language=language,
        show_progress=show_banner,
        checkers=checker_list,
    )
    reporter = Reporter()

    if resolved_fmt == "json":
        text = reporter.to_json(report)
        if output:
            with open(output, "w") as f:
                f.write(text)
            console.print(f"\n[green]Report saved to {output}[/green]")
        else:
            click.echo(text)
    elif resolved_fmt == "markdown":
        text = reporter.to_markdown(report)
        if output:
            with open(output, "w") as f:
                f.write(text)
            console.print(f"\n[green]Report saved to {output}[/green]")
        else:
            console.print()
            console.print(Markdown(text))
    else:
        # terminal format
        renderable = reporter.to_terminal(report)
        if output:
            buf = StringIO()
            file_console = RichConsole(file=buf, no_color=True, width=120)
            file_console.print(renderable)
            with open(output, "w") as f:
                f.write(buf.getvalue())
            console.print(f"\n[green]Report saved to {output}[/green]")
        else:
            console.print()
            console.print(renderable)

    # Exit codes: 0 = pass/warn, 1 = fail (or warn with --strict), 2 = error
    if report.overall_status == "fail":
        sys.exit(1)
    if strict and report.overall_status == "warn":
        sys.exit(1)


def _format_scan_report(analysis: AnalysisResult) -> str:
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
