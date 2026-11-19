"""Conformance: every implementation must answer the endpoints it serves identically.

Rules (also in CONTRIBUTING.md):
- status 200 and the expected media type (a `charset` parameter, if present,
  must be utf-8; /fortunes must declare charset=utf-8);
- /text: the body is byte-identical;
- /html: the body is byte-identical after removing trailing whitespace
  (template files usually end with a newline);
- /json and /db-single: the body parses to the expected JSON value (key order
  and insignificant whitespace may differ);
- /db-single reads the database on every request: the harness changes the
  row between requests and the response must follow;
- HTTP/1.1 keep-alive works (several requests on one connection);
- /queries, /updates and /fortunes (when bench.json declares them) follow the
  TechEmpower Framework Benchmarks round 23 rules: see check_queries,
  check_updates and check_fortunes. pg_stat_statements counts the statements
  each request runs;
- the phase-2 endpoints (when declared) follow docs/v3-spec.md:
  bench/conformance_phase2.py.
"""

from __future__ import annotations

import http.client
import json
import random
from html.parser import HTMLParser

from common import BASE_ENDPOINTS
from containers import psql

TEXT = b"Hello World"
JSON_VALUE = {"message": "Hello World"}
HTML = (b"<!DOCTYPE html><html><head><title>Benchmark</title></head>"
        b"<body><h1>Hello World</h1></body></html>")

# TechEmpower's expected /fortunes response (its example response, with the
# Japanese row): the 12 rows of init.sql plus the one added at request time,
# sorted by message, the <script> message escaped.
FORTUNES_HTML = (
    "<!DOCTYPE html><html><head><title>Fortunes</title></head><body><table>"
    "<tr><th>id</th><th>message</th></tr>"
    "<tr><td>11</td><td>&lt;script&gt;alert(&quot;This should not be displayed in a browser alert box."
    "&quot;);&lt;/script&gt;</td></tr>"
    "<tr><td>4</td><td>A bad random number generator: 1, 1, 1, 1, 1, 4.33e+67, 1, 1, 1</td></tr>"
    "<tr><td>5</td><td>A computer program does what you tell it to do, not what you want it to do.</td></tr>"
    "<tr><td>2</td><td>A computer scientist is someone who fixes things that aren&apos;t broken.</td></tr>"
    "<tr><td>8</td><td>A list is only as strong as its weakest link. — Donald Knuth</td></tr>"
    "<tr><td>0</td><td>Additional fortune added at request time.</td></tr>"
    "<tr><td>3</td><td>After enough decimal places, nobody gives a damn.</td></tr>"
    "<tr><td>7</td><td>Any program that runs right is obsolete.</td></tr>"
    "<tr><td>10</td><td>Computers make very fast, very accurate mistakes.</td></tr>"
    "<tr><td>6</td><td>Emacs is a nice operating system, but I prefer UNIX. — Tom Christaensen</td></tr>"
    "<tr><td>9</td><td>Feature: A bug with seniority.</td></tr>"
    "<tr><td>1</td><td>fortune: No such file or directory</td></tr>"
    "<tr><td>12</td><td>フレームワークのベンチマーク</td></tr>"
    "</table></body></html>"
)

MEDIA_TYPES = {
    "/text": "text/plain",
    "/json": "application/json",
    "/db-single": "application/json",
    "/html": "text/html",
    "/queries": "application/json",
    "/updates": "application/json",
    "/fortunes": "text/html",
}

# The `queries` values the checks send, and the row count each must return
# (missing, empty, non-numeric or below 1 count as 1; above 500 as 500).
QUERY_CASES = [(None, 1), ("", 1), ("foo", 1), ("0", 1), ("-3", 1), ("1", 1), ("20", 20), ("500", 500),
               ("501", 500)]
UPDATE_CASES = [(None, 1), ("foo", 1), ("0", 1), ("1", 1), ("20", 20), ("501", 500)]
MAX_ID = 10000
# The share of the rows /updates returns that must have a new value in the
# database (TechEmpower's threshold: a new random value can equal the old one).
UPDATED_SHARE = 0.9


def check_content_type(path: str, header: str | None, require_charset: bool = False) -> str | None:
    return check_content_type_for(MEDIA_TYPES[path], header, require_charset)


def check_content_type_for(expected: str, header: str | None, require_charset: bool = False) -> str | None:
    """The media type must be `expected`; a charset, if present (or required), must be utf-8."""
    if not header:
        return "no Content-Type header"
    parts = [p.strip() for p in header.split(";")]
    media = parts[0].lower()
    if media != expected:
        return f"Content-Type is '{header}', expected {expected}"
    charset = None
    for param in parts[1:]:
        key, _, value = param.partition("=")
        if key.strip().lower() == "charset":
            charset = value.strip().strip('"').lower()
            if charset not in ("utf-8", "utf8"):
                return f"charset is '{value}', expected utf-8"
    if require_charset and charset is None:
        return f"Content-Type is '{header}', expected {expected}; charset=utf-8"
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


def expected_count(value: str | None) -> int:
    """TechEmpower's rule for the `queries` parameter: an integer clamped to 1..500, otherwise 1."""
    try:
        number = int(value) if value is not None else 1
    except ValueError:
        return 1
    return min(max(number, 1), 500)


def parse_world_rows(body: bytes, count: int) -> tuple[list[tuple[int, int]] | None, str | None]:
    """Parse a /queries or /updates body: a JSON array of `count` {"id", "randomNumber"} objects."""
    try:
        value = json.loads(body)
    except ValueError:
        return None, f"body is not JSON: {body[:200]!r}"
    if not isinstance(value, list):
        return None, f"expected a JSON array, got {type(value).__name__}: {body[:200]!r}"
    if len(value) != count:
        return None, f"expected {count} rows, got {len(value)}"
    rows = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"id", "randomNumber"}:
            return None, f"each row must be {{\"id\", \"randomNumber\"}}, got {str(item)[:120]}"
        ident, number = item["id"], item["randomNumber"]
        if type(ident) is not int or type(number) is not int:
            return None, f"id and randomNumber must be integers, got {str(item)[:120]}"
        if not (1 <= ident <= MAX_ID and 1 <= number <= MAX_ID):
            return None, f"id and randomNumber must be between 1 and {MAX_ID}, got {str(item)[:120]}"
        rows.append((ident, number))
    return rows, None


def check_query_rows(rows: list[tuple[int, int]], table: dict[int, int]) -> str | None:
    """Every row /queries returned must be the row in the database."""
    for ident, number in rows:
        if table.get(ident) != number:
            return f"row {ident} has randomNumber {number}, the database has {table.get(ident)}"
    return None


def check_update_rows(rows: list[tuple[int, int]], before: dict[int, int], after: dict[int, int]) -> str | None:
    """/updates: the returned rows were written to the database, and no other row changed.

    A row id that appears more than once in one response may end with any of
    its returned values (a batched UPDATE applies one of them).
    """
    returned: dict[int, list[int]] = {}
    for ident, number in rows:
        returned.setdefault(ident, []).append(number)
    for ident, numbers in returned.items():
        stored = after.get(ident)
        if stored not in numbers:
            shown = numbers[0] if len(numbers) == 1 else numbers
            return f"row {ident} was returned with randomNumber {shown} but the database has {stored} after the request"
    others = [i for i in after if i not in returned and after[i] != before.get(i)]
    if others:
        return f"rows that were not returned changed: {sorted(others)[:5]}"
    changed = sum(1 for i in returned if after.get(i) != before.get(i))
    if changed < int(UPDATED_SHARE * len(returned)):
        return f"only {changed} of {len(returned)} returned rows have a new value in the database"
    return None


def required_update_rows(rows: list[tuple[int, int]], before: dict[int, int], after: dict[int, int]) -> int:
    """The rows /updates' UPDATE statements must have written at least: the returned ids whose value changed.

    An ORM that tracks changes skips the UPDATE of an object whose new value
    equals the one it read (Rullst's RowSnapshot, ActiveRecord, Eloquent,
    Ecto, SQLAlchemy): a new random value that equals the old one (1 row in
    10,000), or a repeated id that ends where it started. Such a row still
    passes check_update_rows (its returned value is the stored one) but
    needs no UPDATE, so the count depends only on the database before and
    after the request.
    """
    return len({ident for ident, _ in rows if after.get(ident) != before.get(ident)})


class _Tokens(HTMLParser):
    """An HTML document as a token list: declarations, tags with attributes, decoded text.

    Character references are decoded, so `&#39;`, `&#x27;` and `&apos;` are
    the same text (TechEmpower's checker accepts each escape form). Text that
    is only whitespace is dropped and other text is trimmed: only whitespace
    may differ. An unescaped `<script>` parses as an element and does not
    match.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[tuple] = []
        self._text: list[str] = []

    def _flush(self) -> None:
        text = "".join(self._text).strip()
        self._text = []
        if text:
            self.tokens.append(("text", text))

    def handle_data(self, data: str) -> None:
        self._text.append(data)

    def handle_decl(self, decl: str) -> None:
        self._flush()
        self.tokens.append(("decl", " ".join(decl.lower().split())))

    def handle_starttag(self, tag: str, attrs) -> None:
        self._flush()
        self.tokens.append(("start", tag, tuple(attrs)))

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        self._flush()
        self.tokens.append(("end", tag))

    def handle_comment(self, data: str) -> None:
        self._flush()
        self.tokens.append(("comment", data))

    def unknown_decl(self, data: str) -> None:
        self._flush()
        self.tokens.append(("decl", data))

    def handle_pi(self, data: str) -> None:
        self._flush()
        self.tokens.append(("pi", data))

    def close(self) -> None:
        super().close()
        self._flush()


def html_tokens(text: str) -> list[tuple]:
    parser = _Tokens()
    parser.feed(text)
    parser.close()
    return parser.tokens


def _describe(token: tuple | None) -> str:
    if token is None:
        return "the end of the document"
    kind = token[0]
    if kind == "start":
        attrs = "".join(f' {k}="{v}"' for k, v in token[2])
        return f"<{token[1]}{attrs}>"
    if kind == "end":
        return f"</{token[1]}>"
    if kind == "decl":
        return f"<!{token[1]}>"
    return f"{kind} {token[1][:80]!r}"


def check_fortunes_body(body: bytes) -> str | None:
    """/fortunes: TechEmpower's expected HTML; only whitespace and the form of character references may differ."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        return f"body is not UTF-8: {exc}"
    if "<script" in text.lower():
        return "the <script> fortune is not escaped"
    expected, actual = html_tokens(FORTUNES_HTML), html_tokens(text)
    for index, want in enumerate(expected):
        got = actual[index] if index < len(actual) else None
        if got != want:
            return f"HTML differs at token {index}: expected {_describe(want)}, got {_describe(got)}"
    if len(actual) > len(expected):
        return f"unexpected content after </html>: {_describe(actual[len(expected)])}"
    return None


def _request(conn: http.client.HTTPConnection, path: str) -> tuple[int, str | None, bytes, bool]:
    conn.request("GET", path, headers={"Accept": "*/*"})
    response = conn.getresponse()
    body = response.read()
    return response.status, response.getheader("Content-Type"), body, response.will_close


def world_table(config: dict) -> dict[int, int]:
    rows = psql(config, "SELECT id, randomnumber FROM world")
    return {int(i): int(n) for i, n in (line.split("|") for line in rows.splitlines() if line)}


# Statements counted per request: SELECTs and UPDATEs that name a table.
STATEMENT_SQL = r"""
SELECT coalesce(sum(calls) FILTER (WHERE kind = 'select'), 0),
       coalesce(sum(rows) FILTER (WHERE kind = 'select'), 0),
       coalesce(sum(calls) FILTER (WHERE kind = 'update'), 0),
       coalesce(sum(rows) FILTER (WHERE kind = 'update'), 0),
       count(*) FILTER (WHERE kind = 'select' AND q ~ '\morder\s+by\M')
FROM (SELECT lower(query) AS q, calls, rows,
             CASE WHEN lower(query) ~ '^\s*\(?\s*select\M' THEN 'select'
                  WHEN lower(query) ~ '^\s*(with\M.*)?\mupdate\M' THEN 'update' END AS kind
      FROM pg_stat_statements WHERE lower(query) ~ '\m{table}\M') s
"""


def reset_statements(config: dict) -> None:
    psql(config, "SELECT pg_stat_statements_reset()")


def statements(config: dict, table: str) -> dict:
    """What the requests since reset_statements ran against `table` (pg_stat_statements)."""
    values = [int(float(v)) for v in psql(config, STATEMENT_SQL.replace("{table}", table)).split("|")]
    return dict(zip(("select_calls", "select_rows", "update_calls", "update_rows", "ordered_selects"), values))


def _queries_path(endpoint: str, value: str | None) -> str:
    return endpoint if value is None else f"{endpoint}?queries={value}"


def run_checks(port: int, config: dict, row_id: int = 1, endpoints: list[str] | tuple = BASE_ENDPOINTS,
               manifest: dict | None = None) -> dict:
    """Run every check against a server on 127.0.0.1:port; returns a report.

    `manifest` (bench.json) gives the phase-2 settings (CSRF design, write_csrf).
    """
    checks: list[dict] = []
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)

    def record(path: str, problem: str | None, **extra) -> None:
        checks.append({"endpoint": path, "ok": problem is None, "problem": problem, **extra})

    def get(path: str, media_path: str, require_charset: bool = False) -> tuple[bytes, str | None, dict]:
        """One request on the keep-alive connection; returns the body, a problem and the details."""
        nonlocal conn
        status, ctype, body, will_close = _request(conn, path)
        problem = f"status {status}" if status != 200 else None
        problem = problem or check_content_type(media_path, ctype, require_charset)
        if will_close:
            conn.close()
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            problem = problem or "server closed the keep-alive connection"
        return body, problem, {"status": status, "content_type": ctype, "body_bytes": len(body)}

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
        # Leave the row as init.sql created it before the checks that read random rows.
        psql(config, f"UPDATE world SET randomnumber = 1 + ({row_id} * 7919) % 10000 WHERE id = {row_id}")

        if "queries" in endpoints:
            record("/queries", check_queries(get, config))
        if "updates" in endpoints:
            record("/updates", check_updates(get, config))
        if "fortunes" in endpoints:
            record("/fortunes", check_fortunes(get, config))
        # Imported here: conformance_phase2 reuses this module's helpers.
        import conformance_phase2
        conformance_phase2.run_checks(port, config, endpoints, manifest, record)
    except (OSError, http.client.HTTPException) as exc:
        record("connection", f"{type(exc).__name__}: {exc}")
    finally:
        conn.close()
        # Leave the table as init.sql created it.
        psql(config, "UPDATE world SET randomnumber = 1 + (id * 7919) % 10000")

    return {"passed": bool(checks) and all(c["ok"] for c in checks), "checks": checks}


def check_queries(get, config: dict) -> str | None:
    """/queries?queries=N: N rows, each read by its own query, as they are in the database."""
    table = world_table(config)
    ids_seen: list[set[int]] = []
    for value, count in QUERY_CASES:
        reset_statements(config)
        body, problem, _ = get(_queries_path("/queries", value), "/queries")
        rows, problem = (None, problem) if problem else parse_world_rows(body, count)
        problem = problem or check_query_rows(rows, table)
        if not problem:
            stats = statements(config, "world")
            if stats["select_calls"] < count:
                problem = (f"{stats['select_calls']} SELECT statements read {stats['select_rows']} rows; each of "
                           f"the {count} rows must be read by its own query")
        if problem:
            return f"queries={value!r}: {problem}"
        if count >= 20:
            ids_seen.append({ident for ident, _ in rows})
            if count == 500 and len(ids_seen[-1]) < 400:
                return f"queries=500 returned only {len(ids_seen[-1])} different rows: the ids must be random"
    if len(ids_seen) >= 2 and ids_seen[0] == ids_seen[1]:
        return "two requests returned the same rows: the ids must be random"
    return None


def check_updates(get, config: dict) -> str | None:
    """/updates?queries=N: N rows read one by one, given new random values, written, returned."""
    for value, count in UPDATE_CASES:
        before = world_table(config)
        reset_statements(config)
        body, problem, _ = get(_queries_path("/updates", value), "/updates")
        rows, problem = (None, problem) if problem else parse_world_rows(body, count)
        if not problem:
            stats = statements(config, "world")
            after = world_table(config)
            problem = check_update_rows(rows, before, after)
            required = required_update_rows(rows, before, after)
            if not problem and stats["select_calls"] < count:
                problem = (f"{stats['select_calls']} SELECT statements read {stats['select_rows']} rows; each of "
                           f"the {count} rows must be read by its own query")
            if not problem and stats["update_rows"] < required:
                problem = (f"UPDATE statements changed {stats['update_rows']} rows, expected at least {required} "
                           "(the returned rows whose value changed)")
        if problem:
            return f"queries={value!r}: {problem}"
    return None


def check_fortunes(get, config: dict) -> str | None:
    """/fortunes: the table read on every request (no ORDER BY), rendered and escaped as expected."""
    for _ in range(2):
        reset_statements(config)
        body, problem, _ = get("/fortunes", "/fortunes", require_charset=True)
        problem = problem or check_fortunes_body(body)
        if not problem:
            stats = statements(config, "fortune")
            if stats["select_calls"] < 1 or stats["select_rows"] < 12:
                problem = "the fortune table must be read from the database on every request"
            elif stats["ordered_selects"]:
                problem = "the query must not sort (no ORDER BY): the application sorts the list"
        if problem:
            return problem
    return None
