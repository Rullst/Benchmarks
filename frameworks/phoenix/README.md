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
| Templates | HEEx: `page_html/hello.html.heex` rendered inside the root layout `layouts/root.html.heex` |
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
  test only). Phoenix, LiveView, Ecto SQL, Postgrex and Bandit are pinned
  exactly; `mix.lock` comes from the Dockerfile's `lockfile` stage.
- **Image references** written out in the `FROM` lines instead of the
  generated `ARG`s, so the harness can record their digests.
- **Secret**: `SECRET_KEY_BASE` is a fixed dummy value in the Dockerfile
  (`runtime.exs` refuses to start without it). It protects nothing here.
- **SSL and hosts**: no change. The generated `force_ssl` in
  `config/prod.exs` excludes the hosts `localhost` and `127.0.0.1`, which the
  harness uses, so these requests are neither redirected nor given HSTS.
  Phoenix does not check the `Host` header of HTTP requests.

Why: this is the release setup the
[Deploying with Releases](https://phoenix.hexdocs.pm/releases.html) guide
describes and `mix phx.gen.release --docker` generates. Phoenix runs as a
single node whose schedulers use every CPU, so one pool of `DB_POOL_SIZE`
connections serves the whole server.
