"""Git history analysis and archaeology reports."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from rich.progress import Progress, SpinnerColumn, TextColumn

from decipher.llm import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class GitStats:
    """Raw statistics extracted from git history."""

    total_commits: int = 0
    contributors: list[dict[str, str | int]] = field(default_factory=list)
    first_commit_date: str = ""
    last_commit_date: str = ""
    hotspot_files: list[dict[str, str | int]] = field(default_factory=list)
    recent_commits: list[dict[str, str]] = field(default_factory=list)
    tag_history: list[str] = field(default_factory=list)


@dataclass
class ArchaeologyReport:
    """Full archaeology report: stats + LLM narrative."""

    stats: GitStats
    narrative: str = ""
    tech_debt_analysis: str = ""
    evolution_timeline: str = ""


SYSTEM_PROMPT = """\
You are a software historian analyzing a project's git history. You write clear, insightful \
narratives about how a project evolved, identifying patterns, key decisions, and areas of concern. \
Be specific and reference actual data."""

NARRATIVE_PROMPT = """\
Analyze this git history data and write an archaeology report.

## Repository statistics
- Total commits: {total_commits}
- First commit: {first_commit}
- Last commit: {last_commit}
- Project age: from {first_commit} to {last_commit}

## Contributors (top {num_contributors})
{contributors}

## Most frequently changed files (hotspots)
{hotspots}

## Recent commits (last 20)
{recent_commits}

## Tags / releases
{tags}

---

Write a report with these sections:

### Evolution timeline
A narrative of how the project evolved over time. Identify major phases (initial development, \
feature expansion, maintenance, etc.) based on commit patterns and dates.

### Key contributors
Who built what. Identify the core maintainers vs occasional contributors.

### Tech debt hotspots
Files changed most frequently are often tech debt. Analyze the hotspot list and explain which \
files are likely problematic and why (high churn = instability, bug-prone, or poor abstraction).

### Observations
Notable patterns: is the project actively maintained? Are there signs of abandonment? \
Major refactors? Dependency upgrades?

Write in Markdown. Be direct and analytical."""


def extract_git_stats(repo_path: str) -> GitStats:
    """Extract statistics from git history using GitPython."""
    import git

    stats = GitStats()

    try:
        repo = git.Repo(repo_path)
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        logger.warning("Not a git repository: %s", repo_path)
        return stats

    if repo.bare:
        logger.warning("Bare repository, limited analysis: %s", repo_path)
        return stats

    # Count commits and get date range
    commits = list(repo.iter_commits("HEAD", max_count=5000))
    if not commits:
        return stats

    stats.total_commits = len(commits)
    stats.first_commit_date = commits[-1].committed_datetime.strftime("%Y-%m-%d")
    stats.last_commit_date = commits[0].committed_datetime.strftime("%Y-%m-%d")

    # Contributors
    author_counts: dict[str, int] = {}
    for commit in commits:
        name = commit.author.name or "Unknown"
        author_counts[name] = author_counts.get(name, 0) + 1

    stats.contributors = [
        {"name": name, "commits": count}
        for name, count in sorted(author_counts.items(), key=lambda x: -x[1])[:20]
    ]

    # File change frequency (hotspots)
    file_changes: dict[str, int] = {}
    for commit in commits[:500]:  # Limit to avoid slowness on huge repos
        for path in commit.stats.files:
            file_changes[path] = file_changes.get(path, 0) + 1

    stats.hotspot_files = [
        {"file": path, "changes": count}
        for path, count in sorted(file_changes.items(), key=lambda x: -x[1])[:30]
    ]

    # Recent commits
    for commit in commits[:20]:
        stats.recent_commits.append(
            {
                "hash": commit.hexsha[:8],
                "date": commit.committed_datetime.strftime("%Y-%m-%d"),
                "author": commit.author.name or "Unknown",
                "message": commit.message.strip().splitlines()[0][:120],
            }
        )

    # Tags
    stats.tag_history = [
        f"{tag.name} ({tag.commit.committed_datetime.strftime('%Y-%m-%d')})"
        for tag in sorted(repo.tags, key=lambda t: t.commit.committed_datetime, reverse=True)[:20]
    ]

    return stats


def generate_archaeology_report(
    repo_path: str,
    llm: LLMClient,
    show_progress: bool = True,
) -> ArchaeologyReport:
    """Generate a full archaeology report for a git repository."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        disable=not show_progress,
    ) as progress:
        progress.add_task("Extracting git history...", total=None)
        stats = extract_git_stats(repo_path)

    if stats.total_commits == 0:
        return ArchaeologyReport(
            stats=stats,
            narrative="No git history found. This directory is either not a git repository "
            "or has no commits.",
        )

    # Format data for the prompt
    contributors_str = "\n".join(
        f"- {c['name']}: {c['commits']} commits" for c in stats.contributors
    )
    hotspots_str = "\n".join(
        f"- {h['file']}: changed {h['changes']} times" for h in stats.hotspot_files
    )
    recent_str = "\n".join(
        f"- [{c['hash']}] {c['date']} ({c['author']}): {c['message']}"
        for c in stats.recent_commits
    )
    tags_str = "\n".join(f"- {t}" for t in stats.tag_history) if stats.tag_history else "no tags"

    prompt = NARRATIVE_PROMPT.format(
        total_commits=stats.total_commits,
        first_commit=stats.first_commit_date,
        last_commit=stats.last_commit_date,
        num_contributors=len(stats.contributors),
        contributors=contributors_str,
        hotspots=hotspots_str,
        recent_commits=recent_str,
        tags=tags_str,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        disable=not show_progress,
    ) as progress:
        progress.add_task("Generating archaeology report with LLM...", total=None)
        narrative = llm.chat(prompt, system=SYSTEM_PROMPT, max_tokens=4096)

    return ArchaeologyReport(stats=stats, narrative=narrative)


def format_report(report: ArchaeologyReport) -> str:
    """Format an archaeology report as Markdown."""
    lines = [
        "# Archaeology Report",
        "",
        f"**Commits:** {report.stats.total_commits} | "
        f"**Period:** {report.stats.first_commit_date} to {report.stats.last_commit_date} | "
        f"**Contributors:** {len(report.stats.contributors)}",
        "",
    ]

    if report.stats.contributors:
        lines.append("## Top Contributors")
        lines.append("")
        lines.append("| Contributor | Commits |")
        lines.append("|---|---|")
        for c in report.stats.contributors[:10]:
            lines.append(f"| {c['name']} | {c['commits']} |")
        lines.append("")

    if report.stats.hotspot_files:
        lines.append("## Change Hotspots")
        lines.append("")
        lines.append("| File | Changes |")
        lines.append("|---|---|")
        for h in report.stats.hotspot_files[:15]:
            lines.append(f"| `{h['file']}` | {h['changes']} |")
        lines.append("")

    lines.append("## Analysis")
    lines.append("")
    lines.append(report.narrative)
    lines.append("")

    return "\n".join(lines)
