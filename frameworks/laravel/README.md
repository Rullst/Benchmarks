# Laravel

The `laravel/laravel` 13.11.0 skeleton with the benchmark's endpoints, served the
way Laravel's [deployment documentation](https://laravel.com/docs/13.x/deployment)
describes: Nginx with the documented server block in front of PHP-FPM, and
`php artisan optimize`.

| | |
| --- | --- |
| Version | laravel/framework 13.42.0 on PHP 8.5.12 (exact versions in `composer.lock`); Nginx from Debian trixie (version in the results) |
| Build | `composer install --no-dev`, optimized autoloader; `php artisan optimize` (configuration, events, routes and views cached) when the container starts |
| Server | Nginx with the server block from the deployment documentation (`docker/nginx-site.conf`), passing requests to PHP-FPM over a Unix socket; the production `php.ini` and OPcache with the PHP manual's recommended production settings (`docker/opcache.ini`) |
| Workers | Nginx: `BENCH_WORKERS` (2) worker processes. PHP-FPM: `pm = static` with `pm.max_children` = `DB_POOL_SIZE` (16) processes |
| Database | Eloquent, `World::findOrFail(1)`. Each PHP-FPM process handles one request at a time and opens its database connection for each request (Laravel's default, no persistent PDO connections), so at most 16 connections are open, the suite's pool size |
| Database endpoints | `/queries`: `World::findOrFail` per row. `/updates`: per row, `World::findOrFail`, a new random value (drawn again while it equals the current one, so the row changes) and `save()`, all in one `DB::transaction` with the ids sorted, so concurrent requests lock rows in the same order. `/fortunes`: `Fortune::all()` (no `ORDER BY`), sorted with `strcmp` (byte order, i.e. code points), rendered by Blade (`{{ }}` escapes) |
| Request input (phase 2) | `GET /world/{id}` and `PUT /world/{id}` use `whereNumber('id')`, so a non-integer id matches no route (404). `GET /worlds` and the PUT body use `$request->validate` (`integer`, `between`; `integer:strict` for the JSON body, so the string `"5"` is refused): 422 with the errors as JSON (the api group's exceptions render as JSON, `bootstrap/app.php`); malformed JSON is empty input, so `required` fails (422). `GET /worlds` is one Eloquent query (`whereBetween`, `orderBy`, `limit`, `offset`). `PUT /world/{id}` validates first, then `World::find` (404 without a row), assigns and `save()`s |
| CSRF | the `web` group's `PreventRequestForgery`: it accepts a post with `Sec-Fetch-Site: same-origin` (which the load sends, like a browser), else compares the `_token` field (`@csrf`) with the token in the session; a forged post gets 419. The token lives as long as the session. `PUT /world/{id}` is in the `api` group, which has no CSRF check |
| Sessions | the session guard (`Auth::attempt`, `auth` middleware), as in Laravel's "Manually Authenticating Users": `POST /login` checks `users.password_bcrypt` with Laravel's bcrypt hasher, regenerates the session and redirects to `/me` (302); a wrong password is redirected back. `GET /me` reads the user id from the session and the user's row with Eloquent (`SELECT * FROM users WHERE id = ?`) on every request; without a session it answers 401 (JSON). The session is stored by the **cookie** driver (see below) |
| Templates | Blade (`resources/views/`), compiled by `php artisan optimize` |
| Logging | none: Nginx's and PHP-FPM's access logs are off; Laravel logs warnings and errors to stderr (`LOG_CHANNEL=stderr`, `LOG_LEVEL=warning`) |
| Image | `php:8.5.12-fpm-trixie` (runtime), `php:8.5.12-cli-trixie` and `composer:2.11.2` (build) |

`/text`, `/json` and `/db-single` are in `routes/api.php` and use the `api`
middleware group, which Laravel's routing documentation describes for
stateless routes (served here without the default `/api` prefix, through
`apiPrefix: ''` in `bootstrap/app.php`). `/html` is in `routes/web.php` and
uses the default `web` group: encrypted cookies, a session, CSRF protection.
Laravel starts the session on every request in that group, so each `/html`
response sets the session and `XSRF-TOKEN` cookies. Phase 1's endpoints and
`/world/{id}`, `/worlds` and `PUT /world/{id}` are in the `api` group;
`/form`, `/login` and `/me` in the `web` group, like `/html`.

Changes from the skeleton and the documented setup, and why:

- **Environment**: `APP_ENV=production` and `APP_DEBUG=false`, as the
  deployment documentation requires; `APP_KEY` is a fixed dummy key (it
  protects nothing here); `DB_CONNECTION=pgsql`, with `DB_URL` taken from the
  harness's `DATABASE_URL`.
- **Session driver** `cookie` (decision 4 of docs/v3-spec.md, pending
  the maintainer's confirmation; `phase2.session.store` is
  `cookie-encrypted`): Laravel's default is the `database` driver, which
  section 6.2's rule would pick. But `/html` is in the `web` group and the
  load generator sends it no cookies, so every `/html` request would start a
  new session and the `database` driver would insert a `sessions` row for
  each one, an artifact of the load generator rather than of Laravel (the
  `file` driver would create a file for each). The cookie driver keeps the
  `web` group's work (session, CSRF token, cookie encryption) without
  server-side storage: the session data travels in an encrypted cookie that
  Laravel rewrites on every response, and `/me` costs a decryption plus the
  user's row instead of a session `SELECT` and `UPDATE`. The choice is made
  in one place, the default of `driver` in `config/session.php`; switching to
  `database` also needs the skeleton's `sessions` table in a `db.sql`
  (declared as `db_setup`).
- **Phase 2 auth**: the skeleton's `User` model on the shared `users` table
  (no timestamps or remember token). Its password is `password_bcrypt`, read
  through `getAuthPassword()` with the `$2y$` prefix: bench/db/phase2.sql
  stores the `$2b$` form, which PHP's password API names `$2y$` (the same
  algorithm), and Laravel's bcrypt hasher refuses any other prefix.
  `BCRYPT_ROUNDS=10`, the cost of the stored hashes, so Laravel's
  rehash-on-login does not rewrite them. The login has no throttle: the
  starter kits' `RateLimiter` check is not part of the session guard, and it
  would need the cache store's table.
- **Exceptions**: `shouldRenderJsonWhen` recognises the `api` group's routes
  by their middleware group (the skeleton's `is('api/*')` does not match
  without the `/api` prefix), so their validation errors are JSON 422, not a
  redirect.
- **`php artisan optimize` at start-up**, not in the image build: the cached
  configuration keeps the environment it was created in.
- **Nginx**: the documented server block, listening on `$PORT` (IPv4 only)
  instead of port 80, with `server_name` 127.0.0.1 and localhost, the access
  log off and PHP-FPM's socket at `/run/php/php-fpm.sock`. Debian's
  `nginx.conf` is otherwise unchanged, except `worker_processes`, which is
  `BENCH_WORKERS`: Debian's `auto` counts the host's CPUs, not the CPUs the
  container may use.
- **PHP-FPM**: the Unix socket instead of TCP port 9000, no access log, and
  production sizing instead of the example values in the image's `www.conf`
  (`pm = dynamic`, at most 5 children). The PHP-FPM manual sizes
  `pm.max_children` by the memory available to the pool; a Laravel worker
  uses about 30-50 MiB beside the shared OPcache, so the 2 GiB container
  could hold more than 30. The pool is capped at `DB_POOL_SIZE` (16) because
  every child opens its own database connection, which keeps the connection
  count equal to every other implementation's pool. `pm = static` keeps all
  children running, the mode for a dedicated server with known memory.
- **OPcache**: the PHP manual's recommended settings, with
  `max_accelerated_files` raised above the number of PHP files in the
  application and its vendor directory and `validate_timestamps` off because
  the code in the image never changes.
- **Skeleton**: the `config/` files, `bootstrap/`, `public/index.php`,
  `artisan` and `routes/console.php` are the skeleton's; frontend assets,
  tests, migrations, factories and the development
  packages (Tinker, Pail, Pint, PHPUnit, ...) are left out.

Why: Nginx and PHP-FPM is the first server setup in Laravel's deployment
documentation, and `php artisan optimize` and `APP_DEBUG=false` are the
production steps it lists. Laravel's documentation does not size PHP-FPM, so
the pool follows the PHP-FPM manual's memory-based sizing, capped at the
suite's connection count. FrankenPHP and Octane are
documented alternatives that keep the application in memory between
requests; this implementation measures the classic PHP-FPM setup.

## Production settings

| Setting | Value | Source |
| --- | --- | --- |
| Environment | `APP_ENV=production`, `APP_DEBUG=false` | [Deployment: Debug Mode](https://laravel.com/docs/13.x/deployment#debug-mode) |
| Caches | `php artisan optimize` at start-up: configuration, events, routes and views cached | [Deployment: Optimization](https://laravel.com/docs/13.x/deployment#optimization) |
| Autoloader | `composer install --no-dev`, `composer dump-autoload --optimize` | [Composer: autoloader optimization](https://getcomposer.org/doc/articles/autoloader-optimization.md) |
| Logging | Nginx `access_log off`, PHP-FPM's access log removed; Laravel `LOG_CHANNEL=stderr`, `LOG_LEVEL=warning` (Laravel writes no line per request) | [Logging](https://laravel.com/docs/13.x/logging) |
| Database connection | **a new PostgreSQL connection for every request**: each PHP-FPM child connects when a request first queries and disconnects when the request ends; no persistent PDO connections (`PDO::ATTR_PERSISTENT` is not set). At most 16 open at once, one per child | see "Database connections" below |
| Prepared statements | Laravel's default PDO options (`PDO::ATTR_EMULATE_PREPARES => false`): pdo_pgsql prepares each statement on the server, on that request's new connection | [Connector.php](https://github.com/laravel/framework/blob/13.x/src/Illuminate/Database/Connectors/Connector.php) |
| Server | Nginx with the documented server block in front of PHP-FPM, over a Unix socket | [Deployment: Nginx](https://laravel.com/docs/13.x/deployment#nginx) |
| Workers | Nginx `worker_processes` = `BENCH_WORKERS` (2); PHP-FPM `pm = static`, `pm.max_children` = `DB_POOL_SIZE` (16) | [PHP-FPM configuration](https://www.php.net/manual/en/install.fpm.configuration.php) |
| php.ini | the image's `php.ini-production` | [php image: Configuration](https://hub.docker.com/_/php) |
| OPcache | on (`opcache.enable=1`, PHP's default for PHP-FPM; built in since PHP 8.5); `memory_consumption=128` and `interned_strings_buffer=8` (the manual's recommended values), `max_accelerated_files=20000` (above the application's PHP file count), `validate_timestamps=0` (the image's code never changes; Forge's production OPcache optimisation likewise needs a PHP-FPM reload on every deployment) | [OPcache installation](https://www.php.net/manual/en/opcache.installation.php), [OPcache configuration](https://www.php.net/manual/en/opcache.configuration.php), [Forge: PHP, OPcache](https://laravel.com/forge/docs/servers/php) |
| OPcache JIT | **off**: `opcache.jit` is not set, and its default has been `disable` since PHP 8.4. Neither Laravel's documentation nor Forge's recommends turning it on | [OPcache configuration: `opcache.jit`](https://www.php.net/manual/en/opcache.configuration.php) |
| Structure | Nginx (2 workers) and PHP-FPM (16 children) run in the same container and share its 2 vCPUs | |

### Database connections

Laravel opens its PDO connection lazily and PHP closes it at the end of the
request; under PHP-FPM every request therefore starts a new PostgreSQL
connection (authentication and backend start-up included), which shows up as
PostgreSQL CPU per request on the database endpoints. Persistent connections
were considered and **not** used, because Laravel's own guidance does not
recommend them:

- Laravel's [database](https://laravel.com/docs/13.x/database) and
  [deployment](https://laravel.com/docs/13.x/deployment) pages do not mention
  `PDO::ATTR_PERSISTENT` or persistent connections; the per-connection
  `options` array is only shown for MySQL's SSL CA.
- [Forge's PHP page](https://laravel.com/forge/docs/servers/php) covers
  OPcache and PHP-FPM settings, not persistent connections. Laravel Cloud's
  [Serverless Postgres](https://laravel.com/cloud/docs/resources/databases/postgres)
  page answers too many connections with its pgbouncer pooler or fewer
  workers, not with persistent PDO connections.
- PHP's manual describes the trade-off without recommending it as a default:
  "Persistent connections are beneficial when the overhead of creating a link
  to an SQL server is high", but "PDO does not perform any cleanup of
  persistent connections. Temporary tables, locks, transactions and other
  stateful changes may remain from previous usage of the connection"
  ([persistent connections](https://www.php.net/manual/en/features.persistent-connections.php),
  [PDO connections](https://www.php.net/manual/en/pdo.connections.php)).

Laravel documents [Octane](https://laravel.com/docs/13.x/octane) for keeping
the application in memory between requests; this implementation measures the
classic PHP-FPM setup, so its database results include a new connection per
request.
