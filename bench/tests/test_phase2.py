"""Unit tests of the phase-2 prototypes: workloads and the wrk and oha parsers."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import loadgen_oha  # noqa: E402
import loadgen_wrk  # noqa: E402
import workload as W  # noqa: E402


class WorkloadTests(unittest.TestCase):
    def test_world_ids_cover_every_row_once(self):
        wl = W.world_by_id()
        ids = sorted(int(r.path.rsplit("/", 1)[1]) for r in wl.requests)
        self.assertEqual(ids, list(range(1, 10001)))
        self.assertEqual(wl.requests, W.world_by_id().requests)  # fixed seed

    def test_worlds_queries_stay_in_bounds(self):
        for r in W.worlds_pages(200).requests:
            query = dict(p.split("=") for p in r.path.split("?", 1)[1].split("&"))
            self.assertTrue(1 <= int(query["min"]) <= int(query["max"]) <= 10000)
            self.assertEqual(query["limit"], "20")
            self.assertIn(int(query["page"]), range(1, 6))

    def test_put_bodies_are_valid(self):
        wl = W.put_world(100, write_csrf=("rullst_csrf", "X-CSRF-Token", "abc"))
        for r in wl.requests:
            self.assertTrue(1 <= json.loads(r.body)["randomNumber"] <= 10000)
            self.assertIn(("Cookie", "rullst_csrf=abc"), r.headers)
            self.assertIn(("X-CSRF-Token", "abc"), r.headers)

    def test_form_posts_pair_cookie_and_token(self):
        sessions = [W.Session(cookie=f"sid={i}", csrf_field="_token", csrf_token=f"t{i}") for i in range(3)]
        wl = W.form_posts(sessions, count=9)
        self.assertEqual(wl.pairing, "joint")
        for r in wl.requests:
            cookie = dict(r.headers)["Cookie"]
            self.assertIn(f"_token=t{cookie.split('=')[1]}".encode(), r.body)


class WrkTests(unittest.TestCase):
    def test_parse_without_status_hook(self):
        out = ('Running 10s test\nWRK_JSON {"duration_us":10000000,"requests":1000,"bytes":5,"connect":0,'
               '"read":2,"write":0,"status":10,"timeout":1,"mean_us":1500.5,"max_us":9000,"p50_us":1000,'
               '"p90_us":2000,"p99_us":5000,"s1xx":-1,"s2xx":-1,"s3xx":-1,"s4xx":-1,"s5xx":-1}\n')
        m = loadgen_wrk.parse_output(out)
        self.assertEqual((m["requests_ok"], m["non_2xx"], m["transport_errors"], m["timeouts"]), (990, 10, 3, 1))
        self.assertEqual(m["rps"], 99.0)
        self.assertEqual(m["latency_ms"]["p99"], 5.0)
        self.assertNotIn("status_classes", m)

    def test_parse_with_status_hook_counts_redirects(self):
        out = ('WRK_JSON {"duration_us":1000000,"requests":100,"bytes":5,"connect":0,"read":0,"write":0,'
               '"status":0,"timeout":0,"mean_us":1,"max_us":1,"p50_us":1,"p90_us":1,"p99_us":1,'
               '"s1xx":0,"s2xx":90,"s3xx":10,"s4xx":0,"s5xx":0}')
        m = loadgen_wrk.parse_output(out)
        self.assertEqual((m["requests_ok"], m["non_2xx"]), (90, 10))
        self.assertEqual(m["status_classes"]["3xx"], 10)

    def test_request_file_rejects_separators(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = W.Workload([W.Request("GET", "/a\tb")])
            with self.assertRaises(ValueError):
                loadgen_wrk.write_files(bad, Path(tmp))
            script, requests = loadgen_wrk.write_files(W.world_by_id(10), Path(tmp), count_statuses=True)
            self.assertIn("function request()", script.read_text())
            self.assertIn("function response(", script.read_text())
            self.assertEqual(len(requests.read_text().splitlines()), 10)


class OhaTests(unittest.TestCase):
    def test_parse_ignores_deadline_aborts(self):
        out = json.dumps({"summary": {"total": 2.0, "average": 0.001, "slowest": 0.01},
                          "latencyPercentiles": {"p50": 0.001, "p90": 0.002, "p99": 0.004},
                          "statusCodeDistribution": {"200": 1000, "302": 5},
                          "errorDistribution": {"aborted due to deadline": 7, "connection reset": 1}})
        m = loadgen_oha.parse_output(out)
        self.assertEqual((m["requests_ok"], m["non_2xx"], m["transport_errors"]), (1000, 5, 1))
        self.assertEqual(m["aborted_at_deadline"], 7)
        self.assertEqual(m["rps"], 500.0)

    def test_joint_workloads_are_refused(self):
        sessions = [W.Session(cookie=f"sid={i}") for i in range(2)]
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            loadgen_oha.build_command(Path("oha"), "http://h/", W.me(sessions), Path(tmp), connections=1,
                                      duration_s=1, threads=1, timeout_s=5, client_cpus=[0])

    def test_independent_paths_and_bodies(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd = loadgen_oha.build_command(Path("oha"), "http://h/", W.put_world(50), Path(tmp), connections=4,
                                            duration_s=1, threads=1, timeout_s=5, client_cpus=[0])
            self.assertIn("--urls-from-file", cmd)
            self.assertIn("-Z", cmd)
            self.assertEqual(cmd[cmd.index("-m") + 1], "PUT")
            self.assertEqual(cmd[cmd.index("-T") + 1], "application/json")


if __name__ == "__main__":
    unittest.main()
