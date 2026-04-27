# Best Practices Auditor — Roadmap

Items listed here are explicitly **out of scope** for v0.2. They are
documented for consideration in future releases.

## v0.3+ Candidates

### Additional Languages
- Rust, Go, JavaScript/TypeScript checker suites under
  `checkers/<language>/` mirroring the Python structure.
- `--language` flag already accepts a string; adding a new language
  means creating a new checker directory and registering it in
  `runner.SUPPORTED_LANGUAGES`.

### Security Scanning
- Dependency vulnerability checks (e.g. querying OSV or PyPI advisory
  database).
- Secret detection in source files.
- This is planned as a **separate feature**, not part of the
  best-practices auditor.

### Performance Profiling
- Detect common anti-patterns (e.g. N+1 queries, synchronous I/O in
  async contexts).

### Observability
- Check for structured logging configuration.
- Check for OpenTelemetry / metrics instrumentation.

### Deep Type Analysis
- Use mypy or pyright output to report type coverage percentage.
- Currently out of scope because it requires running an external tool
  against the audited repo.

### Accessibility
- Relevant only if the audited project includes a web frontend.
  Not applicable to pure Python libraries.
