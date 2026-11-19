#!/usr/bin/env python3
"""Benchmark harness entry point.

  harness.py validate                     check every framework folder
  harness.py plan --frameworks all        print the job matrix (JSON list)
  harness.py conformance --framework X    build X, start PostgreSQL, run conformance
  harness.py db-check                     start PostgreSQL, check bench/db and every
                                          folder's db_setup file (no image builds)
  harness.py run --framework X --rounds N --out result.json
                                          build X and the baseline, check both,
                                          then measure interleaved rounds
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (BenchError, declared_endpoints, framework_slugs, load_config, load_manifest, log,  # noqa: E402
                    validate_manifest, write_json)
from conformance import run_checks  # noqa: E402
from containers import (apply_db_setup, build_image, psql, run_sql_file, set_statement_tracking,  # noqa: E402
                        start_database, start_server, remove, DB_CONTAINER, FRAMEWORKS)
from loadgen import describe_binary  # noqa: E402
from measure import measure_round, ratios, require_measurable, summarize  # noqa: E402
from system import cpu_split, environment  # noqa: E402

SCHEMA = 1


def cmd_validate(_args) -> int:
    problems = []
    for slug in framework_slugs():
        manifest = json.loads((Path(__file__).resolve().parent.parent / "frameworks" / slug / "bench.json").read_text())
        problems += validate_manifest(slug, manifest)
    if load_config()["baseline"] not in framework_slugs():
        problems.append("the baseline framework folder is missing")
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"{len(framework_slugs())} framework folders checked, {len(problems)} problems")
    return 1 if problems else 0


def resolve_frameworks(spec: str) -> list[str]:
    available = framework_slugs()
    baseline = load_config()["baseline"]
    if spec.strip().lower() in ("", "all"):
        chosen = available
    else:
        chosen = [s.strip() for s in spec.split(",") if s.strip()]
        unknown = [s for s in chosen if s not in available]
        if unknown:
            raise BenchError(f"unknown frameworks: {', '.join(unknown)} (available: {', '.join(available)})")
    # Every job measures the baseline alongside its framework, so the baseline
    # gets its own job only when it is the only one requested.
    jobs = [s for s in chosen if s != baseline]
    return jobs or [baseline]


def cmd_plan(args) -> int:
    print(json.dumps(resolve_frameworks(args.frameworks)))
    return 0


def database_cpus(config: dict) -> int:
    """CPUs reserved for PostgreSQL: 0 shares the load generator's (config or BENCH_DATABASE_CPUS)."""
    value = os.environ.get("BENCH_DATABASE_CPUS", "").strip()
    if value:
        if not value.isdigit():
            raise BenchError("BENCH_DATABASE_CPUS must be a whole number")
        return int(value)
    return int(config["database"].get("cpus", 0))


def _split(config: dict) -> dict:
    split = cpu_split(config["server"]["cpus"], config["min_runner_cpus"], database_cpus(config))
    if split["database_shared"]:
        log(f"CPU split: server {split['server']}, load generator and database {split['client']}")
    else:
        log(f"CPU split: server {split['server']}, load generator {split['client']}, "
            f"database {split['database']}")
    return split


def _prepare(config: dict) -> tuple[dict, Path, dict]:
    split = _split(config)
    binary = Path(os.environ.get("WRK", "wrk"))
    loadgen = describe_binary(binary, config["load_generator"])
    # The harness itself (and its RAM sampler) stays off the server CPUs.
    os.sched_setaffinity(0, split["client"])
    return split, binary, loadgen


def _check(manifest: dict, config: dict, split: dict) -> dict:
    server = start_server(manifest, config, split["server"], keep_logs=True)
    report: dict
    try:
        startup = server.wait_ready(manifest.get("startup_timeout_s", 120))
        report = run_checks(server.port, config, endpoints=declared_endpoints(manifest), manifest=manifest)
        report["startup_s"] = startup
    except BenchError as exc:
        report = {"passed": False, "checks": [{"endpoint": "startup", "ok": False, "problem": str(exc)}]}
    if not report["passed"]:
        report["logs_tail"] = server.logs_tail()
    server.stop()
    return report


def _implementation(slug: str, config: dict, split: dict) -> dict:
    manifest = load_manifest(slug)
    entry: dict = {"manifest": manifest, "status": "pending"}
    try:
        entry["build"] = build_image(manifest)
    except BenchError as exc:
        entry.update(status="build-failed", error=str(exc)[-3000:])
        return entry
    try:
        entry["db_setup"] = apply_db_setup(config, manifest)
    except BenchError as exc:
        entry["conformance"] = {"passed": False, "checks": [
            {"endpoint": f"db_setup ({manifest.get('db_setup')})", "ok": False, "problem": str(exc)[-1500:]}]}
        entry["status"] = "failed-conformance"
        return entry
    entry["conformance"] = _check(manifest, config, split)
    entry["status"] = "conformant" if entry["conformance"]["passed"] else "failed-conformance"
    return entry


def framework_tables(entry: dict) -> list[str]:
    """The tables an implementation's db_setup created (emptied at the start of every round)."""
    return list((entry.get("db_setup") or {}).get("tables", []))


# What bench/db/phase2.sql must contain (docs/v2-phase2-spec.md section 2.2).
USER_CHECKS = {
    "accounts user1..user1000 with display names 'User N'":
        "SELECT count(*) = 1000 AND min(id) = 1 AND max(id) = 1000 AND bool_and(username = 'user' || id) "
        "AND bool_and(display_name = 'User ' || id) FROM users",
    # Every row has the same hash (one salt): pgcrypto checks each distinct value once. It reads
    # bcrypt's $2a$ prefix; $2b$ is the same algorithm for this password.
    "bcrypt ($2b$, cost 10) hashes of 'bench-password'":
        "SELECT bool_and(password_bcrypt LIKE '$2b$10$%') AND (SELECT bool_and(crypt('bench-password', h) = h "
        "AND crypt('wrong-password', h) <> h) FROM (SELECT DISTINCT '$2a$' || substr(password_bcrypt, 5) AS h "
        "FROM users) hashes) FROM users",
    "Argon2id PHC strings with m=19456, t=2, p=1":
        "SELECT bool_and(password_argon2id ~ '^\\$argon2id\\$v=19\\$m=19456,t=2,p=1\\$[A-Za-z0-9+/]{22}\\$"
        "[A-Za-z0-9+/]{43}$') FROM users",
}


def cmd_db_check(_args) -> int:
    """Load bench/db into PostgreSQL, check the phase-2 accounts, and dry-run every db_setup file."""
    config = load_config()
    problems = []
    database = start_database(config, list(os.sched_getaffinity(0)))
    try:
        psql(config, "CREATE EXTENSION IF NOT EXISTS pgcrypto")
        for name, sql in USER_CHECKS.items():
            ok = psql(config, sql) == "t"
            print(f"{'ok' if ok else 'FAILED'}: users: {name}")
            if not ok:
                problems.append(f"users: {name}")
        psql(config, "DROP EXTENSION pgcrypto")
        for slug in framework_slugs():
            manifest = load_manifest(slug)
            setup = manifest.get("db_setup")
            if not setup:
                continue
            try:
                run_sql_file(config, (FRAMEWORKS / slug / setup).read_text(), rollback=True)
                print(f"ok: {slug}/{setup} applies (rolled back)")
            except BenchError as exc:
                print(f"FAILED: {slug}/{setup}: {exc}")
                problems.append(f"{slug}/{setup}")
    finally:
        remove(DB_CONTAINER)
    print(f"PostgreSQL {database['version']}: {len(problems)} problems")
    return 1 if problems else 0


def cmd_conformance(args) -> int:
    config = load_config()
    split = _split(config)
    database = start_database(config, split["database"])
    try:
        entry = _implementation(args.framework, config, split)
    finally:
        remove(DB_CONTAINER)
    entry["database"] = database
    if args.out:
        write_json(Path(args.out), entry)
    print(json.dumps(entry.get("conformance", {"error": entry.get("error")}), indent=2))
    return 0 if entry["status"] == "conformant" else 1


def cmd_run(args) -> int:
    config = load_config()
    baseline = config["baseline"]
    if args.rounds < 1:
        raise BenchError("--rounds must be at least 1")
    split, binary, loadgen = _prepare(config)
    result: dict = {
        "schema": SCHEMA,
        "framework": args.framework,
        "baseline": baseline,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rounds_requested": args.rounds,
        "config": config,
        "environment": environment(split, loadgen),
        "implementations": {},
    }
    out = Path(args.out)
    database = start_database(config, split["database"])
    result["database"] = database
    order = [args.framework] if args.framework == baseline else [args.framework, baseline]
    try:
        for slug in order:
            result["implementations"][slug] = _implementation(slug, config, split)
        write_json(out, result)
        base = result["implementations"][baseline]
        if base["status"] != "conformant":
            raise BenchError(f"baseline {baseline} is not measurable: {base.get('error') or base['conformance']}")
        fw = result["implementations"][args.framework]
        if fw["status"] != "conformant":
            log(f"{args.framework}: {fw['status']}; it will not be measured")
            result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_json(out, result)
            return 3
        # Query statistics are for the conformance check only.
        database["statement_tracking"] = set_statement_tracking(config, False)
        rounds: dict[str, list] = {slug: [] for slug in order}
        for number in range(1, args.rounds + 1):
            for slug in order:
                manifest = result["implementations"][slug]["manifest"]
                log(f"round {number}/{args.rounds}: {slug}")
                rounds[slug].append(measure_round(manifest, config, split, binary, number,
                                                  framework_tables(result["implementations"][slug])))
                write_json(out, {**result, "partial_rounds": rounds})
        for slug in order:
            entry = result["implementations"][slug]
            entry["rounds"] = rounds[slug]
            entry["summary"] = summarize(rounds[slug])
            crashed = entry["summary"]["flags"]["crashed_rounds"]
            entry["status"] = "crashed" if crashed else "measured"
        if args.framework != baseline:
            result["ratios"] = ratios(rounds[args.framework], rounds[baseline])
    finally:
        remove(DB_CONTAINER)
    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_json(out, result)
    log(f"wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    sub.add_parser("db-check")
    plan = sub.add_parser("plan")
    plan.add_argument("--frameworks", default="all")
    conf = sub.add_parser("conformance")
    conf.add_argument("--framework", required=True)
    conf.add_argument("--out")
    run_p = sub.add_parser("run")
    run_p.add_argument("--framework", required=True)
    run_p.add_argument("--rounds", type=int, default=5)
    run_p.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    handlers = {"validate": cmd_validate, "plan": cmd_plan, "conformance": cmd_conformance, "run": cmd_run,
                "db-check": cmd_db_check}
    try:
        return handlers[args.command](args)
    except BenchError as exc:
        log(f"error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
