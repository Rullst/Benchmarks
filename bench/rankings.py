"""Per-category and overall rankings, computed from the ratios to the Axum baseline.

Six categories, each scored so that higher is better and Axum is 1.0:

  speed      Tier 1: geometric mean of the capacity ratios of /text, /json,
             /db-single and /html
  database   Tier 1: geometric mean of the capacity ratios of /queries,
             /updates and /fortunes
  pressure   Tier 2: capacity ratio (300 connections on /json)
  memory     Tier 3: 1 / peak RAM ratio (lower RAM is better)
  endurance  Tier 4: capacity ratio (500 connections on /json for 2 minutes)
  startup    Axum's median start-up time / the implementation's, both at least
             one readiness poll interval (0.25 s)

A run's capacity ratio (`<run>.capacity`, measure.capacity_ratio) is the
requests/s ratio when neither server's run was client-bound, and the ratio of
requests per server CPU-second (server efficiency) when either was: a
client-bound server had idle CPU, so its requests/s says less than its cost
per request. Client-bound results therefore get positions instead of ties.
Rows without capacity ratios (results measured before they existed) use the
requests/s ratios.

The overall score is the geometric mean of the six category scores with equal
weights. An implementation without every metric is listed as incomplete, with
no overall position, instead of being ranked on fewer metrics.

Ties: equal scores share a position, and start-up times within one readiness
poll interval of each other share a position.
"""

from __future__ import annotations

import math

from common import BASE_ENDPOINTS, EXTRA_ENDPOINTS, READY_POLL_S

# Client-bound results are scored by server efficiency instead of sharing a
# position, so there is no tolerance; the published field stays (as 0).
TIE_TOLERANCE = 0.0
ENDPOINTS = BASE_ENDPOINTS
DATABASE_ENDPOINTS = EXTRA_ENDPOINTS
CAPACITY = ("the requests/s ratio, or the ratio of requests per server CPU-second when the run was "
            "client-bound")

CATEGORIES = [
    {"key": "speed", "title": "Speed", "tier": "Tier 1",
     "metrics": [f"tier1.{ep}.rps" for ep in ENDPOINTS], "runs": [f"tier1.{ep}" for ep in ENDPOINTS],
     "lower_is_better": False, "throughput": True,
     "description": "geometric mean over /text, /json, /db-single and /html (125 connections for 10 s each) "
                    f"of {CAPACITY}"},
    {"key": "database", "title": "Database", "tier": "Tier 1",
     "metrics": [f"tier1.{ep}.rps" for ep in DATABASE_ENDPOINTS],
     "runs": [f"tier1.{ep}" for ep in DATABASE_ENDPOINTS],
     "lower_is_better": False, "throughput": True,
     "description": "geometric mean over /queries?queries=20, /updates?queries=20 and /fortunes (125 connections "
                    f"for 10 s each) of {CAPACITY}"},
    {"key": "pressure", "title": "Under pressure", "tier": "Tier 2",
     "metrics": ["tier2.rps"], "runs": ["tier2"], "lower_is_better": False, "throughput": True,
     "description": f"on /json with 300 connections for 30 s, {CAPACITY}"},
    {"key": "memory", "title": "Memory", "tier": "Tier 3",
     "metrics": ["tier3.load_ram_peak_mib"], "runs": ["tier3_load"], "lower_is_better": True, "throughput": False,
     "description": "peak RAM ratio on /json with 200 connections; lower RAM is better, so the score is "
                    "1 / ratio"},
    {"key": "endurance", "title": "Endurance", "tier": "Tier 4",
     "metrics": ["tier4.rps"], "runs": ["tier4"], "lower_is_better": False, "throughput": True,
     "description": f"on /json with 500 connections for 2 minutes, {CAPACITY}"},
    {"key": "startup", "title": "Startup", "tier": "",
     "metrics": ["startup_s"], "runs": [], "lower_is_better": True, "throughput": False,
     "description": "time from starting the container to the first answer; lower is better, so the score is "
                    "Axum's median time / the implementation's, where times below the 0.25 s readiness poll "
                    "interval count as 0.25 s"},
]
CATEGORY_KEYS = [c["key"] for c in CATEGORIES]
# The harness polls a starting server every READY_POLL_S, so a start-up time
# is only known to that interval: below it, times count as equal.
STARTUP_FLOOR_S = READY_POLL_S

METHOD = {
    "overall": "geometric mean of the six category scores, each weighted equally (1/6); every score is "
               "oriented so that higher is better and Axum is 1.00. The weighting is a choice; the "
               "per-category rankings are the detail.",
    "ratios": "medians of the per-round ratios to Axum measured on the same runner (results[].ratios), "
              f"except start-up: the harness checks a starting server every {READY_POLL_S} s, so a start-up "
              f"time is known only to {READY_POLL_S} s; the score divides Axum's median time by the "
              f"implementation's, with times below {READY_POLL_S} s counted as {READY_POLL_S} s, instead of "
              "dividing by Axum's 0.01-0.02 s; in Speed, Database, Under pressure and Endurance, each run's "
              "ratio is its capacity ratio (results[].ratios['<run>.capacity']): the requests/s ratio, or, in "
              "the rounds where either server's run was client-bound (load generator or database vCPUs at "
              "least 90% busy), the ratio of requests per server CPU-second, because a client-bound server "
              "had idle CPU and its requests/s understates what it could serve",
    "ties": f"equal scores share a position; in Startup, times within {READY_POLL_S} s (the readiness poll "
            "interval) of the fastest of their group share a position; overall, implementations that share a "
            "position in all six categories share a position. Client-bound results do not tie: they are "
            "scored by server efficiency",
    "not comparable": "in Speed, Database, Under pressure and Endurance, a run that was client-bound in most "
                      "rounds for both the implementation and its paired Axum run, and that server efficiency "
                      "could not score, compares two load generators rather than two servers: the category "
                      "lists the implementation as not comparable, without a position, and it has no overall "
                      "position",
    "incomplete": "an implementation without a value for every metric of a category (not measured, not served "
                  "yet according to its bench.json \"endpoints\", or left out by a correction) has no position "
                  "in that category and no overall position",
    "reference": "Axum is the reference (1.00) and is listed without a position",
}


def _median(row: dict, path: str, kind: str = "metrics"):
    stat = row.get(kind, {}).get(path)
    return stat["median"] if stat else None


def geometric_mean(values: list[float]) -> float:
    if any(v == 0 for v in values):
        return 0.0
    return math.exp(sum(math.log(v) for v in values) / len(values))


def _client_bound_runs(row: dict) -> list[str]:
    flags = row.get("flags", {})
    rounds = flags.get("rounds") or 0
    bound = flags.get("client_bound_rounds", {})
    return [run for run, count in bound.items() if rounds and count * 2 >= rounds]


def _detail(category: str, row: dict, ratios: dict) -> dict:
    if category == "speed":
        return {ep: ratios.get(f"tier1.{ep}.rps") for ep in ENDPOINTS}
    if category == "database":
        return {ep: ratios.get(f"tier1.{ep}.rps") for ep in DATABASE_ENDPOINTS}
    if category == "pressure":
        return {"rps": _median(row, "tier2.rps"), "p99_ms": _median(row, "tier2.latency_ms.p99"),
                "p99_ratio": ratios.get("tier2.latency_ms.p99")}
    if category == "memory":
        return {"peak_ram_mib": _median(row, "tier3.load_ram_peak_mib")}
    if category == "endurance":
        flags = row.get("flags", {})
        return {"rps": _median(row, "tier4.rps"), "error_rate": _median(row, "tier4.error_rate"),
                "timeouts": _median(row, "tier4.timeouts"), "ram_growing_rounds": flags.get("ram_growing_rounds", 0),
                "crashed_rounds": flags.get("crashed_rounds", 0), "rounds": flags.get("rounds", 0)}
    return {"startup_s": _median(row, "startup_s")}


def _measured(row: dict) -> bool:
    return row.get("status") in ("measured", "crashed")


def _capacity(row: dict, metric: str) -> tuple[float | None, bool, bool]:
    """The capacity ratio of the run a requests/s metric belongs to, whether efficiency decided it,
    and whether it is comparable.

    A run is not comparable when the implementation and its paired Axum run
    were both client-bound in most rounds and server efficiency was not used
    for it: the requests/s ratio would then compare two load generators.
    Results without capacity ratios fall back to the requests/s ratio, and to
    the client-bound flags of both sides for that check.
    """
    ratios = row.get("ratios", {})
    run = metric[: -len(".rps")]
    stat = ratios.get(run + ".capacity")
    if stat:
        rounds = stat.get("n") or 0
        used = bool(rounds and stat.get("efficiency_rounds", 0) * 2 >= rounds)
        comparable = not (rounds and stat.get("not_comparable_rounds", 0) * 2 > rounds)
        return stat["median"], used, comparable
    rps = ratios.get(metric)
    comparable = not (_mostly_bound(row.get("flags", {}), run)
                      and _mostly_bound(row.get("paired_baseline_flags", {}), run))
    return (rps["median"] if rps else None), False, comparable


def _mostly_bound(flags: dict, run: str) -> bool:
    """Client-bound in more than half of the rounds."""
    rounds = flags.get("rounds") or 0
    return bool(rounds and flags.get("client_bound_rounds", {}).get(run, 0) * 2 > rounds)


def _not_served(row: dict, metrics: list[str]) -> list[str]:
    """Endpoints of these tier 1 metrics that the row's bench.json does not declare."""
    declared = row.get("endpoints")
    if declared is None:
        return []
    names = [m.split(".")[1] for m in metrics if m.startswith("tier1.")]
    return [f"/{name}" for name in names if name not in declared]


def _category_entry(category: dict, row: dict, base: dict | None, name) -> dict:
    """One implementation's value and score in one category, or the reason it has none."""
    key = category["key"]
    is_reference = bool(row.get("is_baseline"))
    if is_reference:
        ratios = {m: 1.0 for m in category["metrics"] if m in row.get("metrics", {})}
    else:
        ratios = {m: row["ratios"][m]["median"] for m in category["metrics"] if m in row.get("ratios", {})}
    runs = [r for r in _client_bound_runs(row) if r in category["runs"]]
    entry = {
        "slug": row["slug"], "framework": name(row), "position": None, "tie": False, "tied_with": [],
        "status": "reference" if is_reference else "ranked", "score": None, "ratio": None,
        "client_bound": bool(category["throughput"] and category["runs"] and set(runs) == set(category["runs"])),
        "client_bound_runs": runs, "efficiency_runs": [], "detail": _detail(key, row, ratios), "reason": "",
    }
    if not _measured(row):
        entry.update(status="not measured", reason=f"not measured ({row.get('status')})", client_bound=False)
        return entry
    missing = [m for m in category["metrics"] if m not in ratios]
    not_served = _not_served(row, missing)
    if not_served:
        entry.update(status="incomplete", reason=f"does not serve {', '.join(not_served)} yet (bench.json "
                                                 "\"endpoints\")")
        return entry
    if key == "startup":
        own, ref = _median(row, "startup_s"), _median(base, "startup_s") if base else None
        missing = [] if own is not None and ref is not None else ["startup_s"]
        if not missing:
            ratios = {"startup_s": max(own, STARTUP_FLOOR_S) / max(ref, STARTUP_FLOOR_S)}
    if missing:
        excluded = [p for p in row.get("excluded", []) if any(m == p or m.startswith(p + ".") for m in missing)]
        reason = "no value for " + ", ".join(missing)
        if excluded:
            reason += " (left out by a correction)"
        entry.update(status="incomplete", reason=reason)
        return entry
    value = geometric_mean(list(ratios.values()))
    if category["lower_is_better"]:
        if value <= 0:
            entry.update(status="incomplete", reason="ratio is zero")
            return entry
        score = 1.0 / value
    elif category["throughput"] and not is_reference:
        capacities = {m: _capacity(row, m) for m in category["metrics"]}
        if any(c is None for c, _, _ in capacities.values()):
            entry.update(status="incomplete", reason="no capacity ratio")
            return entry
        not_comparable = [m[: -len(".rps")] for m, (_, _, ok) in capacities.items() if not ok]
        if not_comparable:
            entry.update(status="not comparable", ratio=round(value, 4), not_comparable_runs=not_comparable,
                         reason="client-bound in most rounds for both it and Axum, without server efficiency "
                                f"to compare: {', '.join(not_comparable)}")
            return entry
        score = geometric_mean([c for c, _, _ in capacities.values()])
        entry["efficiency_runs"] = [m[: -len(".rps")] for m, (_, used, _) in capacities.items() if used]
        entry["detail"]["capacity"] = {m.split(".")[1] if m.startswith("tier1.") else m.split(".")[0]: round(c, 4)
                                       for m, (c, _, _) in capacities.items()}
    else:
        score = value
    entry.update(score=round(score, 4), ratio=round(value, 4))
    return entry


def _startup(entry: dict) -> float:
    return entry["detail"]["startup_s"]


def _same_group(category: dict, leader: dict, entry: dict) -> bool:
    if leader["score"] == entry["score"]:
        return True
    if category["key"] == "startup":
        return _startup(entry) - _startup(leader) < READY_POLL_S
    return False


def _assign_positions(scored: list[dict], same_group) -> None:
    """Standard competition positions (1, 1, 3) for ranked entries; the reference takes none."""
    groups: list[list[dict]] = []
    for entry in scored:
        if groups and same_group(groups[-1][0], entry):
            groups[-1].append(entry)
        else:
            groups.append([entry])
    position = 1
    for group in groups:
        ranked = [e for e in group if e["status"] == "ranked"]
        for entry in group:
            others = [e["slug"] for e in group if e is not entry]
            entry["tie"] = bool(others)
            entry["tied_with"] = others
            if entry["status"] == "ranked":
                entry["position"] = position
        position += len(ranked)


def _order(entries: list[dict]) -> list[dict]:
    status_order = {"ranked": 0, "reference": 0, "not comparable": 1, "incomplete": 1, "not measured": 2}
    return sorted(entries, key=lambda e: (status_order[e["status"]], -(e["score"] or 0), e["framework"].lower()))


def compute(rows: list[dict], baseline: str, name=lambda row: row.get("name", row["slug"])) -> dict:
    """The `rankings` field of the published results."""
    base = next((r for r in rows if r.get("is_baseline") or r["slug"] == baseline), None)
    categories = []
    by_slug: dict[str, dict[str, dict]] = {r["slug"]: {} for r in rows}
    for category in CATEGORIES:
        entries = [_category_entry(category, row, base, name) for row in rows]
        entries = _order(entries)
        scored = [e for e in entries if e["status"] in ("ranked", "reference")]
        _assign_positions(scored, lambda leader, entry, c=category: _same_group(c, leader, entry))
        for entry in entries:
            by_slug[entry["slug"]][category["key"]] = entry
        categories.append({k: category[k] for k in ("key", "title", "tier", "description", "metrics",
                                                    "lower_is_better")} | {"entries": entries})

    overall = []
    for row in rows:
        cells = by_slug[row["slug"]]
        scores = {key: cells[key]["score"] for key in CATEGORY_KEYS}
        missing = [key for key in CATEGORY_KEYS if scores[key] is None]
        entry = {"slug": row["slug"], "framework": name(row), "position": None, "tie": False, "tied_with": [],
                 "status": "reference" if row.get("is_baseline") else "ranked", "score": None,
                 "categories": scores, "missing": missing, "reason": ""}
        if not _measured(row):
            entry.update(status="not measured", reason=f"not measured ({row.get('status')})")
        elif missing:
            blocked = [key for key in missing if cells[key]["status"] == "not comparable"]
            entry.update(status="incomplete", reason="no score in: " + ", ".join(missing)
                         + (f" (not comparable: {', '.join(blocked)})" if blocked else ""))
        else:
            entry["score"] = round(geometric_mean(list(scores.values())), 4)
        overall.append(entry)
    overall = _order(overall)

    def same_everywhere(leader: dict, entry: dict) -> bool:
        cells_a, cells_b = by_slug[leader["slug"]], by_slug[entry["slug"]]
        return all(cells_b[key]["slug"] in cells_a[key]["tied_with"] for key in CATEGORY_KEYS)

    _assign_positions([e for e in overall if e["status"] in ("ranked", "reference")], same_everywhere)
    return {
        "reference": baseline,
        "tie_tolerance": TIE_TOLERANCE,
        "startup_resolution_s": READY_POLL_S,
        "method": METHOD,
        "categories": categories,
        "overall": {"weights": {key: round(1 / len(CATEGORY_KEYS), 4) for key in CATEGORY_KEYS},
                    "entries": overall},
    }
