"""FastAPI: the suite's four endpoints with SQLModel and Jinja2Templates.

The database code follows the FastAPI tutorial "SQL (Relational) Databases":
one SQLModel engine, a session per request from a dependency, and a plain
`def` path operation (FastAPI runs it in its thread pool).
"""

import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, select


class World(SQLModel, table=True):
    id: int = Field(primary_key=True)
    randomnumber: int


class Message(BaseModel):
    message: str


class WorldOut(BaseModel):
    id: int
    randomNumber: int


def database_url() -> str:
    # The harness passes postgres://...; SQLAlchemy names the driver in the scheme.
    _, rest = os.environ["DATABASE_URL"].split("://", 1)
    return f"postgresql+psycopg://{rest}"


# Uvicorn starts BENCH_WORKERS processes and each one imports this module, so
# each has its own engine: the DB_POOL_SIZE connections are divided between them.
POOL_SIZE = max(1, int(os.environ.get("DB_POOL_SIZE", "16")) // int(os.environ.get("BENCH_WORKERS", "2")))
engine = create_engine(database_url(), pool_size=POOL_SIZE, max_overflow=0)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/text", response_class=PlainTextResponse)
async def text():
    return "Hello World"


@app.get("/json")
async def json() -> Message:
    return Message(message="Hello World")


@app.get("/db-single")
def db_single(session: SessionDep) -> WorldOut:
    world = session.exec(select(World).where(World.id == 1)).one()
    return WorldOut(id=world.id, randomNumber=world.randomnumber)


@app.get("/html", response_class=HTMLResponse)
async def html(request: Request):
    return templates.TemplateResponse(request=request, name="hello.html", context={"name": "World"})
