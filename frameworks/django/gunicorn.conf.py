"""Gunicorn settings (https://gunicorn.org/reference/settings/).

Gunicorn reads ./gunicorn.conf.py from the working directory by default.
"""

import os

wsgi_app = 'benchsite.wsgi'
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"

# One worker process per vCPU (BENCH_WORKERS, the suite's convention for
# Python servers).
workers = int(os.environ.get('BENCH_WORKERS', '2'))

# The threaded worker (gthread): the default sync worker does not support
# keep-alive connections. Gunicorn's documentation gives 2-4 x CPU cores as
# the usual range for threads; 4 x 2 = 8 per worker. Every thread keeps one
# persistent database connection (CONN_MAX_AGE), so the count is capped at
# DB_POOL_SIZE / workers to stay within the suite's 16 connections.
worker_class = 'gthread'
threads = min(4 * workers, int(os.environ.get('DB_POOL_SIZE', '16')) // workers)

# Access log off (Gunicorn's default); the error log goes to stderr.
accesslog = None
