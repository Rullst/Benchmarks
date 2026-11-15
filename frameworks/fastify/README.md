# Fastify

| | |
| --- | --- |
| Version | fastify 5.12.8 (exact versions in `package-lock.json`) |
| Build | `npm ci --omit=dev` on Node.js 26.13.1, the active LTS release, with `NODE_ENV=production` |
| Server | Fastify on `node:http`, listening on `0.0.0.0`; the primary process forks `BENCH_WORKERS` workers (2) with `node:cluster`, which share the port (round-robin, Node.js's default on Linux) |
| Database | `@fastify/postgres` 6.1 (node-postgres 8.23 `Pool`), `fastify.pg.query('SELECT id, randomnumber FROM world WHERE id = $1', [1])`; `max` is `DB_POOL_SIZE / BENCH_WORKERS` (8) per process |
| Templates | `@fastify/view` 12 with EJS 7 (`views/hello.ejs`); in production mode the plugin caches the compiled template, not the response |
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
