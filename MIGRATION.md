# Migration Guide: v0.1.0 to v0.2.0

This document covers **breaking changes only**. For the full list of additions,
deprecations, and fixes, see [CHANGELOG.md](CHANGELOG.md).

---

## 1. License change: Apache-2.0 to MIT

The project license changed from Apache-2.0 to MIT starting with v0.2.0.

**What this means:**

- MIT is more permissive than Apache-2.0. If your use was compliant under
  Apache-2.0, it remains compliant under MIT.
- Apache-2.0's patent-grant clause no longer applies. If patent protection was
  important to your use case, evaluate whether MIT meets your requirements.
- Copies of v0.1.0 remain under Apache-2.0. The relicense applies to v0.2.0
  and all subsequent versions.

The full license text is in [LICENSE](LICENSE).

---

## 2. `--json-only` flag deprecated

The `--json-only` flag on `decipher practices` is deprecated. It continues to
work as a hidden alias in v0.2.0 but will be **removed in v0.3**.

**Before (v0.1.0):**

```sh
decipher practices /path/to/repo --json-only
```

**After (v0.2.0+):**

```sh
decipher practices /path/to/repo --format json
```

The new `--format` flag also accepts `terminal` and `markdown`, and
auto-detects the format from the `-o` file extension or the TTY/CI environment
when omitted.

---

## Notes for downstream Python consumers

### `Reporter.to_terminal()` is new in v0.2.0

The Reporter API exposes a new `to_terminal()` method that returns a
`rich.console.Group` containing a `Panel`, `Table`, and `Text` renderable.
Callers must pass the return value to a `rich.console.Console` instance for
rendering:

```python
from rich.console import Console
from decipher.practices.reporter import Reporter

reporter = Reporter()
renderable = reporter.to_terminal(report)

console = Console()
console.print(renderable)
```

This is a new API surface, not a change to an existing one. It is noted here
because the return type (`Group` rather than `None`) is a deliberate design
decision that downstream consumers should be aware of.
