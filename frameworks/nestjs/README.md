# NestJS

| | |
| --- | --- |
| Version | NestJS 12.5.0 (`@nestjs/core`, `@nestjs/platform-node`), `@nestjs/typeorm` 12.0.3, TypeORM 1.1.3, `pg` 8.23.1, `hbs` 4.4.0 (exact versions in `package-lock.json`) |
| Build | `npm ci`, `nest build` (tsc, TypeScript 6.0, ES modules as `nest new` generates them), then `npm prune --omit=dev`; started with `node dist/main.js` and `NODE_ENV=production` |
| Runtime | Node.js 26.13.1, the active LTS release |
| Server | Nest's `NodeAdapter` (`@nestjs/platform-node`, on `node:http`) |
| Workers | `node:cluster` with `BENCH_WORKERS` (2) worker processes, each running the Nest application; the primary only hands out connections (Node's default round-robin) and exits if a worker dies, so a crash is visible |
| Database | TypeORM through `@nestjs/typeorm`, `Repository.findOneBy({ id: 1 })`; a `pg` pool of `DB_POOL_SIZE / BENCH_WORKERS` (8) connections per process; `synchronize: false`; TypeORM reads `DATABASE_URL` as its `url` option |
| Templates | `hbs` (Handlebars), `views/hello.hbs` rendered with `@Render('hello')`; compiled once per process because `NODE_ENV=production` |
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
