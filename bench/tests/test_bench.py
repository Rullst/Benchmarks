"""Unit tests for the parts of the harness that do not need Docker."""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aggregate  # noqa: E402
import rankings  # noqa: E402
import report  # noqa: E402
from common import load_config  # noqa: E402
from conformance import check_body, check_content_type  # noqa: E402
from loadgen import MIB, parse_result  # noqa: E402
from measure import ram_trend, ratios, summarize  # noqa: E402
from release_check import newest, semver_key  # noqa: E402
from system import busy_fraction, parse_cpu_list, read_cpu_times, split_cpus  # noqa: E402

BOMBARDIER = {
    "spec": {"numberOfConnections": 125},
    "result": {
        "bytesRead": 1, "bytesWritten": 1, "timeTakenSeconds": 10.0,
        "req1xx": 0, "req2xx": 99000, "req3xx": 0, "req4xx": 0, "req5xx": 500, "others": 0,
        "errors": [{"description": "timeout", "count": 400}, {"description": "connection refused", "count": 100}],
        "latency": {"mean": 1200.5, "stddev": 10, "max": 90000,
                    "percentiles": {"50": 1000, "75": 1500, "90": 2000, "95": 2500, "99": 8000}},
        "rps": {"mean": 9900, "stddev": 1, "max": 10000, "percentiles": {"50": 9900}},
    },
}


def fake_round(scale: float, number: int = 1) -> dict:
    run = {"rps": 1000 * scale, "latency_ms": {"mean": 1.2 / scale, "p50": 1.0 / scale, "p99": 4.0 / scale},
           "error_rate": 0.0,
           "server_cpu_cores": 1.9, "client_bound": scale > 1, "timeouts": 0, "transport_errors": 0}
    return {
        "round": number, "crashed": None, "startup_s": 0.5,
        "idle": {"ram_mib": 10 * scale, "cpu_cores": 0.001, "tasks": 4},
        "tier1": {ep: copy.deepcopy(run) for ep in ("text", "json", "db-single", "html")},
        "tier2": copy.deepcopy(run),
        "tier3": {"idle_ram_mib": 10 * scale, "idle_cpu_cores": 0.001, "load_ram_peak_mib": 20 * scale,
                  "load_cpu_cores": 1.9, "rps": 900 * scale, "client_bound": False},
        "tier4": dict(copy.deepcopy(run), ram_mid_mib=20.0, ram_end_mib=21.0, ram_growth_mib=1.0, ram_growing=False),
        "after": {"ram_mib": 12.0, "memory_peak_mib": 30.0},
    }


def fake_job(framework: str, scale: float, rounds: int = 3) -> dict:
    config = load_config()
    fw_rounds = [fake_round(scale, n) for n in range(1, rounds + 1)]
    base_rounds = [fake_round(1.0, n) for n in range(1, rounds + 1)]
    manifest = {"name": framework.title(), "language": "Rust", "group": "rust", "framework": framework,
                "framework_version": "1.0", "runtime": "Rust", "server": "x", "workers": "2",
                "database_layer": "SQLx", "template_engine": "Askama", "logging": "off",
                "version_package": framework}
    versions = "rullst 13.0.0-alpha.5\n" if framework.startswith("rullst") else f"{framework} 1.2.3\n"
    return {
        "schema": 1, "framework": framework, "baseline": "axum", "rounds_requested": rounds,
        "started_at": "2026-11-15T04:00:00Z", "finished_at": "2026-11-15T05:00:00Z",
        "config": config, "environment": {"cpu_model": "Test CPU", "cpu_count": 4, "memory_total_mib": 16000,
                                          "runner": {}, "load_generator": {"name": "bombardier", "version": "2.0.2"}},
        "database": {"version": "18.6"},
        "implementations": {
            framework: {"manifest": manifest, "status": "measured", "build": {"versions": versions},
                        "rounds": fw_rounds, "summary": summarize(fw_rounds)},
            "axum": {"manifest": dict(manifest, name="Axum", version_package="axum"), "status": "measured",
                     "build": {"versions": "axum 0.8.9\n"}, "rounds": base_rounds, "summary": summarize(base_rounds)},
        },
        "ratios": ratios(fw_rounds, base_rounds),
    }


class LoadgenTests(unittest.TestCase):
    def test_parse_result(self):
        metrics = parse_result(BOMBARDIER)
        self.assertEqual(metrics["requests_ok"], 99000)
        self.assertEqual(metrics["rps"], 9900.0)
        self.assertEqual(metrics["non_2xx"], 500)
        self.assertEqual(metrics["transport_errors"], 500)
        self.assertEqual(metrics["timeouts"], 400)
        self.assertAlmostEqual(metrics["error_rate"], 1000 / 100000)
        self.assertEqual(metrics["latency_ms"]["p50"], 1.0)
        self.assertEqual(metrics["latency_ms"]["p99"], 8.0)

    def test_parse_result_without_latency(self):
        raw = copy.deepcopy(BOMBARDIER)
        del raw["result"]["latency"]
        raw["result"]["errors"] = []
        self.assertIsNone(parse_result(raw)["latency_ms"]["p99"])


class SamplerTests(unittest.TestCase):
    def test_sampler_thread_runs(self):
        import time
        from loadgen import RamSampler

        class Fake:
            def ram_bytes(self):
                return 5 * MIB

        sampler = RamSampler(Fake(), 0.005)
        sampler.start()
        time.sleep(0.05)
        samples = sampler.stop()
        self.assertGreater(len(samples), 2)
        self.assertEqual(samples[-1][1], 5 * MIB)


class SystemTests(unittest.TestCase):
    def test_cpu_list(self):
        self.assertEqual(parse_cpu_list("0-2,5,7-8\n"), [0, 1, 2, 5, 7, 8])

    def test_split_prefers_whole_cores(self):
        server, client = split_cpus([0, 1, 2, 3], 2, [[0, 2], [1, 3]])
        self.assertEqual((server, client), ([0, 2], [1, 3]))

    def test_split_without_smt(self):
        server, client = split_cpus([0, 1, 2, 3], 2, [[0], [1], [2], [3]])
        self.assertEqual((server, client), ([0, 1], [2, 3]))

    def test_cpu_times(self):
        before = read_cpu_times([1], "cpu 1 1 1 1 1 1 1 1 0 0\ncpu1 100 0 100 800 0 0 0 0 0 0\n")
        after = read_cpu_times([1], "cpu1 190 0 190 820 0 0 0 0 0 0\n")
        self.assertAlmostEqual(busy_fraction(before, after), 180 / 200)


class ConformanceTests(unittest.TestCase):
    def test_content_type(self):
        self.assertIsNone(check_content_type("/json", "application/json"))
        self.assertIsNone(check_content_type("/text", "text/plain; charset=UTF-8"))
        self.assertIsNotNone(check_content_type("/html", "text/plain"))
        self.assertIsNotNone(check_content_type("/text", "text/plain; charset=latin1"))
        self.assertIsNotNone(check_content_type("/json", None))

    def test_bodies(self):
        self.assertIsNone(check_body("/text", b"Hello World"))
        self.assertIsNotNone(check_body("/text", b"Hello World\n"))
        self.assertIsNone(check_body("/json", b'{ "message" : "Hello World" }'))
        self.assertIsNotNone(check_body("/json", b'{"message":"Hello, World!"}'))
        html = (b"<!DOCTYPE html><html><head><title>Benchmark</title></head>"
                b"<body><h1>Hello World</h1></body></html>\n")
        self.assertIsNone(check_body("/html", html))
        self.assertIsNone(check_body("/db-single", b'{"randomNumber": 77, "id": 1}', 77))
        self.assertIsNotNone(check_body("/db-single", b'{"id":1,"randomNumber":76}', 77))


class MeasureTests(unittest.TestCase):
    def test_ram_trend_flags_growth(self):
        leak = {"min_growth_mib": 8, "min_growth_ratio": 0.1}
        flat = [(t / 10, 50 * MIB) for t in range(1200)]
        self.assertFalse(ram_trend(flat, leak)["ram_growing"])
        rising = [(t / 10, int((50 + t / 10) * MIB)) for t in range(1200)]
        trend = ram_trend(rising, leak)
        self.assertTrue(trend["ram_growing"])
        self.assertGreater(trend["ram_growth_mib"], 40)
        self.assertLessEqual(len(trend["ram_series_mib"]), 121)

    def test_ratios(self):
        fw = [fake_round(2.0, n) for n in (1, 2)]
        base = [fake_round(1.0, n) for n in (1, 2)]
        result = ratios(fw, base)
        self.assertAlmostEqual(result["tier1.json.rps"]["median"], 2.0)
        self.assertAlmostEqual(result["tier3.idle_ram_mib"]["median"], 2.0)
        self.assertNotIn("tier4.error_rate", result)
        flags = summarize(fw)["flags"]
        self.assertEqual(flags["client_bound_rounds"]["tier1.json"], 2)


class AggregateTests(unittest.TestCase):
    def test_combine_and_render(self):
        jobs = [fake_job("rullst", 0.9), fake_job("actix", 1.1)]
        failed = fake_job("loco", 1.0)
        failed["implementations"]["loco"].update(status="failed-conformance", rounds=[], summary=None,
                                                 conformance={"passed": False, "checks": [
                                                     {"endpoint": "/html", "ok": False, "problem": "body differs"}]})
        jobs.append(failed)
        combined = aggregate.combine(jobs, ["rullst", "actix", "loco"])
        slugs = [r["slug"] for r in combined["implementations"]]
        self.assertEqual(slugs[0], "axum")
        self.assertEqual(combined["rullst_version"], "13.0.0-alpha.5")
        axum = combined["implementations"][0]
        self.assertEqual(axum["metrics"]["tier1.json.rps"]["n"], 9)
        self.assertEqual(axum["framework_version"], "0.8.9")
        rullst = next(r for r in combined["implementations"] if r["slug"] == "rullst")
        self.assertAlmostEqual(rullst["ratios"]["tier1.json.rps"]["median"], 0.9)
        text = report.render_results(combined)
        self.assertIn("Rullst 13.0.0-alpha.5", text)
        self.assertIn("## Not measured", text)
        self.assertIn("body differs", text)
        readme = report.replace_between_markers("a\n<!-- results:start -->\nold\n<!-- results:end -->\nb",
                                                report.render_readme_table(combined))
        self.assertNotIn("old", readme)
        self.assertTrue(readme.endswith("<!-- results:end -->\nb"))
        entry = aggregate.history_entry(combined)
        self.assertEqual(entry["file"], "rullst/13.0.0-alpha.5.json")
        self.assertIn("tier1.json.rps", entry["implementations"]["rullst"]["ratios"])

    def test_site_document_matches_the_site_contract(self):
        import datetime
        import math
        import re
        jobs = [fake_job("rullst", 0.9), fake_job("rullst-minimal", 1.0), fake_job("loco", 1.0)]
        jobs[1]["implementations"]["rullst-minimal"]["manifest"].update(name="Rullst", variant="minimal")
        jobs[0]["implementations"]["rullst"]["manifest"].update(variant="as generated", default_variant=True)
        jobs[2]["implementations"]["loco"].update(status="failed-conformance", rounds=[], summary=None,
                                                  conformance={"passed": False, "checks": [
                                                      {"endpoint": "/html", "ok": False, "problem": "x"}]})
        doc = aggregate.site_document(aggregate.combine(jobs, ["rullst", "rullst-minimal", "loco"]))
        # The checks the site's assembler applies (Rullst/Rullst .github/assemble-organization-site.py).
        self.assertEqual(doc["schema"], "rullst.benchmarks.latest.v1")
        datetime.date.fromisoformat(doc["measured_on"])
        version = re.compile(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,39}")
        names = [r["framework"] for r in doc["results"]]
        self.assertIn("Rullst", names)
        self.assertIn("Rullst (minimal)", names)
        self.assertNotIn("loco", [n.lower() for n in names])
        self.assertEqual([r["slug"] for r in doc["not_measured"]], ["loco"])
        for row in doc["results"]:
            self.assertTrue(version.fullmatch(str(row["version"])))
            metrics = [row[k] for k in ("json_rps", "db_single_rps", "avg_latency_ms", "peak_ram_mib") if k in row]
            self.assertTrue(metrics)
            self.assertTrue(all(math.isfinite(v) and v >= 0 for v in metrics))
        rullst = next(r for r in doc["results"] if r["framework"] == "Rullst")
        self.assertAlmostEqual(rullst["vs_axum"]["json_rps"], 0.9)
        self.assertIn("avg_latency_ms", rullst)
        self.assertNotIn("implementations", doc)

    def test_corrections_leave_out_metrics(self):
        combined = aggregate.combine([fake_job("fastapi", 1.0)], ["fastapi"])
        row = next(r for r in combined["implementations"] if r["slug"] == "fastapi")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "corrections.json"
            path.write_text('{"13.0.0-alpha.5": {"fastapi": {"exclude": ["tier1.db-single"], "problem": "broken"}}}')
            aggregate.apply_corrections("13.0.0-alpha.5", [row], path)
        self.assertNotIn("tier1.db-single.rps", row["metrics"])
        self.assertIn("tier1.json.rps", row["metrics"])
        self.assertNotIn("tier1.db-single.rps", row["ratios"])
        self.assertEqual(row["problem"], "broken")
        entry = next(r for r in aggregate.site_document(combined)["results"] if r["slug"] == "fastapi")
        self.assertNotIn("db_single_rps", entry)
        self.assertNotIn("db_single_rps", entry["vs_axum"])
        self.assertIn("broken", report.render_results(combined))

    def test_version_note(self):
        rows = [{"slug": "rullst", "ratios": {"tier1.json.rps": {"median": 0.214}}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text('{"1.0.0": "as generated {rullst:tier1.json.rps}x, minimal {rullst-minimal:tier1.json.rps}x"}')
            self.assertEqual(aggregate.version_note("1.0.0", rows, path), "as generated 0.21x, minimal –x")
            self.assertEqual(aggregate.version_note("2.0.0", rows, path), "")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "notes.json"
            path.write_text('{"1.0.0": {"en": "at {rullst:tier1.json.rps}x", "pt_br": "a {rullst:tier1.json.rps}x"}}')
            self.assertEqual(aggregate.version_note("1.0.0", rows, path), "at 0.21x")
            self.assertEqual(aggregate.version_note("1.0.0", rows, path, lang="pt_br"), "a 0,21x")
        combined = aggregate.combine([fake_job("rullst", 0.5)], ["rullst"])
        self.assertIn("0.50", combined["note"])
        self.assertIn("0,50×", combined["note_pt_br"])
        self.assertTrue(combined["note_pt_br"].startswith("Esta medição"))
        self.assertEqual(aggregate.site_document(combined)["note_pt_br"], combined["note_pt_br"])
        self.assertIn("**Note:**", report.render_results(combined))
        self.assertEqual(aggregate.site_document(combined)["note"], combined["note"])

    def test_write_outputs_keeps_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("x\n<!-- results:start -->\n<!-- results:end -->\n")
            old_root, old_results = aggregate.ROOT, aggregate.RESULTS
            aggregate.ROOT, aggregate.RESULTS = root, root / "results"
            try:
                for version in ("13.0.0-alpha.6", "13.0.0-alpha.5"):
                    job = fake_job("rullst", 1.0)
                    job["implementations"]["rullst"]["build"]["versions"] = f"rullst {version}\n"
                    aggregate.write_outputs(aggregate.combine([job], ["rullst"]), [job])
            finally:
                aggregate.ROOT, aggregate.RESULTS = old_root, old_results
            index = aggregate.json.loads((root / "results" / "versions.json").read_text())
            self.assertEqual([e["version"] for e in index["versions"]], ["13.0.0-alpha.5", "13.0.0-alpha.6"])
            self.assertTrue((root / "results" / "rullst" / "13.0.0-alpha.6.json").is_file())
            self.assertTrue((root / "results" / "raw" / "13.0.0-alpha.5" / "rullst.json").is_file())


def rank_row(slug: str, speed=(1.0, 1.0, 1.0, 1.0), t2=1.0, ram=1.0, t4=1.0, startup_s=0.01, bound=(),
             status="measured", rounds=5, **extra) -> dict:
    """A combined row with the ratios the rankings read; `bound` lists the client-bound runs."""
    ratios = {f"tier1.{ep}.rps": value for ep, value in zip(rankings.ENDPOINTS, speed) if value is not None}
    ratios.update({"tier2.rps": t2, "tier3.load_ram_peak_mib": ram, "tier4.rps": t4})
    stat = lambda v: {"median": v, "min": v, "max": v, "spread": 0.0, "n": rounds}  # noqa: E731
    metrics = {"startup_s": stat(startup_s), "tier2.rps": stat(1000 * t2), "tier2.latency_ms.p99": stat(5.0),
               "tier3.load_ram_peak_mib": stat(10 * ram), "tier4.rps": stat(1000 * t4),
               "tier4.error_rate": stat(0.0), "tier4.timeouts": stat(0)}
    metrics.update({f"tier1.{ep}.rps": stat(1000 * value) for ep, value in zip(rankings.ENDPOINTS, speed)
                    if value is not None})
    runs = [f"tier1.{ep}" for ep in rankings.ENDPOINTS] + ["tier2", "tier3_load", "tier4"]
    row = {"slug": slug, "name": slug.title(), "status": status,
           "ratios": {k: stat(v) for k, v in ratios.items()}, "metrics": metrics,
           "flags": {"rounds": rounds, "crashed_rounds": 0, "ram_growing_rounds": 0,
                     "client_bound_rounds": {r: (rounds if r in bound else 0) for r in runs}}}
    row.update(extra)
    return row


ALL_RUNS = ("tier1.text", "tier1.json", "tier1.db-single", "tier1.html", "tier2", "tier3_load", "tier4")


class RankingTests(unittest.TestCase):
    def rank(self, rows):
        base = rank_row("axum", bound=ALL_RUNS, is_baseline=True, ratios={})
        result = rankings.compute([base, *rows], "axum")
        cats = {c["key"]: {e["slug"]: e for e in c["entries"]} for c in result["categories"]}
        overall = {e["slug"]: e for e in result["overall"]["entries"]}
        return result, cats, overall

    def test_scores_are_oriented_so_higher_is_better(self):
        _, cats, overall = self.rank([rank_row("a", speed=(2.0, 0.5, 1.0, 1.0), t2=0.8, ram=2.0, t4=0.9,
                                               startup_s=1.0)])
        a = {key: cats[key]["a"] for key in rankings.CATEGORY_KEYS}
        self.assertAlmostEqual(a["speed"]["score"], 1.0)
        self.assertEqual(a["speed"]["detail"]["text"], 2.0)
        self.assertAlmostEqual(a["memory"]["score"], 0.5)
        self.assertAlmostEqual(a["memory"]["ratio"], 2.0)
        # 1 s against Axum's 0.01 s, which counts as the 0.25 s poll interval.
        self.assertAlmostEqual(a["startup"]["score"], 0.25)
        expected = (1.0 * 0.8 * 0.5 * 0.9 * 0.25) ** 0.2
        self.assertAlmostEqual(overall["a"]["score"], round(expected, 4))
        self.assertEqual(overall["a"]["position"], 1)

    def test_reference_is_listed_without_a_position(self):
        result, cats, overall = self.rank([rank_row("fast", t2=1.5), rank_row("slow", t2=0.5)])
        self.assertEqual(overall["axum"]["status"], "reference")
        self.assertIsNone(overall["axum"]["position"])
        self.assertEqual(overall["axum"]["score"], 1.0)
        self.assertEqual((cats["pressure"]["fast"]["position"], cats["pressure"]["slow"]["position"]), (1, 2))
        order = [e["slug"] for e in result["categories"][1]["entries"]]
        self.assertEqual(order, ["fast", "axum", "slow"])
        self.assertEqual(result["overall"]["weights"], {key: 0.2 for key in rankings.CATEGORY_KEYS})

    def test_a_missing_metric_makes_the_row_incomplete(self):
        row = rank_row("fastapi", speed=(0.5, 0.5, None, 0.5), excluded=["tier1.db-single"])
        failed = rank_row("broken", status="failed-conformance", ratios={}, metrics={}, flags={})
        _, cats, overall = self.rank([row, failed, rank_row("other", t2=0.1)])
        self.assertEqual(cats["speed"]["fastapi"]["status"], "incomplete")
        self.assertIsNone(cats["speed"]["fastapi"]["position"])
        self.assertIn("left out by a correction", cats["speed"]["fastapi"]["reason"])
        self.assertEqual(cats["pressure"]["fastapi"]["position"], 1)
        self.assertEqual(overall["fastapi"]["status"], "incomplete")
        self.assertIsNone(overall["fastapi"]["position"])
        self.assertIsNone(overall["fastapi"]["score"])
        self.assertEqual(overall["fastapi"]["missing"], ["speed"])
        self.assertEqual(overall["broken"]["status"], "not measured")
        self.assertEqual(overall["other"]["position"], 1)

    def test_client_bound_results_within_the_tolerance_tie(self):
        rows = [rank_row("a", t2=1.02, ram=0.95, bound=ALL_RUNS), rank_row("b", t2=0.95, bound=ALL_RUNS),
                rank_row("c", t2=0.90), rank_row("d", t2=0.89),
                rank_row("e", t2=0.60, bound=ALL_RUNS)]
        _, cats, _ = self.rank(rows)
        pressure = cats["pressure"]
        self.assertEqual([pressure[s]["position"] for s in "abcde"], [1, 1, 3, 4, 5])
        self.assertTrue(pressure["a"]["tie"])
        self.assertEqual(sorted(pressure["a"]["tied_with"]), ["axum", "b"])
        self.assertFalse(pressure["c"]["tie"])  # close, but not client-bound
        self.assertFalse(pressure["e"]["tie"])  # client-bound, but not close
        self.assertFalse(cats["memory"]["a"]["tie"])  # 5% less RAM: memory has no client-bound ties

    def test_speed_ties_only_when_every_endpoint_is_client_bound(self):
        rows = [rank_row("a", speed=(0.98,) * 4, bound=ALL_RUNS),
                rank_row("b", speed=(0.95,) * 4, bound=("tier1.db-single",))]
        _, cats, _ = self.rank(rows)
        self.assertTrue(cats["speed"]["a"]["tie"])
        self.assertFalse(cats["speed"]["b"]["tie"])
        self.assertEqual(cats["speed"]["b"]["client_bound_runs"], ["tier1.db-single"])
        self.assertEqual(cats["speed"]["b"]["position"], 2)

    def test_startup_ties_within_the_poll_interval(self):
        rows = [rank_row("a", startup_s=0.02), rank_row("b", startup_s=0.28), rank_row("c", startup_s=0.41),
                rank_row("d", startup_s=0.61), rank_row("e", startup_s=4.1)]
        _, cats, overall = self.rank(rows)
        startup = cats["startup"]
        self.assertEqual([startup[s]["position"] for s in "abcde"], [1, 2, 2, 4, 5])
        self.assertEqual(startup["a"]["score"], 1.0)
        self.assertEqual(startup["a"]["tied_with"], ["axum"])
        self.assertEqual(startup["d"]["detail"]["startup_s"], 0.61)
        self.assertAlmostEqual(startup["e"]["score"], round(0.25 / 4.1, 4))
        # b and c differ only in start-up, where they tie, so they tie overall too.
        self.assertEqual((overall["b"]["position"], overall["c"]["position"]), (2, 2))

    def test_overall_ties_only_when_tied_in_every_category(self):
        same = dict(speed=(0.99,) * 4, t2=0.99, t4=0.99, bound=ALL_RUNS)
        rows = [rank_row("a", ram=1.0, **same), rank_row("b", ram=1.0, **same), rank_row("c", ram=0.5, **same)]
        _, _, overall = self.rank(rows)
        self.assertEqual(overall["c"]["position"], 1)
        self.assertFalse(overall["c"]["tie"])  # better memory is a real difference
        self.assertEqual((overall["a"]["position"], overall["b"]["position"]), (2, 2))
        # a and b equal Axum's memory and tie with it in every other category.
        self.assertEqual(sorted(overall["a"]["tied_with"]), ["axum", "b"])

    def test_published_and_rendered(self):
        jobs = [fake_job("rullst", 0.5), fake_job("actix", 1.1)]
        combined = aggregate.combine(jobs, ["rullst", "actix"])
        doc = aggregate.site_document(combined)
        self.assertEqual(doc["schema"], "rullst.benchmarks.latest.v1")
        self.assertEqual([c["key"] for c in doc["rankings"]["categories"]], rankings.CATEGORY_KEYS)
        overall = doc["rankings"]["overall"]["entries"]
        self.assertEqual([e["slug"] for e in overall if e["position"]], ["actix", "rullst"])
        self.assertEqual(next(e for e in overall if e["slug"] == "rullst")["framework"], "Rullst")
        readme = report.render_readme_table(combined)
        self.assertIn("### Rankings", readme)
        self.assertIn("| Actix | 1: ", readme)
        self.assertIn("## Rankings", report.render_results(combined))


class ReleaseCheckTests(unittest.TestCase):
    def test_semver_order(self):
        versions = ["12.3.0", "13.0.0-alpha.10", "13.0.0-alpha.5", "13.0.0-rc.1", "13.0.0-beta.2"]
        self.assertEqual(sorted(versions, key=semver_key)[-1], "13.0.0-rc.1")
        self.assertEqual(newest([{"num": v} for v in versions] + [{"num": "14.0.0", "yanked": True}]),
                         "13.0.0-rc.1")
        self.assertLess(semver_key("13.0.0-rc.1"), semver_key("13.0.0"))
        self.assertLess(semver_key("13.0.0-alpha.5"), semver_key("13.0.0-alpha.10"))



class YieldTests(unittest.TestCase):
    def test_decide(self):
        from yield_check import decide
        release = {"path": ".github/workflows/release.yml", "status": "in_progress", "html_url": "u", "event": "push"}
        admission = {"path": ".github/workflows/ci.yml", "status": "queued", "html_url": "u", "event": "workflow_dispatch"}
        pr_ci = {"path": ".github/workflows/ci.yml", "status": "in_progress", "html_url": "u", "event": "pull_request"}
        self.assertFalse(decide([release], 0, 10)[0])
        self.assertFalse(decide([admission], 0, 10)[0])
        self.assertTrue(decide([pr_ci], 3, 10)[0])
        self.assertFalse(decide([pr_ci], 11, 10)[0])

    def test_parallelism(self):
        from yield_check import parallelism
        self.assertEqual(parallelism(True, 0, 4), 8)
        self.assertEqual(parallelism(True, 5, 4), 3)
        self.assertEqual(parallelism(True, 0, 15), 3)
        self.assertEqual(parallelism(False, 0, 0), 3)


if __name__ == "__main__":
    unittest.main()
