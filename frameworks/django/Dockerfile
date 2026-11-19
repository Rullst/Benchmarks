# Django has no generated Dockerfile; this one follows the deployment
# checklist and "How to use Django with Gunicorn" (see README.md).

# Resolves requirements.txt for the pull request check, which exports the
# `lockfile` stage (see CONTRIBUTING.md), with the command at the top of
# requirements.txt. The image below does not use it.
FROM python:3.15.2-slim-trixie AS resolve
RUN pip install --no-cache-dir --root-user-action=ignore uv==0.13.9
WORKDIR /app
COPY requirements.in ./
RUN uv pip compile requirements.in --python-version 3.15 \
      --python-platform x86_64-manylinux_2_28 --generate-hashes --emit-index-url \
      -o requirements.txt

FROM scratch AS lockfile
COPY --from=resolve /app/requirements.txt /

FROM python:3.15.2-slim-trixie AS build
# psycopg's C extension is compiled against the system libpq.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
# Record the resolved versions for the results.
RUN mkdir /out \
    && python -c 'import platform; from importlib.metadata import version; print("python", platform.python_version()); [print(n, version(n)) for n in ("django", "gunicorn", "psycopg", "psycopg-c")]' \
       > /out/versions.txt \
    && cat /out/versions.txt

FROM python:3.15.2-slim-trixie
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --system --create-home --uid 1000 django
COPY --from=build /opt/venv /opt/venv
COPY --from=build /out/versions.txt /bench/versions.txt
WORKDIR /app
COPY manage.py gunicorn.conf.py ./
COPY benchsite ./benchsite
COPY world ./world
# Compile the bytecode now: the non-root user cannot write __pycache__ here.
RUN python -m compileall -q /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=benchsite.settings
# A fixed dummy key, the same in every Gunicorn worker: it signs the session
# and CSRF values of the benchmark's accounts, which protect nothing.
ENV SECRET_KEY="benchmark-dummy-secret-key-it-protects-nothing-0123456789abcdef"
USER django
EXPOSE 8080
# Gunicorn reads ./gunicorn.conf.py.
CMD ["gunicorn"]
