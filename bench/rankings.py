"""Per-category rankings, an A/A tie margin per category, and an optional overall ranking.

Scored categories, each oriented so that higher is better and Axum is 1.0:

  hello        Tier 1 /text, /json and /html: geometric mean of the capacity
               ratios (hello-world throughput)
  database     Tier 1 /db-single, /queries, /updates and /fortunes
  application  Tier 1 GET /world/{id}, GET /worlds, PUT /world/{id},
               POST /form and GET /me
  memory       the RAM high-water mark under Tier 3's load, measured after the
               other load tiers and an idle period: Axum's / the
               implementation's, both counted as at least 64 MiB
  startup      Axum's start-up time / the implementation's, both counted as
               at least 1 s

A check, not a score:

  stability    Tiers 2 (300 connections) and 4 (500 connections, 2 minutes)
               on /json: "fail" when the server stopped or a round had more
               than 1% errors (timeouts included); "warn" when RAM was still
               growing at the end of Tier 4 (for a garbage-collected runtime
               that can be heap growth rather than a leak); otherwise "pass"

A run's capacity ratio (measure.capacity_ratio) is the requests/s ratio when
neither server's run was client-bound, and otherwise the ratio of requests per
CPU-second of the server and PostgreSQL together; a run limited by the load
generator while its server used less than 75% of its vCPUs is not comparable.
A run whose median error rate is above 1% has no score (every request the
load sends is valid).

Ties come from the A/A control: an identical copy of Axum measured like every
other implementation, whose scores should be 1.00. Its largest deviation from
1.00 in a category (per job, and pooled) is that category's tie margin: two
scores closer than it share a position, and a score within it of 1.00 is not
distinguishable from Axum's.

The overall score (the geometric mean of the five category scores) is
computed for the maintainer's review and the sensitivity table, and published
only when config.json scoring.publish_overall is true.
"""

from __future__ import annotations

import math

from common import BASE_ENDPOINTS, ENDPOINT_LABELS, EXTRA_ENDPOINTS, PHASE2_ENDPOINTS, READY_POLL_S

HELLO_ENDPOINTS = tuple(ep for ep in BASE_ENDPOINTS if ep != "db-single")
DATABASE_ENDPOINTS = ("db-single", *EXTRA_ENDPOINTS)
APPLICATION_ENDPOINTS = PHASE2_ENDPOINTS
DEFAULTS = {"publish_overall": False, "max_error_rate": 0.01, "memory_floor_mib": 64, "startup_floor_s": 1.0}
MAX_ERROR_RATE = DEFAULTS["max_error_rate"]
CAPACITY = ("the requests/s ratio, or, when either side was client-bound, the ratio of requests per CPU-second of "
            "the server and PostgreSQL together")


def _runs(endpoints) -> list[str]:
    return [f"tier1.{ep}" for ep in endpoints]


CATEGORIES = [
    {"key": "hello", "title": "Hello world", "tier": "Tier 1", "kind": "throughput", "runs": _runs(HELLO_ENDPOINTS),
     "description": "geometric mean over /text, /json and /html (125 connections for 10 s each) of " + CAPACITY},
    {"key": "database", "title": "Database", "tier": "Tier 1", "kind": "throughput",
     "runs": _runs(DATABASE_ENDPOINTS),
     "description": "geometric mean over /db-single, /queries?queries=20, /updates?queries=20 and /fortunes "
                    "(125 connections for 10 s each) of " + CAPACITY},
    {"key": "application", "title": "Application", "tier": "Tier 1", "kind": "throughput",
     "runs": _runs(APPLICATION_ENDPOINTS),
     "description": "geometric mean over GET /world/{id}, GET /worlds, PUT /world/{id}, POST /form (with CSRF "
                    "verification) and GET /me (a signed-in session) (125 connections for 10 s each) of " + CAPACITY},
    {"key": "memory", "title": "Memory (high-water mark)", "tier": "Tier 3", "kind": "memory", "runs": [],
     "metric": "tier3.load_ram_peak_mib",
     "description": "the most RAM the server used while answering /json with 200 connections for 15 s, after the "
                    "phase-1 Tier 1 runs, Tiers 2 and 4 and an idle period; lower is better: the score is Axum's "
                    "RAM / the implementation's, both counted as at least 64 MiB"},
    {"key": "startup", "title": "Startup", "tier": "", "kind": "startup", "runs": [], "metric": "startup_s",
     "description": "time from starting the container to the first answer; lower is better: the score is Axum's "
                    "time / the implementation's, both counted as at least 1 s"},
]
for _category in CATEGORIES:
    _category["metrics"] = ([f"{run}.rps" for run in _category["runs"]] if _category["kind"] == "throughput"
                            else [_category["metric"]])
    _category["lower_is_better"] = _category["kind"] != "throughput"
CATEGORY_KEYS = [c["key"] for c in CATEGORIES]
STABILITY = {"key": "stability", "title": "Stability", "tier": "Tiers 2 and 4",
             "description": "/json with 300 connections for 30 s and 500 connections for 2 minutes: fail when the "
                            "server stopped or a round had more than 1% errors (timeouts included), warn when RAM "
                            "was still growing at the end of Tier 4, otherwise pass; not a score"}
# Ranks under other weightings: how much the overall order depends on the choice of weights.
WEIGHTINGS = [
    {"key": "equal", "title": "Equal weights", "weights": {k: 1 for k in CATEGORY_KEYS}},
    {"key": "throughput", "title": "Throughput only",
     "weights": {"hello": 1, "database": 1, "application": 1}},
    {"key": "db-app", "title": "Database and Application", "weights": {"database": 1, "application": 1}},
    {"key": "no-hello", "title": "Without Hello world",
     "weights": {"database": 1, "application": 1, "memory": 1, "startup": 1}},
    {"key": "throughput-x2", "title": "Throughput ×2",
     "weights": {"hello": 2, "database": 2, "application": 2, "memory": 1, "startup": 1}},
]
ROLE_STATUS = {"ranked": "ranked", "diagnostic": "diagnostic", "control": "A/A control"}
UNRANKED = ("reference", "diagnostic", "A/A control")

METHOD = {
    "categories": "Hello world, Database and Application are throughput categories; Memory and Startup are "
                  "costs scored as Axum's value / the implementation's; Stability (Tiers 2 and 4) is a pass, warn "
                  "or fail check without a score",
    "ratios": "medians of the per-round ratios to Axum measured on the same runner, pooled over every job "
              "(runner) of an implementation; each throughput run counts with its capacity ratio: " + CAPACITY
              + "; a side limited by the load generator while its server used less than 75% of its vCPUs makes "
                "that round pair not comparable",
    "limits": "a run is client-bound when the vCPUs the load generator and PostgreSQL share were at least 90% "
              "busy; it is PostgreSQL-bound when PostgreSQL used more of them than the load generator, and "
              "load-generator-bound otherwise",
    "floors": "Memory counts every high-water mark as at least 64 MiB and Startup every time as at least 1 s, "
              "so that differences far below what matters in production do not move the scores",
    "ties": "the tie margin of a category is the largest deviation from 1.00 of the A/A control's scores (an "
            "identical copy of Axum, per job and pooled); scores within it of the best score of their group "
            "share a position, and a score within it of 1.00 is marked as indistinguishable from Axum; in "
            "Startup, times within the readiness poll interval also share a position",
    "not comparable": "a run whose round pairs were mostly not comparable (see ratios) has no score in its "
                      "category",
    "errors": "a run whose median error rate is above 1% (any response that is not 2xx, any transport error or "
              "timeout) has no score in its category; the cell shows the error rate",
    "incomplete": "an implementation without a value for every run of a category (not measured, not served "
                  "according to its bench.json \"endpoints\", or left out by a correction) has no position in it",
    "roles": "Axum is the reference (1.00); diagnostics (for example Rullst's minimal configuration) and the A/A "
             "control are listed next to it, with a score and without a position",
    "overall": "the geometric mean of the five category scores with equal weights, computed for review; it is "
               "published only when config.json scoring.publish_overall is true, with a sensitivity table of "
               "the positions under other weightings",
}


def geometric_mean(values: list[float], weights: list[float] | None = None) -> float:
    weights = weights or [1.0] * len(values)
    if any(v <= 0 for v in values):
        return 0.0
    return math.exp(sum(w * math.log(v) for v, w in zip(values, weights)) / sum(weights))


def _median(row: dict | None, path: str, kind: str = "metrics"):
    stat = (row or {}).get(kind, {}).get(path)
    return stat["median"] if stat else None


def _measured(row: dict) -> bool:
    return row.get("status") in ("measured", "crashed")


def _status(row: dict) -> str:
    if row.get("is_baseline"):
        return "reference"
    return ROLE_STATUS.get(row.get("role", "ranked"), "ranked")


def _not_served(row: dict, runs: list[str]) -> list[str]:
    declared = row.get("endpoints")
    if declared is None:
        return []
    names = [run.split(".")[1] for run in runs if run.startswith("tier1.")]
    return [f"/{name}" for name in names if name not in declared]


def _limited(row: dict, run: str) -> dict:
    return dict(row.get("flags", {}).get("limited_rounds", {}).get(run, {}))


def _capacity(row: dict, run: str) -> tuple[float | None, str, dict]:
    """A run's capacity ratio, its basis ("rps", "cpu" or "not comparable") and the pair counts.

    Rows without capacity ratios (results measured before they existed) use
    the requests/s ratio.
    """
    stat = row.get("ratios", {}).get(f"{run}.capacity")
    if stat:
        pairs = stat.get("pairs", stat.get("n") or 0)
        if pairs and stat.get("not_comparable_rounds", 0) * 2 > pairs:
            return None, "not comparable", stat
        if stat.get("median") is None:
            return None, "not comparable", stat
        comparable = stat.get("n") or 0
        basis = "cpu" if comparable and stat.get("cpu_rounds", stat.get("efficiency_rounds", 0)) * 2 >= comparable \
            else "rps"
        return stat["median"], basis, stat
    rps = row.get("ratios", {}).get(f"{run}.rps")
    return (rps["median"] if rps else None), "rps", {}


def _label(run: str) -> str:
    name = run.split(".", 1)[1] if run.startswith("tier1.") else run
    return ENDPOINT_LABELS.get(name, f"/{name}")


def _base_entry(category: dict, row: dict, name) -> dict:
    return {"slug": row["slug"], "framework": name(row), "position": None, "tie": False, "tied_with": [],
            "status": _status(row), "role_note": row.get("role_note", ""), "score": None, "ratio": None,
            "reason": "", "detail": {}, "client_bound": False, "client_bound_runs": [], "limited_runs": {},
            "efficiency_runs": [], "within_reference_margin": None}


def _throughput_entry(category: dict, row: dict, entry: dict, settings: dict) -> dict:
    runs = category["runs"]
    is_reference = entry["status"] == "reference"
    detail = entry["detail"]
    detail["error_rates"] = {run.split(".")[1]: _median(row, f"{run}.error_rate") for run in runs}
    detail["db_us_per_request"] = {run.split(".")[1]: _median(row, f"{run}.db_us_per_request") for run in runs}
    detail["db_us_ratio"] = {run.split(".")[1]: (1.0 if is_reference and _median(row, f"{run}.db_us_per_request")
                                                 else _median(row, f"{run}.db_us_per_request", "ratios"))
                             for run in runs}
    entry["limited_runs"] = {run: _limited(row, run) for run in runs if _limited(row, run)}
    rounds = row.get("flags", {}).get("rounds") or 0
    entry["client_bound_runs"] = [run for run in runs
                                  if rounds and row.get("flags", {}).get("client_bound_rounds", {}).get(run, 0) * 2
                                  >= rounds]
    entry["client_bound"] = bool(runs) and set(entry["client_bound_runs"]) == set(runs)
    if category["key"] == "database" and row.get("database_note"):
        entry["database_note"] = row["database_note"]
    if category["key"] == "application":
        settings_p2 = row.get("phase2") or {}
        detail["csrf"] = (settings_p2.get("csrf") or {}).get("design")
        detail["session_store"] = (settings_p2.get("session") or {}).get("store")
    limit = settings["max_error_rate"]
    failing = {run.split(".")[1]: rate for run in runs
               if (rate := _median(row, f"{run}.error_rate")) is not None and rate > limit}
    if is_reference:
        entry.update(score=1.0, ratio=1.0)
        if failing:
            entry["error_runs"] = failing
        return entry
    ratios = {run: _median(row, f"{run}.rps", "ratios") for run in runs}
    missing = [run for run, value in ratios.items() if value is None]
    not_served = _not_served(row, missing)
    if not_served:
        return dict(entry, status="incomplete",
                    reason=f"does not serve {', '.join(not_served)} yet (bench.json \"endpoints\")")
    if failing:
        return dict(entry, status="errors", error_runs=failing,
                    reason=f"error rate above {limit:.0%}: " + ", ".join(
                        f"{_label('tier1.' + ep)} {rate:.1%}" for ep, rate in failing.items()))
    if missing:
        excluded = [p for p in row.get("excluded", []) if any(m == p or m.startswith(p + ".") for m in missing)]
        reason = "no value for " + ", ".join(f"{m}.rps" for m in missing)
        return dict(entry, status="incomplete", reason=reason + (" (left out by a correction)" if excluded else ""))
    capacities = {run: _capacity(row, run) for run in runs}
    blocked = [run for run, (value, basis, _) in capacities.items() if value is None]
    rps_ratio = geometric_mean(list(ratios.values()))
    detail["rps_ratio"] = {run.split(".")[1]: round(value, 4) for run, value in ratios.items()}
    detail["basis"] = {run.split(".")[1]: basis for run, (_, basis, _) in capacities.items()}
    if blocked:
        return dict(entry, status="not comparable", ratio=round(rps_ratio, 4), not_comparable_runs=blocked,
                    reason="limited by the load generator in most rounds while its server or Axum's used less "
                           "than 75% of its vCPUs, so efficiency would extrapolate: " + ", ".join(blocked))
    detail["capacity"] = {run.split(".")[1]: round(value, 4) for run, (value, _, _) in capacities.items()}
    entry["efficiency_runs"] = [run for run, (_, basis, _) in capacities.items() if basis == "cpu"]
    score = geometric_mean([value for value, _, _ in capacities.values()])
    return dict(entry, score=round(score, 4), ratio=round(rps_ratio, 4))


def _reference_value(row: dict, base: dict | None, path: str):
    """The reference's value from the same runners (paired), else the pooled reference row's."""
    paired = (row.get("paired_baseline") or {}).get(path)
    return paired if paired is not None else _median(base, path)


def _cost_entry(category: dict, row: dict, base: dict | None, entry: dict, settings: dict) -> dict:
    path = category["metric"]
    own = _median(row, path)
    ref = own if entry["status"] == "reference" else _reference_value(row, base, path)
    floor = settings["memory_floor_mib"] if category["key"] == "memory" else settings["startup_floor_s"]
    entry["detail"] = {"value": own, "reference": ref, "floor": floor}
    if category["key"] == "startup":
        entry["detail"]["startup_s"] = own
    else:
        entry["detail"]["peak_ram_mib"] = own
    if own is None or ref is None:
        excluded = [p for p in row.get("excluded", []) if path == p or path.startswith(p + ".")]
        return dict(entry, status="incomplete" if entry["status"] not in UNRANKED else entry["status"],
                    reason=f"no value for {path}" + (" (left out by a correction)" if excluded else ""))
    value = max(own, floor) / max(ref, floor)
    return dict(entry, score=round(1.0 / value, 4), ratio=round(own / ref, 4) if ref else None)


def _category_entry(category: dict, row: dict, base: dict | None, name, settings: dict) -> dict:
    """One implementation's value and score in one category, or the reason it has none."""
    entry = _base_entry(category, row, name)
    if not _measured(row):
        return dict(entry, status="not measured", reason=f"not measured ({row.get('status')})")
    if category["kind"] == "throughput":
        return _throughput_entry(category, row, entry, settings)
    return _cost_entry(category, row, base, entry, settings)


def stability_entry(row: dict, name, settings: dict) -> dict:
    """Tiers 2 and 4 as a pass, warn or fail check."""
    entry = {"slug": row["slug"], "framework": name(row), "status": _status(row), "result": None, "reasons": [],
             "detail": {}}
    if not _measured(row):
        return dict(entry, result="not measured")
    flags = row.get("flags", {})
    detail = {}
    for tier in ("tier2", "tier4"):
        rate = (row.get("metrics", {}).get(f"{tier}.error_rate") or {})
        detail[tier] = {"rps": _median(row, f"{tier}.rps"), "p99_ms": _median(row, f"{tier}.latency_ms.p99"),
                        "error_rate_max": rate.get("max"), "error_rate": rate.get("median"),
                        "timeouts": _median(row, f"{tier}.timeouts")}
    detail["crashed_rounds"] = flags.get("crashed_rounds", 0)
    detail["ram_growing_rounds"] = flags.get("ram_growing_rounds", 0)
    detail["rounds"] = flags.get("rounds", 0)
    entry["detail"] = detail
    reasons, result = [], "pass"
    if detail["crashed_rounds"]:
        reasons.append(f"stopped in {detail['crashed_rounds']}/{detail['rounds']} rounds")
        result = "fail"
    for tier, title in (("tier2", "Tier 2"), ("tier4", "Tier 4")):
        worst = detail[tier]["error_rate_max"]
        if worst is None:
            reasons.append(f"{title} not measured")
            result = "fail" if result == "fail" else "incomplete"
        elif worst > settings["max_error_rate"]:
            reasons.append(f"{title} errors {worst:.1%} in its worst round")
            result = "fail"
    if detail["ram_growing_rounds"] and result == "pass":
        result = "warn"
    if detail["ram_growing_rounds"]:
        reasons.append(f"RAM still growing at the end of Tier 4 in {detail['ram_growing_rounds']}/"
                       f"{detail['rounds']} rounds")
    return dict(entry, result=result, reasons=reasons)


def _same_group(category: dict, margin: float | None, leader: dict, entry: dict) -> bool:
    if leader["score"] == entry["score"]:
        return True
    if margin is not None and leader["score"] and entry["score"] \
            and abs(math.log(leader["score"] / entry["score"])) <= margin + 1e-12:
        return True
    if category.get("key") == "startup":
        lead, own = leader["detail"].get("startup_s"), entry["detail"].get("startup_s")
        return lead is not None and own is not None and own - lead < READY_POLL_S
    return False


def _assign_positions(entries: list[dict], same_group) -> None:
    """Standard competition positions (1, 1, 3) for ranked entries in score order."""
    ranked = [e for e in entries if e["status"] == "ranked" and e["score"] is not None]
    groups: list[list[dict]] = []
    for entry in ranked:
        if groups and same_group(groups[-1][0], entry):
            groups[-1].append(entry)
        else:
            groups.append([entry])
    position = 1
    for group in groups:
        for entry in group:
            others = [e["slug"] for e in group if e is not entry]
            entry.update(position=position, tie=bool(others), tied_with=others)
        position += len(group)


ORDER = {"ranked": 0, "reference": 0, "diagnostic": 0, "A/A control": 0, "not comparable": 1, "errors": 1,
         "incomplete": 1, "unstable": 1, "not measured": 2}


def _order(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda e: (ORDER.get(e["status"], 1), -(e["score"] or 0), e["framework"].lower()))


def _margin_from(scores: list[float]) -> float | None:
    clean = [s for s in scores if s]
    return round(max(abs(math.log(s)) for s in clean), 6) if clean else None


def aa_margins(control_rows: list[dict], base: dict | None, settings: dict) -> dict:
    """Each category's tie margin (in natural-log units) from the A/A control's rows.

    control_rows holds the control's row per job and its pooled row (role
    "control"); each one's score should be exactly 1.00, so the largest
    deviation is the noise a score carries. Returns, per category and
    "overall", {"margin": ln units or None, "percent": the same as a
    percentage, "scores": the control's scores}.
    """
    name = lambda row: row["slug"]  # noqa: E731
    out: dict = {}
    per_row: list[dict] = []
    for row in control_rows:
        as_ranked = dict(row, role="ranked", is_baseline=False)
        per_row.append({c["key"]: _category_entry(c, as_ranked, base, name, settings)["score"] for c in CATEGORIES})
    for key in [*CATEGORY_KEYS, "overall"]:
        if key == "overall":
            scores = [geometric_mean([s[k] for k in CATEGORY_KEYS]) for s in per_row
                      if all(s.get(k) for k in CATEGORY_KEYS)]
        else:
            scores = [s[key] for s in per_row if s.get(key)]
        margin = _margin_from(scores)
        out[key] = {"margin": margin, "percent": round((math.exp(margin) - 1) * 100, 2) if margin is not None
                    else None, "scores": [round(s, 4) for s in scores]}
    return out


def _weighted(scores: dict, weights: dict) -> float | None:
    keys = [k for k in weights if weights[k]]
    if any(scores.get(k) is None for k in keys):
        return None
    return geometric_mean([scores[k] for k in keys], [weights[k] for k in keys])


def compute(rows: list[dict], baseline: str, name=lambda row: row.get("name", row["slug"]),
            settings: dict | None = None, control_rows: list[dict] | None = None) -> dict:
    """The `rankings` field of the published results.

    control_rows: the A/A control's row per job (the pooled one is found in
    rows by its role); without any, ties are exact and the margins are None.
    """
    settings = DEFAULTS | (settings or {})
    base = next((r for r in rows if r.get("is_baseline") or r["slug"] == baseline), None)
    pooled_controls = [r for r in rows if r.get("role") == "control" and _measured(r)]
    margins = aa_margins([*(control_rows or []), *pooled_controls], base, settings)
    categories = []
    by_slug: dict[str, dict[str, dict]] = {r["slug"]: {} for r in rows}
    for category in CATEGORIES:
        margin = margins[category["key"]]["margin"]
        entries = _order([_category_entry(category, row, base, name, settings) for row in rows])
        for entry in entries:
            if entry["score"] is not None and entry["status"] != "reference" and margin is not None:
                entry["within_reference_margin"] = abs(math.log(entry["score"])) <= margin + 1e-12
        _assign_positions(entries, lambda leader, entry, c=category, m=margin: _same_group(c, m, leader, entry))
        for entry in entries:
            by_slug[entry["slug"]][category["key"]] = entry
        categories.append({k: category[k] for k in ("key", "title", "tier", "description", "metrics", "runs",
                                                    "lower_is_better", "kind")}
                          | {"entries": entries, "tie_margin": margins[category["key"]]})
    stability = [stability_entry(row, name, settings) for row in rows]

    overall = []
    stable = {e["slug"]: e for e in stability}
    for row in rows:
        cells = by_slug[row["slug"]]
        scores = {key: cells[key]["score"] for key in CATEGORY_KEYS}
        missing = [key for key in CATEGORY_KEYS if scores[key] is None]
        entry = {"slug": row["slug"], "framework": name(row), "position": None, "tie": False, "tied_with": [],
                 "status": _status(row), "score": None, "categories": scores, "missing": missing, "reason": "",
                 "stability": stable[row["slug"]]["result"]}
        if not _measured(row):
            entry.update(status="not measured", reason=f"not measured ({row.get('status')})")
        elif missing:
            notes = {s: [k for k in missing if cells[k]["status"] == s] for s in ("not comparable", "errors")}
            entry.update(status="incomplete" if entry["status"] not in UNRANKED else entry["status"],
                         reason="no score in: " + ", ".join(missing)
                         + "".join(f" ({s}: {', '.join(keys)})" for s, keys in notes.items() if keys))
        else:
            entry["score"] = round(geometric_mean(list(scores.values())), 4)
            if entry["stability"] == "fail" and entry["status"] == "ranked":
                entry.update(status="unstable", reason="failed the stability check: "
                             + "; ".join(stable[row["slug"]]["reasons"]))
        overall.append(entry)
    overall = _order(overall)
    margin = margins["overall"]["margin"]
    _assign_positions(overall, lambda leader, entry: _same_group({}, margin, leader, entry))

    sensitivity = []
    for weighting in WEIGHTINGS:
        scored = []
        for entry in overall:
            value = _weighted(entry["categories"], weighting["weights"])
            status = entry["status"] if entry["status"] != "unstable" else "unstable"
            scored.append({"slug": entry["slug"], "framework": entry["framework"], "status": status,
                           "score": round(value, 4) if value is not None else None, "position": None,
                           "tie": False, "tied_with": [], "detail": {}})
        scored = _order(scored)
        _assign_positions(scored, lambda leader, entry: _same_group({}, margin, leader, entry))
        sensitivity.append({**weighting, "entries": scored})
    return {
        "reference": baseline,
        "tie_margins": margins,
        "tie_tolerance": margins["overall"]["margin"],
        "startup_resolution_s": READY_POLL_S,
        "settings": settings,
        "method": METHOD,
        "categories": categories,
        "stability": {**STABILITY, "entries": stability},
        "publish_overall": bool(settings["publish_overall"]),
        "overall": {"weights": {key: round(1 / len(CATEGORY_KEYS), 4) for key in CATEGORY_KEYS},
                    "entries": overall},
        "sensitivity": sensitivity,
    }


def published(rankings: dict) -> dict:
    """The rankings as published: without the overall ranking and the sensitivity table unless enabled."""
    if rankings.get("publish_overall"):
        return rankings
    return {k: v for k, v in rankings.items() if k not in ("overall", "sensitivity")}
