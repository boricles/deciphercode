# DecipherCode

[![GitHub release](https://img.shields.io/github/v/release/boricles/deciphercode?include_prereleases&label=version)](https://github.com/boricles/deciphercode/releases)
[![GitHub stars](https://img.shields.io/github/stars/boricles/deciphercode)](https://github.com/boricles/deciphercode/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/boricles/deciphercode)](https://github.com/boricles/deciphercode/network/members)
[![License: MIT](https://img.shields.io/github/license/boricles/deciphercode)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)

**Give your legacy code a voice.**

DecipherCode is a CLI tool that uses LLMs to analyze legacy codebases and generate comprehensive documentation. Point it at any project directory (or GitHub URL) and get instant architecture analysis, README generation, diagrams, and git archaeology reports.

Works with any OpenAI-compatible API: OpenAI, Ollama, Azure OpenAI, Anthropic (via proxy), and more.

## Features

- :mag: **Full Repo Analysis** - Detect languages, frameworks, architecture patterns, APIs, database models, environment variables, and dead code
- :page_facing_up: **README Generation** - Generate a professional README.md complete with badges, setup instructions, and API documentation
- :triangular_ruler: **Architecture Diagrams** - Produce Mermaid or GraphViz DOT diagrams showing components, data flow, and module dependencies
- :scroll: **Git Archaeology** - Analyze commit history to find contributors, tech debt hotspots, and project evolution narrative
- :speech_balloon: **Interactive Q&A** - Ask natural language questions about any codebase and get precise, context-aware answers
- :electric_plug: **LLM-Agnostic** - Configure once via environment variables; works with OpenAI, Azure OpenAI, Anthropic, and Ollama
- :white_check_mark: **Repository Health Auditor** - `decipher practices` scores a Python project against 8 categories (project structure, testing, quality tooling, CI/CD, licensing, release readiness, dependency hygiene, documentation) with a reproducible fail/warn severity model

## Quick Start

### Installation

<!--
```bash
pip install deciphercode
```
Or--> Install from source:

```bash
git clone https://github.com/boricles/deciphercode.git
cd deciphercode
pip install -e ".[dev]"
```

### Configuration

DecipherCode supports multiple LLM providers. Configure via environment variables:

```bash
# OpenAI
export DECIPHER_API_BASE="https://api.openai.com/v1"
export DECIPHER_API_KEY="sk-..."
export DECIPHER_MODEL="gpt-4o"

# Ollama (default, no key needed)
export DECIPHER_API_BASE="http://localhost:11434/v1"
export DECIPHER_API_KEY="ollama"
export DECIPHER_MODEL="llama3"

# Azure OpenAI (auto-detected from URL)
export DECIPHER_API_BASE="https://your-resource.cognitiveservices.azure.com"
export DECIPHER_API_KEY="your-azure-key"
export DECIPHER_MODEL="your-deployment-name"
export DECIPHER_API_VERSION="2024-10-21"    # optional, this is the default

# Anthropic via proxy
export DECIPHER_API_PROVIDER="anthropic"
export DECIPHER_API_BASE="http://localhost:8080"
export DECIPHER_API_KEY="your-anthropic-key"
export DECIPHER_MODEL="claude-opus-4-6"
```

**Provider auto-detection:** If your `DECIPHER_API_BASE` URL contains `azure.com`, the Azure OpenAI client is used automatically. Set `DECIPHER_API_PROVIDER` explicitly to force a specific provider (`openai`, `azure`, or `anthropic`).

### Usage

```bash
# Full codebase analysis
decipher scan ./my-legacy-app

# Generate a README
decipher readme ./my-legacy-app -o README.md

# Architecture diagrams (Mermaid or DOT)
decipher diagram ./my-legacy-app --format mermaid
decipher diagram ./my-legacy-app --format dot -o architecture.dot

# Git archaeology report
decipher history ./my-legacy-app

# Ask a question
decipher ask ./my-legacy-app "How does the auth flow work?"

# Interactive Q&A session
decipher ask ./my-legacy-app

# Scan from a GitHub URL
decipher scan https://github.com/user/repo

# Export analysis as JSON
decipher scan ./my-legacy-app --json -o analysis.json

# Verbose mode for debugging
decipher -v scan ./my-legacy-app
```

## Practices Auditor

Audit any Python repository against software-development best practices:

```bash
# Default audit (terminal output when TTY, markdown in CI)
decipher practices /path/to/repo

# JSON report to file
decipher practices . --format json -o report.json

# Fail CI on warnings (not just failures)
decipher practices . --strict

# Run only specific checkers
decipher practices . --only testing,quality_gates
```

The auditor produces a structured report with per-category scores (0-100) and
prioritised recommendations. Exit codes: 0 = pass, 1 = fail (or warn with
`--strict`), 2 = input error.

## Commands

| Command | Description |
|---|---|
| `decipher scan <target>` | Full analysis: languages, architecture, APIs, dead code, and more |
| `decipher readme <target>` | Generate a professional README.md |
| `decipher diagram <target>` | Generate Mermaid or GraphViz architecture diagrams |
| `decipher history <target>` | Git archaeology: contributors, hotspots, evolution timeline |
| `decipher ask <target> [question]` | Ask questions about the codebase (interactive if no question given) |
| `decipher practices <target>` | Audit repository against best practices (8 checkers, fail/warn scoring) |

All commands accept a local directory path or a GitHub URL as the target.

## Example Output

See the [examples/](examples/) directory for sample outputs:

- [Scan report](examples/sample-scan-report.md) - Full analysis of a Django e-commerce API
- [Mermaid diagrams](examples/sample-mermaid-diagram.md) - Component, data flow, and dependency diagrams
- [Archaeology report](examples/sample-archaeology-report.md) - Git history analysis with contributor and hotspot data

## Project Structure

```
deciphercode/
├── decipher/
│   ├── __init__.py          # Package version
│   ├── cli.py               # Click CLI commands
│   ├── scanner.py           # Codebase scanning and file discovery
│   ├── analyzer.py          # LLM-powered code analysis
│   ├── readme_generator.py  # README.md generation
│   ├── archaeologist.py     # Git history analysis
│   ├── diagrammer.py        # Mermaid/DOT diagram generation
│   ├── interactive.py       # Interactive Q&A mode
│   ├── llm.py               # LLM client wrapper (OpenAI, Azure, Anthropic)
│   └── utils.py             # File reading, language detection, helpers
├── tests/                   # Test suite (72 tests)
├── examples/                # Sample outputs
├── pyproject.toml           # Project metadata and dependencies
├── LICENSE                  # MIT
└── README.md
```

## How It Works

1. **Scan** - Walks the directory tree, identifies source files, detects languages and frameworks, finds dependency files, maps config and environment variables, and identifies entry points.

2. **Analyze** - Representative source files are sampled and sent to the LLM along with the project structure. The LLM identifies the architecture pattern, components, API routes, database models, dead code candidates, and key observations.

3. **Generate** - Based on the analysis, DecipherCode can produce a README, architecture diagrams, or an archaeology report. Each output type uses a specialized prompt designed to produce accurate, well-structured results.

4. **Interactive** - In Q&A mode, the full codebase context is loaded into the conversation, allowing you to ask natural language questions and get precise answers that reference specific files and functions.

## Upgrading

See [CHANGELOG.md](CHANGELOG.md) for what's new and [MIGRATION.md](MIGRATION.md) for breaking changes between releases.

## Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `DECIPHER_API_BASE` | `http://localhost:11434/v1` | API base URL |
| `DECIPHER_API_KEY` | `ollama` | API key (use `ollama` for local Ollama) |
| `DECIPHER_MODEL` | `llama3` | Model name (or Azure deployment name) |
| `DECIPHER_API_PROVIDER` | *(auto-detected)* | Force a provider: `openai`, `azure`, or `anthropic` |
| `DECIPHER_API_VERSION` | `2024-10-21` | Azure OpenAI API version |

## Dependencies

- [Click](https://click.palletsprojects.com/) - CLI framework
- [OpenAI Python SDK](https://github.com/openai/openai-python) - OpenAI and Azure OpenAI client
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) - Anthropic API client
- [Rich](https://rich.readthedocs.io/) - Terminal formatting and progress bars
- [GitPython](https://gitpython.readthedocs.io/) - Git history analysis
- [tiktoken](https://github.com/openai/tiktoken) - Token counting for prompt management
- [PyYAML](https://pyyaml.org/) - YAML config file parsing

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=decipher

# Lint
ruff check decipher/ tests/
```

## Contributing

Contributions are welcome! Here's how to get involved:

1. **Report bugs** - Open an [issue](https://github.com/boricles/deciphercode/issues) with steps to reproduce
2. **Suggest features** - Describe the use case and expected behavior in an issue
3. **Submit PRs** - Fork the repo, create a feature branch, add tests, and open a pull request

Please keep PRs focused on a single change and ensure all tests pass before submitting.

## Acknowledgments

This project was built with [Claude Code](https://claude.ai/code) by Anthropic as the primary development tool. Architecture design, implementation, testing, and documentation were developed through collaborative AI-assisted programming.

## License

MIT License. See [LICENSE](LICENSE) for details.
