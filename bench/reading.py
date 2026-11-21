"""A plain-language reading of the results for Rullst as generated, written from the data.

The README's "What this means for Rullst" block and the dashboard show it
(`reading_rullst` in latest.json); results/site.json carries it in English
and Brazilian Portuguese for the Rullst website. It states positions, scores
and RAM with the same wording whichever way they point, and says who
maintains the benchmark. Both languages say the same things.
"""

from __future__ import annotations

from report import PUT_SIGN, _label, _stat, _times, put_flags

SUBJECT = "rullst"
DISCLOSURE = ("This benchmark is maintained by Rullst's maintainer, who also wrote every implementation in it and "
              "designed the method.")
LANGS = ("en", "pt_br")
# The wording of each language; numbers in pt_br use a decimal comma and a dot for thousands.
WORDS = {
    "en": {
        "position": "position {first}{of}", "positions": "positions {first}–{last}{of}", "of": " of {ranked}",
        "in_position": "{place}",
        "group": "in the same group as {names}",
        "closest": "the closest {verb} {names}", "closest_one": "score{where} is", "closest_many": "scores{where} are",
        "outside": " outside its group", "and": " and ", "higher": "higher", "lower": "lower",
        "subject": "Rullst as `cargo rullst new` generates it ({version}, with its production middleware)",
        "overall": "{subject} is in {place} in the overall score, at {score}× Axum (Axum = 1.00)",
        "no_overall": "{subject} has no overall position in these results.",
        "by_category": "By category: ", "status": "{title}: {status}", "unplaced": "{title}: {score}×, without a position",
        "placed": "{title} {place} ({score}×)",
        "memory": "Memory: its RAM high-water mark under the Tier 3 load was {peak} (Axum: {axum} on the same runners)",
        "floor": ", both counted as the {floor} MiB floor of the Memory score",
        "after": "; after the {logins} logins of the application endpoints its peak was {after}",
        "after_axum": " (Axum: {axum})", "after_end": ", which no score includes",
        "put": "Its Application figure, and through it the overall score, is affected by this run's "
               "PUT /world/{{id}} problem ({sign}): most of its measured PUT requests did not write, so its PUT "
               "ratio and its Application score are higher than they would be with a write.",
        "disclosure": DISCLOSURE,
        "titles": {}, "statuses": {},
    },
    "pt_br": {
        "position": "posição {first}{of}", "positions": "posições {first}–{last}{of}", "of": " de {ranked}",
        "in_position": "na {place}",
        "group": "no mesmo grupo que {names}",
        "closest": "{verb} {names}", "closest_one": "a pontuação mais próxima{where} é",
        "closest_many": "as pontuações mais próximas{where} são",
        "outside": " fora do grupo", "and": " e ", "higher": "acima", "lower": "abaixo",
        "subject": "O Rullst como o `cargo rullst new` o gera ({version}, com o middleware de produção dele)",
        "overall": "{subject} está {place} na pontuação geral, com {score}× o Axum (Axum = 1,00)",
        "no_overall": "{subject} não tem posição geral nestes resultados.",
        "by_category": "Por categoria: ", "status": "{title}: {status}", "unplaced": "{title}: {score}×, sem posição",
        "placed": "{title}: {place} ({score}×)",
        "memory": "Memória: o pico de RAM dele sob a carga do Tier 3 foi de {peak} (Axum: {axum} nas mesmas máquinas)",
        "floor": ", ambos contados como o piso de {floor} MiB da pontuação de Memória",
        "after": "; depois dos {logins} logins dos endpoints de aplicação, o pico dele foi de {after}",
        "after_axum": " (Axum: {axum})", "after_end": ", que nenhuma pontuação inclui",
        "put": "O número de Aplicação dele, e por meio dele a pontuação geral, é afetado pelo problema do "
               "PUT /world/{{id}} desta rodada ({sign}): a maioria das requisições PUT medidas dele não gravou, então a "
               "razão do PUT e a pontuação de Aplicação dele são mais altas do que seriam com uma gravação.",
        "disclosure": "Este benchmark é mantido pelo mantenedor do Rullst, que também escreveu todas as "
                      "implementações dele e projetou o método.",
        "titles": {"hello": "Hello world", "database": "Banco de dados", "application": "Aplicação",
                   "memory": "Memória (pico)", "startup": "Inicialização"},
        "statuses": {"errors": "erros", "incomplete": "incompleto", "not comparable": "não comparável",
                     "not measured": "não medido", "unstable": "instável"},
    },
}
# The plural form of "the in-place phrase": "na posição 4" but "nas posições 4–5".
IN_PLURAL = {"pt_br": "nas {place}"}
NO_SCORES = {"en": "Rullst as generated has no scores in these results.",
             "pt_br": "O Rullst como gerado não tem pontuações nestes resultados."}


def _decimal(text: str, lang: str) -> str:
    """English digits as the language writes them: 1,045.5 -> 1.045,5 in pt_br."""
    return text.translate(str.maketrans(",.", ".,")) if lang == "pt_br" else text


def _x(value: float, lang: str) -> str:
    return _decimal(_times(value), lang)


def _place(entry: dict, ranked: int | None, lang: str = "en") -> str:
    words = WORDS[lang]
    first, last = entry.get("position_range") or [entry["position"], entry["position"]]
    of = words["of"].format(ranked=ranked) if ranked else ""
    if first == last:
        return words["position"].format(first=first, of=of)
    return words["positions"].format(first=first, last=last, of=of)


def _in_place(entry: dict, ranked: int | None, lang: str) -> str:
    first, last = entry.get("position_range") or [entry["position"], entry["position"]]
    template = IN_PLURAL.get(lang, WORDS[lang]["in_position"]) if first != last else WORDS[lang]["in_position"]
    return template.format(place=_place(entry, ranked, lang))


def _neighbours(entries: list[dict], entry: dict, names: dict, lang: str = "en") -> str:
    """The implementations in the subject's group and the nearest ranked scores outside it."""
    words = WORDS[lang]
    ranked = [e for e in entries if e["status"] == "ranked" and e.get("score") is not None]
    group = [e for e in ranked if e["slug"] in entry.get("tied_with", [])]
    above = [e for e in ranked if e["score"] > entry["score"] and e not in group]
    below = [e for e in ranked if e["score"] < entry["score"] and e not in group]
    parts = []
    if group:
        parts.append(words["group"].format(names=", ".join(f"{names.get(e['slug'], e['framework'])} "
                                                           f"({_x(e['score'], lang)}×)" for e in group)))
    outside = []
    if above:
        nearest = min(above, key=lambda e: e["score"])
        outside.append(f"{names.get(nearest['slug'], nearest['framework'])} ({_x(nearest['score'], lang)}×, "
                       f"{words['higher']})")
    if below:
        nearest = max(below, key=lambda e: e["score"])
        outside.append(f"{names.get(nearest['slug'], nearest['framework'])} ({_x(nearest['score'], lang)}×, "
                       f"{words['lower']})")
    if outside:
        where = words["outside"] if group else ""
        verb = (words["closest_many"] if len(outside) > 1 else words["closest_one"]).format(where=where)
        parts.append(words["closest"].format(verb=verb, names=words["and"].join(outside)))
    return "; ".join(parts)


def _ram(value, lang: str = "en") -> str:
    return _decimal(f"{value:,.0f}", lang) + " MiB"


def rullst_reading(data: dict, lang: str = "en") -> list[str]:
    """The sentences of the reading, or [] when Rullst as generated has no scores in these results."""
    words = WORDS[lang]
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
    subject = words["subject"].format(version=version)
    if rankings.get("publish_overall") and overall and overall.get("position"):
        ranked = sum(1 for e in rankings["overall"]["entries"] if e["status"] == "ranked" and e.get("score"))
        around = _neighbours(rankings["overall"]["entries"], overall, names, lang)
        sentences.append(words["overall"].format(subject=subject, place=_in_place(overall, ranked, lang),
                                                 score=_x(overall["score"], lang))
                         + (f"; {around}" if around else "") + ".")
    else:
        sentences.append(words["no_overall"].format(subject=subject))
    parts = []
    for key, entry in cells.items():
        title = words["titles"].get(key, categories[key]["title"])
        if not entry or entry.get("score") is None:
            status = entry["status"] if entry else "not measured"
            parts.append(words["status"].format(title=title, status=words["statuses"].get(status, status)))
        elif entry.get("position") is None:
            parts.append(words["unplaced"].format(title=title, score=_x(entry["score"], lang)))
        else:
            place = _place(entry, categories[key].get("tie_rule", {}).get("ranked"), lang)
            parts.append(words["placed"].format(title=title, place=place, score=_x(entry["score"], lang)))
    sentences.append(words["by_category"] + "; ".join(parts) + ".")
    memory = cells.get("memory") or {}
    detail = memory.get("detail") or {}
    peak, axum = detail.get("peak_ram_mib"), detail.get("reference")
    if peak is not None and axum is not None:
        floor = detail.get("floor")
        text = words["memory"].format(peak=_ram(peak, lang), axum=_ram(axum, lang))
        if floor and peak <= floor and axum <= floor:
            text += words["floor"].format(floor=f"{floor:.0f}")
        after = (_stat(row, "application.ram_peak_mib") or {}).get("median")
        axum_after = (row.get("paired_baseline") or {}).get("application.ram_peak_mib")
        logins = (data.get("config", {}).get("phase2") or {}).get("sessions", 125)
        if after is not None:
            text += (words["after"].format(logins=logins, after=_ram(after, lang))
                     + (words["after_axum"].format(axum=_ram(axum_after, lang)) if axum_after is not None else "")
                     + words["after_end"])
        sentences.append(text + ".")
    if SUBJECT in put_flags(data.get("implementations", []))["flagged"]:
        sentences.append(words["put"].format(sign=PUT_SIGN))
    sentences.append(words["disclosure"])
    return sentences


def reading_text(data: dict, lang: str = "en") -> str:
    return " ".join(rullst_reading(data, lang))


def reading_or_none(data: dict, lang: str = "en") -> str:
    """The reading, or the sentence that says Rullst as generated has no scores (never empty)."""
    return reading_text(data, lang) or NO_SCORES[lang]


def reading_markdown(data: dict) -> str:
    """The README block: the reading, the disclosure linked to Authorship."""
    sentences = rullst_reading(data)
    if not sentences:
        return NO_SCORES["en"]
    text = " ".join(sentences)
    return text.replace(DISCLOSURE, DISCLOSURE[:-1] + " ([Authorship](#authorship)).")
