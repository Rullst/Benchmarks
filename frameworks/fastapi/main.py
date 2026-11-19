"""FastAPI: the suite's endpoints with SQLModel and Jinja2Templates.

The database code follows the FastAPI tutorial "SQL (Relational) Databases":
one SQLModel engine, a session per request, and plain `def` path operations
(FastAPI runs them in its thread pool).

The browser-facing phase-2 routes (/form, /login, /me) are a sub-application
mounted at "/" (FastAPI's "Sub Applications - Mounts"), so its middleware,
Starlette's SessionMiddleware and asgi-csrf, runs only for them: the main
application's routes are matched first and keep their stack.
"""

import os
import random
from pathlib import Path
from typing import Annotated

import pydantic
from asgi_csrf import asgi_csrf
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pwdlib import PasswordHash
from pydantic import BaseModel, StrictInt, model_validator
from sqlmodel import Field, Session, SQLModel, create_engine, select
from starlette.middleware.sessions import SessionMiddleware


class World(SQLModel, table=True):
    id: int = Field(primary_key=True)
    randomnumber: int


class Fortune(SQLModel, table=True):
    id: int = Field(primary_key=True)
    message: str


class User(SQLModel, table=True):
    """The shared users table (bench/db/phase2.sql); only the columns used."""

    __tablename__ = "users"
    id: int = Field(primary_key=True)
    username: str
    display_name: str
    password_argon2id: str


class Message(BaseModel):
    message: str


class WorldOut(BaseModel):
    id: int
    randomNumber: int


class UserOut(BaseModel):
    id: int
    username: str
    displayName: str


class WorldsQuery(BaseModel):
    """The query string of GET /worlds (a query parameter model); unknown parameters are ignored."""

    min: int = pydantic.Field(1, ge=1, le=10000)
    max: int = pydantic.Field(10000, ge=1, le=10000)
    limit: int = pydantic.Field(20, ge=1, le=100)
    page: int = pydantic.Field(1, ge=1, le=1000)

    @model_validator(mode="after")
    def min_not_above_max(self):
        if self.min > self.max:
            raise ValueError("min must not be greater than max")
        return self


class WorldUpdate(BaseModel):
    """The JSON body of PUT /world/{id}; StrictInt refuses a JSON string such as "5"."""

    randomNumber: Annotated[StrictInt, pydantic.Field(ge=1, le=10000)]


class GreetingForm(BaseModel):
    """The fields of POST /form (a form model; the csrftoken field is ignored)."""

    name: str = pydantic.Field(min_length=1, max_length=64)
    randomNumber: int = pydantic.Field(ge=1, le=10000)


class LoginForm(BaseModel):
    username: str
    password: str


def database_url() -> str:
    # The harness passes postgres://...; SQLAlchemy names the driver in the scheme.
    _, rest = os.environ["DATABASE_URL"].split("://", 1)
    return f"postgresql+psycopg://{rest}"


# Uvicorn starts BENCH_WORKERS processes and each one imports this module, so
# each has its own engine: the DB_POOL_SIZE connections are divided between them.
POOL_SIZE = max(1, int(os.environ.get("DB_POOL_SIZE", "16")) // int(os.environ.get("BENCH_WORKERS", "2")))
engine = create_engine(database_url(), pool_size=POOL_SIZE, max_overflow=0)

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
# The hasher of FastAPI's security tutorial (Argon2); it verifies the PHC
# strings of users.password_argon2id whatever their parameters.
password_hash = PasswordHash.recommended()


@app.get("/text", response_class=PlainTextResponse)
async def text():
    return "Hello World"


@app.get("/json")
async def json() -> Message:
    return Message(message="Hello World")


@app.get("/db-single")
def db_single() -> WorldOut:
    # The session is opened and closed in the path operation's own thread. With
    # the tutorial's `yield` dependency, the session's cleanup needs another
    # thread-pool slot; under more concurrent requests than pool connections,
    # every slot is taken by requests waiting for a connection and the cleanup
    # that would return one never runs (all requests time out).
    with Session(engine) as session:
        world = session.exec(select(World).where(World.id == 1)).one()
    return WorldOut(id=world.id, randomNumber=world.randomnumber)


@app.get("/html", response_class=HTMLResponse)
async def html(request: Request):
    return templates.TemplateResponse(request=request, name="hello.html", context={"name": "World"})


# ---------------------------------------------------------------- phase 1

def query_count(value: str) -> int:
    """TechEmpower's rule: an integer clamped to 1..500, anything else is 1."""
    try:
        return min(max(int(value), 1), 500)
    except ValueError:
        return 1


def random_id() -> int:
    return random.randint(1, 10000)


@app.get("/queries")
def queries(queries: str = "") -> list[WorldOut]:
    # A SELECT statement per row (Session.get would return a repeated id from
    # the session's identity map without a query).
    with Session(engine) as session:
        worlds = [session.exec(select(World).where(World.id == random_id())).one()
                  for _ in range(query_count(queries))]
        return [WorldOut(id=world.id, randomNumber=world.randomnumber) for world in worlds]


@app.get("/updates")
def updates(queries: str = "") -> list[WorldOut]:
    # Each row read with its own SELECT and given a new value; the session's
    # autoflush writes a changed row before the next SELECT and the commit
    # writes the last one, all in the session's one transaction. The ids are
    # sorted so that concurrent requests lock rows in the same order.
    rows = []
    with Session(engine) as session:
        for ident in sorted(random_id() for _ in range(query_count(queries))):
            world = session.exec(select(World).where(World.id == ident)).one()
            value = random_id()
            while value == world.randomnumber:
                value = random_id()
            world.randomnumber = value
            session.add(world)
            rows.append(WorldOut(id=world.id, randomNumber=value))
        session.commit()
    return rows


@app.get("/fortunes", response_class=HTMLResponse)
def fortunes(request: Request):
    with Session(engine) as session:
        rows = [(fortune.id, fortune.message) for fortune in session.exec(select(Fortune)).all()]
    rows.append((0, "Additional fortune added at request time."))
    rows.sort(key=lambda row: row[1])
    return templates.TemplateResponse(request=request, name="fortunes.html", context={"fortunes": rows})


# ---------------------------------------------------------------- phase 2: reads and writes

@app.get("/world/{id}")
def get_world(id: int) -> WorldOut:
    with Session(engine) as session:
        world = session.get(World, id)
    if world is None:
        raise HTTPException(status_code=404)
    return WorldOut(id=world.id, randomNumber=world.randomnumber)


@app.get("/worlds")
def get_worlds(query: Annotated[WorldsQuery, Query()]) -> list[WorldOut]:
    # One query: the filter, ORDER BY, LIMIT and OFFSET run in PostgreSQL.
    statement = (select(World).where(World.id >= query.min, World.id <= query.max).order_by(World.id)
                 .offset((query.page - 1) * query.limit).limit(query.limit))
    with Session(engine) as session:
        return [WorldOut(id=world.id, randomNumber=world.randomnumber) for world in session.exec(statement)]


@app.put("/world/{id}")
def put_world(id: int, body: WorldUpdate) -> WorldOut:
    # FastAPI validates the id and the body before calling this function, so a
    # refused request writes nothing. Then the tutorial's update: get, set,
    # add, commit. The response is the value written (no refresh query).
    with Session(engine) as session:
        world = session.get(World, id)
        if world is None:
            raise HTTPException(status_code=404)
        world.randomnumber = body.randomNumber
        session.add(world)
        result = WorldOut(id=world.id, randomNumber=world.randomnumber)
        session.commit()
    return result


# ---------------------------------------------------------------- phase 2: the browser-facing routes

browser = FastAPI()


@browser.get("/form", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse(request=request, name="form.html",
                                      context={"csrftoken": request.scope["csrftoken"]()})


@browser.post("/form", response_class=HTMLResponse)
async def form_submit(request: Request, form: Annotated[GreetingForm, Form()]):
    return templates.TemplateResponse(request=request, name="form_result.html",
                                      context={"name": form.name, "randomNumber": form.randomNumber})


@browser.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html",
                                      context={"csrftoken": request.scope["csrftoken"]()})


@browser.post("/login")
def login(request: Request, form: Annotated[LoginForm, Form()]):
    with Session(engine) as db:
        user = db.exec(select(User).where(User.username == form.username)).first()
    if user is None or not password_hash.verify(form.password, user.password_argon2id):
        return RedirectResponse("/login", status_code=303)
    request.session["user_id"] = user.id
    return RedirectResponse("/me", status_code=303)


@browser.get("/me")
def me(request: Request) -> UserOut:
    # The signed session cookie holds the user id; the user's row is read on
    # every request.
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401)
    with Session(engine) as db:
        user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401)
    return UserOut(id=user.id, username=user.username, displayName=user.display_name)


# Starlette's signed-cookie sessions and asgi-csrf's signed double-submit
# cookie. The keys come from the environment, so every Uvicorn worker accepts
# the cookies of the others. always_protect makes asgi-csrf check the two
# forms' posts even when they carry no cookie at all.
browser.add_middleware(SessionMiddleware, secret_key=os.environ["SESSION_SECRET_KEY"])
app.mount("/", asgi_csrf(browser, signing_secret=os.environ["ASGI_CSRF_SECRET"],
                         always_protect={"/form", "/login"}))
