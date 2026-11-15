# As in the FastAPI "FastAPI in Containers - Docker" guide: the official Python
# image, the requirements installed first, then the code.
FROM python:3.14.10-slim-trixie@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --root-user-action=ignore --require-hashes --only-binary=:all: -r requirements.txt
COPY main.py ./
COPY templates ./templates
# Record the resolved versions of the main packages for the results.
RUN mkdir /bench && python -c "import importlib.metadata as m, platform; \
print('python', platform.python_version()); \
[print(n, m.version(n)) for n in ('fastapi', 'starlette', 'pydantic', 'uvicorn', 'uvloop', 'httptools', 'sqlmodel', 'sqlalchemy', 'psycopg', 'psycopg-binary', 'jinja2')]" \
    > /bench/versions.txt && cat /bench/versions.txt
USER nobody
EXPOSE 8080
# Uvicorn with BENCH_WORKERS worker processes, as in the FastAPI "Server
# Workers" guide; uvloop and httptools are picked automatically. The access log
# is off (`fastapi run` has no option for it, so Uvicorn is started directly).
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port \"${PORT:-8080}\" --workers \"${BENCH_WORKERS:-2}\" --no-access-log"]
