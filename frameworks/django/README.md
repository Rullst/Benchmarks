# Django

A `django-admin startproject` project with one app (`world`), set up for
production with Django's
[deployment checklist](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/)
and served by Gunicorn as in
[How to use Django with Gunicorn](https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/gunicorn/).

| | |
| --- | --- |
| Version | Django 6.1.3, Gunicorn 27.0.1, psycopg 3.3.9, bcrypt 5.0.0 on Python 3.15.2 (exact versions and hashes in `requirements.txt`) |
| Build | `pip install --require-hashes -r requirements.txt` into a virtual environment; psycopg's C extension is built against Debian's libpq |
| Server | Gunicorn with the threaded worker (`gthread`), configured in `gunicorn.conf.py` |
| Workers | `BENCH_WORKERS` (2) worker processes, 8 threads each |
| Database | Django ORM, `World.objects.get(pk=1)` on an unmanaged model of the `world` table; persistent connections (`CONN_MAX_AGE = 600`): each thread keeps one, so at most 2 x 8 = 16 |
| Database endpoints | `/queries`: `World.objects.get(pk=…)` per row. `/updates`: per row, `get`, a new random value (drawn again while it equals the current one) and `save(update_fields=['randomnumber'])`, all in one `transaction.atomic()` with the ids sorted, so concurrent requests lock rows in the same order. `/fortunes`: `Fortune.objects.all()` (no `ORDER BY`), sorted in Python (code points), rendered by a Django template (autoescaped) |
| Request input (phase 2) | `path('world/<int:id>')`: the `int` converter matches digits only, so a non-integer id is 404. Django forms validate `GET /worlds` (`WorldsForm(request.GET)`, `IntegerField` with `min_value`/`max_value`, defaults for absent parameters, `min <= max` in `clean()`), the PUT body (`WorldUpdateForm(json.loads(request.body))`, plus a check that the value is a JSON integer, since `IntegerField` accepts the string `"5"`) and `POST /form` (`GreetingForm(request.POST)`): 422 with the errors (the form page is rendered again for `/form`). Malformed JSON is 400 (`json.loads` in a `try`; Django has no JSON body parser). `GET /worlds` is one query (`filter(id__gte, id__lte).order_by('id')[offset:offset + limit]`). `PUT /world/{id}` validates first, then loads the row (404 without one) and `save(update_fields=…)`s it |
| CSRF | `CsrfViewMiddleware` (in the generated `MIDDLEWARE`): `{% csrf_token %}` sets the secret in the `csrftoken` cookie and puts a masked copy in the `csrfmiddlewaretoken` field; a post's field must unmask to the cookie's secret, and its `Origin`, when present, must match the host. A forged post gets 403. The cookie keeps its secret until a login rotates it. `PUT /world/{id}` is `@csrf_exempt` (a public JSON API call) |
| Sessions | `django.contrib.auth` with the default database session backend: `LoginView` (`AuthenticationForm`: `username`, `password`) on `/login` redirects to `/me` (`LOGIN_REDIRECT_URL`); `AuthenticationMiddleware` gives `/me` its `request.user`: one `SELECT` of the `django_session` row (table in [`db.sql`](db.sql), from `manage.py sqlmigrate sessions 0001`), then the user's row (`ModelBackend.get_user`), with no write. `@login_required` redirects a request without a session to `/login` (302). The user model is a custom `AbstractBaseUser` on the shared `users` table (`AUTH_USER_MODEL = 'world.User'`, unmanaged) |
| Passwords | `BCryptPasswordHasher` (Django's plain bcrypt hasher, with the `bcrypt` package) on `users.password_bcrypt`, read with the `bcrypt$` prefix Django's hashers expect; subclassed with `rounds = 10`, the cost of the stored hashes, as Django's documentation changes a work factor, so a login does not rehash and rewrite the password. The table has no `last_login` column, so the model removes that field and Django does not record logins |
| Templates | Django templates (`world/templates/`); with `DEBUG = False` Django uses the cached template loader, which keeps compiled templates, not rendered pages |
| Logging | none: Gunicorn's access log is off (its default) and Django logs nothing for successful requests; warnings and errors go to stderr |
| Image | `python:3.15.2-slim-trixie` |

Settings changed from the generated `settings.py`, and why:

- `DEBUG = False`, `SECRET_KEY` from the environment (a fixed dummy value in
  the Dockerfile; it protects nothing here), and `ALLOWED_HOSTS` set to
  `127.0.0.1` and `localhost`, the hosts the harness uses. These are the
  checklist's critical settings; with `DEBUG = False` Django rejects every
  host not in `ALLOWED_HOSTS`.
- PostgreSQL from `DATABASE_URL` (generated: SQLite) with `CONN_MAX_AGE`,
  which the checklist recommends ("persistent database connections").
- `django.contrib.admin` and `django.contrib.staticfiles` removed from
  `INSTALLED_APPS` (no admin site and no static files). The default
  `MIDDLEWARE` list and template context processors are unchanged, so every
  request goes through the security, session, common, CSRF, authentication,
  messages and clickjacking middleware (Django has no per-route middleware;
  phase 2's endpoints add no middleware). The session and the user are loaded
  lazily, so the existing endpoints neither query `django_session` nor set a
  cookie.
- Phase 2: `AUTH_USER_MODEL`, `PASSWORD_HASHERS`, `LOGIN_URL` and
  `LOGIN_REDIRECT_URL` (see the table). There is no login throttle in Django
  to configure.
- The checklist's HTTPS settings (`SECURE_SSL_REDIRECT`, HSTS, secure
  cookies) stay at their defaults: there is no TLS, and the redirect would
  send every request to `https://`.
- `LOGGING` sends warnings and errors to stderr; Django's default with
  `DEBUG = False` only emails them to `ADMINS`.

Gunicorn: one worker process per vCPU, the suite's convention for Python
servers (Gunicorn's documentation suggests 2-4 x cores and leaves the number
to the user). The threaded worker is used because the default `sync` worker
does not keep connections alive. Gunicorn's documentation gives 2-4 x the
number of cores as the usual range for `threads`; 4 x 2 = 8, which also
divides the suite's 16 database connections between the two processes, since
Django keeps one persistent connection per thread.

psycopg is installed from source with its C extension (`psycopg[c]`), the
"local installation" its
[documentation](https://www.psycopg.org/psycopg3/docs/basic/install.html)
recommends for production. `requirements.txt` was compiled from
`requirements.in` for Python 3.15 on x86_64 Linux with
`uv pip compile --generate-hashes` (command at the top of the file); the
Dockerfile's `lockfile` stage runs that command for the pull request check.

## Production settings

| Setting | Value | Source |
| --- | --- | --- |
| Django | `DEBUG = False`, `SECRET_KEY` from the environment, `ALLOWED_HOSTS` | [Deployment checklist](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/) |
| Logging | Gunicorn `accesslog = None` (its default: no access log); Django's `LOGGING` sends warnings and errors to stderr and logs nothing for a successful request | [Gunicorn `accesslog`](https://gunicorn.org/reference/settings/), [checklist: LOGGING](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/) |
| Server | Gunicorn, `gthread` worker (the `sync` default closes every connection; gthread "supports keep-alive connections") | [How to use Django with Gunicorn](https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/gunicorn/), [Gunicorn design](https://gunicorn.org/design/) |
| Workers | `BENCH_WORKERS` (2) processes, the suite's convention for Python (Gunicorn suggests "2-4 x $(NUM_CORES)" and leaves the choice to the workload) | [Gunicorn `workers`](https://gunicorn.org/reference/settings/), CONTRIBUTING.md |
| Threads | 8 per worker: 4 x 2 cores, inside Gunicorn's "2-4 x $(NUM_CORES)" range, and `DB_POOL_SIZE / workers` | [Gunicorn `threads`](https://gunicorn.org/reference/settings/) |
| Connections | persistent (`CONN_MAX_AGE = 600`), one per thread: 2 x 8 = 16, all usable; `CONN_HEALTH_CHECKS` off (default). Django's optional psycopg pool (`OPTIONS["pool"]`) is not used: the checklist recommends `CONN_MAX_AGE`, and the pool needs `psycopg[pool]` | [checklist: CONN_MAX_AGE](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/), [Databases: Connection pool](https://docs.djangoproject.com/en/6.1/ref/databases/) |
| Prepared statements | none: with psycopg 3 Django defaults to client-side binding cursors (`server_side_binding` off) | [Databases: Server-side parameters binding](https://docs.djangoproject.com/en/6.1/ref/databases/) |
| Driver | `psycopg[c]`, the local installation, "the preferred way to install Psycopg for a production site" | [psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html) |
| Templates | cached template loader (on when `DEBUG = False`) | [checklist: TEMPLATES](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/) |
| Python | **3.15.2** (FastAPI's folder uses 3.14.10): Django 6.1.3 supports 3.12-3.15, and Django recommends "the latest version of Python 3" | [FAQ: Installation](https://docs.djangoproject.com/en/6.1/faq/install/) |
| JIT | none: the official `python` image is built without CPython's experimental JIT (PGO and LTO only) | [python image Dockerfile](https://github.com/docker-library/python/blob/master/3.15/slim-trixie/Dockerfile) |
| Structure | Gunicorn alone (arbiter and 2 workers) in the 2 vCPUs. Gunicorn's deployment guide "strongly recommend[s] running Gunicorn behind a proxy server" (Nginx), mainly to buffer slow clients for the `sync` worker; no proxy runs in the container, as in Django's Gunicorn how-to | [Gunicorn: Deploying](https://gunicorn.org/deploy/) |
