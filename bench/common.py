"""Shared helpers: paths, configuration, manifests and subprocess calls."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "bench"
FRAMEWORKS = ROOT / "frameworks"

# How often a starting server is checked (GET /text) until it answers.
READY_POLL_S = 0.25

# The endpoints every implementation serves, and the ones added in v2 that an
# implementation serves once its bench.json lists them in "endpoints" (the
# harness checks and measures only the endpoints a folder declares).
BASE_ENDPOINTS = ("text", "json", "db-single", "html")
EXTRA_ENDPOINTS = ("queries", "updates", "fortunes")
ENDPOINTS = BASE_ENDPOINTS + EXTRA_ENDPOINTS

GROUPS = {
    "rust": "Rust",
    "full-stack": "Full-stack frameworks",
    "reference": "Popular references",
}

REQUIRED_MANIFEST_FIELDS = (
    "name",
    "language",
    "group",
    "framework",
    "framework_version",
    "runtime",
    "server",
    "workers",
    "database_layer",
    "template_engine",
    "logging",
)


class BenchError(Exception):
    """A failure that stops the current job with a readable message."""


def log(message: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", file=sys.stderr, flush=True)


def load_config() -> dict:
    return json.loads((BENCH / "config.json").read_text())


def framework_slugs() -> list[str]:
    return sorted(p.parent.name for p in FRAMEWORKS.glob("*/bench.json"))


def validate_manifest(slug: str, manifest: dict) -> list[str]:
    """Return a list of problems with a framework folder (empty when valid)."""
    problems = []
    folder = FRAMEWORKS / slug
    for field in REQUIRED_MANIFEST_FIELDS:
        if not str(manifest.get(field, "")).strip():
            problems.append(f"{slug}: bench.json is missing '{field}'")
    if manifest.get("group") not in GROUPS:
        problems.append(f"{slug}: group must be one of {', '.join(GROUPS)}")
    for name in ("Dockerfile", "README.md"):
        if not (folder / name).is_file():
            problems.append(f"{slug}: {name} is missing")
    for arg in manifest.get("build_args_from_env", []):
        if not arg.isidentifier():
            problems.append(f"{slug}: invalid build argument name '{arg}'")
    if not isinstance(manifest.get("env", {}), dict):
        problems.append(f"{slug}: 'env' must be an object")
    endpoints = manifest.get("endpoints", list(BASE_ENDPOINTS))
    if not isinstance(endpoints, list) or not all(isinstance(e, str) for e in endpoints):
        problems.append(f"{slug}: 'endpoints' must be a list of endpoint names")
    else:
        unknown = [e for e in endpoints if e not in ENDPOINTS]
        missing = [e for e in BASE_ENDPOINTS if e not in endpoints]
        if unknown:
            problems.append(f"{slug}: unknown endpoints {', '.join(unknown)} (known: {', '.join(ENDPOINTS)})")
        if missing:
            problems.append(f"{slug}: 'endpoints' must include {', '.join(missing)}")
    return problems


def declared_endpoints(manifest: dict) -> list[str]:
    """The endpoints a framework folder serves, in the suite's order (bench.json "endpoints")."""
    declared = set(manifest.get("endpoints") or BASE_ENDPOINTS)
    return [e for e in ENDPOINTS if e in declared]


def endpoint_path(config: dict, endpoint: str) -> str:
    """The request path the load generator uses for an endpoint (with its query string)."""
    return config.get("endpoint_paths", {}).get(endpoint, f"/{endpoint}")


def load_manifest(slug: str) -> dict:
    path = FRAMEWORKS / slug / "bench.json"
    if not path.is_file():
        raise BenchError(f"unknown framework '{slug}' (no {path.relative_to(ROOT)})")
    manifest = json.loads(path.read_text())
    problems = validate_manifest(slug, manifest)
    if problems:
        raise BenchError("; ".join(problems))
    manifest["slug"] = slug
    return manifest


def run(cmd: list[str], *, check: bool = True, timeout: float | None = None,
        input_text: str | None = None) -> subprocess.CompletedProcess:
    """Run a command and capture its text output."""
    try:
        result = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BenchError(f"timed out after {timeout}s: {' '.join(cmd)}") from exc
    if check and result.returncode != 0:
        tail = (result.stderr or result.stdout).strip()[-2000:]
        raise BenchError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{tail}")
    return result


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")
