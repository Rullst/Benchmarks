# Laravel

The `laravel/laravel` 13.11.0 skeleton with the four endpoints, served the
way Laravel's [deployment documentation](https://laravel.com/docs/13.x/deployment)
describes: Nginx with the documented server block in front of PHP-FPM, and
`php artisan optimize`.

| | |
| --- | --- |
| Version | laravel/framework 13.42.0 on PHP 8.5.12 (exact versions in `composer.lock`); Nginx from Debian trixie (version in the results) |
| Build | `composer install --no-dev`, optimized autoloader; `php artisan optimize` (configuration, events, routes and views cached) when the container starts |
| Server | Nginx with the server block from the deployment documentation (`docker/nginx-site.conf`), passing requests to PHP-FPM over a Unix socket; OPcache on (part of PHP 8.5) with the production `php.ini` |
| Workers | Nginx: `BENCH_WORKERS` (2) worker processes. PHP-FPM: the pool's defaults, `pm = dynamic` with at most 5 processes (`pm.max_children`); PHP-FPM does not size its pool by CPU |
| Database | Eloquent, `World::findOrFail(1)`. Each PHP-FPM process handles one request at a time and opens its database connection for each request (Laravel's default, no persistent PDO connections), so at most 5 connections are open |
| Templates | Blade (`resources/views/hello.blade.php`), compiled by `php artisan optimize` |
| Logging | none: Nginx's and PHP-FPM's access logs are off; Laravel logs warnings and errors to stderr (`LOG_CHANNEL=stderr`, `LOG_LEVEL=warning`) |
| Image | `php:8.5.12-fpm-trixie` (runtime), `php:8.5.12-cli-trixie` and `composer:2.11.2` (build) |

`/text`, `/json` and `/db-single` are in `routes/api.php` and use the `api`
middleware group, which Laravel's routing documentation describes for
stateless routes (served here without the default `/api` prefix, through
`apiPrefix: ''` in `bootstrap/app.php`). `/html` is in `routes/web.php` and
uses the default `web` group: encrypted cookies, a session, CSRF protection.
Laravel starts the session on every request in that group, so each `/html`
response sets the session and `XSRF-TOKEN` cookies.

Changes from the skeleton and the documented setup, and why:

- **Environment**: `APP_ENV=production` and `APP_DEBUG=false`, as the
  deployment documentation requires; `APP_KEY` is a fixed dummy key (it
  protects nothing here); `DB_CONNECTION=pgsql`, with `DB_URL` taken from the
  harness's `DATABASE_URL`.
- **Session driver** `cookie`: the skeleton's default `database` driver needs
  the `sessions` table from its migrations, and the benchmark database has
  only the `world` table (no migrations, no schema writes). The `file` driver
  would create a new session file for every request, because the load
  generator does not send cookies back. The cookie driver keeps the `web`
  group's work (session, CSRF token, cookie encryption) without server-side
  storage.
- **`php artisan optimize` at start-up**, not in the image build: the cached
  configuration keeps the environment it was created in.
- **Nginx**: the documented server block, listening on `$PORT` (IPv4 only)
  instead of port 80, with `server_name` 127.0.0.1 and localhost, the access
  log off and PHP-FPM's socket at `/run/php/php-fpm.sock`. Debian's
  `nginx.conf` is otherwise unchanged, except `worker_processes`, which is
  `BENCH_WORKERS`: Debian's `auto` counts the host's CPUs, not the CPUs the
  container may use.
- **PHP-FPM**: the image's pool configuration with the Unix socket instead of
  TCP port 9000 and without the access log the image enables.
- **Skeleton**: the `config/` files, `bootstrap/`, `public/index.php`,
  `artisan` and `routes/console.php` are the skeleton's; frontend assets,
  tests, migrations, factories, the `User` model and the development
  packages (Tinker, Pail, Pint, PHPUnit, ...) are left out.

Why: Nginx and PHP-FPM is the first server setup in Laravel's deployment
documentation, and `php artisan optimize` and `APP_DEBUG=false` are the
production steps it lists. Laravel's documentation does not size PHP-FPM, so
the pool keeps PHP-FPM's shipped defaults. FrankenPHP and Octane are
documented alternatives that keep the application in memory between
requests; this implementation measures the classic PHP-FPM setup.
