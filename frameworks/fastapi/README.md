# FastAPI

| | |
| --- | --- |
| Version | fastapi 0.163.0, Starlette 1.10, Pydantic 2.14 (exact versions and hashes in `requirements.txt`, compiled from `requirements.in`) |
| Build | `pip install --require-hashes --only-binary=:all:` on `python:3.14.10-slim-trixie` (CPython 3.14.10) |
| Server | Uvicorn 0.54 with `--workers $BENCH_WORKERS` (2 processes) and `--no-access-log`; Uvicorn picks uvloop and httptools, installed by `uvicorn[standard]` |
| Database | SQLModel 0.0.50 (SQLAlchemy 2.1) with psycopg 3.3, sync engine and one `Session` per request, opened in the `def` path operation (`with Session(engine)`), `select(World).where(World.id == 1)`; each process has a pool of `DB_POOL_SIZE / BENCH_WORKERS` connections (8, no overflow) |
| Database endpoints | `/queries`: one `select(World).where(World.id == …)` per row (`Session.get` would answer a repeated id from the session's identity map without a query). `/updates`: per row, that `SELECT`, a new random value (drawn again while it equals the current one) set on the object; the session's autoflush writes each changed row before the next `SELECT` and `commit()` writes the last one, all in the session's one transaction, with the ids sorted so concurrent requests lock rows in the same order. `/fortunes`: `select(Fortune)` (no `ORDER BY`), sorted in Python (code points), rendered by Jinja2 (autoescape on in `Jinja2Templates`) |
| Request input (phase 2) | `GET /world/{id}`: `id: int` (a non-integer is 422), `Session.get`, 404 without a row. `GET /worlds`: a query parameter model (`Annotated[WorldsQuery, Query()]`, Pydantic `Field(ge, le)` with the defaults, `min <= max` in a model validator; unknown parameters ignored): 422 when invalid; one `select(World).where(...).order_by(World.id).offset().limit()`. `PUT /world/{id}`: a Pydantic body model with `StrictInt` (the string `"5"` is refused; malformed JSON is 422), validated by FastAPI before the function runs, then the tutorial's update: `get`, set, `add`, `commit` (the response is the value written, without the tutorial's `refresh` query). `POST /form`: a form model (`Annotated[GreetingForm, Form()]`, `python-multipart`): 422 |
| CSRF | [asgi-csrf](https://github.com/simonw/asgi-csrf) 0.11 (FastAPI has none; the library is listed in Starlette's middleware documentation): `GET /form` and `GET /login` put the token, an itsdangerous-signed value that is also set as the `csrftoken` cookie, in a hidden `csrftoken` field; a urlencoded post must carry the cookie's value in that field (signed double-submit cookie), else 403. `always_protect={"/form", "/login"}` makes it check those posts also when they carry no cookie (the library skips cookieless posts otherwise). The cookie, and so the token, does not change during the session |
| Sessions | Starlette's `SessionMiddleware` (FastAPI has no session store; Starlette's is cookie-only): `POST /login` checks `users.password_argon2id` with pwdlib's Argon2 hasher (`PasswordHash.recommended()`, as in FastAPI's security tutorial), stores the user id in the session and redirects to `/me` (303); `GET /me` reads the id from the signed `session` cookie (re-signed on every response, Starlette's behaviour) and the user's row with `Session.get`; without a session it answers 401. A wrong password redirects back to `/login` and leaves the session empty |
| Middleware scope | `/form`, `/login` and `/me` are a second FastAPI application mounted at `/` ([Sub Applications - Mounts](https://fastapi.tiangolo.com/advanced/sub-applications/)) with `SessionMiddleware` and asgi-csrf around it. The main application's routes are matched first, so the existing endpoints (and phase 1's, `/world/{id}`, `/worlds` and `PUT /world/{id}`) do not go through either: asgi-csrf would otherwise sign a new token for every cookieless request |
| Templates | Jinja2 3.1 through `Jinja2Templates` (`templates/`) |
| Logging | none: Uvicorn's access log is off; startup messages only |
| Image | `python:3.14.10-slim-trixie` |

Why: this follows the FastAPI documentation.

- Workers: [Server Workers](https://fastapi.tiangolo.com/deployment/server-workers/)
  runs `fastapi run --workers 4` or the equivalent
  `uvicorn main:app --workers 4`. `fastapi run` has no option to turn the
  access log off, so the image starts Uvicorn directly with
  [`--no-access-log`](https://uvicorn.dev/settings/) and one worker per vCPU.
  The image layout follows [FastAPI in Containers](https://fastapi.tiangolo.com/deployment/docker/).
- Database: the [SQL (Relational) Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/)
  tutorial uses SQLModel with a sync engine, a session dependency and `def`
  path operations, which FastAPI runs in its thread pool. The official
  [full-stack template](https://github.com/fastapi/full-stack-fastapi-template)
  uses the same setup with psycopg 3 on PostgreSQL. The session is opened
  with `with Session(engine)` inside the path operation, as in the SQLModel
  tutorial, instead of the tutorial's `yield` dependency: FastAPI runs that
  dependency's cleanup in the thread pool too, and with more concurrent
  requests than pool connections every pool thread waits for a connection
  that only a pending cleanup would return, so the server stops answering
  `/db-single` (the 2026-11-15 run timed out on every request). SQLAlchemy's defaults are
  kept (a transaction per session, rolled back when the session closes); only
  the pool size is set, so the 16 connections are split between the two
  processes.
- Responses: `/json` and `/db-single` declare a Pydantic return type, as in
  [Response Model - Return Type](https://fastapi.tiangolo.com/tutorial/response-model/),
  so Pydantic serializes them. `/text` uses `PlainTextResponse` and `/html`
  `Jinja2Templates`, as in [Custom Response](https://fastapi.tiangolo.com/advanced/custom-response/)
  and [Templates](https://fastapi.tiangolo.com/advanced/templates/).

The signing keys of the session and the CSRF token (`SESSION_SECRET_KEY`,
`ASGI_CSRF_SECRET`) are fixed dummy values in the Dockerfile, so every
Uvicorn worker process accepts the cookies the others set. Nothing throttles
logins. `requirements.txt` comes from the Dockerfile's `lockfile` stage
(`uv pip compile`, the command at the top of `requirements.in`).

Python 3.14 is used rather than 3.15 because it is the newest release that
Uvicorn lists as supported, and every dependency publishes 3.14 wheels.

## Production settings

| Setting | Value | Source |
| --- | --- | --- |
| Server | Uvicorn with `--workers $BENCH_WORKERS` (2 processes), uvloop and httptools chosen by `--loop auto` / `--http auto` (`uvicorn[standard]`) | [Server Workers](https://fastapi.tiangolo.com/deployment/server-workers/), [Uvicorn settings](https://uvicorn.dev/settings/) |
| Logging | `--no-access-log`; Uvicorn's `--log-level` stays `info`, which prints only start-up messages once the access log is off | [Uvicorn settings](https://uvicorn.dev/settings/) |
| Threads | FastAPI runs the `def` path operations "in an external threadpool" (AnyIO's default size); the `async def` ones (`/text`, `/json`, `/html`, the form pages) on the event loop | [Concurrency and async / await](https://fastapi.tiangolo.com/async/) |
| Pool | SQLAlchemy's `QueuePool` per process, `pool_size` = `DB_POOL_SIZE / BENCH_WORKERS` (8), `max_overflow=0`: 16 in total, all usable; no `pool_pre_ping` (SQLAlchemy's default; the full-stack template sets it, the SQL tutorial does not) | [SQL (Relational) Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/), [SQLAlchemy pooling](https://docs.sqlalchemy.org/en/21/core/pooling.html) |
| Prepared statements | psycopg 3's default: a statement is prepared on a connection after it has run `prepare_threshold` (5) times there | [psycopg: Prepared statements](https://www.psycopg.org/psycopg3/docs/advanced/prepare.html) |
| Driver | `psycopg[binary]`, as FastAPI's [full-stack template](https://github.com/fastapi/full-stack-fastapi-template/blob/master/backend/pyproject.toml) installs it; psycopg calls the binary package "recommended for most users" and the local `psycopg[c]` build (Django's folder) "the preferred way ... for a production site". Not changed: it would need a new lockfile and a compiler in the image | [psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html) |
| Python | **3.14.10** (Django's folder uses 3.15.2): FastAPI's container guide and full-stack template use `python:3.14`, and Uvicorn 0.54 lists Python up to 3.14 | [FastAPI in Containers](https://fastapi.tiangolo.com/deployment/docker/), [uvicorn on PyPI](https://pypi.org/project/uvicorn/0.54.0/) |
| JIT | none: the official `python` image is built without CPython's experimental JIT (PGO and LTO only) | [python image Dockerfile](https://github.com/docker-library/python/blob/master/3.14/slim-trixie/Dockerfile) |
| Structure | Uvicorn alone (a supervisor process and 2 workers) in the 2 vCPUs; FastAPI's container guide puts the TLS termination proxy outside the container | [FastAPI in Containers](https://fastapi.tiangolo.com/deployment/docker/) |
