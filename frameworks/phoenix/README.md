# Phoenix

A `mix phx.new bench --no-assets --no-dashboard --no-gettext --no-mailer
--no-live` application (PostgreSQL, Bandit) built and run with the
Dockerfile `mix phx.gen.release --docker` generates.

| | |
| --- | --- |
| Version | Phoenix 1.8.16, Phoenix LiveView 1.2.13 (HEEx), Bandit 1.14.1, Ecto SQL 3.14.0, Postgrex 0.22.4 on Elixir 1.20.5 and Erlang/OTP 29.1.2 (exact versions in `mix.lock`) |
| Build | the generated Dockerfile: `MIX_ENV=prod`, `mix deps.get --only prod`, `mix compile`, `mix release` |
| Server | Bandit, Phoenix's default adapter, started by the release's generated `bin/server` (`PHX_SERVER=true`) on `$PORT` |
| Workers | one BEAM node; the runtime starts one scheduler online per CPU the container may use (2) and Bandit serves each connection in its own process |
| Database | Ecto, `Repo.get!(World, 1)`; one pool of `DB_POOL_SIZE` (16) connections |
| Database endpoints | `/queries`: `Repo.get!(World, id)` per row. `/updates`: per row, `Repo.get!`, a new random value (drawn again while it equals the current one, since Ecto skips an update without changes) and `Repo.update!` of a changeset (one `UPDATE` per row, no transaction): like `/queries`, every Repo call checks a connection out of the pool and returns it (see Production settings). `/fortunes`: `Repo.all(Fortune)` (no `ORDER BY`), sorted in Elixir (binary order, i.e. code points), rendered by HEEx (escaped) without a layout, through a pipeline that only accepts `html` |
| Request input (phase 2) | The router's `:id` is a string, cast with `Ecto.Type.cast(:id, id)` before the query: a non-integer is answered 400, the status phoenix_ecto gives the `Ecto.Query.CastError` that `Repo.get` would raise for it (cast first: in the conformance check, Bandit closed the keep-alive connection after that exception without a `Connection: close` header, and the next request on it failed). `GET /worlds`, the PUT body and `POST /form` are validated with schemaless changesets (`cast`, `validate_required`, `validate_number`, `validate_length`): 422 with the errors (the form page again for `/form`). `cast` turns the JSON string `"5"` into 5, so the PUT also checks that the body's value is a JSON integer. Malformed JSON is 400 (`Plug.Parsers.ParseError`). `GET /worlds` is one Ecto query (`where`, `order_by`, `limit`, `offset`). `PUT /world/:id` validates first, then casts the id, `Repo.get` (404 without a row) and `Repo.update!` |
| CSRF | `protect_from_forgery` (`Plug.CSRFProtection`) in the generated `:browser` pipeline: the forms' hidden `_csrf_token` (`get_csrf_token()`) is a masked copy of the token kept in the signed cookie session (`_bench_key`); a post without a matching token raises `InvalidCSRFTokenError`, 403. The token does not change until a login renews the session. `PUT /world/:id` is in the `:api` pipeline, which has no CSRF protection |
| Sessions | `mix phx.gen.auth` (Phoenix 1.8), password login only, adapted to the shared `users` table: `Accounts.User` reads `users.password_bcrypt` (as its `hashed_password` field) and checks it with `Bcrypt.verify_pass` (bcrypt_elixir, the dependency the generator adds); a login inserts a session token into `users_tokens` (table in [`db.sql`](db.sql), the SQL of the generated migration), renews the session, puts the token in it and redirects to `/me` (302). `fetch_current_scope_for_user` finds the user with one query joining `users_tokens` and `users` on every request; `require_authenticated_user` redirects a request without a session to `/login` (302) |
| Middleware scope | `/form` uses the generated `:browser` pipeline, like `/html`; `/login` and `/me` add `fetch_current_scope_for_user` (and `/me` `require_authenticated_user`) with `pipe_through`, instead of the generator's `plug` in `:browser`, so `/html` and `/form` keep the generated pipeline. `:browser` accepts `json` as well as `html`, for `/me`. The phase-1 endpoints, `/world/:id` and `/worlds` use the `:api` pipeline |
| Templates | HEEx: `page_html/hello.html.heex` rendered inside the root layout `layouts/root.html.heex`; the phase-1 and phase-2 pages are whole documents rendered without the root layout (the `:plain_html` pipeline of `/fortunes` sets none; the form and login controllers turn the `:browser` pipeline's off with `put_root_layout(false)`) |
| Logging | Logger level `:warning`: the generated `:info` level logs every request |
| Image | builder `hexpm/elixir:1.20.5-erlang-29.1.2-debian-trixie-20261104-slim`, runner `debian:trixie-20261104-slim`, as the generated Dockerfile pairs them |

The HTML page goes through the generated `:browser` pipeline (session,
flash, root layout, CSRF protection, secure browser headers) and the other
endpoints through the generated `:api` pipeline. The page's session and CSRF
token are not used, so no cookie is set. The root layout is the document the
benchmark specifies; the generated one adds a CSRF meta tag, assets and a
title suffix, and the generated app layout and `CoreComponents` are not
included.

Changes from the generated files, and why:

- **Logger level** `:warning` in `config/prod.exs`, to turn off the request
  log.
- **Pool size**: `config/runtime.exs` reads `DB_POOL_SIZE` (generated:
  `POOL_SIZE`, default 10).
- **Dependencies**: no `phoenix_live_reload` and `lazy_html` (development and
  test only); `bcrypt_elixir` added, as `mix phx.gen.auth` adds it. Phoenix, LiveView, Ecto SQL, Postgrex and Bandit are pinned
  exactly; `mix.lock` comes from the Dockerfile's `lockfile` stage.
- **Image references** written out in the `FROM` lines instead of the
  generated `ARG`s, so the harness can record their digests.
- **Secret**: `SECRET_KEY_BASE` is a fixed dummy value in the Dockerfile
  (`runtime.exs` refuses to start without it). It signs the session cookie of
  the benchmark's test accounts.
- **phx.gen.auth**: the generated Accounts context, `UserToken`, `Scope` and
  `UserAuth`, cut down to the password login and the session (no
  registration, magic links, remember-me cookie or sudo mode); the user signs
  in with a username (generated: email), as top-level `username` and
  `password` fields. The generated login has no throttle.
- **SSL and hosts**: no change. The generated `force_ssl` in
  `config/prod.exs` excludes the hosts `localhost` and `127.0.0.1`, which the
  harness uses, so these requests are neither redirected nor given HSTS.
  Phoenix does not check the `Host` header of HTTP requests.

Why: this is the release setup the
[Deploying with Releases](https://phoenix.hexdocs.pm/releases.html) guide
describes and `mix phx.gen.release --docker` generates. Phoenix runs as a
single node whose schedulers use every CPU, so one pool of `DB_POOL_SIZE`
connections serves the whole server.

## Production settings

| Setting | Value | Source |
| --- | --- | --- |
| Build | `MIX_ENV=prod` release (`mix release`), started by the generated `bin/server` | [Deploying with Releases](https://phoenix.hexdocs.pm/releases.html) |
| Logging | Logger `level: :warning`: no request lines (Phoenix logs them at `:info`) and no Ecto query lines (the Repo's `:log` level defaults to `:debug`) | [Logger `:level`](https://logger.hexdocs.pm/Logger.html), [Ecto.Repo `:log`](https://ecto.hexdocs.pm/Ecto.Repo.html) |
| Pool | one Ecto pool, `pool_size` = `DB_POOL_SIZE` (16); `pool_count` 1 (Ecto's default; the generated `runtime.exs` suggests several pools "for machines with several cores", and the container has 2) | [Ecto.Repo `:pool_size`, `:pool_count`](https://ecto.hexdocs.pm/Ecto.Repo.html) |
| Pool queue | `queue_target` 50 ms and `queue_interval` 2000 ms, DBConnection's defaults, unchanged: past them the pool drops checkouts on purpose ("we can refuse requests before they are sent to the database, which would otherwise increase the burden on the database"); the docs give no advice to raise them for load | [DBConnection, Queue config](https://db-connection.hexdocs.pm/DBConnection.html#module-queue-config) |
| Connection use | each Repo call checks a connection out and returns it; no request-long `Repo.checkout`/transaction (see below) | [Ecto.Repo `checkout/2`, `transact/2`](https://ecto.hexdocs.pm/Ecto.Repo.html) |
| Prepared statements | Postgrex's default `prepare: :named`; Ecto caches the prepared queries | [Postgrex](https://postgrex.hexdocs.pm/Postgrex.html) |
| Server | Bandit with its defaults (Phoenix's default adapter) | [Bandit](https://bandit.hexdocs.pm/Bandit.html) |
| Schedulers | BEAM default: one scheduler online per logical processor available, limited by the container's CPU quota (2) | [erl `+S`](https://www.erlang.org/doc/apps/erts/erl_cmd.html) |
| JIT | BeamAsm, the runtime's JIT on x86-64 and aarch64 (no setting) | [BeamAsm](https://www.erlang.org/doc/apps/erts/beamasm.html) |
| Caches | none (no response or query-result cache) | |

`/updates` and the pool queue: the 20 reads and 20 writes of
`/updates?queries=20` used to run in one `Repo.transaction`, which holds one
of the 16 connections for all 40 statements (and its row locks until the
commit). At 125 concurrent connections a trial measured 17.6% errors on that
endpoint, which matches the pool's queue: requests waited longer than
DBConnection's queue target for a connection, and the pool dropped them
(`DBConnection.ConnectionError`, answered 500). Of the two fixes, raising
`queue_target`/`queue_interval` was not chosen: the DBConnection docs present
the dropping as deliberate overload protection and do not recommend larger
values. A transaction is optional in TechEmpower's rules ("Use of
transactions is acceptable",
[test 5](https://github.com/TechEmpower/FrameworkBenchmarks/wiki/Project-Information-Framework-Tests-Overview))
and in CONTRIBUTING.md, so `/updates` now runs each `Repo.get!` and
`Repo.update!` on its own, with Ecto's default checkout per call, as
`/queries` does (`Repo.transaction` is also deprecated in Ecto 3.14 in
favour of `Repo.transact`). The other endpoints already did: none uses a
transaction or `Repo.checkout`; `PUT /world/:id` is a `Repo.get` and a
`Repo.update!`, `/me` one query, and the login a `SELECT` and an `INSERT`.
