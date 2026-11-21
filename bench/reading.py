"""A plain-language reading of the results for Rullst as generated, written from the data.

The README's "What this means for Rullst" block and the dashboard show it
(`reading_rullst` in latest.json). It states positions, scores and RAM with
the same wording whichever way they point, and says who maintains the
benchmark.
"""

from __future__ import annotations

from report import PUT_SIGN, _label, _stat, _times, put_flags

SUBJECT = "rullst"
DISCLOSURE = ("This benchmark is maintained by Rullst's maintainer, who also wrote every implementation in it and "
              "designed the method.")


def _place(entry: dict, ranked: int | None) -> str:
    first, last = entry.get("position_range") or [entry["position"], entry["position"]]
    of = f" of {ranked}" if ranked else ""
    if first == last:
        return f"position {first}{of}"
    return f"positions {first}–{last}{of}"


def _score(entry: dict) -> str:
    return f"{_times(entry['score'])}× Axum"


def _neighbours(entries: list[dict], entry: dict, names: dict) -> str:
    """The implementations in the subject's group and the nearest ranked scores outside it."""
    ranked = [e for e in entries if e["status"] == "ranked" and e.get("score") is not None]
    group = [e for e in ranked if e["slug"] in entry.get("tied_with", [])]
    above = [e for e in ranked if e["score"] > entry["score"] and e not in group]
    below = [e for e in ranked if e["score"] < entry["score"] and e not in group]
    parts = []
    if group:
        parts.append("in the same group as " + ", ".join(f"{names.get(e['slug'], e['framework'])} "
                                                         f"({_times(e['score'])}×)" for e in group))
    outside = []
    if above:
        nearest = min(above, key=lambda e: e["score"])
        outside.append(f"{names.get(nearest['slug'], nearest['framework'])} ({_times(nearest['score'])}×, higher)")
    if below:
        nearest = max(below, key=lambda e: e["score"])
        outside.append(f"{names.get(nearest['slug'], nearest['framework'])} ({_times(nearest['score'])}×, lower)")
    if outside:
        where = " outside its group" if group else ""
        verb = "scores" + where + " are" if len(outside) > 1 else "score" + where + " is"
        parts.append(f"the closest {verb} " + " and ".join(outside))
    return "; ".join(parts)


def _ram(value) -> str:
    return f"{value:,.0f} MiB"


def rullst_reading(data: dict) -> list[str]:
    """The sentences of the reading, or [] when Rullst as generated has no scores in these results."""
    rankings = data.get("rankings") or {}
    rows = {r["slug"]: r for r in data.get("implementations", [])}
    row = rows.get(SUBJECT)
    categories = {c["key"]: c for c in rankings.get("categories", [])}
    cells = {key: next((e for e in c["entries"] if e["slug"] == SUBJECT), None) for key, c in categories.items()}
    if not row or not any(e and e.get("score") is not None for e in cells.values()):
        return []
    names = {slug: _label(r) for slug, r in rows.items()}
    version = row.get("framework_version") or data.get("rullst_version") or ""
    sentences = []
    overall = next((e for e in (rankings.get("overall") or {}).get("entries", []) if e["slug"] == SUBJECT), None)
    subject = f"Rullst as `cargo rullst new` generates it ({version}, with its production middleware)"
    if rankings.get("publish_overall") and overall and overall.get("position"):
        ranked = sum(1 for e in rankings["overall"]["entries"] if e["status"] == "ranked" and e.get("score"))
        around = _neighbours(rankings["overall"]["entries"], overall, names)
        sentences.append(f"{subject} is in {_place(overall, ranked)} in the overall score, at "
                         f"{_score(overall)} (Axum = 1.00)" + (f"; {around}" if around else "") + ".")
    else:
        sentences.append(f"{subject} has no overall position in these results.")
    parts = []
    for key, entry in cells.items():
        title = categories[key]["title"]
        if not entry or entry.get("score") is None:
            parts.append(f"{title}: {entry['status'] if entry else 'not measured'}")
        elif entry.get("position") is None:
            parts.append(f"{title}: {_times(entry['score'])}×, without a position")
        else:
            parts.append(f"{title} {_place(entry, categories[key].get('tie_rule', {}).get('ranked'))} "
                         f"({_times(entry['score'])}×)")
    sentences.append("By category: " + "; ".join(parts) + ".")
    memory = cells.get("memory") or {}
    detail = memory.get("detail") or {}
    peak, axum = detail.get("peak_ram_mib"), detail.get("reference")
    if peak is not None and axum is not None:
        floor = detail.get("floor")
        text = (f"Memory: its RAM high-water mark under the Tier 3 load was {_ram(peak)} (Axum: {_ram(axum)} on the "
                "same runners)")
        if floor and peak <= floor and axum <= floor:
            text += f", both counted as the {floor:.0f} MiB floor of the Memory score"
        after = (_stat(row, "application.ram_peak_mib") or {}).get("median")
        axum_after = (row.get("paired_baseline") or {}).get("application.ram_peak_mib")
        logins = (data.get("config", {}).get("phase2") or {}).get("sessions", 125)
        if after is not None:
            text += (f"; after the {logins} logins of the application endpoints its peak was {_ram(after)}"
                     + (f" (Axum: {_ram(axum_after)})" if axum_after is not None else "")
                     + ", which no score includes")
        sentences.append(text + ".")
    if SUBJECT in put_flags(data.get("implementations", []))["flagged"]:
        sentences.append(f"Its Application figure, and through it the overall score, is affected by this run's "
                         f"PUT /world/{{id}} problem ({PUT_SIGN}): most of its measured PUT requests did not write, so "
                         "its PUT ratio and its Application score are higher than they would be with a write.")
    sentences.append(DISCLOSURE)
    return sentences


def reading_text(data: dict) -> str:
    return " ".join(rullst_reading(data))


def reading_markdown(data: dict) -> str:
    """The README block: the reading, the disclosure linked to Authorship."""
    sentences = rullst_reading(data)
    if not sentences:
        return "Rullst as generated has no scores in these results."
    text = " ".join(sentences)
    return text.replace(DISCLOSURE, DISCLOSURE[:-1] + " ([Authorship](#authorship)).")
