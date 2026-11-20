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

# The endpoints every implementation serves, and the ones added in v3 that an
# implementation serves once its bench.json lists them in "endpoints" (the
# harness checks and measures only the endpoints a folder declares).
BASE_ENDPOINTS = ("text", "json", "db-single", "html")
EXTRA_ENDPOINTS = ("queries", "updates", "fortunes")
# Phase 2 (docs/v3-spec.md): request handling, writes, forms and sessions.
PHASE2_ENDPOINTS = ("world", "worlds", "world-update", "form", "me")
ENDPOINTS = BASE_ENDPOINTS + EXTRA_ENDPOINTS + PHASE2_ENDPOINTS

# How each endpoint is named in the results (the request the load sends).
ENDPOINT_LABELS = {
    "world": "GET /world/{id}",
    "worlds": "GET /worlds",
    "world-update": "PUT /world/{id}",
    "form": "POST /form",
    "me": "GET /me",
}

# bench.json "phase2" block (docs/v3-spec.md section 2.1).
CSRF_DESIGNS = ("token", "fetch-metadata")
MECHANISM_SOURCES = ("built-in", "generator", "stdlib", "documented", "library")
SESSION_STORES = ("cookie-signed", "cookie-encrypted", "postgresql", "memory")

GROUPS = {
    "rust": "Rust",
    "full-stack": "Full-stack frameworks",
    "reference": "Popular references",
}

# bench.json "role": ranked (the default), an unranked diagnostic shown next
# to the reference (for example Rullst's minimal configuration), or the A/A
# control (an identical copy of the reference, from which the tie margins come).
ROLES = ("ranked", "diagnostic", "control")

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
        problems += _phase2_problems(slug, manifest, endpoints)
    role = manifest.get("role", "ranked")
    if role not in ROLES:
        problems.append(f"{slug}: role must be one of {', '.join(ROLES)}")
    if role != "ranked" and not str(manifest.get("role_note", "")).strip():
        problems.append(f"{slug}: a {role} implementation needs a 'role_note' saying what it is for")
    if "jit" in manifest and not isinstance(manifest["jit"], bool):
        problems.append(f"{slug}: 'jit' must be true or false")
    for field in ("structure_note", "role_note", "control_of", "database_note"):
        if field in manifest and not isinstance(manifest[field], str):
            problems.append(f"{slug}: '{field}' must be a string")
    setup = manifest.get("db_setup")
    if setup is not None:
        path = folder / str(setup)
        if not isinstance(setup, str) or "/" in setup or not setup.endswith(".sql") or not path.is_file():
            problems.append(f"{slug}: 'db_setup' must name a .sql file in the folder (got {setup!r})")
    return problems


def _phase2_problems(slug: str, manifest: dict, endpoints: list[str]) -> list[str]:
    """Problems with the "phase2" block, which a folder needs once it declares a phase-2 endpoint."""
    declared = [e for e in endpoints if e in PHASE2_ENDPOINTS]
    block = manifest.get("phase2")
    if block is None:
        return [f"{slug}: bench.json needs a 'phase2' block for {', '.join(declared)}"] if declared else []
    if not isinstance(block, dict):
        return [f"{slug}: 'phase2' must be an object"]
    problems = []
    if not str(block.get("validation", "")).strip():
        problems.append(f"{slug}: phase2.validation must name the validation mechanism")
    for key, required_by, extra in (("csrf", "form", ("design", CSRF_DESIGNS)),
                                    ("session", "me", ("store", SESSION_STORES))):
        value = block.get(key)
        if value is None and required_by not in endpoints:
            continue
        if not isinstance(value, dict):
            problems.append(f"{slug}: phase2.{key} must be an object (needed for /{required_by})")
            continue
        field, allowed = extra
        if value.get(field) not in allowed:
            problems.append(f"{slug}: phase2.{key}.{field} must be one of {', '.join(allowed)}")
        if value.get("source") not in MECHANISM_SOURCES:
            problems.append(f"{slug}: phase2.{key}.source must be one of {', '.join(MECHANISM_SOURCES)}")
        if not str(value.get("mechanism", "")).strip():
            problems.append(f"{slug}: phase2.{key}.mechanism must name the mechanism")
    write_csrf = block.get("write_csrf")
    if write_csrf is not None and not (isinstance(write_csrf, dict) and set(write_csrf) == {"cookie", "header"}
                                       and all(isinstance(v, str) and v.strip() for v in write_csrf.values())):
        problems.append(f"{slug}: phase2.write_csrf must be null or {{\"cookie\": name, \"header\": name}}")
    return problems


def declared_endpoints(manifest: dict) -> list[str]:
    """The endpoints a framework folder serves, in the suite's order (bench.json "endpoints")."""
    declared = set(manifest.get("endpoints") or BASE_ENDPOINTS)
    return [e for e in ENDPOINTS if e in declared]


def phase2(manifest: dict) -> dict:
    """The folder's "phase2" block (empty when it declares no phase-2 endpoint)."""
    return manifest.get("phase2") or {}


def endpoint_label(config: dict, endpoint: str) -> str:
    """How the results name an endpoint: its request, with the query string phase 1 uses."""
    return ENDPOINT_LABELS.get(endpoint) or endpoint_path(config, endpoint)


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
