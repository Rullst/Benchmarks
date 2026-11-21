"""results/site.json: the compact summary the Rullst website renders on its comparison page.

The website (Rullst/Rullst .github/assemble-organization-site.py, documented
in docs/src/website-maintenance.md there) downloads this file at build time,
checks every value and renders a table of the overall and category scores of
a few implementations, their position ranges, tie margins and flags, their
memory, and the Rullst reading in English and Brazilian Portuguese. The file
is written with latest.json on every publication; latest.json keeps its full
shape for the dashboard and other consumers.

The schema string changes whenever the website would have to change to read
the file correctly: a new field the website must show (a new flag, category,
status or stability result), a removed or renamed field, or a different
meaning. The website discards a file with a schema, flag, category, status or
weighting it does not know and shows no numbers instead.
"""

from __future__ import annotations

from reading import LANGS, reading_or_none
from report import _label, _stat, put_flags

SCHEMA = "rullst.benchmarks.site.v2"
RESULTS_URL = "https://rullst.win/Benchmarks/"
# The implementations the comparison page shows: the three it compares, two more references and the
# Rullst diagnostic; the page lists them by overall position.
SLUGS = ("rullst", "loco", "topcoat", "actix", "gin", "rullst-minimal")
THROUGHPUT = ("hello", "database", "application")
# Flags of a category cell, as the README's tables mark them.
FLAGS = {
    "cpu_cost": "*",                   # a run counted with its CPU-cost ratio (client-bound or PostgreSQL-bound)
    "database_note": "†",              # a database setup the results explain (database_note)
    "put_not_written": "‡",            # an Application score whose PUT /world/{id} mostly did not write
    "within_reference_margin": "≈",    # within the tie margin of Axum's 1.00
}


def _rounded(value, digits: int = 4):
    return None if value is None else round(float(value), digits)


def _position(entry: dict) -> list[int] | None:
    if entry.get("position") is None:
        return None
    first, last = entry.get("position_range") or [entry["position"], entry["position"]]
    return [int(first), int(last)]


def _margin(entry: dict) -> float | None:
    """The margin of the comparison that set the entry's position (the README's "±"); none for position 1."""
    return _rounded((entry.get("tie_check") or {}).get("percent"), 2)


def _cell(key: str, entry: dict | None, flagged: dict) -> dict:
    """One score: status, score, position range, margin and flags; the overall score carries the PUT flag of
    the Application score it includes."""
    if entry is None:
        return {"status": "not measured", "score": None, "position": None, "margin_percent": None, "flags": []}
    flags = []
    if entry.get("score") is not None:
        if key in THROUGHPUT and entry.get("efficiency_runs"):
            flags.append("cpu_cost")
        if entry.get("database_note"):
            flags.append("database_note")
        if key in ("application", "overall") and entry["slug"] in flagged:
            flags.append("put_not_written")
        if entry.get("within_reference_margin"):
            flags.append("within_reference_margin")
    return {"status": entry["status"], "score": _rounded(entry.get("score")), "position": _position(entry),
            "margin_percent": _margin(entry) if entry.get("position") is not None else None, "flags": flags}


def _display_name(row: dict) -> str:
    """aggregate.display_name: the variant is added unless it is the default one."""
    if row.get("variant") and not row.get("default_variant"):
        return f"{row['name']} ({row['variant']})"
    return row["name"]


def _source(combined: dict) -> dict | None:
    source = combined.get("rullst_source") or {}
    return {"kind": source.get("kind"), "label": source.get("label")} if source.get("kind") else None


def site_summary(combined: dict) -> dict:
    """The site.json document for the combined results of one run."""
    rankings = combined.get("rankings") or {}
    categories = rankings.get("categories", [])
    cells = {c["key"]: {e["slug"]: e for e in c["entries"]} for c in categories}
    publish_overall = bool(rankings.get("publish_overall") and rankings.get("overall"))
    overall = {e["slug"]: e for e in (rankings.get("overall") or {}).get("entries", [])} if publish_overall else {}
    stability = {e["slug"]: e for e in (rankings.get("stability") or {}).get("entries", [])}
    rows = {r["slug"]: r for r in combined["implementations"]}
    flagged = put_flags(combined["implementations"])["flagged"]
    reference = rows.get(combined["baseline"], {})
    ranked = (categories[0].get("tie_rule") or {}).get("ranked") if categories else None
    shown = []
    for slug in SLUGS:
        row = rows.get(slug)
        if row is None:
            continue
        memory = (cells.get("memory", {}).get(slug) or {}).get("detail") or {}
        startup = (cells.get("startup", {}).get(slug) or {}).get("detail") or {}
        entry = {
            "slug": slug,
            "framework": _display_name(row),
            "label": _label(row),
            "version": row.get("framework_version") or "",
            "role": row.get("role") or "ranked",
            "status": row["status"],
            "overall": (_cell("overall", overall.get(slug), flagged) if publish_overall else None),
            "categories": {c["key"]: _cell(c["key"], cells[c["key"]].get(slug), flagged) for c in categories},
            "stability": (stability.get(slug) or {}).get("result"),
            "memory": {
                "peak_ram_mib": _rounded(memory.get("peak_ram_mib"), 1),
                "axum_peak_ram_mib": _rounded(memory.get("reference"), 1),
                "after_logins_peak_ram_mib": _rounded((_stat(row, "application.ram_peak_mib") or {}).get("median"), 1),
                "axum_after_logins_peak_ram_mib": _rounded((row.get("paired_baseline") or {}).get(
                    "application.ram_peak_mib"), 1),
            },
            "startup_s": _rounded(startup.get("startup_s"), 3),
        }
        shown.append(entry)
    weights = (rankings.get("overall") or {}).get("weight_ratio") or {}
    return {
        "schema": SCHEMA,
        "measured_on": (combined["measured_from"] or combined["generated_at"])[:10],
        "measured_from": combined["measured_from"],
        "measured_to": combined.get("measured_to", ""),
        "generated_at": combined["generated_at"],
        "rullst_version": combined["rullst_version"],
        "rullst_source": _source(combined),
        "run": {"id": combined["run"]["id"], "url": combined["run"]["url"]},
        "results_url": RESULTS_URL,
        "reference": {"slug": combined["baseline"], "framework": reference.get("name", ""),
                      "version": reference.get("framework_version", "")},
        "ranked": ranked,
        "overall_published": publish_overall,
        "weights": weights if publish_overall else {},
        "categories": [{"key": c["key"], "title": c["title"]} for c in categories],
        "flags": FLAGS,
        "logins": (combined.get("config", {}).get("phase2") or {}).get("sessions"),
        "rows": shown,
        "reading": {lang: reading_or_none(combined, lang) for lang in LANGS},
        "note": combined.get("note", ""),
        "note_pt_br": combined.get("note_pt_br", ""),
    }
