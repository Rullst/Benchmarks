# Ruby on Rails

A `rails new bench --database=postgresql` application with the Dockerfile
that command generates, and the four endpoints as actions of one controller.

| | |
| --- | --- |
| Version | Rails 8.1.4.1, Puma 8.1.0, Thruster 0.1.27, pg 1.7.0, Bootsnap 1.26.1 on Ruby 4.0.9 (exact versions in `Gemfile.lock`) |
| Build | the generated Dockerfile: `bundle install` with `BUNDLE_DEPLOYMENT=1` and `BUNDLE_WITHOUT=development`, Bootsnap precompiled, `RAILS_ENV=production` (eager loading on), jemalloc through `LD_PRELOAD`; Rails turns YJIT on at boot (`config.yjit`, the default since Rails 7.2) |
| Server | Thruster, the HTTP proxy the generated Dockerfile starts, on `$PORT`, in front of Puma on port 3000 |
| Workers | Puma cluster mode with `WEB_CONCURRENCY` = `BENCH_WORKERS` (2) workers, the application preloaded (Puma's default in cluster mode), 3 threads per worker (the generated `RAILS_MAX_THREADS` default) |
| Database | Active Record, `World.find(1)`; each worker's pool holds up to `DB_POOL_SIZE / WEB_CONCURRENCY` = 8 connections (16 in total, never fewer than the thread count) |
| Templates | ERB, `app/views/bench/hello_html.html.erb` (the app has no layout) |
| Logging | `RAILS_LOG_LEVEL=warn`: the generated `info` level writes lines for every request. Thruster's request log is off (`LOG_REQUESTS=false`) |
| Image | `ruby:4.0.9-slim-trixie` (the generated `ruby:$RUBY_VERSION-slim`, tag written out) |

The application is what `rails new` generates without the parts it does not
use: Active Job, Active Storage, Action Mailer, Action Mailbox, Action Text,
Action Cable, the asset pipeline, JavaScript and Hotwire, Jbuilder, the Solid
adapters, Kamal and the development and test gems. Every request goes
through Rails' default middleware stack and the generated
`ApplicationController` (`ActionController::Base` with
`allow_browser versions: :modern`, which only rejects old browser versions;
the harness and the load generator are not browsers).

Changes from the generated files, and why:

- **Pool size** (`config/database.yml`): `DB_POOL_SIZE / WEB_CONCURRENCY`
  per worker instead of `RAILS_MAX_THREADS` (5), so the server never opens
  more than the suite's 16 connections. The connection comes from
  `DATABASE_URL`, which Rails merges into the `production` entry.
- **No `db:prepare` at start-up**: the generated `bin/docker-entrypoint` only
  runs `bin/rails db:prepare`, which would create Rails' `schema_migrations`
  and `ar_internal_metadata` tables in the benchmark database. The schema
  already exists, so the image has no entrypoint.
- **Ports**: Thruster listens on `$PORT` (`HTTP_PORT`; generated: 80, which
  would need root, while the image runs as uid 1000) and starts Puma on its
  default target port 3000.
- **SSL**: `config.force_ssl` and `config.assume_ssl` stay commented out, as
  `rails new` generates them for its default Kamal deployment, where
  kamal-proxy terminates TLS. There is no TLS here, and `force_ssl` would
  redirect every request to `https://`.
- **Hosts**: no change. The generated production config leaves `config.hosts`
  empty, so Host authorization allows every host, including 127.0.0.1.
- **Secret**: `SECRET_KEY_BASE` is a fixed dummy value in the Dockerfile
  (the generated setup reads encrypted credentials with `RAILS_MASTER_KEY`).
  It protects nothing in this benchmark.
- **Versions**: exact versions in the `Gemfile` (generated: `~> 8.1.4`,
  `>= 8.1.4.1`, and `puma >= 5.0`); `Gemfile.lock` comes from the
  Dockerfile's `lockfile` stage (`bundle lock --add-platform=x86_64-linux`,
  as `rails new` runs it).

Why: this is the production setup Rails generates and documents. The
[Tuning Performance for Deployment](https://guides.rubyonrails.org/tuning_performance_for_deployment.html)
guide recommends one Puma process per CPU core through `WEB_CONCURRENCY`,
keeps the default of 3 threads, and relies on YJIT (enabled by Rails) and on
jemalloc (preconfigured in the generated Dockerfile). Thruster is part of the
generated Dockerfile; Rails responses are `Cache-Control: private`, so its
cache does not store them, and it compresses only for clients that send
`Accept-Encoding`, which the harness does not.
