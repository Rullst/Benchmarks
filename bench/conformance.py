"""Conformance: every implementation must answer the four endpoints identically.

Rules (also in CONTRIBUTING.md):
- status 200 and the expected media type (a `charset` parameter, if present,
  must be utf-8);
- /text: the body is byte-identical;
- /html: the body is byte-identical after removing trailing whitespace
  (template files usually end with a newline);
- /json and /db-single: the body parses to the expected JSON value (key order
  and insignificant whitespace may differ);
- /db-single reads the database on every request: the harness changes the
  row between requests and the response must follow;
- HTTP/1.1 keep-alive works (several requests on one connection).
"""

from __future__ import annotations

import http.client
import json
import random

from containers import psql

TEXT = b"Hello World"
JSON_VALUE = {"message": "Hello World"}
HTML = (b"<!DOCTYPE html><html><head><title>Benchmark</title></head>"
        b"<body><h1>Hello World</h1></body></html>")

MEDIA_TYPES = {
    "/text": "text/plain",
    "/json": "application/json",
    "/db-single": "application/json",
    "/html": "text/html",
}


def check_content_type(path: str, header: str | None) -> str | None:
    if not header:
        return "no Content-Type header"
    parts = [p.strip() for p in header.split(";")]
    media = parts[0].lower()
    if media != MEDIA_TYPES[path]:
        return f"Content-Type is '{header}', expected {MEDIA_TYPES[path]}"
    for param in parts[1:]:
        key, _, value = param.partition("=")
        if key.strip().lower() == "charset" and value.strip().strip('"').lower() not in ("utf-8", "utf8"):
            return f"charset is '{value}', expected utf-8"
    return None


def check_body(path: str, body: bytes, db_value: int | None = None) -> str | None:
    if path == "/text":
        return None if body == TEXT else f"body {body[:200]!r} != {TEXT!r}"
    if path == "/html":
        return None if body.rstrip() == HTML else f"body {body[:300]!r} != {HTML!r}"
    try:
        value = json.loads(body)
    except ValueError:
        return f"body is not JSON: {body[:200]!r}"
    if path == "/json":
        return None if value == JSON_VALUE else f"JSON {value!r} != {JSON_VALUE!r}"
    expected = {"id": 1, "randomNumber": db_value}
    return None if value == expected else f"JSON {value!r} != {expected!r}"


def _request(conn: http.client.HTTPConnection, path: str) -> tuple[int, str | None, bytes, bool]:
    conn.request("GET", path, headers={"Accept": "*/*"})
    response = conn.getresponse()
    body = response.read()
    return response.status, response.getheader("Content-Type"), body, response.will_close


def run_checks(port: int, config: dict, row_id: int = 1) -> dict:
    """Run every check against a server on 127.0.0.1:port; returns a report."""
    checks: list[dict] = []
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)

    def record(path: str, problem: str | None, **extra) -> None:
        checks.append({"endpoint": path, "ok": problem is None, "problem": problem, **extra})

    try:
        for path in ("/text", "/json", "/html"):
            for attempt in range(3):
                status, ctype, body, will_close = _request(conn, path)
                problem = None
                if status != 200:
                    problem = f"status {status}"
                problem = problem or check_content_type(path, ctype) or check_body(path, body)
                if problem is None and will_close:
                    problem = "server closed the keep-alive connection"
                if problem or attempt == 2:
                    record(path, problem, status=status, content_type=ctype, body_bytes=len(body))
                if problem:
                    conn.close()
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
                    break

        db_problem = None
        rng = random.Random()
        for _ in range(5):
            value = rng.randint(10001, 99999)
            psql(config, f"UPDATE world SET randomnumber = {value} WHERE id = {row_id}")
            status, ctype, body, _ = _request(conn, "/db-single")
            db_problem = (f"status {status}" if status != 200 else None) \
                or check_content_type("/db-single", ctype) or check_body("/db-single", body, value)
            if db_problem:
                db_problem += " (the response must reflect the current database row)"
                break
        record("/db-single", db_problem, status=status, content_type=ctype, body_bytes=len(body))
    except (OSError, http.client.HTTPException) as exc:
        record("connection", f"{type(exc).__name__}: {exc}")
    finally:
        conn.close()
        # Leave the row as init.sql created it.
        psql(config, f"UPDATE world SET randomnumber = 1 + ({row_id} * 7919) % 10000 WHERE id = {row_id}")

    return {"passed": bool(checks) and all(c["ok"] for c in checks), "checks": checks}
