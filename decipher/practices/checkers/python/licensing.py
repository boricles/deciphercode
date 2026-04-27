"""Checker for licensing best practices."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from decipher.practices.models import CheckerResult, Finding, compute_score, worst_status

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[import-not-found]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

_LICENSE_VARIANTS = [
    "LICENSE",
    "LICENSE.txt",
    "LICENSE.md",
    "LICENCE",
    "LICENCE.txt",
    "LICENCE.md",
]

# Maps a keyword found in the LICENSE text to its SPDX-like short name.
# Order matters: first match wins. More specific patterns go first.
_KNOWN_LICENSES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"Apache License.*Version 2", re.IGNORECASE), "Apache-2.0"),
    (re.compile(r"GNU GENERAL PUBLIC LICENSE.*Version 3", re.IGNORECASE | re.DOTALL), "GPL-3.0"),
    (re.compile(r"GNU GENERAL PUBLIC LICENSE.*Version 2", re.IGNORECASE | re.DOTALL), "GPL-2.0"),
    (re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE", re.IGNORECASE), "LGPL"),
    (re.compile(r"Mozilla Public License.*2\.0", re.IGNORECASE), "MPL-2.0"),
    (re.compile(r"MIT License", re.IGNORECASE), "MIT"),
    (re.compile(r"Permission is hereby granted.*The above copyright", re.DOTALL), "MIT"),
    (re.compile(r"BSD 3-Clause", re.IGNORECASE), "BSD-3-Clause"),
    (re.compile(r"BSD 2-Clause", re.IGNORECASE), "BSD-2-Clause"),
    (re.compile(r"Redistribution and use in source and binary forms", re.IGNORECASE), "BSD"),
    (re.compile(r"The Unlicense", re.IGNORECASE), "Unlicense"),
    (re.compile(r"ISC License", re.IGNORECASE), "ISC"),
]


class Checker:
    """Licensing checker for Python repos.

    Finding IDs: LIC-001 through LIC-003.

    - LIC-001: LICENSE file present at repository root
    - LIC-002: LICENSE file identifies a known license
    - LIC-003: License declared in pyproject.toml is consistent with LICENSE file

    LIC-002 and LIC-003 are only emitted when LIC-001 passes
    (conditional suppression: no LICENSE file means nothing to inspect).

    Per-file license headers are NOT checked in v0.2. The project
    convention is no headers; this check may be added as opt-in in v0.3.

    Scoring: uses the default compute_score() formula.
        score = max(0, 100 - (warn_count * 10) - (fail_count * 25))
    """

    name = "licensing"
    display_name = "Licensing"

    def run(self, repo_path: Path) -> CheckerResult:
        findings: list[Finding] = []
        recommendations: list[str] = []

        license_path, license_text = self._find_license(repo_path)

        has_license = self._check_license_present(
            license_path,
            findings,
            recommendations,
        )

        if has_license:
            detected = self._check_known_license(
                license_path,
                license_text,
                findings,
                recommendations,
            )
            self._check_pyproject_consistency(
                repo_path,
                license_path,
                detected,
                findings,
                recommendations,
            )

        return CheckerResult(
            name=self.name,
            display_name=self.display_name,
            status=worst_status(findings) if findings else "pass",
            score=compute_score(findings),
            findings=findings,
            recommendations=recommendations,
        )

    @staticmethod
    def _find_license(repo_path: Path) -> tuple[str | None, str]:
        """Return (relative_path, text) for the first LICENSE variant found."""
        for name in _LICENSE_VARIANTS:
            path = repo_path / name
            if path.exists():
                try:
                    return name, path.read_text()
                except OSError:
                    return name, ""
        return None, ""

    @staticmethod
    def _detect_license(text: str) -> str | None:
        """Return the SPDX-like short name if the text matches a known license."""
        for pattern, spdx in _KNOWN_LICENSES:
            if pattern.search(text):
                return spdx
        return None

    def _check_license_present(
        self,
        license_path: str | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> bool:
        if license_path:
            findings.append(
                Finding(
                    id="LIC-001",
                    message=f"LICENSE file found ({license_path})",
                    severity="pass",
                    category=self.name,
                    file_path=license_path,
                )
            )
            return True

        findings.append(
            Finding(
                id="LIC-001",
                message="No LICENSE file found at repository root",
                severity="fail",
                category=self.name,
            )
        )
        recommendations.append("Add a LICENSE file to the repository root")
        return False

    def _check_known_license(
        self,
        license_path: str | None,
        license_text: str,
        findings: list[Finding],
        recommendations: list[str],
    ) -> str | None:
        detected = self._detect_license(license_text)

        if detected:
            findings.append(
                Finding(
                    id="LIC-002",
                    message=f"License identified as {detected}",
                    severity="pass",
                    category=self.name,
                    file_path=license_path,
                )
            )
        else:
            findings.append(
                Finding(
                    id="LIC-002",
                    message="LICENSE file does not match a known license",
                    severity="warn",
                    category=self.name,
                    file_path=license_path,
                    detail="Could not identify MIT, Apache-2.0, BSD, GPL, or other common licenses",
                )
            )
            recommendations.append("Use a standard license text (e.g. from choosealicense.com)")
        return detected

    def _check_pyproject_consistency(
        self,
        repo_path: Path,
        license_path: str | None,
        detected_license: str | None,
        findings: list[Finding],
        recommendations: list[str],
    ) -> None:
        pyproject = repo_path / "pyproject.toml"
        if not pyproject.exists():
            return  # No pyproject.toml → nothing to compare

        declared = self._get_declared_license(pyproject)
        if declared is None:
            findings.append(
                Finding(
                    id="LIC-003",
                    message="No license declared in pyproject.toml",
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
            recommendations.append(
                "Declare the license in pyproject.toml under [project] "
                '(e.g. license = {text = "MIT"})'
            )
            return

        if detected_license is None:
            # Can't compare if we couldn't identify the LICENSE file
            return

        # Normalize for comparison: lowercase, strip punctuation
        declared_norm = declared.lower().replace("-", "").replace(".", "").strip()
        detected_norm = detected_license.lower().replace("-", "").replace(".", "").strip()

        if detected_norm in declared_norm or declared_norm in detected_norm:
            findings.append(
                Finding(
                    id="LIC-003",
                    message=(
                        f"pyproject.toml license ({declared}) is consistent "
                        f"with LICENSE file ({detected_license})"
                    ),
                    severity="pass",
                    category=self.name,
                    file_path="pyproject.toml",
                )
            )
        else:
            findings.append(
                Finding(
                    id="LIC-003",
                    message=(
                        f'pyproject.toml declares "{declared}" but LICENSE '
                        f"file appears to be {detected_license}"
                    ),
                    severity="warn",
                    category=self.name,
                    file_path="pyproject.toml",
                    detail="Ensure the declared license matches the LICENSE file",
                )
            )
            recommendations.append("Make pyproject.toml license field match the LICENSE file")

    @staticmethod
    def _get_declared_license(pyproject: Path) -> str | None:
        """Extract the license string from pyproject.toml."""
        if tomllib is not None:
            try:
                data = tomllib.loads(pyproject.read_text())
                project = data.get("project", {})
                lic = project.get("license")
                if isinstance(lic, str):
                    return lic
                if isinstance(lic, dict):
                    return lic.get("text") or lic.get("file")
                # PEP 639: license-expression
                return project.get("license-expression")
            except Exception:
                return None
        # Fallback: basic string search
        content = pyproject.read_text()
        for line in content.splitlines():
            if "license" in line.lower() and "=" in line:
                # Rough extraction
                _, _, value = line.partition("=")
                return value.strip().strip('"').strip("'").strip("{}")
        return None
