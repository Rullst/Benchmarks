# NestJS

| | |
| --- | --- |
| Version | NestJS 12.5.0 (`@nestjs/core`, `@nestjs/platform-node`), `@nestjs/typeorm` 12.0.3, TypeORM 1.1.3, `pg` 8.23.1, `hbs` 4.4.0, `class-validator` 0.15.1, `class-transformer` 0.5.1, `bcrypt` 6.0.0, `express-session` 1.19.0, `connect-pg-simple` 10.0.0 (exact versions in `package-lock.json`) |
| Build | `npm ci`, `nest build` (tsc, TypeScript 6.0, ES modules as `nest new` generates them), then `npm prune --omit=dev`; started with `node dist/main.js` and `NODE_ENV=production` |
| Runtime | Node.js 26.13.1, the active LTS release |
| Server | Nest's `NodeAdapter` (`@nestjs/platform-node`, on `node:http`) |
| Workers | `node:cluster` with `BENCH_WORKERS` (2) worker processes, each running the Nest application; the primary only hands out connections (Node's default round-robin) and exits if a worker dies, so a crash is visible |
| Database | TypeORM through `@nestjs/typeorm`, entities `World`, `Fortune` and `User` (`users`); a `pg` pool of `DB_POOL_SIZE / BENCH_WORKERS` (8) connections per process; `synchronize: false`; TypeORM reads `DATABASE_URL` as its `url` option |
| Templates | `hbs` (Handlebars), `views/*.hbs` rendered with `@Render()`; compiled once per process because `NODE_ENV=production` |
| Validation | `ParseIntPipe` for `:id`; `ValidationPipe` with `class-validator` DTOs (`src/dto.ts`) for the `/worlds` query, the `PUT` body and the form, passed per parameter; failures answer 400 |
| CSRF | `app.enableCsrfProtection()`, built into Nest since 12.1: Go's `CrossOriginProtection` rule (`Sec-Fetch-Site`, else `Origin` against `Host`), 403 |
| Sessions | `express-session` with its PostgreSQL store `connect-pg-simple` (table in `db.sql`), as Nest middleware of `/form`, `/login` and `/me` only (`AppModule.configure`) |
| Logging | Nest's default logger: start-up messages from each process, nothing per request |
| Image | `node:26.13.1-trixie-slim`, running as the image's `node` user |

Why:

- [HTTP adapters](https://docs.nestjs.com/http/performance): "Starting with
  NestJS v12.3, we recommend the `NodeAdapter`", which "will become the
  default" in v13; Nest still uses Express when no adapter is passed. Since
  the documentation recommends it, this implementation uses it. It supports
  `@Render()` and `setViewEngine('hbs')` as the Express adapter does.
- [Model-View-Controller](https://docs.nestjs.com/http/mvc): the `hbs` engine,
  `setBaseViewsDir()`, `setViewEngine('hbs')` and `@Render()`, as in that
  chapter. As in its first example, no layout is configured; `hbs` then looks
  for `views/layout.hbs` on every render (a failed file read) before
  rendering the view on its own. That is the documented default and is kept.
- [Databases](https://docs.nestjs.com/data/overview) and
  [TypeORM](https://docs.nestjs.com/data/typeorm): TypeORM through
  `@nestjs/typeorm` with the `pg` driver, an entity, `forFeature()` and an
  injected `Repository`; "Don't use `synchronize: true` in production". The
  pool size is TypeORM's `poolSize` option (the `pg` pool's `max`).
- [Deployment](https://docs.nestjs.com/deployment): `NODE_ENV=production`
  and `node dist/main.js`; the image keeps only production dependencies, one
  of the customisations that page suggests.
- The Nest documentation does not describe running several processes; the
  `node:cluster` setup is the suite's Node.js convention (one process per
  vCPU, the database pool divided between them; see CONTRIBUTING.md). As PID
  1 in the container, the primary handles `SIGTERM` itself.

Database and application endpoints:

- `/queries`: one `findOneBy({ id })` per random id, run concurrently
  (`Promise.all`) on the process's pool.
- `/updates`: each row is read with its own `findOneBy`, given a new value
  (different from the current one) and written with its own
  `Repository.update({ id }, { randomNumber })`: one `UPDATE` per row, in
  autocommit, so no transaction spans the rows.
- `GET /world/:id`: `ParseIntPipe` (400 for `abc`), `findOneBy`, 404 without
  a row. `PUT /world/:id`: `ValidationPipe` checks the body (`@IsInt()
  @Min(1) @Max(10000)`, no conversion, so `"5"` is refused) before the
  handler loads the row, sets the field and calls `Repository.save()`
  (TypeORM's usual way; it reads the row again and writes it in a
  transaction).
- `GET /worlds`: `ValidationPipe` with `transform` and
  `enableImplicitConversion` (query values are strings), defaults in the DTO;
  `min > max` is checked by hand. One `find()` with `Between`, `order`, `skip`
  and `take`.
- `/fortunes`: `find()` (no `ORDER BY`), sorted with `<` on the messages
  (UTF-16 code units, which is code-point order for these messages), rendered
  by `hbs` (`{{message}}` is escaped). No `layout.hbs` exists.

Browser routes:

- CSRF: `app.enableCsrfProtection()` is Nest's built-in protection (the
  [CSRF](https://docs.nestjs.com/security/csrf) chapter): it reads
  `Sec-Fetch-Site` (and `Origin` when that is missing) and refuses cross-origin
  unsafe requests with 403 before routing. There is no token, so the form
  pages have no hidden field. It is a global hook: every request passes
  through it, and for the other endpoints it is a method check (GET) or, for
  `PUT /world/:id`, which carries neither header, a check that ends at "no
  browser headers". The documented API has no per-route form: its `exclude`
  option is consulted only for a request it would otherwise refuse.
- Sessions: the spec's first choice, [`@nestjs/authentication`](https://docs.nestjs.com/security/authentication),
  works on the `NodeAdapter`, but its module always registers a global
  interceptor (`AuthenticationScopeInterceptor`, an `APP_INTERCEPTOR` with no
  option to turn it off), which would wrap every handler, the existing
  endpoints included. So this folder uses the spec's fallback, the session
  middleware of Nest's [Session](https://docs.nestjs.com/techniques/session)
  chapter, `express-session`, with its PostgreSQL store `connect-pg-simple`.
  `AppModule.configure()` applies it with `MiddlewareConsumer.forRoutes('form',
  'login', 'me')`, so no other route runs it. It is connect-style middleware
  that relies only on Node's request and response API, which the `NodeAdapter`
  supports.
- The store queries through TypeORM's `pg` pool (`PostgresDriver.master`), so
  each process keeps one pool of `DB_POOL_SIZE / BENCH_WORKERS` connections.
  The table is `connect-pg-simple`'s `table.sql`, created by `db.sql` (the
  store's `createTableIfMissing` is off by default). Options: `resave: false`
  and `saveUninitialized: false` (the values the express-session README
  recommends), so `GET /form` and `GET /login` create no session.
- `POST /login` checks the password with `bcrypt` (the package the
  [hashing](https://docs.nestjs.com/security/encryption-and-hashing) chapter
  names) against `users.password_bcrypt`, gives the session a new id
  (`req.session.regenerate()`, against session fixation), stores the user's id
  in it and redirects (303) to `/me`; express-session writes the row and sets
  the signed `connect.sid` cookie when the response ends. A wrong password is
  a 401 and creates no session.
- `GET /me`: the middleware reads the session row (one `SELECT` on `session`)
  and the handler reads the user's row with TypeORM on every request; without
  a session, 401. With the defaults, `connect-pg-simple` implements `touch`, so
  express-session also writes the row's `expire` (one `UPDATE`) at the end of
  every request that loaded a session; this is the library's default and is
  kept.
- The cookie is signed with `SESSION_SECRET`, a fixed test value in bench.json
  `env`, the same in both cluster processes; the sessions are in PostgreSQL,
  so either process serves any session. The CSRF check has no secret. No login
  throttling exists in this setup.
