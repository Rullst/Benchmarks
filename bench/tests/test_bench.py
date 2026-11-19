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
import conformance  # noqa: E402
from common import BASE_ENDPOINTS, ENDPOINTS, declared_endpoints, endpoint_path, load_config, validate_manifest  # noqa: E402,E501
from conformance import check_body, check_content_type  # noqa: E402
from loadgen import MIB, efficiency, parse_result  # noqa: E402
from measure import capacity_ratio, ram_trend, ratios, summarize  # noqa: E402
from release_check import newest, semver_key  # noqa: E402
from system import busy_fraction, parse_cpu_list, read_cpu_times, split_cpus, split_database  # noqa: E402

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


def fake_round(scale: float, number: int = 1, endpoints=ENDPOINTS) -> dict:
    run = {"rps": 1000 * scale, "latency_ms": {"mean": 1.2 / scale, "p50": 1.0 / scale, "p99": 4.0 / scale},
           "error_rate": 0.0, "server_cpu_cores": 1.9, "rps_per_cpu": round(1000 * scale / 1.9, 1),
           "db_cpu_cores": 0.5, "client_bound": scale > 1, "timeouts": 0, "transport_errors": 0}
    return {
        "round": number, "crashed": None, "startup_s": 0.5,
        "idle": {"ram_mib": 10 * scale, "cpu_cores": 0.001, "tasks": 4},
        "tier1": {ep: copy.deepcopy(run) for ep in endpoints},
        "tier2": copy.deepcopy(run),
        "tier3": {"idle_ram_mib": 10 * scale, "idle_cpu_cores": 0.001, "load_ram_peak_mib": 20 * scale,
                  "load_cpu_cores": 1.9, "rps": 900 * scale, "client_bound": False},
        "tier4": dict(copy.deepcopy(run), ram_mid_mib=20.0, ram_end_mib=21.0, ram_growth_mib=1.0, ram_growing=False),
        "after": {"ram_mib": 12.0, "memory_peak_mib": 30.0},
    }


def fake_job(framework: str, scale: float, rounds: int = 3, endpoints=ENDPOINTS) -> dict:
    config = load_config()
    fw_rounds = [fake_round(scale, n, endpoints) for n in range(1, rounds + 1)]
    base_rounds = [fake_round(1.0, n) for n in range(1, rounds + 1)]
    manifest = {"name": framework.title(), "language": "Rust", "group": "rust", "framework": framework,
                "framework_version": "1.0", "runtime": "Rust", "server": "x", "workers": "2",
                "database_layer": "SQLx", "template_engine": "Askama", "logging": "off",
                "version_package": framework, "endpoints": list(endpoints)}
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
            "axum": {"manifest": dict(manifest, name="Axum", version_package="axum", endpoints=list(ENDPOINTS)),
                     "status": "measured",
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

    def test_database_cpus(self):
        self.assertEqual(split_database([2, 3], 0), ([2, 3], [2, 3]))
        self.assertEqual(split_database([2, 3], 1), ([2], [3]))
        with self.assertRaises(Exception):
            split_database([2], 1)

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


class EndpointConformanceTests(unittest.TestCase):
    def test_queries_parameter_is_clamped(self):
        cases = {None: 1, "": 1, "foo": 1, "0": 1, "-3": 1, "1": 1, "20": 20, "500": 500, "501": 500, "1.5": 1}
        for value, count in cases.items():
            self.assertEqual(conformance.expected_count(value), count, value)
        self.assertEqual(dict(conformance.QUERY_CASES)["501"], 500)

    def test_world_rows(self):
        rows, problem = conformance.parse_world_rows(b'[{"id": 3, "randomNumber": 7}, {"randomNumber": 1, "id": 9}]', 2)
        self.assertIsNone(problem)
        self.assertEqual(rows, [(3, 7), (9, 1)])
        for body, count, fragment in [(b'{"id": 3, "randomNumber": 7}', 1, "JSON array"),
                                      (b'[{"id": 3, "randomNumber": 7}]', 2, "expected 2 rows"),
                                      (b'[{"id": 3, "randomnumber": 7}]', 1, "randomNumber"),
                                      (b'[{"id": "3", "randomNumber": 7}]', 1, "integers"),
                                      (b'[{"id": 0, "randomNumber": 7}]', 1, "between 1 and 10000"),
                                      (b'not json', 1, "not JSON")]:
            self.assertIn(fragment, conformance.parse_world_rows(body, count)[1])

    def test_query_rows_match_the_database(self):
        table = {1: 10, 2: 20}
        self.assertIsNone(conformance.check_query_rows([(1, 10), (2, 20), (1, 10)], table))
        self.assertIn("row 2", conformance.check_query_rows([(1, 10), (2, 21)], table))

    def test_update_rows_are_written(self):
        before = {i: i for i in range(1, 31)}
        rows = [(i, 100 + i) for i in range(1, 21)]
        after = before | {i: 100 + i for i in range(1, 21)}
        self.assertIsNone(conformance.check_update_rows(rows, before, after))
        # A repeated id may end with either returned value.
        repeated = rows + [(5, 999)]
        self.assertIsNone(conformance.check_update_rows(repeated, before, after | {5: 999}))
        self.assertIsNone(conformance.check_update_rows(repeated, before, after))
        self.assertIn("database has 5", conformance.check_update_rows(rows, before, after | {5: 5}))
        self.assertIn("not returned changed", conformance.check_update_rows(rows, before, after | {25: 1}))
        # Returned values that were never written are caught, unless the new value equals the old one.
        unchanged = [(i, i) for i in range(1, 21)]
        self.assertIn("only 0 of 20", conformance.check_update_rows(unchanged, before, before))
        one = [(i, i if i == 3 else 100 + i) for i in range(1, 21)]
        self.assertIsNone(conformance.check_update_rows(one, before, after | {3: 3}))

    def test_fortunes_html(self):
        check = conformance.check_fortunes_body
        expected = conformance.FORTUNES_HTML
        self.assertIsNone(check(expected.encode()))
        # Whitespace and the form of character references may differ.
        pretty = (expected.replace("<tr>", "\n    <tr>").replace("<table>", "\n  <table>")
                  .replace("&apos;", "&#x27;").replace("&quot;", "&#34;").replace("&lt;/script", "&lt;&#x2F;script")
                  .replace("<!DOCTYPE html>", "<!doctype html>\n") + "\n")
        self.assertIsNone(check(pretty.encode()))
        self.assertIsNone(check(expected.replace("aren&apos;t", "aren't").replace("<td>11</td>", "<td> 11 </td>")
                                .encode()))
        self.assertIn("not escaped", check(expected.replace("&lt;script&gt;", "<script>").encode()))
        self.assertIn("expected <tr>, got <tbody>", check(expected.replace("<table>", "<table><tbody>").encode()))
        self.assertIn('<html lang="en">', check(expected.replace("<html>", '<html lang="en">').encode()))
        self.assertIn("expected text '0'", check(expected.replace(
            "<tr><td>0</td><td>Additional fortune added at request time.</td></tr>", "").encode()))
        unsorted = expected.replace("<tr><td>12</td>", "<tr><td>13</td>")
        self.assertIn("expected text '12'", check(unsorted.encode()))
        self.assertIn("not UTF-8", check(expected.encode("utf-16")))
        self.assertIn("after </html>", check((expected + "<p>x</p>").encode()))
        self.assertIn("A list is", check(expected.replace(" — Donald", " - Donald").encode()))

    def test_fortunes_need_a_utf8_charset(self):
        self.assertIsNone(check_content_type("/fortunes", "text/html; charset=utf-8", require_charset=True))
        self.assertIn("charset=utf-8", check_content_type("/fortunes", "text/html", require_charset=True))
        self.assertIsNone(check_content_type("/queries", "application/json"))


class ManifestTests(unittest.TestCase):
    def test_endpoints(self):
        self.assertEqual(declared_endpoints({}), list(BASE_ENDPOINTS))
        self.assertEqual(declared_endpoints({"endpoints": ["fortunes", *BASE_ENDPOINTS]}),
                         [*BASE_ENDPOINTS, "fortunes"])
        config = load_config()
        self.assertEqual(endpoint_path(config, "queries"), "/queries?queries=20")
        self.assertEqual(endpoint_path(config, "fortunes"), "/fortunes")
        self.assertEqual(config["tiers"]["tier1"]["endpoints"], list(ENDPOINTS))

    def test_validation(self):
        manifest = {"name": "X", "language": "Rust", "group": "rust", "framework": "x", "framework_version": "1",
                    "runtime": "r", "server": "s", "workers": "w", "database_layer": "d", "template_engine": "t",
                    "logging": "none"}
        problems = lambda m: [p for p in validate_manifest("axum", m) if "missing" not in p or "endpoints" in p]  # noqa: E731,E501
        self.assertEqual(problems(manifest), [])
        self.assertEqual(problems(dict(manifest, endpoints=list(ENDPOINTS))), [])
        self.assertIn("unknown endpoints", problems(dict(manifest, endpoints=[*BASE_ENDPOINTS, "plaintext"]))[0])
        self.assertIn("must include html", problems(dict(manifest, endpoints=["text", "json", "db-single"]))[0])
        self.assertIn("list of endpoint names", problems(dict(manifest, endpoints="all"))[0])

    def test_every_rust_folder_declares_the_new_endpoints(self):
        import json
        from common import FRAMEWORKS
        for slug in ("axum", "actix", "loco", "topcoat", "rullst", "rullst-minimal"):
            manifest = json.loads((FRAMEWORKS / slug / "bench.json").read_text())
            self.assertEqual(declared_endpoints(manifest), list(ENDPOINTS), slug)


class EfficiencyTests(unittest.TestCase):
    def test_efficiency(self):
        self.assertEqual(efficiency({"rps": 1000, "server_cpu_cores": 0.5}), 2000.0)
        self.assertEqual(efficiency({"rps": 1000, "server_cpu_cores": 0.5, "rps_per_cpu": 7.0}), 7.0)
        self.assertIsNone(efficiency({"rps": 1000, "server_cpu_cores": 0}))
        self.assertIsNone(efficiency(None))

    def test_capacity_uses_efficiency_when_either_side_is_client_bound(self):
        free = {"rps": 1000, "server_cpu_cores": 2.0, "client_bound": False}
        bound = {"rps": 1500, "server_cpu_cores": 1.0, "client_bound": True}
        self.assertEqual(capacity_ratio(free, dict(free, rps=2000)), (0.5, False))
        # The baseline was client-bound at 1500 req/s with half its CPU idle: 500 vs 1500 req per CPU-s.
        self.assertEqual(capacity_ratio(free, bound), (500 / 1500, True))
        self.assertEqual(capacity_ratio(bound, free), (3.0, True))
        self.assertEqual(capacity_ratio(None, free), (None, False))

    def test_ratios_count_pairs_that_efficiency_cannot_compare(self):
        bound = dict(fake_round(1.0, 1), tier2={"rps": 900, "client_bound": True, "server_cpu_cores": None})
        result = ratios([bound, bound], [bound, fake_round(1.0, 2)])
        self.assertEqual(result["tier2.capacity"]["not_comparable_rounds"], 1)
        self.assertEqual(result["tier2.capacity"]["efficiency_rounds"], 0)
        self.assertEqual(result["tier1.json.capacity"]["not_comparable_rounds"], 0)

    def test_ratios_include_capacity(self):
        fw = [fake_round(2.0, n) for n in (1, 2)]  # client-bound
        base = [fake_round(1.0, n) for n in (1, 2)]
        result = ratios(fw, base)
        self.assertAlmostEqual(result["tier1.updates.capacity"]["median"], 2.0, places=3)
        self.assertEqual(result["tier1.updates.capacity"]["efficiency_rounds"], 2)
        self.assertEqual(result["tier2.capacity"]["efficiency_rounds"], 2)
        self.assertNotIn("tier1.json.db_cpu_cores", result)
        self.assertIn("tier1.fortunes.rps_per_cpu", result)
        partial = [fake_round(1.0, n, BASE_ENDPOINTS) for n in (1, 2)]
        result = ratios(partial, base)
        self.assertNotIn("tier1.queries.capacity", result)
        self.assertEqual(result["tier1.json.capacity"]["efficiency_rounds"], 0)
        flags = summarize(partial)["flags"]["client_bound_rounds"]
        self.assertIn("tier1.json", flags)
        self.assertNotIn("tier1.queries", flags)


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
        self.assertNotIn("\nold\n", readme)
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
             status="measured", rounds=5, database=(1.0, 1.0, 1.0), capacity=None, efficiency_rounds=(),
             **extra) -> dict:
    """A combined row with the ratios the rankings read; `bound` lists the client-bound runs.

    `capacity` maps runs to capacity ratios (otherwise the requests/s ratios
    are used); `efficiency_rounds` lists runs whose capacity came from
    efficiency in every round.
    """
    tier1 = dict(zip(rankings.ENDPOINTS, speed)) | dict(zip(rankings.DATABASE_ENDPOINTS, database))
    ratios = {f"tier1.{ep}.rps": value for ep, value in tier1.items() if value is not None}
    ratios.update({"tier2.rps": t2, "tier3.load_ram_peak_mib": ram, "tier4.rps": t4})
    stat = lambda v: {"median": v, "min": v, "max": v, "spread": 0.0, "n": rounds}  # noqa: E731
    metrics = {"startup_s": stat(startup_s), "tier2.rps": stat(1000 * t2), "tier2.latency_ms.p99": stat(5.0),
               "tier3.load_ram_peak_mib": stat(10 * ram), "tier4.rps": stat(1000 * t4),
               "tier4.error_rate": stat(0.0), "tier4.timeouts": stat(0)}
    metrics.update({f"tier1.{ep}.rps": stat(1000 * value) for ep, value in tier1.items() if value is not None})
    runs = [f"tier1.{ep}" for ep in ENDPOINTS] + ["tier2", "tier3_load", "tier4"]
    ratio_stats = {k: stat(v) for k, v in ratios.items()}
    for run, value in (capacity or {}).items():
        ratio_stats[f"{run}.capacity"] = dict(stat(value), efficiency_rounds=rounds if run in efficiency_rounds else 0)
    row = {"slug": slug, "name": slug.title(), "status": status, "endpoints": list(ENDPOINTS),
           "ratios": ratio_stats, "metrics": metrics,
           "flags": {"rounds": rounds, "crashed_rounds": 0, "ram_growing_rounds": 0,
                     "client_bound_rounds": {r: (rounds if r in bound else 0) for r in runs}}}
    row.update(extra)
    return row


ALL_RUNS = (*(f"tier1.{ep}" for ep in ENDPOINTS), "tier2", "tier3_load", "tier4")


class RankingTests(unittest.TestCase):
    def rank(self, rows):
        base = rank_row("axum", bound=ALL_RUNS, is_baseline=True, ratios={})
        result = rankings.compute([base, *rows], "axum")
        cats = {c["key"]: {e["slug"]: e for e in c["entries"]} for c in result["categories"]}
        overall = {e["slug"]: e for e in result["overall"]["entries"]}
        return result, cats, overall

    def test_scores_are_oriented_so_higher_is_better(self):
        _, cats, overall = self.rank([rank_row("a", speed=(2.0, 0.5, 1.0, 1.0), t2=0.8, ram=2.0, t4=0.9,
                                               startup_s=1.0, database=(0.5, 0.5, 0.5))])
        a = {key: cats[key]["a"] for key in rankings.CATEGORY_KEYS}
        self.assertAlmostEqual(a["speed"]["score"], 1.0)
        self.assertEqual(a["speed"]["detail"]["text"], 2.0)
        self.assertAlmostEqual(a["database"]["score"], 0.5)
        self.assertEqual(a["database"]["detail"]["updates"], 0.5)
        self.assertAlmostEqual(a["memory"]["score"], 0.5)
        self.assertAlmostEqual(a["memory"]["ratio"], 2.0)
        # 1 s against Axum's 0.01 s, which counts as the 0.25 s poll interval.
        self.assertAlmostEqual(a["startup"]["score"], 0.25)
        expected = (1.0 * 0.5 * 0.8 * 0.5 * 0.9 * 0.25) ** (1 / 6)
        self.assertAlmostEqual(overall["a"]["score"], round(expected, 4))
        self.assertEqual(overall["a"]["position"], 1)

    def test_reference_is_listed_without_a_position(self):
        result, cats, overall = self.rank([rank_row("fast", t2=1.5), rank_row("slow", t2=0.5)])
        self.assertEqual(overall["axum"]["status"], "reference")
        self.assertIsNone(overall["axum"]["position"])
        self.assertEqual(overall["axum"]["score"], 1.0)
        self.assertEqual((cats["pressure"]["fast"]["position"], cats["pressure"]["slow"]["position"]), (1, 2))
        pressure = next(c for c in result["categories"] if c["key"] == "pressure")
        self.assertEqual([e["slug"] for e in pressure["entries"]], ["fast", "axum", "slow"])
        self.assertEqual(result["overall"]["weights"], {key: round(1 / 6, 4) for key in rankings.CATEGORY_KEYS})

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

    def test_an_endpoint_not_served_yet_makes_the_database_category_incomplete(self):
        row = rank_row("gin", database=(None, None, None), endpoints=list(BASE_ENDPOINTS))
        _, cats, overall = self.rank([row, rank_row("full")])
        self.assertEqual(cats["database"]["gin"]["status"], "incomplete")
        self.assertIn("does not serve /queries, /updates, /fortunes yet", cats["database"]["gin"]["reason"])
        self.assertEqual(cats["speed"]["gin"]["status"], "ranked")
        self.assertEqual(overall["gin"]["missing"], ["database"])
        self.assertEqual(overall["full"]["position"], 1)

    def test_client_bound_runs_are_ranked_by_efficiency(self):
        # Both client-bound at the same requests/s, but b needs a third more CPU per request.
        rows = [rank_row("a", t2=1.0, bound=ALL_RUNS, capacity={"tier2": 1.2}, efficiency_rounds=("tier2",)),
                rank_row("b", t2=1.0, bound=ALL_RUNS, capacity={"tier2": 0.9}, efficiency_rounds=("tier2",)),
                rank_row("c", t2=0.95, capacity={"tier2": 0.95})]
        _, cats, _ = self.rank(rows)
        pressure = cats["pressure"]
        self.assertEqual([pressure[s]["position"] for s in "acb"], [1, 2, 3])
        self.assertFalse(pressure["a"]["tie"])
        self.assertEqual(pressure["a"]["score"], 1.2)
        self.assertEqual(pressure["a"]["ratio"], 1.0)  # the requests/s ratio is still reported
        self.assertEqual(pressure["a"]["efficiency_runs"], ["tier2"])
        self.assertEqual(pressure["c"]["efficiency_runs"], [])
        self.assertTrue(pressure["a"]["client_bound"])

    def test_runs_client_bound_on_both_sides_without_efficiency_are_not_comparable(self):
        # No capacity ratios (no efficiency): both it and its paired Axum run were client-bound in most rounds.
        both = {"rounds": 5, "client_bound_rounds": {"tier2": 3}}
        rows = [rank_row("a", t2=1.05, bound=("tier2",), paired_baseline_flags=both),
                rank_row("b", t2=1.05, bound=("tier2",),
                         paired_baseline_flags={"rounds": 5, "client_bound_rounds": {"tier2": 2}}),
                rank_row("c", t2=0.9, bound=("tier2",), capacity={"tier2": 0.9}, efficiency_rounds=("tier2",),
                         paired_baseline_flags=both)]
        _, cats, overall = self.rank(rows)
        pressure = cats["pressure"]
        self.assertEqual(pressure["a"]["status"], "not comparable")
        self.assertIsNone(pressure["a"]["position"])
        self.assertIsNone(pressure["a"]["score"])
        self.assertEqual(pressure["a"]["not_comparable_runs"], ["tier2"])
        self.assertIn("client-bound in most rounds for both", pressure["a"]["reason"])
        self.assertEqual(overall["a"]["status"], "incomplete")
        self.assertIn("not comparable: pressure", overall["a"]["reason"])
        # Axum was not client-bound in most rounds: comparable by requests/s.
        self.assertEqual(pressure["b"]["position"], 1)
        # Efficiency scored the run: comparable.
        self.assertEqual(pressure["c"]["status"], "ranked")
        # With capacity ratios, the harness counts the round pairs that could not be compared.
        stat = {"median": 1.0, "min": 1.0, "max": 1.0, "spread": 0.0, "n": 3, "efficiency_rounds": 0,
                "not_comparable_rounds": 2}
        row = rank_row("d", t4=1.0)
        row["ratios"]["tier4.capacity"] = stat
        _, cats, _ = self.rank([row])
        self.assertEqual(cats["endurance"]["d"]["status"], "not comparable")

    def test_speed_combines_capacity_ratios(self):
        capacity = {"tier1.text": 2.0, "tier1.json": 0.5, "tier1.db-single": 1.0, "tier1.html": 1.0}
        rows = [rank_row("a", capacity=capacity, efficiency_rounds=("tier1.text",), bound=("tier1.text",))]
        _, cats, _ = self.rank(rows)
        self.assertAlmostEqual(cats["speed"]["a"]["score"], 1.0)
        self.assertEqual(cats["speed"]["a"]["efficiency_runs"], ["tier1.text"])
        self.assertEqual(cats["speed"]["a"]["detail"]["capacity"]["text"], 2.0)
        self.assertEqual(cats["speed"]["a"]["client_bound_runs"], ["tier1.text"])

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
        same = dict(speed=(0.99,) * 4, t2=0.99, t4=0.99, database=(0.99,) * 3)
        rows = [rank_row("a", ram=1.0, **same), rank_row("b", ram=1.0, **same), rank_row("c", ram=0.5, **same)]
        _, _, overall = self.rank(rows)
        self.assertEqual(overall["c"]["position"], 1)
        self.assertFalse(overall["c"]["tie"])  # better memory is a real difference
        self.assertEqual((overall["a"]["position"], overall["b"]["position"]), (2, 2))
        self.assertEqual(overall["a"]["tied_with"], ["b"])

    def test_published_and_rendered(self):
        jobs = [fake_job("rullst", 0.5), fake_job("actix", 1.1), fake_job("gin", 0.8, endpoints=BASE_ENDPOINTS)]
        combined = aggregate.combine(jobs, ["rullst", "actix", "gin"])
        doc = aggregate.site_document(combined)
        self.assertEqual(doc["schema"], "rullst.benchmarks.latest.v1")
        self.assertEqual([c["key"] for c in doc["rankings"]["categories"]], rankings.CATEGORY_KEYS)
        overall = doc["rankings"]["overall"]["entries"]
        self.assertEqual([e["slug"] for e in overall if e["position"]], ["actix", "rullst"])
        self.assertEqual(next(e for e in overall if e["slug"] == "rullst")["framework"], "Rullst")
        self.assertEqual(next(e for e in overall if e["slug"] == "gin")["status"], "incomplete")
        readme = report.render_readme_table(combined)
        self.assertIn("### Rankings", readme)
        self.assertIn("| Actix | 1: ", readme)
        self.assertIn("1.10×*", readme)  # client-bound (scale > 1): scored by efficiency
        self.assertIn("| Gin | 1.2.3 | Rust | 0.80 | 0.80 | 0.80 | n/i | n/i | n/i | 800 (1,000) |", readme)
        results = report.render_results(combined)
        self.assertIn("## Rankings", results)
        self.assertIn("### /queries?queries=20", results)
        self.assertIn("not implemented yet", results)


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
