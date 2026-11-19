# Ruby on Rails

A `rails new bench --database=postgresql` application with the Dockerfile
that command generates. The four original endpoints and phase 1's database
endpoints are actions of one controller (`BenchController`); phase 2's are in
`WorldsController`, `FormsController`, `SessionsController` and
`UsersController`.

| | |
| --- | --- |
| Version | Rails 8.1.4.1, Puma 8.1.0, Thruster 0.1.27, pg 1.7.0, Bootsnap 1.26.1 on Ruby 4.0.9 (exact versions in `Gemfile.lock`) |
| Build | the generated Dockerfile: `bundle install` with `BUNDLE_DEPLOYMENT=1` and `BUNDLE_WITHOUT=development`, Bootsnap precompiled, `RAILS_ENV=production` (eager loading on), jemalloc through `LD_PRELOAD`; Rails turns YJIT on at boot (`config.yjit`, the default since Rails 7.2) |
| Server | Thruster, the HTTP proxy the generated Dockerfile starts, on `$PORT`, in front of Puma on port 3000 |
| Workers | Puma cluster mode with `WEB_CONCURRENCY` = `BENCH_WORKERS` (2) workers, the application preloaded (Puma's default in cluster mode), 3 threads per worker (the generated `RAILS_MAX_THREADS` default) |
| Database | Active Record, `World.find(1)`; each worker's pool holds up to `DB_POOL_SIZE / WEB_CONCURRENCY` = 8 connections (16 in total, never fewer than the thread count) |
| Database endpoints | `/queries`: `World.find` per row. `/updates`: per row, `World.find`, a new random value (drawn again while it equals the current one, so the row changes) and `save!`, all in one `World.transaction` with the ids sorted, so concurrent requests lock rows in the same order. Both run inside `World.uncached`: Rails enables Active Record's query cache for every request, which would answer a repeated id without a query. `/fortunes`: `Fortune.all` (no `ORDER BY`), sorted in Ruby (`sort_by(&:message)`, byte order, i.e. code points), rendered by ERB without a layout |
| Request input (phase 2) | `GET /world/:id` and `PUT /world/:id` have the route constraint `id: /\d+/`, so a non-integer id matches no route (404). `GET /worlds` and the bodies are validated with Active Model form objects (`app/forms/`, `ActiveModel::API` with `numericality` and `length` validations): 422 with the errors. The raw strings are validated, so `abc` and `1.5` fail; the JSON body's `randomNumber` must also be an `Integer` (a JSON string `"5"` passes `numericality`). Malformed JSON raises `ActionDispatch::Http::Parameters::ParseError` (400). `GET /worlds` is one `World.where(id: min..max).order(:id).limit().offset()` query. `PUT /world/:id` validates the body, then `World.find_by` (404 without a row) and `update!` (Active Record's transaction for a save) |
| CSRF | `protect_from_forgery`, on by default in `ActionController::Base` (`with: :exception`): `GET /form` and `GET /login` (`form_with`) put a masked `authenticity_token` in the form and the real token in the encrypted cookie session (`_bench_session`); a post is checked against it, and its `Origin` header, when present, against the request's base URL (`forgery_protection_origin_check`, on since Rails 5). A forged post raises `InvalidAuthenticityToken`, answered 422. The token does not change during the session. `PUT /world/:id` is exempt with `skip_forgery_protection only: :update` (a public JSON API call) |
| Sessions | `bin/rails generate authentication` (Rails 8.1), adapted to the shared `users` table: `User` with `has_secure_password` (bcrypt 3.1, the gem the generator uncomments) reading `users.password_bcrypt` (`alias_attribute :password_digest, :password_bcrypt`), `User.authenticate_by(username:, password:)`, the `Session` model and the `Authentication` concern. A login inserts a `sessions` row (table in [`db.sql`](db.sql), the SQL of the generated migration) and sets the signed `session_id` cookie; `GET /me` finds the row by that id, then loads the user through the session's association (one `SELECT` each); without a session it redirects to `/login` (302) |
| Templates | ERB, `app/views/` (the app has no layout; the HTML actions also say `layout false`) |
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

- **Authentication, phase 2**: the generator includes the `Authentication`
  concern in `ApplicationController`, which puts every action behind a login.
  Here only `SessionsController` and `UsersController` include it, so the
  other endpoints keep their stack (docs/v3-spec.md, section 2.3). The
  generated `rate_limit to: 10, within: 3.minutes` on the login is left out:
  it would refuse the harness's 125 logins from 127.0.0.1 in every round.
  The login form posts `username` (generated: `email_address`), and a login
  redirects to `/me` (generated: `root_url`; the app has no root route). The
  routes are `/login` and `/me` instead of `resource :session`.
- **Middleware**: none added. The cookie session and `protect_from_forgery`
  are part of the generated `ActionController::Base` stack that every
  endpoint already went through; they write a cookie only when an action
  uses the session.

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

## Production settings

| Setting | Value | Source |
| --- | --- | --- |
| Environment | `RAILS_ENV=production`: eager loading, no reloading, `consider_all_requests_local = false` (the generated `production.rb`) | [Configuring Rails Applications](https://guides.rubyonrails.org/configuring.html) |
| Logging | `RAILS_LOG_LEVEL=warn`, the variable the generated `production.rb` reads (generated default `info`, a line per request); Thruster `LOG_REQUESTS=false` (default: every request logged) | [Configuring: `config.log_level`](https://guides.rubyonrails.org/configuring.html), [Thruster](https://github.com/basecamp/thruster/blob/v0.1.27/README.md) |
| Workers | Puma cluster mode, `WEB_CONCURRENCY` = `BENCH_WORKERS` (2), one per CPU core | [Tuning Performance for Deployment](https://guides.rubyonrails.org/tuning_performance_for_deployment.html) |
| Threads | 3 per worker, the generated `RAILS_MAX_THREADS` default, kept as the guide advises (with Ruby's GVL an application "is unlikely to benefit from more than 3 threads") | [Tuning Performance for Deployment](https://guides.rubyonrails.org/tuning_performance_for_deployment.html) |
| Pool | `max_connections` = `DB_POOL_SIZE / WEB_CONCURRENCY` = 8 per worker; **6 of the 16 connections are used** (see below) | [Configuring: Database Pooling](https://guides.rubyonrails.org/configuring.html#database-pooling) |
| Prepared statements | the PostgreSQL adapter's default: on, up to 1000 per connection | [Configuring a PostgreSQL Database](https://guides.rubyonrails.org/configuring.html#configuring-a-postgresql-database) |
| Query cache | Rails' per-request query cache stays on; `/queries` and `/updates` bypass it with `World.uncached`, since the TechEmpower rules forbid answering a repeated id from a cache | |
| JIT | **YJIT on**: `config.yjit` defaults to `!Rails.env.local?` in the 8.1 defaults (Rails enables YJIT since 7.2 on Ruby 3.3+), and the official `ruby` image is built with `--enable-yjit` on x86-64. Not checked at run time here | [Tuning: YJIT](https://guides.rubyonrails.org/tuning_performance_for_deployment.html), [Rails 7.2 release notes](https://guides.rubyonrails.org/7_2_release_notes.html), [ruby image Dockerfile](https://github.com/docker-library/ruby/blob/master/4.0/slim-trixie/Dockerfile) |
| Memory allocator | jemalloc through `LD_PRELOAD`, as the generated Dockerfile sets it | [Tuning: Memory Allocators](https://guides.rubyonrails.org/tuning_performance_for_deployment.html) |
| Proxy | Thruster in front of Puma, as the generated Dockerfile starts it; its cache does not store Rails' `private` responses and it compresses only for clients that send `Accept-Encoding` | [Thruster](https://github.com/basecamp/thruster/blob/v0.1.27/README.md) |
| Structure | Thruster (one Go process) and Puma (2 workers x 3 threads) run in the same container and share its 2 vCPUs | |

**Connections in use: 6 of 16.** Each Puma thread handles one request at a
time and uses at most one Active Record connection, which the pool opens only
when a thread needs one. With the Rails and Puma production defaults, 2
workers x 3 threads, at most 6 connections are ever open, although each
worker's pool may hold 8 (the suite's 16 divided between the two workers).
Using all 16 would mean 8 threads per worker. The tuning guide keeps the
generated 3: an application that spends less than half its time on I/O "is
unlikely to benefit from more than 3 threads", and more threads "may severely
hurt latency". So the threads stay at the generated default and 10 of the
suite's connections stay unused.
