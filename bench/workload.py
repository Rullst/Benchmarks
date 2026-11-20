"""What a phase-2 load test sends: one request, or many chosen per request.

A Workload is tool-neutral. bench/loadgen_wrk.py replays any workload (its
Lua script cycles through the prebuilt requests); bench/loadgen_oha.py can
replay one whose requests share the method and headers, choosing the path and
the body independently (oha's --urls-from-file and -Z). The builders below
are the phase-2 endpoints of docs/v3-spec.md.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from urllib.parse import urlencode

MAX_ID = 10000
# Fixed seed: every implementation and every round gets the same request mix.
SEED = 20261119
# What a browser sends with a same-origin form submission (docs/v3-spec.md section 2.4).
ORIGIN = "http://127.0.0.1:8080"


@dataclass(frozen=True)
class Request:
    method: str
    path: str  # path and query string
    headers: tuple[tuple[str, str], ...] = ()
    body: bytes = b""


@dataclass
class Workload:
    """The requests of one load test, chosen uniformly (cycled in a shuffled order).

    `pairing` says how the requests were built: "joint" when a request's
    path, headers and body belong together (a session cookie and its CSRF
    token), "independent" when the paths and the bodies were drawn
    independently, so a tool may also draw them independently.
    """

    requests: list[Request]
    pairing: str = "independent"
    label: str = ""
    notes: dict = field(default_factory=dict)

    @property
    def static(self) -> bool:
        return len(self.requests) == 1

    def methods(self) -> set[str]:
        return {r.method for r in self.requests}

    def header_sets(self) -> set[tuple[tuple[str, str], ...]]:
        return {r.headers for r in self.requests}

    def paths(self) -> list[str]:
        return list(dict.fromkeys(r.path for r in self.requests))

    def bodies(self) -> list[bytes]:
        return list(dict.fromkeys(r.body for r in self.requests))


def static(path: str, method: str = "GET", headers: dict | None = None, body: bytes = b"") -> Workload:
    return Workload([Request(method, path, tuple((headers or {}).items()), body)], label=path)


def _rng(salt: str) -> random.Random:
    return random.Random(f"{SEED}:{salt}")


def world_by_id(count: int = MAX_ID) -> Workload:
    """GET /world/{id}: every id in 1..10000 once, shuffled (uniform ids)."""
    ids = list(range(1, count + 1))
    _rng("world").shuffle(ids)
    return Workload([Request("GET", f"/world/{i}") for i in ids], label="/world/{id}")


def worlds_pages(count: int = 2000) -> Workload:
    """GET /worlds?min=&max=&limit=&page=: random 1,000-id windows, 20 rows, pages 1-5."""
    rng = _rng("worlds")
    requests = []
    for _ in range(count):
        low = rng.randint(1, MAX_ID - 999)
        query = urlencode({"min": low, "max": low + 999, "limit": 20, "page": rng.randint(1, 5)})
        requests.append(Request("GET", f"/worlds?{query}"))
    return Workload(requests, label="/worlds")


def _put_headers(write_csrf: tuple[str, str, str] | None) -> tuple[tuple[str, str], ...]:
    headers: tuple[tuple[str, str], ...] = (("Content-Type", "application/json"),)
    if write_csrf:
        cookie, header, token = write_csrf
        headers += (("Cookie", f"{cookie}={token}"), (header, token))
    return headers


def _put_body(rng: random.Random) -> bytes:
    return json.dumps({"randomNumber": rng.randint(1, MAX_ID)}, separators=(",", ":")).encode()


def put_world(count: int = MAX_ID, write_csrf: tuple[str, str, str] | None = None) -> Workload:
    """PUT /world/{id} with {"randomNumber": n}: random id and value, drawn independently.

    write_csrf is (cookie name, header name, token) for implementations whose
    bench.json declares phase2.write_csrf: the cookie and the header carry
    the same token, as a same-site script sends them.
    """
    rng = _rng("put")
    ids = list(range(1, count + 1))
    rng.shuffle(ids)
    headers = _put_headers(write_csrf)
    requests = [Request("PUT", f"/world/{i}", headers, _put_body(rng)) for i in ids]
    return Workload(requests, label="PUT /world/{id}")


def hot_rows(ids: int = 10, count: int = 2000, write_csrf: tuple[str, str, str] | None = None) -> Workload:
    """PUT /world/{id} on a few rows (ids 1..`ids`): every connection writes the same rows, so
    requests wait for each other's row locks (write contention)."""
    rng = _rng("hot")
    headers = _put_headers(write_csrf)
    requests = [Request("PUT", f"/world/{rng.randint(1, ids)}", headers, _put_body(rng)) for _ in range(count)]
    return Workload(requests, label=f"PUT /world/{{1..{ids}}}", notes={"ids": ids})


@dataclass(frozen=True)
class Session:
    """What the harness obtained once before measuring (docs/v3-spec.md, CSRF and sessions)."""

    cookie: str  # the Cookie header value to send
    fields: tuple[tuple[str, str], ...] = ()  # the hidden fields of the session's form page
    csrf_field: str = ""  # form field name for the token ("" when the token goes in a header)
    csrf_token: str = ""
    csrf_header: str = ""  # header name, for implementations that take the token in a header
    bearer: str = ""  # Authorization: Bearer token, for login responses that return one


def _session_headers(session: Session) -> list[tuple[str, str]]:
    headers = []
    if session.cookie:
        headers.append(("Cookie", session.cookie))
    if session.bearer:
        headers.append(("Authorization", f"Bearer {session.bearer}"))
    return headers


def form_posts(sessions: list[Session], count: int = 2000, origin: str = ORIGIN) -> Workload:
    """POST /form (urlencoded) as a browser submits it: each session's cookies and hidden fields
    (its CSRF token), `Origin` and `Sec-Fetch-Site: same-origin`; joint pairing."""
    rng = _rng("form")
    requests = []
    for index in range(count):
        session = sessions[index % len(sessions)]
        fields = dict(session.fields)
        fields.update({"name": f"user{rng.randint(1, 99999)}", "randomNumber": rng.randint(1, MAX_ID)})
        headers = [("Content-Type", "application/x-www-form-urlencoded"), ("Origin", origin),
                   ("Sec-Fetch-Site", "same-origin"), *_session_headers(session)]
        if session.csrf_field:
            fields[session.csrf_field] = session.csrf_token
        if session.csrf_header:
            headers.append((session.csrf_header, session.csrf_token))
        requests.append(Request("POST", "/form", tuple(headers), urlencode(fields).encode()))
    pairing = "joint" if len(sessions) > 1 else "independent"
    return Workload(requests, pairing=pairing, label="POST /form", notes={"sessions": len(sessions)})


def me(sessions: list[Session]) -> Workload:
    """GET /me with each signed-in session in turn: joint pairing when there are several."""
    requests = [Request("GET", "/me", (("Accept", "application/json"), *_session_headers(s))) for s in sessions]
    pairing = "joint" if len(sessions) > 1 else "independent"
    return Workload(requests, pairing=pairing, label="GET /me", notes={"sessions": len(sessions)})


def query_variants(path: str, count: int = MAX_ID) -> Workload:
    """`path?id=N` for N in 1..count, shuffled: the load generator's cost of varying the URL."""
    ids = list(range(1, count + 1))
    _rng("variants").shuffle(ids)
    return Workload([Request("GET", f"{path}?id={i}") for i in ids], label=f"{path}?id=N")
