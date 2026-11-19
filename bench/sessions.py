"""Browser sessions for the phase-2 endpoints: form pages, CSRF pairs and logins.

The harness acts as a browser that loaded a page once (docs/v3-spec.md
sections 4-6): it keeps the cookies the responses set (their attributes,
`Secure` included, are ignored: the harness talks plain HTTP to 127.0.0.1),
submits the hidden fields of the page's form, and sends `Origin` and
`Sec-Fetch-Site: same-origin` with every form post. Conformance and the load
bootstrap (measure.py, before the application endpoints' warm-up) use the same code.
"""

from __future__ import annotations

import email.utils
import http.client
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

from common import BenchError
from workload import ORIGIN, Session

PASSWORD = "bench-password"
# POST /login answers for correct credentials (section 6.1).
LOGIN_OK = (200, 204, 302, 303)
FORM_TYPE = "application/x-www-form-urlencoded"


@dataclass
class Response:
    status: int
    content_type: str | None
    body: bytes
    set_cookies: list[str] = field(default_factory=list)
    will_close: bool = False

    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


def send(port: int, method: str, path: str, headers: dict | None = None, body: bytes | None = None,
         conn: http.client.HTTPConnection | None = None) -> Response:
    """One request; on a connection of its own unless one is given."""
    own = conn is None
    conn = conn or http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        return Response(response.status, response.getheader("Content-Type"), data,
                        response.msg.get_all("Set-Cookie") or [], response.will_close)
    finally:
        if own:
            conn.close()


def _expired(attributes: list[str]) -> bool:
    for attribute in attributes:
        key, _, value = attribute.strip().partition("=")
        key = key.strip().lower()
        if key == "max-age":
            try:
                return int(value.strip()) <= 0
            except ValueError:
                continue
        if key == "expires":
            try:
                return email.utils.parsedate_to_datetime(value.strip()).timestamp() < time.time()
            except (TypeError, ValueError):
                continue
    return False


class Browser:
    """A cookie jar and one keep-alive connection to the server under test.

    The connection is replaced after a response that closes it and after an
    error response (4xx, 5xx).
    """

    def __init__(self, port: int, cookies: dict[str, str] | None = None):
        self.port = port
        self.cookies: dict[str, str] = dict(cookies or {})
        self._conn: http.client.HTTPConnection | None = None

    def cookie_header(self) -> str:
        return "; ".join(f"{name}={value}" for name, value in self.cookies.items())

    def store(self, set_cookies: list[str]) -> list[str]:
        """Apply Set-Cookie headers to the jar; returns the names of the cookies set."""
        names = []
        for header in set_cookies:
            pair, *attributes = header.split(";")
            name, sep, value = pair.partition("=")
            name = name.strip()
            if not sep or not name:
                continue
            if _expired(attributes):
                self.cookies.pop(name, None)
            else:
                self.cookies[name] = value.strip()
                names.append(name)
        return names

    def request(self, method: str, path: str, *, headers: dict | None = None, body: bytes | None = None,
                cookies: bool = True) -> Response:
        """A request with the jar's cookies (unless cookies=False); the response's cookies go into the jar."""
        all_headers = dict(headers or {})
        if cookies and self.cookies:
            all_headers["Cookie"] = self.cookie_header()
        if self._conn is None:
            self._conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        try:
            response = send(self.port, method, path, all_headers, body, conn=self._conn)
        except (OSError, http.client.HTTPException):
            self.close()
            raise
        if response.will_close or response.status >= 400:
            # A server may close the connection after an error response without
            # saying so (no `Connection: close`): the next request reconnects.
            self.close()
        self.store(response.set_cookies)
        return response

    def get(self, path: str, headers: dict | None = None) -> Response:
        return self.request("GET", path, headers={"Accept": "*/*", **(headers or {})})

    def post_form(self, path: str, fields: list[tuple[str, str]], *, same_origin: bool = True,
                  origin: str = ORIGIN, site: str = "same-origin") -> Response:
        """A urlencoded form post, with the headers a browser adds when same_origin is set."""
        headers = {"Content-Type": FORM_TYPE}
        if same_origin:
            headers.update({"Origin": origin, "Sec-Fetch-Site": site})
        return self.request("POST", path, headers=headers, body=urlencode(fields).encode())

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class _Forms(HTMLParser):
    """The forms of a page: action, method and inputs (type, name, value), in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[dict] = []
        self._open = False

    def handle_starttag(self, tag: str, attrs) -> None:
        values = {k.lower(): (v or "") for k, v in attrs}
        if tag == "form":
            self.forms.append({"action": values.get("action", ""), "method": values.get("method", "get").lower(),
                               "inputs": []})
            self._open = True
        elif tag == "input" and self._open and values.get("name"):
            self.forms[-1]["inputs"].append((values.get("type", "text").lower(), values["name"],
                                             values.get("value", "")))

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag == "form":
            self._open = False

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._open = False


def find_form(html: str, action: str) -> dict | None:
    """The first form that posts to `action` (an empty action posts to the page itself)."""
    parser = _Forms()
    parser.feed(html)
    parser.close()
    for form in parser.forms:
        target = urlsplit(form["action"].strip()).path
        if target in ("", action, action + "/"):
            return form
    return None


def hidden_fields(form: dict) -> list[tuple[str, str]]:
    return [(name, value) for kind, name, value in form["inputs"] if kind == "hidden"]


def load_form(browser: Browser, page: str) -> tuple[Response, list[tuple[str, str]]]:
    """GET a form page; returns the response and the hidden fields of its form (BenchError if none)."""
    response = browser.get(page)
    if response.status != 200:
        raise BenchError(f"GET {page}: status {response.status}")
    form = find_form(response.text(), page)
    if form is None:
        raise BenchError(f"GET {page}: no <form> whose action is {page} (or empty)")
    return response, hidden_fields(form)


def form_session(port: int) -> Session:
    """One browser that loaded GET /form: its cookies and the form's hidden fields."""
    browser = Browser(port)
    try:
        _, fields = load_form(browser, "/form")
    finally:
        browser.close()
    return Session(cookie=browser.cookie_header(), fields=tuple(fields))


def login(port: int, username: str, password: str = PASSWORD) -> tuple[Response, Browser, Session]:
    """GET /login, then POST /login with its hidden fields and cookies, like a browser.

    The Session carries every cookie the browser holds afterwards, or a
    bearer token when the login answered JSON with a `token` and set no
    cookie (section 6.3).
    """
    browser = Browser(port)
    try:
        _, fields = load_form(browser, "/login")
        response = browser.post_form("/login", [*fields, ("username", username), ("password", password)])
    finally:
        browser.close()
    bearer = ""
    if not response.set_cookies and (response.content_type or "").lower().startswith("application/json"):
        try:
            token = json.loads(response.body).get("token")
        except (ValueError, AttributeError):
            token = None
        bearer = token if isinstance(token, str) else ""
    return response, browser, Session(cookie=browser.cookie_header(), bearer=bearer)


def login_session(port: int, username: str, password: str = PASSWORD) -> Session:
    response, _, session = login(port, username, password)
    if response.status not in LOGIN_OK:
        raise BenchError(f"POST /login as {username}: status {response.status} (expected one of "
                         f"{', '.join(map(str, LOGIN_OK))}): {response.body[:200]!r}")
    if not session.cookie and not session.bearer:
        raise BenchError(f"POST /login as {username}: no session cookie and no bearer token")
    return session


def cookie_value(port: int, name: str) -> str:
    """The value of a cookie that GET /form sets (phase2.write_csrf)."""
    browser = Browser(port)
    try:
        load_form(browser, "/form")
    finally:
        browser.close()
    if name not in browser.cookies:
        raise BenchError(f"GET /form did not set the '{name}' cookie that phase2.write_csrf names")
    return browser.cookies[name]


def fetch(count: int, make, parallel: int) -> list[Session]:
    """`count` sessions, `parallel` at a time; make(index) builds one (index from 1)."""
    try:
        with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
            return list(pool.map(make, range(1, count + 1)))
    except (OSError, http.client.HTTPException) as exc:
        raise BenchError(f"could not obtain the sessions: {type(exc).__name__}: {exc}") from exc


def form_sessions(port: int, count: int, parallel: int = 8) -> list[Session]:
    return fetch(count, lambda _: form_session(port), parallel)


def login_sessions(port: int, count: int, parallel: int = 8) -> list[Session]:
    """Signed-in sessions of user1..user<count> (phase2.sql's accounts)."""
    return fetch(count, lambda index: login_session(port, f"user{index}"), parallel)
