"""Unit tests for the parts of the harness that do not need Docker."""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aggregate  # noqa: E402
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
    run = {"rps": 1000 * scale, "latency_ms": {"p50": 1.0 / scale, "p99": 4.0 / scale}, "error_rate": 0.0,
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


if __name__ == "__main__":
    unittest.main()
