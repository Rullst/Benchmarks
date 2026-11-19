# Fastify

| | |
| --- | --- |
| Version | fastify 5.12.8, `@fastify/formbody` 9.0, `@fastify/cookie` 11.1, `@fastify/csrf-protection` 8.0, `@fastify/secure-session` 8.4, `bcryptjs` 3.0 (exact versions in `package-lock.json`) |
| Build | `npm ci --omit=dev` on Node.js 26.13.1, the active LTS release, with `NODE_ENV=production` |
| Server | Fastify on `node:http`, listening on `0.0.0.0`; the primary process forks `BENCH_WORKERS` workers (2) with `node:cluster`, which share the port (round-robin, Node.js's default on Linux) |
| Database | `@fastify/postgres` 6.1 (node-postgres 8.23 `Pool`), parameterized SQL (`fastify.pg.query`); `max` is `DB_POOL_SIZE / BENCH_WORKERS` (8) per process |
| Templates | `@fastify/view` 12 with EJS 7 (`views/*.ejs`, `<%= %>` escapes); in production mode the plugin caches the compiled template, not the response |
| Validation | JSON schemas for `params`, `querystring` and `body` (Fastify's Ajv); failures answer 400 |
| CSRF | `@fastify/csrf-protection` with `@fastify/cookie`: the secret in the `_csrf` cookie, the token in the form's `_csrf` field, checked in `preValidation` (403) |
| Sessions | `@fastify/secure-session`: the session encrypted (libsodium) in the `session` cookie with `SESSION_KEY` (bench.json `env`), the same key in both cluster processes |
| Logging | none: Fastify's logger is off by default |
| Image | `node:26.13.1-trixie-slim`, started with `node server.js` as the `node` user |

Why: this follows the Fastify documentation and the suite's Node.js
convention.

- Database: the [Database guide](https://fastify.dev/docs/latest/Guides/Database/)
  uses the official `@fastify/postgres` plugin, which passes its options to
  the node-postgres pool; only the pool size is set.
- Templates: `@fastify/view` is Fastify's official template plugin, and its
  [quick start](https://github.com/fastify/point-of-view#quick-start) uses EJS
  with `reply.viewAsync`.
- [Recommendations](https://fastify.dev/docs/latest/Guides/Recommendations/):
  listen on `0.0.0.0` in containers, and define response schemas for JSON
  routes (`/json` and `/db-single` have one, so fast-json-stringify
  serializes them).
- Workers: the suite runs one process per vCPU with
  [`node:cluster`](https://nodejs.org/api/cluster.html) for every Node.js
  implementation (see CONTRIBUTING.md). The Fastify recommendations instead
  suggest 2 vCPUs per instance for the lowest latency (the second vCPU mostly
  serves the garbage collector and libuv's threads) and say 1 vCPU per
  instance is fine for throughput.
- If a worker exits, the primary exits too, so the harness reports a crash
  instead of measuring a server with fewer workers. The primary handles
  `SIGTERM` because it is PID 1 in the container.

## Production settings

| Setting | Value | Source |
| --- | --- | --- |
| `NODE_ENV` | `production` (Dockerfile `ENV`); `@fastify/view` reads it | CONTRIBUTING.md (Node.js convention) |
| Logging | none: `Fastify()` without `logger`, whose default is `false` ("The logger is disabled"), so no request or start-up lines | [Server, `logger`](https://fastify.dev/docs/latest/Reference/Server/#logger) |
| Template cache | on: `@fastify/view`'s `production` option defaults to `NODE_ENV === "production"`, in which it "will heavily cache the templates file and functions" (compiled templates, not responses) | [@fastify/view options](https://github.com/fastify/point-of-view#options) |
| Database layer | `@fastify/postgres` (the plugin the Database guide uses), `fastify.pg.query(text, values)` | [Database guide](https://fastify.dev/docs/latest/Guides/Database/), [@fastify/postgres](https://github.com/fastify/fastify-postgres) |
| Pool | node-postgres `Pool` `max` = `DB_POOL_SIZE / BENCH_WORKERS` = 8 per process, 16 in total (the plugin passes its options to the pool) | [@fastify/postgres](https://github.com/fastify/fastify-postgres), [pg Pool](https://node-postgres.com/apis/pool) (`max`) |
| Prepared statements | not used: the queries carry no `name`, so each is an unnamed statement that PostgreSQL parses and plans every time. node-postgres documents named (prepared) statements but advises against them for simple queries: "Be careful not to fall into the trap of premature optimization. Most of your queries will likely not benefit much, if at all, from using prepared statements"; neither the Database guide nor `@fastify/postgres` mentions them | [node-postgres, Prepared statements](https://node-postgres.com/features/queries) |
| Driver | `pg`, the pure JavaScript client. `@fastify/postgres` offers `native: true` with `pg-native` "if you want maximum performance", but node-postgres does not recommend the native bindings ("the pure JavaScript driver is plenty fast") and they would add a compiled `libpq` dependency, so it is not used | [@fastify/postgres, Native option](https://github.com/fastify/fastify-postgres), [node-postgres, Native bindings](https://node-postgres.com/features/native) |
| Serialization | response schemas on the JSON routes (fast-json-stringify) | [Recommendations](https://fastify.dev/docs/latest/Guides/Recommendations/): "Define response schemas to speed up JSON serialization" |
| Listen address | `0.0.0.0` | [Recommendations](https://fastify.dev/docs/latest/Guides/Recommendations/) (Kubernetes) |
| Workers | `node:cluster`, `BENCH_WORKERS` (2) processes | CONTRIBUTING.md (Node.js convention), [cluster](https://nodejs.org/api/cluster.html) |
| Caches | none (no response or query-result cache) | |

Database and application endpoints:

- `/queries`: one query per random id, run concurrently (`Promise.all`) on
  the process's pool. `/updates`: each row is read with its own query, given
  a new value (different from the current one) and written with its own
  `UPDATE` (autocommit, no transaction).
- `GET /world/:id`: a `params` schema with an `integer` id (400 for `abc`),
  404 without a row. `PUT /world/:id`: Fastify has no ORM, so one `UPDATE …
  RETURNING` after the body schema (`randomNumber`, an integer from 1 to
  10000, required) has accepted the body. Fastify's validator coerces types
  in every part of the request (`coerceTypes: 'array'`), which would accept
  `{"randomNumber": "5"}`; the route has its own validator compiler, as the
  [Validation and Serialization](https://fastify.dev/docs/latest/Reference/Validation-and-Serialization/)
  reference shows for per-`httpPart` options: the JSON body without coercion,
  the path parameter with it.
- `GET /worlds`: a `querystring` schema with ranges and defaults (`useDefaults`);
  `min > max` is checked by hand. One query with `BETWEEN`, `ORDER BY`,
  `LIMIT` and `OFFSET`.
- `/fortunes`: `SELECT id, message FROM fortune` (no `ORDER BY`), sorted
  with `<` (UTF-16 code units, which is code-point order for these messages),
  rendered with EJS.

Browser routes (`browser.js`):

- One encapsulated plugin registers `@fastify/cookie`, `@fastify/secure-session`,
  `@fastify/formbody` and `@fastify/csrf-protection` with `/form`, `/login`
  and `/me`, so their hooks do not run for the other routes (Fastify's
  plugin encapsulation).
- CSRF: `@fastify/csrf-protection` is Fastify's CSRF plugin (Fastify has no
  built-in protection); with its default `sessionPlugin` (`@fastify/cookie`)
  the secret lives in the `_csrf` cookie and `reply.generateCsrf()` derives the
  form's token from it, so a page's cookie and field stay valid for any number
  of posts. `fastify.csrfProtection` runs in `preValidation`, after the body
  is parsed and before the schema checks the fields. The secret is in the
  cookie, so it needs no shared server key across the cluster.
- Sessions: `@fastify/session` has no PostgreSQL store, so the suite's rule
  takes the encrypted cookie store, `@fastify/secure-session`. `POST /login`
  checks the password with `bcryptjs` (the most-used bcrypt package; Fastify
  documents no hasher) against `users.password_bcrypt`, stores the user's id
  in the session and redirects (303) to `/me`; a wrong password is a 401.
  `GET /me` decrypts the cookie and reads the user's row on every request;
  without a session, 401. The cookie is rewritten only when the session
  changes. `SESSION_KEY` is a fixed test key in bench.json, so both cluster
  processes open the same cookies. No login throttling exists in this setup.
