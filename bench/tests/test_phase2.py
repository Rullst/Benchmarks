"""Unit tests of phase 2: workloads, browser sessions, conformance helpers, the wrk and oha parsers."""

from __future__ import annotations

import json
import random
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import conformance_phase2 as C  # noqa: E402
import loadgen_oha  # noqa: E402
import loadgen_wrk  # noqa: E402
import sessions as S  # noqa: E402
import workload as W  # noqa: E402
from conformance import html_tokens  # noqa: E402


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


    def test_form_posts_send_hidden_fields_and_browser_headers(self):
        session = W.Session(cookie="csrf=abc; id=1", fields=(("_token", "t+/="), ("utf8", "✓")))
        request = W.form_posts([session], count=1).requests[0]
        headers = dict(request.headers)
        self.assertEqual(headers["Origin"], "http://127.0.0.1:8080")
        self.assertEqual(headers["Sec-Fetch-Site"], "same-origin")
        self.assertEqual(headers["Cookie"], "csrf=abc; id=1")
        self.assertTrue(request.body.startswith(b"_token=t%2B%2F%3D&utf8=%E2%9C%93&name=user"))

    def test_hot_rows_write_a_few_rows(self):
        wl = W.hot_rows(ids=10, count=500)
        ids = {int(r.path.rsplit("/", 1)[1]) for r in wl.requests}
        self.assertEqual(ids, set(range(1, 11)))
        self.assertEqual({r.method for r in wl.requests}, {"PUT"})
        self.assertEqual(wl.requests, W.hot_rows(ids=10, count=500).requests)  # fixed seed

    def test_me_sends_cookies_or_bearer(self):
        wl = W.me([W.Session(cookie="id=1"), W.Session(cookie="", bearer="tok")])
        self.assertEqual(dict(wl.requests[0].headers), {"Accept": "application/json", "Cookie": "id=1"})
        self.assertEqual(dict(wl.requests[1].headers)["Authorization"], "Bearer tok")


class BrowserTests(unittest.TestCase):
    PAGE = ('<html><body><form action="/search"><input type="hidden" name="q" value="x"></form>'
            '<form method="POST" action="http://127.0.0.1:8080/form">'
            '<input type="hidden" name="_token" value="a&amp;b"><input name="name">'
            '<input type="number" name="randomNumber"/><input type="HIDDEN" name="_x" value=""></form></body></html>')

    def test_find_form_and_hidden_fields(self):
        form = S.find_form(self.PAGE, "/form")
        self.assertEqual(form["method"], "post")
        self.assertEqual(S.hidden_fields(form), [("_token", "a&b"), ("_x", "")])
        self.assertIsNone(S.find_form(self.PAGE, "/login"))
        self.assertIsNotNone(S.find_form('<form method="post"><input name="u"></form>', "/login"))

    def test_browser_reconnects_after_an_error_response(self):
        """A server that closes the connection after a 404 without `Connection: close`."""
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(2)
        listener.settimeout(10)
        accepted = []

        def serve():
            for _ in range(2):
                conn, _ = listener.accept()
                accepted.append(conn)
                with conn:
                    buffer = b""
                    while True:
                        while b"\r\n\r\n" not in buffer:
                            chunk = conn.recv(4096)
                            if not chunk:
                                break
                            buffer += chunk
                        if b"\r\n\r\n" not in buffer:
                            break
                        head, buffer = buffer.split(b"\r\n\r\n", 1)
                        missing = head.split(b" ", 2)[1] == b"/missing"
                        status = b"404 Not Found" if missing else b"200 OK"
                        conn.sendall(b"HTTP/1.1 " + status + b"\r\nContent-Length: 2\r\n\r\nok")
                        if missing:
                            break

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        browser = S.Browser(listener.getsockname()[1])
        try:
            self.assertEqual(browser.get("/ok").status, 200)
            self.assertEqual(browser.get("/missing").status, 404)
            self.assertEqual(browser.get("/ok").status, 200)
        finally:
            browser.close()
            thread.join(10)
            listener.close()
        self.assertEqual(len(accepted), 2)

    def test_cookie_jar_ignores_attributes_and_drops_expired_cookies(self):
        browser = S.Browser(1)
        names = browser.store(["__Host-sid=abc; Path=/; Secure; HttpOnly; SameSite=Strict",
                               "csrf=t%2B1; Max-Age=3600", "bad", "old=1; Max-Age=3600"])
        self.assertEqual(names, ["__Host-sid", "csrf", "old"])
        browser.store(["old=; Max-Age=0", "csrf=t2; Expires=Thu, 01 Jan 2099 00:00:00 GMT",
                       "sid=gone; expires=Thu, 01 Jan 1970 00:00:00 GMT"])
        self.assertEqual(browser.cookies, {"__Host-sid": "abc", "csrf": "t2"})
        self.assertEqual(browser.cookie_header(), "__Host-sid=abc; csrf=t2")


class ConformanceHelperTests(unittest.TestCase):
    def test_form_page_tokens_accept_any_escape_form(self):
        expected = html_tokens(C.form_page(C.FORM_NAME, 42))
        served = ("<!doctype html><html><head><title>Form</title></head><body><h1>Hello, &lt;b&gt;&#34;Tom&#34; "
                  "&amp; &#x27;Jérôme&#x27;&lt;/b&gt;</h1><p>42</p></body></html>\n")
        self.assertEqual(html_tokens(served), expected)
        unescaped = served.replace("&lt;b&gt;", "<b>")
        self.assertNotEqual(html_tokens(unescaped), expected)

    def test_tampered_token_changes_one_middle_character(self):
        self.assertEqual(C._tampered("abcde"), "abAde")
        self.assertEqual(C._tampered("AAAAA"), "AABAA")
        self.assertEqual(sum(a != b for a, b in zip("qzU4F8wicvIIdcJE=", C._tampered("qzU4F8wicvIIdcJE="))), 1)

    def test_changed_value_never_repeats_the_stored_one(self):
        class Fixed:
            def __init__(self, value):
                self.value = value

            def randint(self, low, high):
                self.bounds = (low, high)
                return self.value

        for current, draw, expected in ((1, 1, 2), (5000, 4999, 4999), (5000, 5000, 5001), (10000, 9999, 9999),
                                        (54321, 9999, 9999)):
            rng = Fixed(draw)
            self.assertEqual(C.changed_value(rng, current), expected, (current, draw))
            self.assertEqual(rng.bounds, (1, 9999))
        rng = random.Random(7)
        for current in (1, 2, 5000, 9999, 10000, 54321):
            values = {C.changed_value(rng, current) for _ in range(2000)}
            self.assertNotIn(current, values)
            self.assertTrue(values <= set(range(1, 10001)))

    def test_world_objects_are_strict(self):
        self.assertEqual(C._world({"id": 1, "randomNumber": 2}), (1, 2))
        self.assertIsNone(C._world({"id": 1.0, "randomNumber": 2}))
        self.assertIsNone(C._world({"id": 1, "randomNumber": 2, "extra": 0}))

    def test_worlds_cases_follow_the_contract(self):
        for query, ids in C.WORLDS_CASES:
            params = dict(p.split("=") for p in query.lstrip("?").split("&") if p)
            low, high = int(params.get("min", 1)), int(params.get("max", 10000))
            limit, page = int(params.get("limit", 20)), int(params.get("page", 1))
            rows = list(range(low, high + 1))[(page - 1) * limit:page * limit]
            self.assertEqual(rows, ids, query)


class RoundOrderTests(unittest.TestCase):
    def test_logins_come_after_every_ram_measurement(self):
        import measure
        from common import ENDPOINTS, load_config
        events = []

        class FakeServer:
            port, base_url = 8080, "http://127.0.0.1:8080"
            def state(self): return {"Running": True}
            def wait_ready(self, _): return 0.1
            def cpu_usec(self): return 0
            def ram_bytes(self): return 1
            def memory_peak_bytes(self): return 1
            def tasks(self): return 1
            def processes(self): return 1
            def stop(self): events.append("stop")

        def fake_load(binary, url, *, workload, connections, duration_s, **kwargs):
            events.append(f"load {workload.label} {duration_s}")
            return {"rps": 1.0, "requests_ok": 10, "non_2xx": 0, "transport_errors": 0, "error_rate": 0.0,
                    "client_bound": False,
                    "client_cpu_busy": 0.1, "server_ram_peak_mib": 1.0, "server_cpu_cores": 1.0,
                    "_ram_samples": [(0.0, 1), (1.0, 1)]}

        def fake_context(manifest, config, port):
            events.append("sessions")
            return {"form_sessions": [W.Session(cookie="c=1")], "login_sessions": [W.Session(cookie="id=1")]}

        saved = {name: getattr(measure, name) for name in
                 ("start_server", "reset_tables", "database_handle", "run_load", "phase2_context", "time",
                  "_idle_window")}
        fake_time = type("T", (), {"sleep": staticmethod(lambda s: None), "monotonic": staticmethod(lambda: 0.0)})
        try:
            measure.start_server = lambda *a, **k: FakeServer()
            measure.reset_tables = lambda *a, **k: None
            measure.database_handle = lambda config: None
            measure.run_load = fake_load
            measure.phase2_context = fake_context
            measure.time = fake_time
            measure._idle_window = lambda server, seconds, interval: {"ram_mib": 1.0, "cpu_cores": 0.0, "tasks": 1,
                                                                        "processes": 1}
            config = load_config()
            record = measure.measure_round({"slug": "axum", "endpoints": list(ENDPOINTS)}, config,
                                           {"server": [0], "client": [1]}, Path("wrk"), 1)
        finally:
            for name, value in saved.items():
                setattr(measure, name, value)
        self.assertIsNone(record["crashed"])
        tier4 = events.index(f"load /json {config['tiers']['tier4']['duration_s']}")
        self.assertGreater(events.index("sessions"), tier4)
        self.assertTrue(all("/world" not in e and "/form" not in e and "/me" not in e for e in events[:tier4]))
        self.assertIn("hot_rows", record)
        self.assertEqual(list(record["tier1"])[-5:], ["world", "worlds", "form", "me", "world-update"])
        # Each endpoint is warmed up immediately before its own run, and Tier 3 (Memory) comes after Tier 4.
        warm, t1 = config["warmup"]["duration_s"], config["tiers"]["tier1"]["duration_s"]
        text = events.index(f"load /text {t1}")
        self.assertEqual(events[text - 1], f"load /text {warm}")
        self.assertEqual(events[events.index(f"load GET /me {t1}") - 1], f"load GET /me {warm}")
        self.assertGreater(events.index(f"load /json {config['tiers']['tier3']['duration_s']}"), tier4)
        self.assertEqual(set(record["warmup"]), set(ENDPOINTS))
        self.assertEqual(record["warmup_s"], warm)


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
