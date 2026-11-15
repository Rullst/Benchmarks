# FastAPI

| | |
| --- | --- |
| Version | fastapi 0.163.0, Starlette 1.10, Pydantic 2.14 (exact versions and hashes in `requirements.txt`, compiled from `requirements.in`) |
| Build | `pip install --require-hashes --only-binary=:all:` on `python:3.14.10-slim-trixie` (CPython 3.14.10) |
| Server | Uvicorn 0.54 with `--workers $BENCH_WORKERS` (2 processes) and `--no-access-log`; Uvicorn picks uvloop and httptools, installed by `uvicorn[standard]` |
| Database | SQLModel 0.0.50 (SQLAlchemy 2.1) with psycopg 3.3, sync engine and one `Session` per request, opened in the `def` path operation (`with Session(engine)`), `select(World).where(World.id == 1)`; each process has a pool of `DB_POOL_SIZE / BENCH_WORKERS` connections (8, no overflow) |
| Templates | Jinja2 3.1 through `Jinja2Templates` (`templates/hello.html`) |
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

Python 3.14 is used rather than 3.15 because it is the newest release that
Uvicorn lists as supported, and every dependency publishes 3.14 wheels.
