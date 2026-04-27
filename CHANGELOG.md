# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-27

### Added

- **`decipher practices` command** -- repository health auditor that scores a
  Python project against software-development best practices and produces a
  structured report with per-category scores and prioritised recommendations.
- **8 practice checkers** covering project structure (PROJ-001..011), testing
  (TEST-001..005), quality gates (QUAL-001..005), CI/CD (CICD-001..006),
  dependency hygiene (DEP-001..005), documentation (DOC-001..005), licensing
  (LIC-001..003), and release readiness (REL-001..007).
- **Finding registry** with compact IDs (`PREFIX-NNN`) and gate codes (DEP-001,
  DOC-001) that conditionally suppress downstream findings when a prerequisite
  check fails.
- **Severity model** -- every finding is `fail` (can't ship) or `warn` (should
  improve). Scoring formula: `max(0, 100 - warn*10 - fail*25)`.
- **CLI flags** for the `practices` command:
  - `--format terminal|markdown|json` (auto-detected from TTY, CI environment
    variables, or `-o` file extension).
  - `--strict` -- exit 1 on warnings, not just failures.
  - `--only <checkers>` / `--skip <checkers>` -- run or exclude specific
    checkers (comma-separated, mutually exclusive).
  - `-o <path>` -- write report to file; format inferred from extension
    (`.json`, `.md`).
- **Exit-code semantics** -- 0 (pass, or warn without `--strict`), 1 (fail, or
  warn with `--strict`), 2 (input/argument error).
- **Dogfood gate** -- the tool audits itself (`decipher practices .`) and must
  score 100/100 before shipping.
- **CI workflow** (`.github/workflows/ci.yml`) -- pytest across Python
  3.10--3.13, ruff lint, and mypy (informational, `continue-on-error: true`).
- **Coverage configuration** (`[tool.coverage.run]`/`[tool.coverage.report]`)
  with `fail_under = 80` and an omit list for LLM-dependent modules.
- **mypy strict configuration** (`[tool.mypy] strict = true`) in pyproject.toml.
- **Pre-commit hooks** -- ruff lint + format, plus basic hygiene hooks
  (trailing-whitespace, end-of-file-fixer, check-yaml, check-toml,
  check-merge-conflict).
- **Reporter** with three output backends: `to_json()`, `to_markdown()`, and
  `to_terminal()` (Rich Panel + Table + Text, returned as
  `rich.console.Group`).

### Changed

- **License** changed from Apache-2.0 to MIT. See [LICENSE](LICENSE) and
  [MIGRATION.md](MIGRATION.md) for details.
- `Reporter.to_terminal()` now returns `rich.console.Group` instead of printing
  directly. Downstream Python consumers that called this method must update
  their rendering code. CLI users are unaffected.

### Deprecated

- **`--json-only`** flag on `decipher practices`. Use `--format json` instead.
  The old flag is retained as a hidden alias for one release cycle and will be
  **removed in v0.3**.

### Fixed

- Added `TYPE_CHECKING` guard imports in `cli.py`, resolving 3 mypy
  `[name-defined]` errors for `LLMClient` and `AnalysisResult`.
- Renamed ambiguous variable `l` to `ln` in `analyzer.py` and `interactive.py`
  (ruff E741).

### Internal

- Phase-gated development pattern (A-F) introduced for v0.2.0; used as
  governance baseline for future releases.

### Known Limitations (v0.3 backlog)

- 45 mypy strict-mode errors remain (approximately 30 in practices checkers,
  15 in legacy modules). The CI mypy step is informational
  (`continue-on-error: true`) and will be promoted to blocking once errors
  reach zero.
- LLM-dependent modules (`archaeologist`, `diagrammer`, `interactive`,
  `readme_generator`) are excluded from coverage measurement. Adding response
  recorders (e.g. `vcrpy`) is planned for v0.3.
- `--json-only` hidden alias will be removed in v0.3.
- Only Python repositories are supported. Additional language support is
  planned for future releases.

## [0.1.0] - 2026-04-17

### Added
- Initial release of DecipherCode
- Full codebase analysis with LLM-powered architecture detection
- README generation from any codebase
- Architecture diagrams (Mermaid, GraphViz DOT)
- Git archaeology reports with contributor and hotspot analysis
- Interactive Q&A mode for natural language codebase exploration
- Multi-provider LLM support:
  - OpenAI
  - Azure OpenAI
  - Anthropic (via proxy)
  - Ollama (local)
- Support for local directories and GitHub URLs as input
- JSON export for scan results
