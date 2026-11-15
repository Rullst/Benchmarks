#!/usr/bin/env python3
"""Yield guard: should an automatic measurement start now?

Rullst/Rullst and this repository share the organization's pool of hosted
runners. A measurement keeps several runners busy for hours, so automatic runs
wait while Rullst runs a release, its admission checks or a long verification
workflow, or while its queue is long. Reads only the public Actions API
(GITHUB_TOKEN is used when set, for the rate limit). Prints `go=true|false`,
`max_parallel=N` (how many measurement jobs may run at once: 8 when Rullst is
quiet, 3 otherwise) and `reason=...` (GitHub Actions output format).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

API = "https://api.github.com/repos/Rullst/Rullst/actions"
QUIET_PARALLEL = 8  # never more than this
BUSY_PARALLEL = 3
QUIET_QUEUED_JOBS = 2
QUIET_RUNNING_JOBS = 8
GUARDED = {"release.yml", "fuzzing.yml", "kani.yml", "miri.yml", "sanitizers.yml", "proptest.yml", "dast-zap.yml"}


def _get(url: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Rullst-Benchmarks"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def decide(active_runs: list[dict], queued_jobs: int, max_queued_jobs: int) -> tuple[bool, str]:
    for run in active_runs:
        workflow = run.get("path", "").rsplit("/", 1)[-1]
        if workflow in GUARDED:
            return False, f"Rullst/Rullst {workflow} is {run['status']} ({run['html_url']})"
        if workflow == "ci.yml" and run.get("event") == "workflow_dispatch":
            return False, f"Rullst/Rullst release admission (ci.yml workflow_dispatch) is {run['status']} ({run['html_url']})"
    if queued_jobs > max_queued_jobs:
        return False, f"Rullst/Rullst has {queued_jobs} queued jobs (limit {max_queued_jobs})"
    return True, f"Rullst/Rullst: {len(active_runs)} active runs, {queued_jobs} queued jobs"


def parallelism(go: bool, queued_jobs: int, running_jobs: int) -> int:
    """Measurement jobs to run at once: 8 while Rullst/Rullst is quiet, 3 otherwise."""
    if go and queued_jobs <= QUIET_QUEUED_JOBS and running_jobs <= QUIET_RUNNING_JOBS:
        return QUIET_PARALLEL
    return BUSY_PARALLEL


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-queued-jobs", type=int, default=10)
    args = parser.parse_args(argv)
    try:
        runs = []
        for status in ("in_progress", "queued", "waiting", "pending"):
            runs += _get(f"{API}/runs?status={status}&per_page=100").get("workflow_runs", [])
        queued = running = 0
        for run in runs[:30]:
            jobs = _get(f"{API}/runs/{run['id']}/jobs?filter=latest&per_page=100").get("jobs", [])
            queued += sum(1 for job in jobs if job.get("status") in ("queued", "waiting", "pending"))
            running += sum(1 for job in jobs if job.get("status") == "in_progress")
        go, reason = decide(runs, queued, args.max_queued_jobs)
        max_parallel = parallelism(go, queued, running)
        reason += f", {running} running jobs; up to {max_parallel} measurement jobs at once"
    except (OSError, ValueError) as exc:
        go, reason, max_parallel = False, f"could not read the Rullst/Rullst Actions API: {exc}", BUSY_PARALLEL
    print(f"go={'true' if go else 'false'}")
    print(f"max_parallel={max_parallel}")
    print(f"reason={reason}")
    print(reason, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
