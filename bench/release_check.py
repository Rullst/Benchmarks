#!/usr/bin/env python3
"""Find the newest `rullst` release on crates.io and whether it was measured.

Prints `version=<v>` and `measure=true|false` lines (GitHub Actions output
format). A version counts as done when results/versions.json lists it, or
when results/attempts.json records a failed attempt (so a broken release is
not re-measured every day; run the workflow by hand after fixing it).
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT  # noqa: E402

CRATE_URL = "https://crates.io/api/v1/crates/rullst/versions"
USER_AGENT = "Rullst-Benchmarks (https://github.com/Rullst/Benchmarks)"
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")


def semver_key(version: str) -> tuple:
    """Sort key following SemVer 2.0 precedence (prereleases before the release)."""
    match = SEMVER.match(version)
    if not match:
        return (-1, -1, -1, 0, ())
    major, minor, patch, pre = match.groups()
    if pre is None:
        return (int(major), int(minor), int(patch), 1, ())
    parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))
    return (int(major), int(minor), int(patch), 0, parts)


def newest(versions: list[dict]) -> str | None:
    candidates = [v["num"] for v in versions if not v.get("yanked") and SEMVER.match(v["num"])]
    return max(candidates, key=semver_key) if candidates else None


def fetch_versions() -> list[dict]:
    request = urllib.request.Request(CRATE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["versions"]


def done_versions(root: Path = ROOT) -> set[str]:
    done: set[str] = set()
    for name in ("versions.json", "attempts.json"):
        path = root / "results" / name
        if path.is_file():
            done |= {entry["version"] for entry in json.loads(path.read_text()).get("versions", [])}
    return done


def main() -> int:
    version = newest(fetch_versions())
    if version is None:
        print("no rullst version found on crates.io", file=sys.stderr)
        return 1
    measure = version not in done_versions()
    print(f"version={version}")
    print(f"measure={'true' if measure else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
