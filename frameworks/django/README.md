# Django

A `django-admin startproject` project with one app (`world`), set up for
production with Django's
[deployment checklist](https://docs.djangoproject.com/en/6.1/howto/deployment/checklist/)
and served by Gunicorn as in
[How to use Django with Gunicorn](https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/gunicorn/).

| | |
| --- | --- |
| Version | Django 6.1.3, Gunicorn 27.0.1, psycopg 3.3.9 on Python 3.15.2 (exact versions and hashes in `requirements.txt`) |
| Build | `pip install --require-hashes -r requirements.txt` into a virtual environment; psycopg's C extension is built against Debian's libpq |
| Server | Gunicorn with the threaded worker (`gthread`), configured in `gunicorn.conf.py` |
| Workers | `BENCH_WORKERS` (2) worker processes, 8 threads each |
| Database | Django ORM, `World.objects.get(pk=1)` on an unmanaged model of the `world` table; persistent connections (`CONN_MAX_AGE = 600`): each thread keeps one, so at most 2 x 8 = 16 |
| Templates | Django templates (`world/templates/hello.html`); with `DEBUG = False` Django uses the cached template loader, which keeps compiled templates, not rendered pages |
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
  messages and clickjacking middleware. None of them writes to the database
  or sets a cookie for these requests.
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
`uv pip compile --generate-hashes` (command at the top of the file).
