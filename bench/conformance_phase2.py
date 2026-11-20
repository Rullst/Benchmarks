"""Conformance of the phase-2 endpoints (docs/v3-spec.md sections 3, 4 and 6).

Each check returns None or the first problem it found. They run only for the
endpoints a folder declares in bench.json and use the same browser code as
the load (bench/sessions.py), so a session or CSRF pair that conformance
accepts is one the load can replay.
"""

from __future__ import annotations

import http.client
import json
import random
from urllib.parse import urlencode

from common import ENDPOINT_LABELS, BenchError, phase2
from conformance import check_content_type_for, html_tokens, reset_statements, statements
from containers import psql
from sessions import FORM_TYPE, LOGIN_OK, Browser, Response, find_form, load_form, login, send
from workload import ORIGIN

MAX_ID = 10000
# Statuses that conform, per case. INVALID is decision 1 of the spec's open
# questions (400 or 422 for an invalid query string or body).
INVALID = (400, 422)
NOT_AN_INTEGER = (400, 404, 422)
FORGED = (400, 403, 419, 422)
FORM_INVALID = (200, 302, 303, 400, 422)
NO_SESSION = (401, 403, 302, 303)
WRONG_PASSWORD = (200, 302, 303, 400, 401, 422)
CROSS_SITE_ORIGIN = "http://attacker.invalid"
FORM_NAME = "<b>\"Tom\" & 'Jérôme'</b>"
JSON_TYPE = "application/json"


def form_page(name: str, number) -> str:
    """The POST /form success page before escaping (section 4)."""
    return ("<!DOCTYPE html><html><head><title>Form</title></head><body><h1>Hello, "
            f"{_escape(name)}</h1><p>{number}</p></body></html>")


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            .replace("'", "&#39;"))


def _status(response: Response, allowed: tuple[int, ...], what: str) -> str | None:
    if response.status in allowed:
        return None
    return f"{what}: status {response.status}, expected {' or '.join(map(str, allowed))}"


def _ok(response: Response, media: str, what: str, require_charset: bool = False) -> str | None:
    """200 with the media type (and a utf-8 charset when required)."""
    if response.status != 200:
        return f"{what}: status {response.status}: {response.body[:200]!r}"
    problem = check_content_type_for(media, response.content_type, require_charset)
    return f"{what}: {problem}" if problem else None


def _json(response: Response, what: str):
    try:
        return json.loads(response.body), None
    except ValueError:
        return None, f"{what}: body is not JSON: {response.body[:200]!r}"


def _world(value) -> tuple[int, int] | None:
    """A {"id", "randomNumber"} object with integer values, as (id, randomNumber)."""
    if not isinstance(value, dict) or set(value) != {"id", "randomNumber"}:
        return None
    ident, number = value["id"], value["randomNumber"]
    if type(ident) is not int or type(number) is not int:
        return None
    return ident, number


def _row(config: dict, ident: int) -> int:
    return int(psql(config, f"SELECT randomnumber FROM world WHERE id = {int(ident)}"))


def _rows(config: dict, ids) -> dict[int, int]:
    """The randomNumber of each of `ids`, in one query."""
    listed = ",".join(str(int(ident)) for ident in ids)
    rows = psql(config, f"SELECT id, randomnumber FROM world WHERE id IN ({listed})")
    return {int(i): int(n) for i, n in (line.split("|") for line in rows.splitlines() if line)}


def changed_value(rng: random.Random, current: int) -> int:
    """A randomNumber in 1..10000 other than `current`, uniform over the others.

    A PUT of the stored value may write nothing (an ORM that tracks changes
    skips the UPDATE), so the checks that count UPDATEs never send one.
    """
    value = rng.randint(1, MAX_ID - 1)
    return value + 1 if value >= current else value


# ---------------------------------------------------------------- GET /world/{id}

def check_world(port: int, config: dict, _settings: dict) -> str | None:
    browser = Browser(port)
    rng = random.Random()
    try:
        for ident in rng.sample(range(1, MAX_ID + 1), 5):
            value = rng.randint(10001, 99999)
            psql(config, f"UPDATE world SET randomnumber = {value} WHERE id = {ident}")
            response = browser.get(f"/world/{ident}")
            what = f"GET /world/{ident}"
            problem = _ok(response, JSON_TYPE, what)
            if problem:
                return problem
            if response.will_close:
                return f"{what}: the server closed the keep-alive connection"
            body, problem = _json(response, what)
            if problem:
                return problem
            if _world(body) != (ident, value):
                return f"{what}: {body!r} != {{'id': {ident}, 'randomNumber': {value}}} (the row in the database)"
        # The browser reconnects after each refusal: a server may close the
        # connection after an error response.
        for path in ("/world/0", "/world/10001"):
            problem = _status(browser.get(path), (404,), f"GET {path}")
            if problem:
                return problem
        problem = _status(browser.get("/world/abc"), NOT_AN_INTEGER, "GET /world/abc")
        if problem:
            return problem
        reset_statements(config)
        for _ in range(20):
            response = browser.get(f"/world/{rng.randint(1, MAX_ID)}")
            if response.status != 200:
                return f"GET /world/{{id}}: status {response.status}"
        stats = statements(config, "world")
        if stats["select_calls"] < 20:
            return f"20 requests ran {stats['select_calls']} SELECT statements on world: read the row on every request"
        return None
    finally:
        browser.close()


# ---------------------------------------------------------------- GET /worlds

WORLDS_CASES = [
    ("", list(range(1, 21))),
    ("?min=500&max=600&limit=7&page=3", list(range(514, 521))),
    ("?min=9990&max=10000&limit=100&page=1", list(range(9990, 10001))),
    ("?min=9990&max=10000&limit=100&page=2", []),
    ("?page=2&unknown=1", list(range(21, 41))),
]
WORLDS_INVALID = ["limit=0", "limit=101", "limit=abc", "min=0", "max=10001", "min=600&max=500", "page=0"]


def check_worlds(port: int, config: dict, _settings: dict) -> str | None:
    rows = psql(config, "SELECT id, randomnumber FROM world")
    table = {int(i): int(n) for i, n in (line.split("|") for line in rows.splitlines() if line)}
    browser = Browser(port)
    try:
        for query, ids in WORLDS_CASES:
            what = f"GET /worlds{query}"
            response = browser.get(f"/worlds{query}")
            problem = _ok(response, JSON_TYPE, what)
            if problem:
                return problem
            body, problem = _json(response, what)
            if problem:
                return problem
            if not isinstance(body, list):
                return f"{what}: expected a JSON array, got {response.body[:200]!r}"
            got = [_world(item) for item in body]
            if any(item is None for item in got):
                return f"{what}: each row must be {{\"id\", \"randomNumber\"}} with integers: {response.body[:200]!r}"
            if [ident for ident, _ in got] != ids:
                return f"{what}: ids {[ident for ident, _ in got][:12]}, expected {ids[:12]} (ordered by id)"
            wrong = [(ident, number) for ident, number in got if table.get(ident) != number]
            if wrong:
                return f"{what}: row {wrong[0][0]} has randomNumber {wrong[0][1]}, the database has {table.get(wrong[0][0])}"
        for query in WORLDS_INVALID:
            problem = _status(browser.get(f"/worlds?{query}"), INVALID, f"GET /worlds?{query}")
            if problem:
                return problem
        reset_statements(config)
        response = browser.get("/worlds?min=100&max=5000&limit=20&page=4")
        if response.status != 200:
            return f"GET /worlds?min=100&max=5000&limit=20&page=4: status {response.status}"
        stats = statements(config, "world")
        if stats["select_calls"] != 1:
            return (f"one request ran {stats['select_calls']} SELECT statements on world: filter, order and "
                    "paginate in one query")
        return None
    finally:
        browser.close()


# ---------------------------------------------------------------- PUT /world/{id}

INVALID_BODIES = ['{"randomNumber": 0}', '{"randomNumber": 10001}', '{"randomNumber": "5"}', "{}",
                  '{"randomNumber": 5']


def _put(port: int, conn, ident, body: str, headers: dict) -> Response:
    return send(port, "PUT", f"/world/{ident}", {"Content-Type": JSON_TYPE, **headers}, body.encode(), conn=conn)


def write_headers(port: int, settings: dict) -> dict:
    """The CSRF cookie and header a PUT carries when bench.json declares phase2.write_csrf."""
    write_csrf = settings.get("write_csrf")
    if not write_csrf:
        return {}
    browser = Browser(port)
    try:
        load_form(browser, "/form")
    finally:
        browser.close()
    token = browser.cookies.get(write_csrf["cookie"])
    if not token:
        raise BenchError(f"GET /form did not set the '{write_csrf['cookie']}' cookie that phase2.write_csrf names")
    return {"Cookie": f"{write_csrf['cookie']}={token}", write_csrf["header"]: token}


def _nothing_written(config: dict, ident: int, before: int, what: str) -> str | None:
    stats = statements(config, "world")
    after = _row(config, ident)
    if after != before or stats["update_rows"]:
        return f"{what}: the request was refused but wrote to world (row {ident}: {before} -> {after})"
    return None


def check_world_update(port: int, config: dict, settings: dict) -> str | None:
    headers = write_headers(port, settings)
    rng = random.Random()
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        ids = rng.sample(range(1, MAX_ID + 1), 5)
        current = _rows(config, ids)
        for ident in ids:
            # A new value: the database after the request shows that the PUT wrote it.
            value = changed_value(rng, current[ident])
            what = f"PUT /world/{ident} {{\"randomNumber\": {value}}}"
            response = _put(port, conn, ident, json.dumps({"randomNumber": value}), headers)
            problem = _ok(response, JSON_TYPE, what)
            if problem:
                return problem
            body, problem = _json(response, what)
            if problem:
                return problem
            if _world(body) != (ident, value):
                return f"{what}: answered {body!r}, expected the stored row {{'id': {ident}, 'randomNumber': {value}}}"
            stored = _row(config, ident)
            if stored != value:
                return f"{what}: the database has {stored} after the request"
        ident = rng.randint(1, MAX_ID)
        for body in INVALID_BODIES:
            conn.close()  # a server may close the connection after refusing a body
            before = _row(config, ident)
            reset_statements(config)
            what = f"PUT /world/{ident} {body}"
            problem = _status(_put(port, conn, ident, body, headers), INVALID, what) \
                or _nothing_written(config, ident, before, what)
            if problem:
                return problem
        conn.close()
        for path_id in (0, 10001):
            problem = _status(_put(port, conn, path_id, '{"randomNumber": 5}', headers), (404,),
                              f"PUT /world/{path_id}")
            if problem:
                return problem
        problem = _status(_put(port, conn, "abc", '{"randomNumber": 5}', headers), NOT_AN_INTEGER, "PUT /world/abc")
        if problem:
            return problem
        conn.close()
        # 20 different rows, each given a value other than the stored one, so
        # that every request must run an UPDATE (read before the reset: the
        # harness's own SELECT is not counted).
        ids = rng.sample(range(1, MAX_ID + 1), 20)
        current = _rows(config, ids)
        reset_statements(config)
        for ident in ids:
            response = _put(port, conn, ident, json.dumps({"randomNumber": changed_value(rng, current[ident])}),
                            headers)
            if response.status != 200:
                return f"PUT /world/{ident}: status {response.status}"
        stats = statements(config, "world")
        if stats["update_calls"] < 20:
            return f"20 requests ran {stats['update_calls']} UPDATE statements on world: write on every request"
        if headers:
            conn.close()
            before = _row(config, ident)
            reset_statements(config)
            what = f"PUT /world/{ident} without the CSRF cookie and header (phase2.write_csrf)"
            problem = _status(_put(port, conn, ident, '{"randomNumber": 77}', {}), (403,), what) \
                or _nothing_written(config, ident, before, what)
            if problem:
                return problem
        return None
    finally:
        conn.close()


# ---------------------------------------------------------------- /form

def _tampered(value: str) -> str:
    """The value with its middle character changed (not the last: base64 padding bits may be ignored)."""
    if not value:
        return "x"
    index = len(value) // 2
    replacement = "A" if value[index] != "A" else "B"
    return value[:index] + replacement + value[index + 1:]


def _success(response: Response, name: str, number, what: str) -> str | None:
    problem = _ok(response, "text/html", what, require_charset=True)
    if problem:
        return problem
    try:
        text = response.body.decode("utf-8")
    except UnicodeDecodeError as exc:
        return f"{what}: body is not UTF-8: {exc}"
    expected, actual = html_tokens(form_page(name, number)), html_tokens(text)
    if actual != expected:
        return f"{what}: the page differs from the expected one (name escaped): {response.body[:300]!r}"
    return None


def _is_success_page(response: Response, name: str, number) -> bool:
    return response.status == 200 and _success(response, name, number, "") is None


def check_form(port: int, _config: dict, settings: dict) -> str | None:
    browser = Browser(port)
    try:
        response, fields = load_form(browser, "/form")
        problem = check_content_type_for("text/html", response.content_type)
        if problem:
            return f"GET /form: {problem}"
        form = find_form(response.text(), "/form")
        names = {name for _, name, _ in form["inputs"]}
        if form["method"] != "post" or not {"name", "randomNumber"} <= names:
            return "GET /form: the form must post (method=\"post\") the inputs 'name' and 'randomNumber'"
        cookie = browser.cookie_header()
        pair = {"Content-Type": FORM_TYPE, **({"Cookie": cookie} if cookie else {})}
        browser_headers = {"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}

        def post(form_fields: list[tuple[str, str]], headers: dict) -> Response:
            return send(port, "POST", "/form", headers, urlencode(form_fields).encode())

        number = random.randint(1, MAX_ID)
        for attempt in range(4):  # the pair is reusable: the load replays it
            what = f"POST /form (valid, request {attempt + 1} with the same cookies and token)"
            response = post([*fields, ("name", FORM_NAME), ("randomNumber", str(number))], {**pair, **browser_headers})
            problem = _success(response, FORM_NAME, number, what)
            if problem:
                return problem
        for name, value in (("", "5"), ("x" * 65, "5"), ("Tom", "0"), ("Tom", "abc")):
            what = f"POST /form name={name[:10]!r}{'...' if len(name) > 10 else ''} randomNumber={value!r}"
            response = post([*fields, ("name", name), ("randomNumber", value)], {**pair, **browser_headers})
            problem = _status(response, FORM_INVALID, what)
            if problem:
                return problem
            if _is_success_page(response, name, value):
                return f"{what}: answered the success page for invalid fields"
        valid = [("name", "Tom"), ("randomNumber", "5")]
        forged = post(valid, {**pair, "Origin": CROSS_SITE_ORIGIN, "Sec-Fetch-Site": "cross-site"})
        problem = _status(forged, FORGED, "POST /form from another site (cookies, no hidden fields)")
        if problem:
            return problem
        if (settings.get("csrf") or {}).get("design") == "token":
            if not fields:
                return "GET /form: phase2.csrf.design is 'token' but the form has no hidden field"
            # The longest hidden value is taken to be the token.
            token = max(range(len(fields)), key=lambda i: len(fields[i][1]))
            tampered = [(key, _tampered(value) if i == token else value) for i, (key, value) in enumerate(fields)]
            problem = _status(post([*tampered, *valid], pair), FORGED,
                              "POST /form with the hidden token changed in one character (no Origin header)") \
                or _status(post([*fields, *valid], {"Content-Type": FORM_TYPE}), FORGED,
                           "POST /form with the hidden fields but without the cookies (no Origin header)")
            if problem:
                return problem
        return None
    finally:
        browser.close()


# ---------------------------------------------------------------- POST /login and GET /me

def _me(port: int, session_headers: dict, what: str) -> tuple[dict | None, Response, str | None]:
    response = send(port, "GET", "/me", {"Accept": JSON_TYPE, **session_headers})
    problem = _ok(response, JSON_TYPE, what)
    if problem:
        return None, response, problem
    body, problem = _json(response, what)
    return body, response, problem


def _session_headers(session) -> dict:
    headers = {}
    if session.cookie:
        headers["Cookie"] = session.cookie
    if session.bearer:
        headers["Authorization"] = f"Bearer {session.bearer}"
    return headers


def _expected_user(ident: int, display: str | None = None) -> dict:
    return {"id": ident, "username": f"user{ident}", "displayName": display or f"User {ident}"}


def check_me(port: int, config: dict, _settings: dict) -> str | None:
    problem = _status(send(port, "GET", "/me", {"Accept": JSON_TYPE}), NO_SESSION, "GET /me without a session")
    if problem:
        return problem
    response, _, session = login(port, "user7", "wrong-password")
    problem = _status(response, WRONG_PASSWORD, "POST /login as user7 with a wrong password")
    if problem:
        return problem
    if send(port, "GET", "/me", {"Accept": JSON_TYPE, **_session_headers(session)}).status == 200:
        return "GET /me answered 200 with the cookies of a login with a wrong password"
    sessions = {}
    for ident in (7, 8):
        response, _, session = login(port, f"user{ident}")
        problem = _status(response, LOGIN_OK, f"POST /login as user{ident}")
        if problem:
            return f"{problem}: {response.body[:200]!r}"
        if not session.cookie and not session.bearer:
            return f"POST /login as user{ident}: no session cookie and no bearer token"
        sessions[ident] = _session_headers(session)
    try:
        for step in range(3):
            display = f"Renamed {step} <&>"
            psql(config, f"UPDATE users SET display_name = '{display}' WHERE id = 7")
            body, _, problem = _me(port, sessions[7], "GET /me as user7")
            if problem:
                return problem
            if body != _expected_user(7, display):
                return f"GET /me as user7: {body!r} != {_expected_user(7, display)!r} (read the row on every request)"
    finally:
        psql(config, "UPDATE users SET display_name = 'User 7' WHERE id = 7")
    for ident in (7, 8):
        body, _, problem = _me(port, sessions[ident], f"GET /me as user{ident}")
        if problem:
            return problem
        if body != _expected_user(ident):
            return f"GET /me as user{ident}: {body!r} != {_expected_user(ident)!r}"
    reset_statements(config)
    for index in range(20):
        response = send(port, "GET", "/me", {"Accept": JSON_TYPE, **sessions[7 + index % 2]})
        if response.status != 200:
            return f"GET /me: status {response.status}"
    stats = statements(config, "users")
    if stats["select_calls"] < 20:
        return f"20 requests ran {stats['select_calls']} SELECT statements on users: read the user on every request"
    return None


CHECKS = (("world", check_world), ("worlds", check_worlds), ("world-update", check_world_update),
          ("form", check_form), ("me", check_me))


def run_checks(port: int, config: dict, endpoints, manifest: dict | None, record) -> None:
    """Run the check of every declared phase-2 endpoint; record(label, problem) each result."""
    settings = phase2(manifest or {})
    for endpoint, check in CHECKS:
        if endpoint not in endpoints:
            continue
        try:
            problem = check(port, config, settings)
        except (OSError, http.client.HTTPException, BenchError) as exc:
            problem = f"{type(exc).__name__}: {exc}"
        record(ENDPOINT_LABELS[endpoint], problem)
