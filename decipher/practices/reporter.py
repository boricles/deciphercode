"""Reporter that renders an AuditReport as JSON, Markdown, or Rich terminal."""

from __future__ import annotations

import json
from dataclasses import asdict

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from decipher.practices.models import AuditReport

_STATUS_STYLE = {"pass": "green", "warn": "yellow", "fail": "red"}


class Reporter:
    """Renders an AuditReport to JSON, Markdown, or Rich terminal."""

    def to_json(self, report: AuditReport) -> str:
        """Serialize the report to a JSON string."""
        return json.dumps(asdict(report), indent=2)

    def to_terminal(self, report: AuditReport) -> Group:
        """Render a compact Rich terminal report.

        Returns a Group of renderables: header panel, summary table,
        and priority actions.
        """
        # Header panel
        header = Text()
        header.append(f"Repository: {report.repo_path}\n")
        header.append(f"Language:   {report.language.capitalize()}\n")
        header.append(f"Score:      {report.overall_score}/100 ")
        header.append(
            f"({report.overall_status.upper()})",
            style=_STATUS_STYLE.get(report.overall_status, ""),
        )

        panel = Panel(header, title="Best Practices Audit", border_style="blue")

        # Summary table
        table = Table(show_header=True, title_justify="left")
        table.add_column("Checker", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Status", justify="center")

        for r in report.results:
            style = _STATUS_STYLE.get(r.status, "")
            table.add_row(
                r.display_name,
                str(r.score),
                Text(r.status.upper(), style=style),
            )

        # Overall row
        overall_style = _STATUS_STYLE.get(report.overall_status, "")
        table.add_section()
        table.add_row(
            Text("Overall", style="bold"),
            str(report.overall_score),
            Text(report.overall_status.upper(), style=overall_style),
        )

        parts: list = [panel, table]

        # Priority actions
        if report.top_recommendations:
            rec_text = Text("\nPriority Actions:\n", style="bold")
            for i, rec in enumerate(report.top_recommendations, 1):
                rec_text.append(f"  {i}. {rec}\n")
            parts.append(rec_text)

        # Summary line
        if report.summary:
            parts.append(Text(f"\n{report.summary}\n", style="dim"))

        return Group(*parts)

    def to_markdown(self, report: AuditReport) -> str:
        """Render a human-readable Markdown report."""
        lines: list[str] = []

        # Header
        lines.append("# Best Practices Audit Report")
        lines.append("")
        lines.append(f"**Repository:** `{report.repo_path}`  ")
        lines.append(f"**Language:** {report.language.capitalize()}  ")
        lines.append(f"**Date:** {report.timestamp[:10]}  ")
        lines.append(
            f"**Overall Score:** {report.overall_score} / 100 ({report.overall_status.upper()})"
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        # Summary
        if report.summary:
            lines.append(report.summary)
            lines.append("")
            lines.append("---")
            lines.append("")

        # Per-checker sections
        for result in report.results:
            lines.append(
                f"## {result.display_name} — {result.score} / 100 ({result.status.upper()})"
            )
            lines.append("")

            if result.findings:
                lines.append("| ID | Finding | Severity | File |")
                lines.append("|----|---------|----------|------|")
                for f in result.findings:
                    file_col = f.file_path or ""
                    if f.line is not None and f.file_path:
                        file_col = f"{f.file_path}:{f.line}"
                    lines.append(f"| {f.id} | {f.message} | {f.severity.upper()} | {file_col} |")
                lines.append("")

            if result.recommendations:
                lines.append("**Recommendations:**")
                for rec in result.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Priority Actions
        if report.top_recommendations:
            lines.append("## Priority Actions")
            lines.append("")
            for i, rec in enumerate(report.top_recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        return "\n".join(lines)
