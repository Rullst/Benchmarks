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
from loadgen import MIB, describe_binary, efficiency  # noqa: E402
from loadgen_process import limiter, per_request_cpu  # noqa: E402
from measure import capacity_ratio, ram_trend, ratios, run_limiter, summarize, warmup_seconds  # noqa: E402
from release_check import newest, semver_key  # noqa: E402
from system import busy_fraction, parse_cpu_list, read_cpu_times, split_cpus, split_database  # noqa: E402

def fake_round(scale: float, number: int = 1, endpoints=ENDPOINTS) -> dict:
    run = {"rps": 1000 * scale, "latency_ms": {"mean": 1.2 / scale, "p50": 1.0 / scale, "p99": 4.0 / scale},
           "error_rate": 0.0, "server_cpu_cores": 1.9, "rps_per_cpu": round(1000 * scale / 1.9, 1),
           "db_cpu_cores": 0.5, "client_bound": scale > 1, "timeouts": 0, "transport_errors": 0}
    return {
        "round": number, "crashed": None, "startup_s": 0.5,
        "idle": {"ram_mib": 10 * scale, "cpu_cores": 0.001, "tasks": 4},
        "tier1": {ep: copy.deepcopy(run) for ep in endpoints},
        **({"hot_rows": dict(copy.deepcopy(run), ids=10)} if "world-update" in endpoints else {}),
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
                                          "runner": {}, "load_generator": {"name": "wrk", "version": "4.2.0"}},
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
    def test_wrk_binary_is_required(self):
        from common import BenchError
        with self.assertRaises(BenchError):
            describe_binary(Path("/nonexistent/wrk"), load_config()["load_generator"])

    def test_endpoint_workloads(self):
        from measure import endpoint_workload
        import workload as W
        config = load_config()
        static = endpoint_workload("queries", config, {})
        self.assertTrue(static.static)
        self.assertEqual(static.requests[0].path, "/queries?queries=20")
        self.assertEqual(len(endpoint_workload("world", config, {}).requests), 10000)
        sessions = [W.Session(cookie=f"id={i}") for i in range(125)]
        me = endpoint_workload("me", config, {"login_sessions": sessions})
        self.assertEqual(len(me.requests), 125)
        put = endpoint_workload("world-update", config, {"write_csrf": ("c", "X-T", "tok")})
        self.assertIn(("X-T", "tok"), put.requests[0].headers)

    def test_every_phase2_endpoint_has_a_workload_and_a_tier1_run(self):
        from common import PHASE2_ENDPOINTS
        config = load_config()
        for endpoint in PHASE2_ENDPOINTS:
            self.assertIn(endpoint, config["endpoint_workloads"])
            self.assertIn(endpoint, config["tiers"]["tier1"]["endpoints"])
        order = config["tiers"]["tier1"]["endpoints"]
        self.assertEqual(order[-2:], ["updates", "world-update"])  # writes last


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

    def test_required_update_rows_ignore_unchanged_values(self):
        required = conformance.required_update_rows
        before = {i: i for i in range(1, 31)}
        rows = [(i, 100 + i) for i in range(1, 21)]
        after = before | {i: 100 + i for i in range(1, 21)}
        self.assertEqual(required(rows, before, after), 20)
        # A new random value equal to the old one: an ORM that tracks changes writes nothing for it.
        same = [(i, i if i == 3 else 100 + i) for i in range(1, 21)]
        self.assertEqual(required(same, before, after | {3: 3}), 19)
        # A repeated id counts once, and not at all when it ends where it started.
        self.assertEqual(required(rows + [(5, 999)], before, after | {5: 999}), 20)
        self.assertEqual(required(rows + [(5, 5)], before, after | {5: 5}), 19)
        # Only the database before and after matters, not the order of the rows.
        self.assertEqual(required(list(reversed(rows)), before, after), 20)

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
        self.assertEqual(sorted(config["tiers"]["tier1"]["endpoints"]), sorted(ENDPOINTS))

    def test_validation(self):
        manifest = {"name": "X", "language": "Rust", "group": "rust", "framework": "x", "framework_version": "1",
                    "runtime": "r", "server": "s", "workers": "w", "database_layer": "d", "template_engine": "t",
                    "logging": "none"}
        problems = lambda m: [p for p in validate_manifest("axum", m) if "missing" not in p or "endpoints" in p]  # noqa: E731,E501
        self.assertEqual(problems(manifest), [])
        block = {"validation": "manual", "csrf": {"design": "token", "mechanism": "m", "source": "library"},
                 "session": {"store": "postgresql", "mechanism": "m", "source": "library"}, "write_csrf": None}
        self.assertEqual(problems(dict(manifest, endpoints=list(ENDPOINTS), phase2=block)), [])
        self.assertIn("needs a 'phase2' block", problems(dict(manifest, endpoints=list(ENDPOINTS)))[0])
        self.assertIn("phase2.csrf.design", problems(dict(manifest, endpoints=list(ENDPOINTS), phase2=dict(
            block, csrf={"design": "cookie", "mechanism": "m", "source": "library"})))[0])
        self.assertIn("phase2.session.store", problems(dict(manifest, endpoints=list(ENDPOINTS), phase2=dict(
            block, session={"store": "redis", "mechanism": "m", "source": "library"})))[0])
        self.assertIn("write_csrf", problems(dict(manifest, endpoints=list(ENDPOINTS), phase2=dict(
            block, write_csrf={"cookie": "c"})))[0])
        self.assertEqual(problems(dict(manifest, endpoints=[*BASE_ENDPOINTS, "world"],
                                       phase2={"validation": "manual"})), [])
        self.assertIn("db_setup", problems(dict(manifest, db_setup="../x.sql"))[0])
        self.assertIn("unknown endpoints", problems(dict(manifest, endpoints=[*BASE_ENDPOINTS, "plaintext"]))[0])
        self.assertIn("must include html", problems(dict(manifest, endpoints=["text", "json", "db-single"]))[0])
        self.assertIn("list of endpoint names", problems(dict(manifest, endpoints="all"))[0])

    def test_every_rust_folder_declares_the_phase1_endpoints(self):
        import json
        from common import EXTRA_ENDPOINTS, FRAMEWORKS
        for slug in ("axum", "actix", "loco", "topcoat", "rullst", "rullst-minimal"):
            manifest = json.loads((FRAMEWORKS / slug / "bench.json").read_text())
            self.assertLessEqual(set(EXTRA_ENDPOINTS), set(declared_endpoints(manifest)), slug)

    def test_the_baseline_serves_every_endpoint(self):
        import json
        from common import FRAMEWORKS
        manifest = json.loads((FRAMEWORKS / "axum" / "bench.json").read_text())
        self.assertEqual(declared_endpoints(manifest), list(ENDPOINTS))
        self.assertEqual(validate_manifest("axum", manifest), [])


class EfficiencyTests(unittest.TestCase):
    def test_efficiency(self):
        self.assertEqual(efficiency({"rps": 1000, "server_cpu_cores": 0.5}), 2000.0)
        self.assertEqual(efficiency({"rps": 1000, "server_cpu_cores": 0.5, "rps_per_cpu": 7.0}), 7.0)
        self.assertIsNone(efficiency({"rps": 1000, "server_cpu_cores": 0}))
        self.assertIsNone(efficiency(None))

    def test_per_request_cpu(self):
        out = per_request_cpu({"rps": 1000, "server_cpu_cores": 1.0, "db_cpu_cores": 0.5})
        self.assertEqual(out, {"db_us_per_request": 500.0, "cpu_us_per_request": 1500.0,
                               "total_rps_per_cpu": round(1000 / 1.5, 1)})
        self.assertEqual(per_request_cpu({"rps": 0, "server_cpu_cores": 1.0, "db_cpu_cores": 0.5}), {})

    def test_limiter_names_postgresql_or_the_load_generator(self):
        pg = {"client_bound": True, "db_cpu_cores": 1.6, "loadgen_cpu_cores": 0.35}
        lg = {"client_bound": True, "db_cpu_cores": 0.0, "loadgen_cpu_cores": 1.9}
        self.assertEqual(limiter(pg, 0.9), "postgresql")
        self.assertEqual(limiter(lg, 0.9), "load-generator")
        self.assertIsNone(limiter(dict(pg, client_bound=False), 0.9))
        # PostgreSQL on its own vCPUs: each side's busy fraction decides.
        own = {"client_bound": True, "db_cpu_busy": 0.95, "loadgen_cpu_busy": 0.4}
        self.assertEqual(limiter(own, 0.9, shared=False), "postgresql")
        self.assertEqual(limiter(dict(own, db_cpu_busy=0.5, loadgen_cpu_busy=0.97), 0.9, shared=False),
                         "load-generator")
        # Older results without the field: derived from the CPU use.
        self.assertEqual(run_limiter(pg), "postgresql")
        self.assertEqual(run_limiter(dict(lg, limited_by="load-generator")), "load-generator")

    def test_capacity_bases(self):
        free = {"rps": 1000, "server_cpu_cores": 2.0, "client_bound": False}
        self.assertEqual(capacity_ratio(free, dict(free, rps=2000)), (0.5, "rps"))
        # Limited by PostgreSQL: requests per CPU-second of the server and PostgreSQL together.
        pg = {"rps": 1000, "server_cpu_cores": 0.6, "db_cpu_cores": 1.9, "loadgen_cpu_cores": 0.05,
              "client_bound": True}
        base = {"rps": 1500, "server_cpu_cores": 1.1, "db_cpu_cores": 1.9, "loadgen_cpu_cores": 0.05,
                "client_bound": True}
        value, basis = capacity_ratio(pg, base)
        self.assertEqual(basis, "cpu")
        self.assertAlmostEqual(value, (1000 / 2.5) / (1500 / 3.0))
        # Limited by the load generator with the server near saturation: efficiency is used.
        lg = {"rps": 1500, "server_cpu_cores": 1.9, "db_cpu_cores": 0.0, "loadgen_cpu_cores": 1.9,
              "client_bound": True}
        self.assertEqual(capacity_ratio(free, lg), (500 / (1500 / 1.9), "cpu"))
        # ... far below saturation (under 75% of its vCPUs): not comparable.
        idle = dict(lg, server_cpu_cores=1.0)
        self.assertEqual(capacity_ratio(free, idle), (None, "not comparable"))
        self.assertEqual(capacity_ratio(idle, free), (None, "not comparable"))
        self.assertEqual(capacity_ratio(None, free), (None, "missing"))

    def test_ratios_count_bases_and_pairs(self):
        bound = fake_round(1.0, 1)
        idle = copy.deepcopy(bound)
        idle["tier1"]["json"].update(client_bound=True, limited_by="load-generator", server_cpu_cores=0.5)
        result = ratios([idle, idle], [bound, fake_round(1.0, 2)])
        stat = result["tier1.json.capacity"]
        self.assertEqual((stat["pairs"], stat["n"], stat["not_comparable_rounds"]), (2, 0, 2))
        self.assertIsNone(stat["median"])
        self.assertEqual(stat["load_generator_rounds"], 2)
        self.assertEqual(result["tier1.text.capacity"]["not_comparable_rounds"], 0)

    def test_ratios_include_capacity(self):
        fw = [fake_round(2.0, n) for n in (1, 2)]  # client-bound
        base = [fake_round(1.0, n) for n in (1, 2)]
        result = ratios(fw, base)
        self.assertAlmostEqual(result["tier1.updates.capacity"]["median"], (2000 / 2.4) / (1000 / 2.4), places=3)
        self.assertEqual(result["tier1.updates.capacity"]["cpu_rounds"], 2)
        self.assertNotIn("tier2.capacity", result)  # Tiers 2 and 4 are stability checks
        self.assertNotIn("tier1.json.db_cpu_cores", result)
        self.assertIn("tier1.fortunes.rps_per_cpu", result)
        self.assertIn("tier1.fortunes.db_us_per_request", result)
        partial = [fake_round(1.0, n, BASE_ENDPOINTS) for n in (1, 2)]
        result = ratios(partial, base)
        self.assertNotIn("tier1.queries.capacity", result)
        self.assertEqual(result["tier1.json.capacity"]["cpu_rounds"], 0)
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
            self.assertTrue((root / "results" / "raw" / "13.0.0-alpha.5" / "rullst-job1.json").is_file())

    def test_jobs_of_one_framework_are_pooled(self):
        first, second = fake_job("actix", 1.1, rounds=2), fake_job("actix", 0.9, rounds=3)
        second["job"] = 2
        second["environment"] = dict(second["environment"], cpu_model="Other CPU")
        combined = aggregate.combine([first, second], ["actix"])
        actix = next(r for r in combined["implementations"] if r["slug"] == "actix")
        self.assertEqual(actix["ratios"]["tier1.json.rps"]["n"], 5)
        self.assertEqual(actix["metrics"]["tier1.json.rps"]["n"], 5)
        self.assertAlmostEqual(actix["ratios"]["tier1.json.rps"]["median"], 0.9)
        self.assertEqual(actix["runners"], ["Test CPU", "Other CPU"])
        self.assertEqual([j["job"] for j in actix["jobs"]], [1, 2])
        self.assertEqual(combined["run"]["jobs_per_framework"], 2)
        self.assertEqual(combined["runners"], [{"cpu_model": "Other CPU", "jobs": 1},
                                               {"cpu_model": "Test CPU", "jobs": 1}])
        self.assertIn("Other CPU ×1", report.notice(combined))
        self.assertIn("| Test CPU, Other CPU |", report.render_readme_table(combined))

    def test_the_control_gives_the_tie_margins(self):
        jobs = [fake_job("axum-control", 1.02), fake_job("axum-control", 0.99), fake_job("actix", 1.2)]
        jobs[1]["job"] = 2
        for job in jobs[:2]:
            job["implementations"]["axum-control"]["manifest"].update(role="control", role_note="A/A copy")
        combined = aggregate.combine(jobs, ["axum-control", "actix"])
        margin = combined["rankings"]["tie_margins"]["hello"]
        self.assertAlmostEqual(margin["percent"], 2.0, places=1)
        self.assertEqual(len(margin["scores"]), 3)  # two jobs and the pooled row
        control = next(r for r in combined["implementations"] if r["slug"] == "axum-control")
        self.assertEqual(control["role"], "control")
        self.assertIn("A/A control, unranked", report.render_readme_table(combined))

    def test_dependency_source(self):
        self.assertEqual(aggregate.dependency_source(
            "registry+https://github.com/rust-lang/crates.io-index")["kind"], "crates.io")
        git = aggregate.dependency_source("git+https://github.com/Rullst/Rullst?rev=58438b64ca#58438b64caa847ef")
        self.assertEqual(git["label"], "git Rullst/Rullst@58438b6")
        self.assertIsNone(aggregate.dependency_source(""))
        job = fake_job("rullst", 1.0)
        job["implementations"]["rullst"]["build"]["versions"] += (
            "rullst-source git+https://github.com/Rullst/Rullst?rev=58438b6#58438b64caa847ef\n")
        combined = aggregate.combine([job], ["rullst"])
        self.assertEqual(combined["rullst_source"]["kind"], "git")
        self.assertIn("built from git Rullst/Rullst@58438b6", report.notice(combined))

    def test_publication_gate(self):
        def gate(jobs, names):
            return aggregate.combine(jobs, names)["publication_gate"]
        jobs = [fake_job("actix", 1.1, rounds=5), fake_job("actix", 1.1, rounds=5), fake_job("actix", 1.1, rounds=5),
                fake_job("axum-control", 1.01, rounds=5), fake_job("axum-control", 0.99, rounds=5),
                fake_job("axum-control", 1.0, rounds=5)]
        for job, number in zip(jobs, (1, 2, 3, 1, 2, 3)):
            job["job"] = number
        for job in jobs:
            job["implementations"][job["framework"]]["build"]["versions"] += (
                "actix-source registry+https://github.com/rust-lang/crates.io-index\n")
        for job in jobs[3:]:
            job["implementations"]["axum-control"]["manifest"].update(role="control", role_note="A/A copy")
        result = gate(jobs, ["actix", "axum-control"])
        self.assertEqual([p for p in result["problems"] if "Rullst" not in p], [])
        self.assertTrue(any("Rullst was built from" in p for p in result["problems"]))
        self.assertFalse(result["passed"])
        self.assertEqual(load_config()["publication"]["min_jobs"], 3)  # the official run: 3 jobs per implementation
        two = gate(jobs[:2] + jobs[3:], ["actix", "axum-control"])["problems"]
        self.assertTrue(any("actix: measured on 2 job(s), at least 3 required" in p for p in two))
        one = gate(jobs[:1] + jobs[3:4], ["actix", "axum-control"])["problems"]
        self.assertTrue(any("actix: measured on 1 job(s), at least 3 required" in p for p in one))
        self.assertTrue(any("no between-job spread for hello" in p for p in one))
        older = copy.deepcopy(jobs[:2] + jobs[3:])  # recorded with the former minimum of 2 jobs
        for job in older:
            job["config"] = dict(job["config"], publication=dict(job["config"]["publication"], min_jobs=2))
        self.assertTrue(any("actix: measured on 2 job(s), at least 3 required" in p
                            for p in gate(older, ["actix", "axum-control"])["problems"]))
        noisy = copy.deepcopy(jobs)
        noisy[4] = fake_job("axum-control", 0.8, rounds=5)
        noisy[4].update(job=2)
        noisy[4]["implementations"]["axum-control"]["manifest"].update(role="control", role_note="A/A copy")
        self.assertTrue(any("A/A noise too large in hello" in p for p in gate(noisy, ["actix", "axum-control"])[
            "problems"]))
        rebuilt = copy.deepcopy(jobs)  # the same wrk source and compiler, another binary: consistent
        for number, job in enumerate(rebuilt):
            job["environment"]["load_generator"] = {"version": "4.2.0", "source_sha256": "e2", "compiler": "cc 15",
                                                    "sha256": f"bin{number}"}
        self.assertFalse(any("load generator" in p for p in gate(rebuilt, ["actix", "axum-control"])["problems"]))
        rebuilt[1]["environment"]["load_generator"]["compiler"] = "cc 16"
        self.assertTrue(any("load generator" in p for p in gate(rebuilt, ["actix", "axum-control"])["problems"]))
        mixed = copy.deepcopy(jobs)
        mixed[1]["environment"]["cpu_count"] = 8
        self.assertTrue(any("vCPUs differs" in p for p in gate(mixed, ["actix", "axum-control"])["problems"]))
        errors = copy.deepcopy(jobs)
        for r in errors[0]["implementations"]["actix"]["rounds"] + errors[1]["implementations"]["actix"]["rounds"]:
            r["tier1"]["json"]["error_rate"] = 0.05
        self.assertTrue(any("actix: Hello world: error rate above the limit" in p
                            for p in gate(errors, ["actix", "axum-control"])["problems"]))
        self.assertFalse(gate(jobs[:3], ["actix"])["passed"])  # no A/A control


def rank_row(slug: str, hello=(1.0, 1.0, 1.0), database=(1.0, 1.0, 1.0, 1.0), application=(1.0,) * 5,
             ram=10.0, startup_s=0.01, status="measured", rounds=5, capacity=None, cpu_runs=(), error_rates=None,
             tier_errors=(0.0, 0.0), crashed=0, ram_growing=0, base_ram=10.0, base_startup=0.01, **extra) -> dict:
    """A combined row with the ratios the rankings read.

    `capacity` maps runs to capacity ratios (otherwise the requests/s ratios
    are used); `cpu_runs` lists runs scored by CPU efficiency in every round;
    `tier_errors` are the worst-round error rates of Tiers 2 and 4.
    """
    tier1 = (dict(zip(rankings.HELLO_ENDPOINTS, hello)) | dict(zip(rankings.DATABASE_ENDPOINTS, database))
             | dict(zip(rankings.APPLICATION_ENDPOINTS, application)))
    stat = lambda v, top=None: {"median": v, "min": v, "max": v if top is None else top, "spread": 0.0,  # noqa: E731
                                "n": rounds}
    ratio_stats = {f"tier1.{ep}.rps": stat(value) for ep, value in tier1.items() if value is not None}
    for run, value in (capacity or {}).items():
        ratio_stats[f"{run}.capacity"] = dict(stat(value), pairs=rounds, not_comparable_rounds=0,
                                              cpu_rounds=rounds if run in cpu_runs else 0)
    metrics = {"startup_s": stat(startup_s), "tier3.load_ram_peak_mib": stat(ram),
               "tier2.rps": stat(1000.0), "tier2.error_rate": stat(0.0, tier_errors[0]),
               "tier4.rps": stat(1000.0), "tier4.error_rate": stat(0.0, tier_errors[1]), "tier4.timeouts": stat(0)}
    metrics.update({f"tier1.{ep}.rps": stat(1000 * value) for ep, value in tier1.items() if value is not None})
    metrics.update({f"tier1.{ep}.error_rate": stat(rate) for ep, rate in (error_rates or {}).items()})
    row = {"slug": slug, "name": slug.title(), "status": status, "endpoints": list(ENDPOINTS),
           "ratios": ratio_stats, "metrics": metrics, "role": "ranked",
           "paired_baseline": {"tier3.load_ram_peak_mib": base_ram, "startup_s": base_startup},
           "flags": {"rounds": rounds, "crashed_rounds": crashed, "ram_growing_rounds": ram_growing,
                     "client_bound_rounds": {}, "limited_rounds": {}}}
    row.update(extra)
    return row


class RankingTests(unittest.TestCase):
    def rank(self, rows, controls=None, settings=None):
        base = rank_row("axum", is_baseline=True, ratios={})
        result = rankings.compute([base, *rows], "axum", settings=settings, control_rows=controls)
        cats = {c["key"]: {e["slug"]: e for e in c["entries"]} for c in result["categories"]}
        overall = {e["slug"]: e for e in result["overall"]["entries"]}
        return result, cats, overall

    def test_categories(self):
        self.assertEqual(rankings.CATEGORY_KEYS, ["hello", "database", "application", "memory", "startup"])
        runs = {c["key"]: c["runs"] for c in rankings.CATEGORIES}
        self.assertEqual(runs["hello"], ["tier1.text", "tier1.json", "tier1.html"])
        self.assertEqual(runs["database"][0], "tier1.db-single")

    def test_scores_are_oriented_so_higher_is_better(self):
        _, cats, overall = self.rank([rank_row("a", hello=(2.0, 0.5, 1.0), database=(0.5,) * 4, ram=200.0,
                                               startup_s=2.0)])
        a = {key: cats[key]["a"] for key in rankings.CATEGORY_KEYS}
        self.assertAlmostEqual(a["hello"]["score"], 1.0)
        self.assertEqual(a["hello"]["detail"]["rps_ratio"]["text"], 2.0)
        self.assertAlmostEqual(a["database"]["score"], 0.5)
        # 200 MiB against Axum's 10 MiB, which counts as the 64 MiB floor.
        self.assertAlmostEqual(a["memory"]["score"], round(64 / 200, 4))
        self.assertAlmostEqual(a["memory"]["ratio"], 20.0)
        # 2 s against Axum's 0.01 s, which counts as the 1 s floor.
        self.assertAlmostEqual(a["startup"]["score"], 0.5)
        expected = (1.0 * 0.5 * 1.0 * (64 / 200) * 0.5) ** (1 / 5)
        self.assertAlmostEqual(overall["a"]["score"], round(expected, 4), places=3)
        self.assertEqual(overall["a"]["position"], 1)

    def test_memory_and_startup_floors(self):
        _, cats, _ = self.rank([rank_row("a", ram=50.0, startup_s=0.9), rank_row("b", ram=12.0, startup_s=0.02),
                                rank_row("c", ram=128.0, startup_s=3.0)])
        self.assertEqual([cats["memory"][s]["score"] for s in "abc"], [1.0, 1.0, 0.5])
        self.assertEqual([cats["memory"][s]["position"] for s in "abc"], [1, 1, 3])
        self.assertEqual([cats["startup"][s]["score"] for s in "abc"], [1.0, 1.0, round(1 / 3, 4)])

    def test_reference_diagnostics_and_the_control_have_no_position(self):
        rows = [rank_row("fast", hello=(1.5,) * 3), rank_row("slow", hello=(0.5,) * 3),
                rank_row("minimal", hello=(1.2,) * 3, role="diagnostic", role_note="d"),
                rank_row("copy", hello=(1.01,) * 3, role="control", role_note="c")]
        result, cats, overall = self.rank(rows)
        hello = cats["hello"]
        self.assertEqual(hello["axum"]["status"], "reference")
        self.assertEqual(hello["minimal"]["status"], "diagnostic")
        self.assertEqual(hello["copy"]["status"], "A/A control")
        self.assertEqual([hello[s]["position"] for s in ("fast", "slow", "minimal", "copy", "axum")],
                         [1, 2, None, None, None])
        self.assertAlmostEqual(hello["minimal"]["score"], 1.2)
        order = next(c for c in result["categories"] if c["key"] == "hello")["entries"]
        self.assertEqual([e["slug"] for e in order], ["fast", "minimal", "copy", "axum", "slow"])
        self.assertIsNone(overall["minimal"]["position"])
        self.assertEqual(overall["fast"]["position"], 1)

    def test_a_missing_metric_makes_the_row_incomplete(self):
        row = rank_row("fastapi", database=(None, 0.5, 0.5, 0.5), excluded=["tier1.db-single"])
        failed = rank_row("broken", status="failed-conformance", ratios={}, metrics={}, flags={})
        _, cats, overall = self.rank([row, failed, rank_row("other")])
        self.assertEqual(cats["database"]["fastapi"]["status"], "incomplete")
        self.assertIsNone(cats["database"]["fastapi"]["position"])
        self.assertIn("left out by a correction", cats["database"]["fastapi"]["reason"])
        self.assertEqual(cats["hello"]["fastapi"]["position"], 1)
        self.assertEqual(overall["fastapi"]["status"], "incomplete")
        self.assertEqual(overall["fastapi"]["missing"], ["database"])
        self.assertEqual(overall["broken"]["status"], "not measured")

    def test_endpoints_not_served_yet_make_a_category_incomplete(self):
        row = rank_row("gin", database=(1.0, None, None, None), application=(None,) * 5,
                       endpoints=list(BASE_ENDPOINTS))
        _, cats, overall = self.rank([row, rank_row("full")])
        self.assertIn("does not serve /queries, /updates, /fortunes yet", cats["database"]["gin"]["reason"])
        self.assertIn("does not serve /world, /worlds, /world-update, /form, /me yet",
                      cats["application"]["gin"]["reason"])
        self.assertEqual(cats["hello"]["gin"]["status"], "ranked")
        self.assertEqual(overall["gin"]["missing"], ["database", "application"])

    def test_the_error_gate_applies_to_every_throughput_category(self):
        rows = [rank_row("a", hello=(3.0,) * 3, error_rates={"json": 0.05}),
                rank_row("b", database=(2.0,) * 4, error_rates={"updates": 0.176}),
                rank_row("c", application=(3.0,) * 5, error_rates={"me": 0.05, "form": 0.001}),
                rank_row("ok", error_rates={"json": 0.01, "me": 0.01})]
        _, cats, overall = self.rank(rows)
        self.assertEqual(cats["hello"]["a"]["status"], "errors")
        self.assertEqual(cats["database"]["b"]["error_runs"], {"updates": 0.176})
        self.assertIn("/updates 17.6%", cats["database"]["b"]["reason"])
        self.assertEqual(cats["application"]["c"]["error_runs"], {"me": 0.05})
        self.assertIn("errors (GET /me 5.0%)", report._category_cell("application", cats["application"]["c"]))
        self.assertEqual(cats["hello"]["ok"]["position"], 1)  # 1% is still allowed
        self.assertIn("errors: hello", overall["a"]["reason"])

    def test_cpu_efficiency_scores_client_bound_runs(self):
        capacity = {"tier1.text": 2.0, "tier1.json": 0.5, "tier1.html": 1.0}
        _, cats, _ = self.rank([rank_row("a", capacity=capacity, cpu_runs=("tier1.text",))])
        hello = cats["hello"]["a"]
        self.assertAlmostEqual(hello["score"], 1.0)
        self.assertEqual(hello["efficiency_runs"], ["tier1.text"])
        self.assertEqual(hello["detail"]["basis"], {"text": "cpu", "json": "rps", "html": "rps"})
        self.assertTrue(report._category_cell("hello", hello).endswith("1.00×*"))

    def test_runs_mostly_not_comparable_have_no_score(self):
        row = rank_row("a")
        row["ratios"]["tier1.json.capacity"] = {"median": 1.0, "n": 2, "pairs": 5, "cpu_rounds": 2,
                                                "not_comparable_rounds": 3}
        ok = rank_row("b")
        ok["ratios"]["tier1.json.capacity"] = {"median": 0.9, "n": 3, "pairs": 5, "cpu_rounds": 3,
                                               "not_comparable_rounds": 2}
        _, cats, overall = self.rank([row, ok])
        self.assertEqual(cats["hello"]["a"]["status"], "not comparable")
        self.assertEqual(cats["hello"]["a"]["not_comparable_runs"], ["tier1.json"])
        self.assertIn("75%", cats["hello"]["a"]["reason"])
        self.assertEqual(cats["hello"]["b"]["position"], 1)
        self.assertIn("not comparable: hello", overall["a"]["reason"])

    def test_tie_margins_come_from_the_aa_control(self):
        controls = [rank_row("axum-control", hello=(1.03,) * 3, role="control", role_note="c"),
                    rank_row("axum-control", hello=(0.99,) * 3, role="control", role_note="c")]
        rows = [rank_row("a", hello=(1.20,) * 3), rank_row("b", hello=(1.18,) * 3), rank_row("c", hello=(1.10,) * 3),
                rank_row("d", hello=(1.02,) * 3)]
        result, cats, _ = self.rank(rows, controls=controls)
        margin = result["tie_margins"]["hello"]
        self.assertAlmostEqual(margin["margin"], round(abs(__import__("math").log(1.03)), 6))
        self.assertAlmostEqual(margin["percent"], 3.0, places=1)
        hello = cats["hello"]
        self.assertEqual([hello[s]["position"] for s in "abcd"], [1, 1, 3, 4])
        self.assertEqual(hello["a"]["tied_with"], ["b"])
        self.assertTrue(hello["d"]["within_reference_margin"])
        self.assertFalse(hello["c"]["within_reference_margin"])
        self.assertIn("1.02× ≈", report._category_cell("hello", hello["d"]))
        # Without A/A data only equal scores tie.
        result, cats, _ = self.rank(rows)
        self.assertIsNone(result["tie_margins"]["hello"]["margin"])
        self.assertEqual([cats["hello"][s]["position"] for s in "abcd"], [1, 2, 3, 4])

    def test_startup_ties_within_the_poll_interval(self):
        rows = [rank_row("a", startup_s=1.1), rank_row("b", startup_s=1.3), rank_row("c", startup_s=1.5),
                rank_row("d", startup_s=4.0)]
        _, cats, _ = self.rank(rows)
        self.assertEqual([cats["startup"][s]["position"] for s in "abcd"], [1, 1, 3, 4])

    def test_stability_is_a_check(self):
        rows = [rank_row("ok"), rank_row("leaky", ram_growing=2), rank_row("errors", tier_errors=(0.0, 0.02)),
                rank_row("stops", crashed=1)]
        result, _, overall = self.rank(rows)
        check = {e["slug"]: e for e in result["stability"]["entries"]}
        self.assertEqual([check[s]["result"] for s in ("ok", "leaky", "errors", "stops")],
                         ["pass", "warn", "fail", "fail"])
        self.assertIn("Tier 4 errors 2.0% in its worst round", check["errors"]["reasons"])
        self.assertNotIn("stability", rankings.CATEGORY_KEYS)
        self.assertEqual(overall["errors"]["status"], "unstable")
        self.assertIsNone(overall["errors"]["position"])
        self.assertEqual(overall["leaky"]["position"], 1)

    def test_the_overall_ranking_is_optional(self):
        result, _, _ = self.rank([rank_row("a")])
        self.assertFalse(result["publish_overall"])
        public = rankings.published(result)
        self.assertNotIn("overall", public)
        self.assertNotIn("sensitivity", public)
        self.assertIn("categories", public)
        result, _, _ = self.rank([rank_row("a")], settings={"publish_overall": True})
        self.assertIn("overall", rankings.published(result))

    def test_database_notes_label_the_database_rows(self):
        _, cats, _ = self.rank([rank_row("laravel", database_note="a connection per request")])
        entry = cats["database"]["laravel"]
        self.assertEqual(entry["database_note"], "a connection per request")
        self.assertIn("†", report._category_cell("database", entry))
        self.assertNotIn("database_note", cats["hello"]["laravel"])

    def test_sensitivity_table_ranks_under_other_weightings(self):
        rows = [rank_row("fast", hello=(3.0,) * 3, database=(0.5,) * 4),
                rank_row("db", hello=(0.5,) * 3, database=(2.0,) * 4)]
        result, _, _ = self.rank(rows)
        tables = {w["key"]: {e["slug"]: e for e in w["entries"]} for w in result["sensitivity"]}
        self.assertEqual(tables["equal"]["fast"]["position"], 1)
        self.assertEqual(tables["db-app"]["db"]["position"], 1)
        self.assertEqual(tables["db-app"]["fast"]["position"], 2)

    def test_published_and_rendered(self):
        jobs = [fake_job("rullst", 0.5), fake_job("actix", 1.1), fake_job("gin", 0.8, endpoints=BASE_ENDPOINTS)]
        combined = aggregate.combine(jobs, ["rullst", "actix", "gin"])
        doc = aggregate.site_document(combined)
        self.assertEqual(doc["schema"], "rullst.benchmarks.latest.v1")
        self.assertEqual([c["key"] for c in doc["rankings"]["categories"]], rankings.CATEGORY_KEYS)
        self.assertNotIn("overall", doc["rankings"])
        hello = {e["slug"]: e for e in doc["rankings"]["categories"][0]["entries"]}
        self.assertEqual(hello["actix"]["position"], 1)
        readme = report.render_readme_table(combined)
        self.assertIn("### Rankings", readme)
        self.assertNotIn("| Overall |", readme)
        self.assertIn("| Actix | 1: 1.10×* |", readme)  # client-bound (scale > 1): scored by CPU efficiency
        self.assertIn("| Gin | 1.2.3 | Rust | 0.80 | 0.80 | 0.80 | n/i | n/i | n/i | 800 (1,000) |", readme)
        self.assertIn("Test CPU", readme)
        results = report.render_results(combined)
        self.assertIn("## Rankings", results)
        self.assertIn("### /queries?queries=20", results)
        self.assertIn("PostgreSQL-bound 3/3", results)
        self.assertIn("PG µs/req", results)
        self.assertIn("not implemented yet", results)
        review = report.render_results(combined, review=True)
        self.assertIn("computed for review, not published", review)
        self.assertIn("## Publication gate", review)


class HarnessTests(unittest.TestCase):
    def test_rounds_alternate_abba(self):
        from harness import round_order
        self.assertEqual([round_order("x", "axum", n, 1)[0] for n in (1, 2, 3, 4)], ["x", "axum", "x", "axum"])
        self.assertEqual([round_order("x", "axum", n, 2)[0] for n in (1, 2)], ["axum", "x"])
        self.assertEqual(round_order("axum", "axum", 1, 1), ["axum"])

    def test_plan_has_jobs_per_framework(self):
        from harness import plan
        self.assertEqual(plan("actix,gin", 2), [{"framework": "actix", "job": 1}, {"framework": "actix", "job": 2},
                                                {"framework": "gin", "job": 1}, {"framework": "gin", "job": 2}])
        with self.assertRaises(Exception):
            plan("actix", 0)

    def test_the_control_must_be_an_identical_copy(self):
        import harness
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for slug in ("orig", "copy"):
                (root / slug / "src").mkdir(parents=True)
                (root / slug / "src" / "main.rs").write_text("fn main() {}")
                (root / slug / "bench.json").write_text(slug)
            saved, harness.FRAMEWORKS = harness.FRAMEWORKS, root
            try:
                self.assertEqual(harness.control_differences("copy", "orig"), [])
                (root / "copy" / "src" / "main.rs").write_text("fn main() { tuned() }")
                self.assertEqual(harness.control_differences("copy", "orig"), ["src/main.rs"])
            finally:
                harness.FRAMEWORKS = saved

    def test_jit_runtimes_warm_up_longer(self):
        config = load_config()
        self.assertEqual(warmup_seconds({"jit": True}, config), config["warmup"]["jit_duration_s"])
        self.assertEqual(warmup_seconds({}, config), config["warmup"]["duration_s"])
        self.assertGreater(config["warmup"]["jit_duration_s"], config["warmup"]["duration_s"])


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
