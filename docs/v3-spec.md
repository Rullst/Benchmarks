# Benchmarks v3, phase 2: request handling, writes, forms and sessions

v3 is the suite's third generation: v1 is the hand-run laptop measurement of
22 June 2026 ([history/2026-06-22-laptop.md](../history/2026-06-22-laptop.md)),
v2 the GitHub Actions rebuild of 15 November 2026 (results up to Rullst
13.0.0-alpha.5, measured with bombardier), and v3 this work: phase 1 (the
database endpoints, server efficiency) and phase 2 (this document). The
branches keep their internal `feat/v2*` names.

Status: integrated on branch `feat/v2` (fork `venelouis/Benchmarks`): the
harness, the conformance checks and all 16 implementations follow this
document (the Axum reference first, then the Rust, dynamic and compiled
groups, merged from their implementation branches), and the maintainer's
decisions on the open questions are recorded in section 11 (two of them, 4
and 5, are still pending the maintainer's confirmation and each lives in one
place). Written on 2026-11-19 against `upstream/main` (2727378) and the
phase-1 branch `feat/v2-phase1`; sections 2, 3, 5, 6, 9 and 10 were updated
with what the implementations found. Section 10 is the per-folder checklist.

**Scoring revision (2026-11-19, after an independent review of the first
full trial).** The scoring and round procedure described in the README's
"How the scores are computed" and "Method" replace what this document says
about them: client-bound runs are scored by requests per CPU-second of the
server and PostgreSQL together; a load-generator-bound run whose server used
less than 75% of its vCPUs is not comparable; the 1% error rule applies to
every scored run (not only Application); ties come from an A/A control
(`frameworks/axum-control`) and, since 2026-11-20, also from each
implementation's spread between its jobs and a pooled floor (section 12);
the categories are Hello world (`/text`,
`/json`, `/html`), Database (`/db-single` and the three TechEmpower
endpoints), Application, Memory and Startup (with floors), plus a Stability
check (Tiers 2 and 4, pass or fail); Rullst's minimal configuration is an
unranked diagnostic; the overall ranking is optional (off by default); each
endpoint is warmed up immediately before its run, for 15 s on JIT runtimes;
rounds run in ABBA order on 3 jobs per implementation (2 until 2026-11-20,
section 12); conformance adds a concurrent step (125 connections, 3 s, no
error allowed). The endpoint contracts below are unchanged.

Phase 1 adds the TechEmpower-style `/queries`, `/updates` and `/fortunes`, a
requests-per-server-CPU-second efficiency metric and the CPU split
experiment. Phase 2 answers the rest of the review: the suite has no route
parameters, query strings, request bodies, validation, forms, CSRF, writes
of one record, contention between requests or sessions.

Phase 2 adds five endpoints:

| Name (bench.json) | Requests | What it exercises |
| --- | --- | --- |
| `world` | `GET /world/{id}`, a random id per request | path parameter, primary-key read of varying rows, JSON |
| `worlds` | `GET /worlds?min=&max=&limit=&page=` | query-string parsing and validation, a filtered, ordered, paginated query, a JSON array |
| `world-update` | `PUT /world/{id}` with `{"randomNumber": n}` | JSON body parsing, validation, one write, the stored row returned |
| `form` | `GET /form` once per session, then `POST /form` (urlencoded) | form parsing, CSRF verification, validation, escaping user input in a template |
| `me` | `POST /login` once per session, then `GET /me` | session lookup and loading the signed-in user |

## 1. Decisions at a glance

| Question | Decision | Why (details in the section) |
| --- | --- | --- |
| Load generator | **wrk 4.2.0** (built from the pinned source tarball), for all endpoints, replacing bombardier in the same change, with a Lua status hook on the phase-2 workloads; oha 1.16.0 as the documented fallback | §7: wrk varies URL, headers and body together per request (needed for one session per connection) and does the most requests per client CPU-second (1.2-1.3x bombardier, 1.1x oha on one vCPU; +25% on Axum's `/db-single`) |
| Random ids | The harness pre-builds the requests (all 10,000 ids, shuffled with a fixed seed) and wrk cycles through them | uniform ids, no per-request formatting in the client, the same mix for every implementation |
| Invalid input | **400 or 422** both conform, for query strings and bodies, and nothing may be written; 422 is recommended for well-formed input that fails validation | invalid requests are only sent by the conformance check, never under load, so the code costs nothing in the results; the frameworks' defaults split between the two (§2.6) |
| CSRF | The framework's built-in protection, else the platform's standard library, else the library the framework's docs recommend, else the most-used maintained library. The harness submits the form like a browser (hidden fields, cookies, `Origin`, `Sec-Fetch-Site: same-origin`). CSRF stays in the timing; the results show each implementation's CSRF design | §5 |
| Sessions | The framework's default production mechanism for a signed-in user (its auth generator or documented auth package); without one, the documented or most-used session library, with its PostgreSQL store when it has one, else its signed or encrypted cookie store. `/me` must read the user's row on every request. The results show each implementation's session store | §6 |
| Sessions in the load | 125 sessions (one per connection, like 125 signed-in users), obtained in every round before the phase-2 warm-up, cycled across requests | no single hot session row; the same work for every store |
| Tables a framework owns | `frameworks/<name>/db.sql`, declared in bench.json and applied by the harness; no schema changes at start-up | session tables differ per framework; start-up time stays comparable |
| Tier | All five in Tier 1: 125 connections, 10 s, after a 5 s warm-up, measured at the end of the round, after Tier 4 | like phase 1's endpoints; reads before writes; after Tier 4 because 125 logins with a memory-hard hash leave allocator memory that would distort the RAM of Tiers 3-4 (§8) |
| Rankings | A new **Application** category: geometric mean of the five capacity ratios; no score for a run with more than 1% errors (since the 2026-11-19 revision, the rule of every scored run) | same method as phase 1's Database category |
| Contention | A **hot-rows** run: `PUT /world/{id}` on ids 1-10, Tier 1 connections and duration, after the Tier 1 runs; errors, timeouts and p99 reported, not ranked | a reviewer asked for contention; needs no new endpoint (§3.4) |
| Coexistence | bench.json `"endpoints"` (phase 1's capability list) gains the five names; an implementation that does not declare one is "incomplete" in the Application category, as in phase 1 | §8 |

## 2. Common rules

### 2.1 Declaring the endpoints

An implementation serves a phase-2 endpoint only once its bench.json lists
the name in `"endpoints"` (phase 1's mechanism in `bench/common.py`). The
harness checks and measures only the declared endpoints, so the folders can
be done in any order. Phase 2 adds to bench.json:

```json
"endpoints": ["text", "json", "db-single", "html", "queries", "updates", "fortunes",
              "world", "worlds", "world-update", "form", "me"],
"db_setup": "db.sql",
"phase2": {
  "validation": "Laravel validator ($request->validate)",
  "csrf": {"design": "token", "mechanism": "PreventRequestForgery (web group)", "source": "built-in"},
  "session": {"store": "postgresql", "mechanism": "session guard, database driver", "source": "built-in"},
  "write_csrf": null
}
```

- `phase2.csrf.design` is `token` (a secret the client must echo: synchronizer
  token, double-submit cookie, masked or signed variants) or
  `fetch-metadata` (no token: `Sec-Fetch-Site`/`Origin` checks). The
  conformance check runs the tampered-token case only for `token`.
- `phase2.csrf.source` and `phase2.session.source` are `built-in`,
  `generator` (code the framework's generator writes), `stdlib` (the
  language's standard library), `documented` (a package the framework's
  docs recommend) or `library` (the most-used maintained package). The
  results print them next to the numbers.
- `phase2.session.store` is `cookie-signed`, `cookie-encrypted`,
  `postgresql` or `memory` (process memory; only for single-process servers).
- `phase2.write_csrf` is `null` (the default: `PUT /world/{id}` is sent
  without cookies, as a public JSON API call) or
  `{"cookie": "<name>", "header": "<name>"}` for a framework whose production
  stack refuses every cookieless state-changing request and documents no
  exemption for unauthenticated API routes (Rullst as generated, §3.3): the
  harness then takes that cookie from `GET /form` and sends it with its value
  in the header, as a same-site script (htmx, `fetch`) does.
- `harness.py validate` checks the block: it is required once a phase-2
  endpoint is declared (`csrf` with `form`, `session` with `me`), and
  `db_setup` must name a `.sql` file in the folder.

### 2.2 Database

- `bench/db/phase2.sql` (on this branch) creates `users(id, username,
  display_name, password_bcrypt, password_argon2id)` with 1,000 accounts
  `user1`..`user1000`, all with the password `bench-password`. It runs after
  `init.sql` because the harness mounts `bench/db` as the entrypoint
  directory, so `init.sql` is not edited. The two hash columns let each
  implementation use its framework's standard hasher; the comment in the
  file gives the prefixes that Laravel (`$2y$`), Spring (`{bcrypt}`) and
  Django (`bcrypt$`, `argon2`) expect. Login is not timed.
- Tables a framework owns (Django's `django_session`, Laravel's `sessions`,
  Rails 8's `sessions`, Phoenix's `users_tokens`, Rullst's session registry,
  tower-sessions' `tower_sessions.session`, Loco's `loco_sessions`, …) go in
  `frameworks/<name>/db.sql`, written from the framework's own migration
  (for example `manage.py sqlmigrate sessions 0001`). bench.json declares it
  with `"db_setup"`. The harness applies it once per job before conformance,
  in one transaction (`psql --single-transaction`), records the tables it
  created (the tables outside PostgreSQL's own schemas that did not exist
  before), and empties them (`TRUNCATE`) at the start of every round, after
  phase 1's `reset_tables`. Implementations must not create or migrate tables
  at start-up: start-up time is ranked. Because the tables are emptied every
  round, they hold only per-session data, never reference data. In a job the
  file is applied after the framework's and before Axum's, in the same
  database, so it must not create Axum's `tower_sessions.session`. The CI
  check `harness.py db-check` applies every folder's file in a rolled-back
  transaction (so the file must not contain `BEGIN`/`COMMIT` or statements
  that cannot run in a transaction).
- `users` is not changed by any measured request. The conformance check
  changes `display_name` and restores it.
- **Rehash on login.** The stored hashes are bcrypt cost 10 and Argon2id
  `m=19456,t=2,p=1`. A framework that rehashes a password whose parameters
  differ from its configured ones writes `users` on every login and slows
  the 125 logins of every round: Laravel's `rehash_on_login` (on by default,
  bcrypt cost 12) and Django's hasher upgrade (`must_update`, bcrypt cost 12
  by default). Configure the hasher with the stored parameters, the way the
  framework documents: Laravel `BCRYPT_ROUNDS=10` (its Dockerfile), Django a
  `BCryptPasswordHasher` subclass with `rounds = 10` (`world/hashers.py`).

### 2.3 Framework mechanisms

Each endpoint uses the framework's standard mechanism for each concern, in
this order of preference: built into the framework; generated by the
framework's own generator; the language's standard library; a package the
framework's documentation recommends; the most-used maintained package
(released in the last 24 months, no deprecation or open unfixed advisory).
The folder README names what it uses and why; section 9 lists the expected
choice for every implementation.

Existing endpoints keep their current middleware stack where the framework
documents a way to scope the new mechanisms (route groups, pipelines,
security matchers, plugin encapsulation): `/form`, `/login` and `/me` go in
the browser-facing group. The README says when a mechanism is global and
also runs for the existing endpoints (decision 2). Rullst as generated keeps
its global production stack, as `cargo rullst new` generates it.

### 2.4 Requests the load generator sends

- HTTP/1.1 keep-alive, `Host: 127.0.0.1:8080`, no `Accept-Encoding` (no
  compression), as today.
- `POST /form` also sends what a browser sends for a same-origin form
  submission: `Content-Type: application/x-www-form-urlencoded`,
  `Origin: http://127.0.0.1:8080`, `Sec-Fetch-Site: same-origin`, the cookies
  and the hidden fields of the session's form page.
- `PUT /world/{id}` sends `Content-Type: application/json`.
- `GET /me` sends the session's cookies (or `Authorization: Bearer`, see
  §6.3) and `Accept: application/json`.

### 2.5 Failures under load

Every request the load generator sends is valid, so every response that is
not 2xx is a failure (non-2xx), like a transport error or timeout. With wrk,
see §7.4 for how statuses are counted. A run is reported with its error
rate; a phase-2 run with an error rate above 1% gets no capacity ratio in
the Application category (the cell shows the error rate instead), because
fast error responses would otherwise raise the score.

### 2.6 Invalid input: 400 or 422

Conformance accepts **400 or 422** for every invalid query string or body,
and checks that nothing was written. Reasons:

- invalid requests are sent only by the conformance check, so the status
  costs nothing in the measurement;
- RFC 9110 allows both: 400 for a request the server will not process, 422
  for well-formed content it cannot process;
- the frameworks' default validation pipelines split: 422 in FastAPI,
  Laravel, Rullst (`ValidatedJson`/`ValidatedForm`), Axum's `Json` data
  errors and Phoenix's generated fallback controller; 400 in Spring,
  ASP.NET Core, NestJS, Fastify, Actix and Topcoat, and in Loco's validators
  for a failed rule (a body they cannot deserialize is Axum's `Json` or
  `Form` rejection inside them: 422, as in the Loco folder). A single
  required code would make about half of the implementations replace their
  framework's error handling.

422 is recommended when the framework makes it a one-line choice (decision
1: 400 and 422 both conform).

The refusal must be an error response, not a redirect: these are API
requests (`Accept: */*` on `GET /worlds`, no `Accept` on the PUT). Laravel's
`ValidationException` redirects back (302) unless the request expects JSON,
so the Laravel folder renders the `api` group's exceptions as JSON with the
skeleton's `shouldRenderJsonWhen` hook (`bootstrap/app.php`): 422 with the
errors. (The skeleton's `is('api/*')` test does not match routes served
without the `/api` prefix, so the hook recognises the group's middleware.)

### 2.7 Strict numbers in JSON bodies

`randomNumber` in a JSON body is a JSON integer: the string `"5"` is
invalid (400 or 422, nothing written; conformance sends
`{"randomNumber": "5"}`, §3.3). Query-string and form values are text by
nature and are parsed from it. Many validation layers convert a string to a
number by default, so the implementation sets the documented option or
checks the parsed value's type:

| Implementation | Default | What the folder does |
| --- | --- | --- |
| Spring Boot (Jackson) | coerces scalars | `spring.jackson.mapper.allow-coercion-of-scalars=false` (`application.properties`) |
| ASP.NET Core (System.Text.Json, web defaults) | `AllowReadingFromString` | `ConfigureHttpJsonOptions(o => o.SerializerOptions.NumberHandling = JsonNumberHandling.Strict)` |
| Fastify (Ajv) | `coerceTypes: 'array'` for every part of the request | a validator compiler without coercion for the body (`httpPart === 'body'`), as the Validation and Serialization reference shows for per-part options; the path parameter keeps coercion |
| Laravel | `integer` accepts `"5"` | the `integer:strict` rule on the JSON body |
| FastAPI (Pydantic, lax mode) | `int` accepts `"5"` | `StrictInt` on the body model |
| Django | `forms.IntegerField` accepts `"5"` | `clean_randomNumber` also checks that the parsed JSON value is an `int` |
| Rails | `numericality` accepts `"5"` | an extra validation that the value is an `Integer` |
| Phoenix | Ecto's `cast/3` turns `"5"` into 5 | a changeset check that the raw value `is_integer` |

The rest refuse a string with their defaults: serde in the Rust folders,
class-validator's `@IsInt` without `transform` in NestJS, Go's
`encoding/json` into an integer in Gin.

## 3. Read and write endpoints

### 3.1 `GET /world/{id}`

**Contract**

- `id` is a path segment, a base-10 integer.
- `1 <= id <= 10000`: 200, `application/json`, `{"id": id, "randomNumber": n}`
  where `n` is the row's current `randomnumber`, read from the database on
  every request with the framework's ORM (or its database layer where it
  has no ORM), by primary key.
- An integer with no row (`0`, `10001`): **404**.
- A segment that is not an integer (`abc`, `1.5`): **400, 404 or 422**
  (typed route constraints answer 404, typed extractors 400 or 422).

**Conformance**

1. For 5 random ids: change the row with `psql`, request it, compare the
   parsed JSON with the row (the response must follow the database).
2. `GET /world/0` and `GET /world/10001`: 404.
3. `GET /world/abc`: 400, 404 or 422.
4. Media type and keep-alive as for the existing endpoints (on 200
   responses; after an error response the harness opens a new connection,
   because a server may close it without `Connection: close`).
5. pg_stat_statements (phase 1): 20 requests run at least 20 SELECT
   statements on `world`.

**Load profile:** Tier 1. The workload is the 10,000 ids in a shuffled
order (`bench/workload.py: world_by_id`), each wrk thread starting at a
different offset, so every id is read about equally often.

### 3.2 `GET /worlds`

**Contract**

| Parameter | Default | Valid values |
| --- | --- | --- |
| `min` | 1 | integer, 1..10000 |
| `max` | 10000 | integer, 1..10000, and `min <= max` |
| `limit` | 20 | integer, 1..100 |
| `page` | 1 | integer, 1..1000 |

- Response: 200, `application/json`, a JSON array of
  `{"id": .., "randomNumber": ..}` objects: the rows with
  `min <= id <= max`, ordered by `id` ascending, `limit` rows starting at
  offset `(page - 1) * limit`. A page past the end is `[]`.
- One query per request through the ORM's query builder, with the filter,
  `ORDER BY`, `LIMIT` and `OFFSET` done by PostgreSQL (not in application
  code).
- Parameters are parsed and validated with the framework's validation
  mechanism (§9). A parameter that is present but not a base-10 integer, out
  of range, or `min > max`: **400 or 422**. Unknown parameters are ignored.
- Filtering on the primary key keeps the database's share of the work small
  and the same for everyone (PostgreSQL shares the client vCPUs; phase 1).

**Conformance**

1. No parameters: the first 20 rows (ids 1..20).
2. `min=500&max=600&limit=7&page=3`: ids 514..520 with their current values.
3. `min=9990&max=10000&limit=100&page=1`: 11 rows; `page=2`: `[]`.
4. Each of `limit=0`, `limit=101`, `limit=abc`, `min=0`, `max=10001`,
   `min=600&max=500`, `page=0`: 400 or 422.
5. Values are compared with the table (read with `psql` before the check).
6. pg_stat_statements: one request runs exactly one SELECT on `world`
   (no row-by-row loading).

**Load profile:** Tier 1. 2,000 pre-built queries: a random 1,000-id
window (`min` in 1..9001, `max = min + 999`), `limit=20`, `page` 1..5
(`worlds_pages`). Every response has 20 rows.

### 3.3 `PUT /world/{id}`

**Contract**

- Body: a JSON object with an integer `randomNumber`, 1..10000 (a JSON
  number: the string `"5"` is invalid, §2.7). Other keys are ignored.
- Valid: the row's `randomnumber` is set to the value, and the response is
  200, `application/json`, `{"id": id, "randomNumber": n}`, the row as
  stored.
- ORM implementations use the ORM's usual way to change one record (load
  it, set the field, save it, in whatever transaction the ORM uses by
  default). Implementations without an ORM run one
  `UPDATE … RETURNING`.
- It is a public JSON API call: no cookies, so CSRF protection does not
  apply. Frameworks whose CSRF check is global exempt the route the
  documented way (Laravel's `api` routes, Phoenix's `:api` pipeline, Rails'
  `ActionController::API` or `skip_forgery_protection`, Django's
  `csrf_exempt`, a Spring Security matcher that leaves it out). Rullst's
  production `Server` refuses any state-changing request without its CSRF
  cookie and exempts only authenticated machine endpoints
  (`MachineEndpointPolicy`), so Rullst as generated declares `write_csrf`
  (§2.1) and the load sends `rullst_csrf` plus `X-CSRF-Token` (open
  question 7).
- No row with that id (`0`, `10001`, with a valid body): **404**.
- Non-integer id: 400, 404 or 422. Malformed JSON, a missing or non-integer
  `randomNumber`, or a value outside 1..10000: **400 or 422**, and the row
  is unchanged. When both the id and the body are invalid, any of those
  statuses.

**Conformance**

1. For 5 random ids, each with a value other than the stored one: the
   response equals the sent value, and `psql` reads the same value back.
2. `{"randomNumber": 0}`, `{"randomNumber": 10001}`, `{"randomNumber": "5"}`,
   `{}`, `{"randomNumber": 5` (malformed): 400 or 422; the row keeps its
   value.
3. `PUT /world/10001` with a valid body: 404.
4. pg_stat_statements: 20 requests to 20 different ids run at least 20
   UPDATE statements on `world`. The harness reads the 20 rows first and
   sends each a value other than the stored one, because an ORM that tracks
   changes (Rullst's RowSnapshot, ActiveRecord, Eloquent, Ecto, SQLAlchemy)
   rightly writes nothing when the value does not change.
5. With `write_csrf`: the same PUT without the cookie and header is refused
   (403) and writes nothing.
6. The table is restored afterwards (phase 1's `reset_tables`).

**Load profile:** Tier 1, measured last in the round (it writes). 10,000
requests: the ids 1..10000 shuffled, each with a random value
(`put_world`). With 125 connections over 10,000 rows two requests rarely
hit the same row at once, so this measures one write per request, not lock
contention (§3.4 does). Phase 1's `synchronous_commit=off` applies.

### 3.4 Write contention: hot rows

Decision 5 (pending confirmation). After the Tier 1 runs, an implementation
that declares `world-update` gets one more run of the same `PUT /world/{id}`
with the Tier 1 connections (125) and duration (10 s), but with 2,000
pre-built requests whose ids are drawn from 1..10 only (`hot_rows` in
`bench/workload.py`, `"hot_rows"` in `bench/config.json`; removing that key
removes the run). Every connection writes the same ten rows, so requests
wait for each other's row locks and the run measures lock waits and the
ORM's transaction handling. The results report its requests/s, p50 and p99
latency, errors and timeouts next to Axum's (`hot_rows.*` in the round
record); it is not ranked. It needs no implementation work beyond
`world-update`.

## 4. `/form`

**Contract**

- `GET /form`: 200, `text/html`, rendered with the template engine, a page
  with one `<form method="post" action="/form">` containing a text input
  `name`, a number input `randomNumber`, a submit button and whatever
  hidden CSRF field the framework adds. It may set cookies. Not measured.
- `POST /form`, `application/x-www-form-urlencoded`, fields `name`
  (1..64 characters) and `randomNumber` (integer 1..10000), plus the CSRF
  field. Processing: CSRF verification by the framework's mechanism (§5),
  parsing and validation by its form mechanism, then a page rendered with
  the template engine, the name escaped:
  `<!DOCTYPE html><html><head><title>Form</title></head><body><h1>Hello, {name}</h1><p>{randomNumber}</p></body></html>`,
  200, `text/html` with UTF-8. No database access, no redirect.
- Invalid fields with a valid CSRF token: anything except that page with
  200: the framework's usual answer (re-render with errors, 200 or 422;
  Laravel's redirect back, 302; 400). Allowed statuses: 200, 302, 303, 400,
  422.
- A forged request: rejected with 400, 403, 419 (Laravel) or 422 (Rails'
  `InvalidAuthenticityToken`); never the success page.

**Conformance**

1. `GET /form`: 200, `text/html`; the harness parses the first `<form>`
   whose action is `/form` (or empty), collects its `<input type="hidden">`
   fields and the `Set-Cookie` cookies (the session pair).
2. A valid post with the pair and the browser headers, `name` set to
   `<b>"Tom" & 'Jérôme'</b>`: 200 and the page above. Bodies are compared
   with phase 1's HTML token comparison, so `&#39;`, `&#x27;` and `&apos;`
   are equal and whitespace at the end is ignored.
3. The same post 3 more times with the same pair: 200 each time (the pair
   is reusable, which the load relies on).
4. Forged cross-site post: the cookies, no hidden fields,
   `Origin: http://attacker.invalid`, `Sec-Fetch-Site: cross-site`:
   400, 403, 419 or 422.
5. Only for `phase2.csrf.design = token`: (a) the hidden token changed in
   one character, and (b) the hidden fields without the cookies, both
   without `Origin` and `Sec-Fetch-Site` (an older browser): 400, 403, 419
   or 422. Without those headers Laravel's token path runs (§5.2).
6. Invalid fields with a valid pair (`name` empty, `name` of 65
   characters, `randomNumber=0`, `randomNumber=abc`): one of the allowed
   statuses and not the success page.

**Load profile:** Tier 1. In every round, before the phase-2 warm-up (§8), the harness runs
`GET /form` 125 times (8 at a time), one per future connection, and keeps
125 pairs. The workload is 2,000 posts with random valid fields, the pairs
used in turn (`form_posts`, joint pairing: each request's cookie matches its
hidden token).

## 5. CSRF

### 5.1 Rule

1. **Mechanism:** the framework's built-in CSRF protection, as its
   documentation enables it for browser forms; else the language's standard
   library (Go 1.25's `net/http.CrossOriginProtection`); else the package the
   framework's docs recommend; else the most-used maintained package (§2.3).
2. **Client:** the harness acts as a browser that loaded the form once:
   it sends the form's hidden fields and cookies, `Origin` and
   `Sec-Fetch-Site: same-origin`. It does not need to know each framework's
   token, field or cookie names, and header-based designs (Topcoat, Go,
   NestJS, Laravel's first check) see the headers a browser sends; without
   them those checks would pass by default without doing any work.
3. **Obtaining the pair:** once per session, before measuring (§4). Every
   chosen mechanism accepts the same pair for the whole session: the
   research for §9 found no per-request rotation, the implementations
   confirmed it (`asgi-csrf` included: its token is the signed value of the
   `csrftoken` cookie, which does not change during the session), and
   conformance step 3 of §4 would catch a rotating token. ASP.NET Core binds
   its token to the user, so the pair is fetched while anonymous and used
   anonymously.
4. **Cookieless posts:** `asgi-csrf` checks a form post only when it
   carries the `csrftoken` cookie, unless the path is listed in
   `always_protect`; the FastAPI folder lists `/form` and `/login`, so the
   forged post without cookies (§4, step 5b) is refused (403).
5. **Reporting:** the results name the design (`token` or
   `fetch-metadata`), the mechanism and its source next to `/form`.
6. **Scope:** as §2.3 and decision 2. NestJS's `app.enableCsrfProtection()`
   has no per-route form (its `exclude` option is consulted only for a
   request it would refuse), so it runs for every request: for a `GET` it is
   a method check, and the cookieless `PUT /world/{id}` carries no browser
   headers and passes. Rullst as generated keeps its global stack, so its
   PUT carries the CSRF pair (`write_csrf`, §3.3). The folder READMEs say so.

### 5.2 Is it fair to keep CSRF in the timing?

Yes, with the design shown next to the number:

- every framework that protects forms by default (Rails, Laravel, Django,
  Phoenix's browser pipeline, Spring Security, ASP.NET Core Razor/antiforgery,
  Topcoat, Rullst as generated) runs the check on every real form post, so a
  form endpoint without it would measure a configuration nobody deploys;
- the cost differs by design, and that is a real difference between the
  frameworks, not noise: a header comparison (Topcoat, Go, NestJS), a
  constant-time comparison with a cookie (Rullst, Django, Fastify, the
  library choices), decrypting the encrypted session cookie (Rails) or
  verifying the signed one (Phoenix), a Data Protection decryption of two
  tokens (ASP.NET Core), or a session load from a store (Laravel: the
  database; Spring: memory);
- **Laravel** accepts `Sec-Fetch-Site: same-origin` before comparing tokens,
  but its `web` group still loads and saves the session for the request. The
  load sends the header like a browser, so Laravel's token comparison does not
  run; conformance step 5 checks the token path separately.
- Frameworks that need a library are measured with that library, which the
  results name. A faster or slower library would change their number.

An unprotected control endpoint (`/form` without CSRF) would separate the
check's cost from the rest; it is not part of this phase (decision 3).

## 6. Sessions: `POST /login` and `GET /me`

### 6.1 Contract

- `GET /login`: 200, `text/html`, a page with one
  `<form method="post" action="/login">` with inputs `username` and
  `password` and whatever hidden CSRF field the framework adds to its login
  form. Not measured; the harness parses it like `GET /form` and submits its
  hidden fields and cookies with the login.
- `POST /login`, urlencoded `username` and `password`. Correct
  credentials: a session is established and the response is 200, 204, 302 or
  303 (redirecting after login is the norm in the full-stack frameworks); it
  sets the session cookie(s). The password is checked with the framework's
  standard hasher against `users.password_bcrypt` or
  `users.password_argon2id`. Wrong password: 200 (form re-rendered), 302,
  303, 400, 401 or 422, and no session.
- `GET /me` with a valid session: 200, `application/json`,
  `{"id": id, "username": "...", "displayName": "..."}`. The handler resolves
  the session with the framework's mechanism and **reads the user's row from
  PostgreSQL through the ORM on every request**, by the id the session holds.
  Frameworks that keep the principal in the session or cookie (Spring
  Security, ASP.NET Core cookie auth, the cookie stores) still read the row,
  as an application does to get the current user's data. `GET /me` is sent
  with `Accept: application/json`, so a browser pipeline that negotiates the
  format must accept JSON: Phoenix's generated `:browser` pipeline has
  `plug :accepts, ["html"]` (406 otherwise), and the Phoenix folder makes it
  `["html", "json"]`.
- `GET /me` without a valid session: 401 (recommended), 403, or a 302/303
  redirect to the login page (Rails', Django's, Phoenix's and Spring's
  default for browser routes); never 200.

### 6.2 Which store: the framework's default, not a common one

The two options were "each framework's default production store" and "one
fixed store for everyone". Phase 2 uses the default:

- **Rule:** the mechanism the framework's own generator or documented auth
  package sets up for a signed-in user, with the store it uses by default in
  production: Rails 8's authentication generator (a `sessions` row looked up
  through a signed cookie), Phoenix's `phx.gen.auth` (`users_tokens`), Django's
  `contrib.auth` with database sessions, Laravel's session guard with the
  `database` driver, Spring Security's form login with the servlet
  container's in-memory session, ASP.NET Core's cookie authentication, Loco's
  `auth_session` (signed cookie), Topcoat's `session` tokens, Rullst's
  `make:auth` session registry. A framework without one uses the session
  library its docs recommend, else the most-used maintained one, **with that
  library's PostgreSQL store when it has one** (Axum: tower-sessions with
  `tower-sessions-sqlx-store`), **else its signed or encrypted cookie store**
  (Actix: `actix-session` `CookieSessionStore`; FastAPI: Starlette's
  `SessionMiddleware`; Fastify: `@fastify/secure-session`; Gin:
  `gin-contrib/sessions` cookie store). The PostgreSQL-first preference
  matches what the generators of Rails 8, Phoenix, Django, Laravel and Rullst
  produce, so most implementations compare like with like, including the Axum
  baseline that every ratio uses. Redis and Memcached are not available in
  the harness and are not used.
- **Why not one fixed store:** no store is built into all 16. A fixed
  PostgreSQL store would need hand-written stores in Phoenix (`Plug.Session`
  has none), ASP.NET Core (an `ITicketStore`), Actix (no PostgreSQL store)
  and FastAPI (Starlette's sessions are cookie-only); a fixed cookie store
  would need one in Spring (servlet sessions only) and would replace the
  generated auth of Rails 8, Phoenix, Django, Laravel, Topcoat and Rullst.
  Either way about a third of the implementations would measure a store
  their users do not run, against the suite's rule of using each framework's
  production defaults.
- **What the numbers then mean:** `/me` compares "get the signed-in user"
  as each framework ships it. A database store costs a query (Laravel's
  `database` driver also writes the session on every request), a cookie
  store costs a signature check or a decryption, Spring's in-memory session
  a map lookup; every implementation also reads the user's row. The results
  print the store (`phase2.session.store`) in the `/me` column, and the
  README's Limitations section says that `/me` measures defaults.
- **Laravel's session driver (decision 4, pending confirmation):** Laravel
  keeps the `cookie` driver it uses today, not its default `database`
  driver. `/html` is in the `web` group and the load sends no cookies, so the
  `database` driver would insert a session row on every `/html` request, an
  artifact of the load generator. The Laravel folder README and the results
  (its `phase2.session.store` is `cookie-encrypted`; README Limitations) say
  so. The decision lives in the Laravel folder's session configuration
  only.

### 6.3 Obtaining the sessions

In every round, before the phase-2 warm-up (§8; servers with in-memory sessions start
empty each round): 125 logins as `user1`..`user125` (8 at a time), keeping
the cookies each login sets. If a login response is JSON with a `token`
string and sets no cookie (bearer-token designs), the harness sends
`Authorization: Bearer <token>` instead; the folder must say why it uses a
token rather than a cookie session. The workload cycles through the 125
sessions (`me`).

**Conformance**

1. `GET /me` without cookies: 401, 403, 302 or 303.
2. Login as `user7` with a wrong password: no session (`GET /me` with the
   returned cookies is not 200).
3. Login as `user7`: allowed status; then `GET /me` with its cookies: 200
   and `{"id": 7, "username": "user7", "displayName": "User 7"}`.
4. Change `display_name` of user 7 with `psql` 3 times; each `GET /me`
   follows (the row is read on every request); restore it.
5. Log in as `user8` too: each session returns its own user (no shared
   state).
6. pg_stat_statements: 20 `GET /me` run at least 20 SELECT statements on
   `users`.

**Load profile:** Tier 1, 125 sessions cycled (joint pairing when there is
more than one).

## 7. Load generator

### 7.1 Why bombardier cannot stay

bombardier 2.0.2 sends one fixed request per run: no per-request URL, body
or header, so it cannot do `/world/{id}` with random ids, 125 sessions or
random bodies. Phase 1 kept fixed URLs (`/queries?queries=20`, where the
server picks the random rows).

### 7.2 Candidates

| | wrk 4.2.0 | oha 1.16.0 | wrk2 (44a94c1) | bombardier 2.0.2 |
| --- | --- | --- | --- | --- |
| Language, I/O | C, epoll, one thread per CPU | Rust, Tokio, Hyper | C (wrk fork) | Go, fasthttp |
| Per-request URL | yes (Lua `request()`) | yes (`--urls-from-file`: a uniform random line; `--rand-regex-url` is not uniform over a numeric range) | yes (Lua) | no |
| Per-request body | yes | yes (`-Z`, random line) | yes | no |
| Per-request headers (cookies) | yes, together with URL and body | no: headers fixed per run, URL and body drawn independently | yes | no |
| Latency percentiles | yes (Lua `done()`: `latency:percentile(p)`) | yes (p10..p99.99, also first byte) | yes, corrected for coordinated omission at a fixed rate | yes |
| Status breakdown | errors only for status ≥ 400 (3xx counts as success) unless a Lua `response()` hook counts them (§7.4) | full status distribution | as wrk | 1xx/2xx/3xx/4xx/5xx |
| Machine-readable output | via Lua `done()` (prototype prints one JSON line) | `--output-format json` | via Lua | `-o j` |
| Release binaries | none: source tarball, pinned by SHA-256; `make` builds it in a few seconds on the runner (bundled LuaJIT, system OpenSSL; installing all three candidates took 17 s) | Linux x86-64 binaries (also a PGO build), SHA-256 digests in the release | none; last commit 2019, unmaintained | Linux binaries |
| Maintenance | last release 2021 (4.2.0), stable, very widely used | active (1.17.0 on 2026-11-14) | unmaintained | last release 2.0.2 |
| License | "Modified Apache 2.0": Apache 2.0 plus clause 4(e), a substantially changed derivative must drop the name; unmodified use is unaffected | MIT | Apache 2.0 | MIT |
| Connections | `-c C -t T` opens `C // T` per thread (124 for 125 on 2 threads) | exact | as wrk | exact |
| Fixed-rate mode | no | `-q` with `--latency-correction` | yes (its purpose) | `-r` |

### 7.3 Experiment

Setup: `.github/workflows/loadgen-experiment.yml` runs
`bench/loadgen_experiment.py` on one GitHub-hosted runner: the Axum folder's
image on the server's 2 vCPUs (one physical core with both SMT threads),
PostgreSQL idle on the client side, each tool pinned with `taskset` to the
client vCPUs: both (the current split) or one (phase 1's candidate split,
where PostgreSQL gets the other). 125 connections, 10 s per run, a 5 s
warm-up, 3 rounds with the tool order rotated every round; the table shows
medians. "Dynamic" sends `/json?id=N` for the 10,000 ids in a shuffled order
(wrk: prebuilt requests returned by the Lua `request` function; oha:
`--urls-from-file`), which costs the client what `/world/{id}` will.
"+status" adds wrk's Lua `response` hook that counts every status class.
The workflow runs on a push to this branch that changes the workflow or the
script (`workflow_dispatch` needs the file on the default branch, and
`push` with a `paths` filter was the simplest trigger, as phase 1 did).

Run 1 ([44559821715](https://github.com/venelouis/Benchmarks/actions/runs/44559821715),
AMD EPYC 9V74), `GET /json`:

| Tool | Client vCPUs | req/s | vs bombardier | Load generator CPU (cores) | req/s per client CPU-second | Server CPU (of 2) | p99 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bombardier 2.0.2 | 2 | 154,962 | 1.00 | 1.98 | 78,185 | 1.93 | 2.06 |
| wrk static | 2 | 168,274 | 1.09 | 1.89 | 88,846 | 1.97 | 1.10 |
| wrk dynamic | 2 | 167,208 | 1.08 | 1.91 | 87,814 | 1.96 | 1.18 |
| oha static | 2 | 162,997 | 1.05 | 1.92 | 85,309 | 1.85 | 1.40 |
| oha dynamic | 2 | 164,523 | 1.06 | 1.94 | 84,851 | 1.87 | 1.17 |
| bombardier 2.0.2 | 1 | 98,945 | 1.00 | 1.00 | 98,945 | 1.42 | 2.48 |
| wrk static | 1 | 122,010 | 1.23 | 1.00 | 122,010 | 1.66 | 1.02 |
| wrk dynamic | 1 | 118,460 | 1.20 | 1.00 | 118,460 | 1.59 | 1.04 |
| oha static | 1 | 112,012 | 1.13 | 1.00 | 112,124 | 1.46 | 1.39 |
| oha dynamic | 1 | 108,799 | 1.10 | 1.00 | 108,799 | 1.42 | 1.43 |

Run 2 ([44561794485](https://github.com/venelouis/Benchmarks/actions/runs/44561794485),
AMD EPYC 7763, a slower runner), the same plus the status hook and
`GET /db-single`:

| Path | Tool | Client vCPUs | req/s | vs bombardier | Load generator CPU (cores) | Server CPU (of 2) | p99 (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| /json | bombardier | 2 | 115,058 | 1.00 | 1.98 | 1.95 | 2.56 |
| /json | wrk static | 2 | 115,995 | 1.01 | 1.77 | 1.98 | 1.61 |
| /json | wrk dynamic | 2 | 117,328 | 1.02 | 1.80 | 1.97 | 1.60 |
| /json | wrk dynamic + status | 2 | 119,854 | 1.04 | 1.90 | 1.97 | 1.58 |
| /json | oha static | 2 | 110,123 | 0.96 | 1.82 | 1.80 | 3.84 |
| /json | oha dynamic | 2 | 118,684 | 1.03 | 1.93 | 1.89 | 1.71 |
| /json | bombardier | 1 | 82,373 | 1.00 | 1.00 | 1.75 | 2.98 |
| /json | wrk static | 1 | 107,891 | 1.31 | 1.00 | 1.93 | 1.18 |
| /json | wrk dynamic | 1 | 105,060 | 1.28 | 1.00 | 1.91 | 1.20 |
| /json | wrk dynamic + status | 1 | 96,825 | 1.18 | 1.00 | 1.85 | 1.31 |
| /json | oha static | 1 | 94,335 | 1.15 | 1.00 | 1.74 | 1.76 |
| /json | oha dynamic | 1 | 91,644 | 1.11 | 1.00 | 1.71 | 1.84 |
| /db-single | bombardier | 2 | 10,044 | 1.00 | 0.53 | 1.13 | 14.05 |
| /db-single | wrk static | 2 | 12,574 | 1.25 | 0.35 | 1.37 | 12.20 |
| /db-single | wrk dynamic + status | 2 | 12,154 | 1.21 | 0.39 | 1.32 | 11.72 |
| /db-single | oha static | 2 | 11,934 | 1.19 | 0.42 | 1.31 | 12.10 |

Rounds agreed within 1-8% (spread over the three rounds). No tool had an
error in any run. wrk2 (last commit 2019) built but crashed at start-up in
every run, with and without a script (`PANIC: unprotected error in call to
Lua API`), so it has no numbers; it is out.

What the numbers say:

- **Per client CPU-second, wrk does the most work**: about 1.2-1.3x
  bombardier and about 1.1x oha on one vCPU, where the load generator alone
  is the limit. Varying the URL costs wrk 2-3% and oha about 3%.
- **With two client vCPUs on `/json`, the tools are close** because Axum's
  2 vCPUs are nearly saturated (server CPU 1.93-1.98 of 2). On the slower
  runner all reach about the same requests/s, but wrk needs 0.1-0.2 fewer
  client cores than bombardier for it: headroom that the database or a
  faster server can use.
- **The load generator's cost decides `/db-single`**: PostgreSQL shares the
  client vCPUs, so a cheaper client leaves it more CPU. wrk raised Axum's
  `/db-single` by 25% over bombardier (oha by 19%). Part of what phase 1
  calls client-bound on `/db-single` is bombardier's own cost.
- **The status hook costs wrk about 8% on one vCPU** (`/json`, the
  cheapest endpoint; dynamic with and without the hook). On `/db-single`,
  dynamic URLs plus the hook cost 3% against static wrk. wrk with the hook
  still beats oha and bombardier.
- Latency: wrk's p99 is lower than bombardier's in every case; the tools
  measure differently (closed loop for all three), so latencies are only
  comparable within one tool.
- The machine-readable output, the per-request URL and the CPU measurement
  all worked through the prototypes (`bench/loadgen_wrk.py`,
  `bench/loadgen_oha.py`), which return `loadgen.run_load`'s metrics dict.

### 7.4 Recommendation

**wrk 4.2.0, for every endpoint, replacing bombardier in the same change.**

- It is the most CPU-efficient client measured (the suite's main validity
  problem is the client, more so if phase 1 gives the load generator one
  vCPU), it is the only candidate that varies URL, headers and body
  together per request (125 sessions, each cookie with its own CSRF token),
  and its percentiles and counters come out as JSON through the Lua `done`
  function.
- Static workloads (`/text`, `/json`, `/db-single`, `/html`, phase 1's
  fixed URLs) run without a Lua `request` function, so wrk builds the
  request once; phase-2 workloads use prebuilt requests and **the status
  hook**, so every non-2xx response, a 3xx included, counts as a failure
  (an expired session that redirects to the login page would otherwise
  count as success). The static workloads rely on wrk's own count
  (status 400 and above); conformance already rejects a 3xx on them.
- Pinning: the source tarball's SHA-256 in `bench/loadgens.json`, built on
  the runner (`bench/install-loadgen.sh wrk DIR`, seconds); the results
  record the binary's SHA-256 and the compiler, like the image digests.
- Connections: `-t` is the number of client vCPUs and wrk opens
  `connections // threads` per thread. The tiers keep their connection
  counts (Tier 1 125, so 124 open with 2 threads; Tiers 2-4 divide evenly)
  and every run records `connections_open`; the 125 sessions are still all
  used, cycled over the open connections.
- License: the modified Apache 2.0 licence adds only a naming condition on
  substantially changed derivatives; running it unmodified is not affected.
  Say so in the README's tool section.

**oha 1.16.0 is the fallback** (MIT, release binaries with SHA-256 digests,
full status distribution, JSON output) if a release binary or a single
licence family is required. Its limits: about 10% fewer requests per client
CPU-second than wrk, and one header set per run, so `/form` and `/me` would
use one session for all 125 connections (a hot session row for Laravel's
database driver, which writes the session on every request).

## 8. Harness integration (done on `feat/v2`)

As integrated (the plan below was followed; the differences are noted after
it):

- `bench/config.json`: `load_generator` is wrk (source URL and SHA-256);
  `endpoint_workloads`, `phase2` (125 sessions, 8 at a time) and `hot_rows`;
  Tier 1 order `text, json, db-single, html, queries, fortunes, world,
  worlds, form, me, updates, world-update`.
- `bench/loadgen.py` is a thin wrapper around `loadgen_wrk.run_load`;
  `describe_binary` records the wrk binary's SHA-256, banner and compiler.
  bombardier and its installer are gone; `bench/install-loadgen.sh DIR`
  builds wrk (and `DIR oha` installs the fallback pinned in
  `bench/loadgens.json`).
- `bench/sessions.py`: the browser (cookie jar, form parsing, logins), used by
  conformance and by `measure.phase2_context`.
- **Round order** (`measure.measure_round`, since the 2026-11-19 revision):
  start, idle window, then for each endpoint up to `/fortunes` (`/updates`
  last) its warm-up, a 2 s idle settle and its Tier 1 run; Tier 2, Tier 4, a
  10 s idle period, Tier 3's load (the Memory high-water mark) and the
  `after` RAM snapshot; then the application phase: sessions (125
  `GET /form`, 125 logins), warm-up, settle and Tier 1 of each declared
  phase-2 endpoint (reads first, `world-update` last), and the hot-rows run. The
  first trial (fork run 44571055268) logged in before the warm-up, as the
  plan said: Axum's RAM went from 1.3 MiB idle to 1,041 MiB after the 125
  Argon2id verifications (19 MiB each; glibc keeps the freed memory in its
  per-thread arenas) and its Tier 3 peak became 1,045 MiB instead of about
  11, which would have distorted every Memory ratio. Every RAM metric is now
  taken before the first login.
- `bench/conformance_phase2.py`: the checks of sections 3, 4 and 6, called
  from `conformance.run_checks` for the declared endpoints.
- `bench/containers.py`: `apply_db_setup`, `run_sql_file`, and
  `reset_tables(config, framework_tables)`; `start_database` also checks the
  1,000 accounts. `harness.py db-check` (run by CI) loads `bench/db`,
  verifies the bcrypt hashes with pgcrypto and the Argon2id format, and
  dry-runs every `db_setup` file.
- `bench/rankings.py`: the Application category and the 1% error rule
  (`MAX_ERROR_RATE`); `report.py` and the dashboard show an Application
  table with the CSRF design and session store, and the hot-rows run.

The original plan:

| File | Role |
| --- | --- |
| `bench/workload.py` | tool-neutral workloads; the five phase-2 builders and the 2,000/10,000-request mixes, fixed seed |
| `bench/loadgen_process.py` | runs a load generator process and measures both sides; same keys as `loadgen.run_load`, including phase 1's (`loadgen_cpu_busy`, `db_cpu_busy`, `loadgen_cpu_cores`, `db_cpu_cores`, `rps_per_cpu`) when given the database handle |
| `bench/loadgen_wrk.py`, `bench/loadgen_oha.py` | `run_load(binary, url, *, connections, duration_s, config, client_cpus, server=None, database=None, db_cpus=None, workload=None, ...)`, a superset of phase 1's signature |
| `bench/loadgens.json`, `bench/install-loadgen.sh` | pins and installer (oha: binary + SHA-256; wrk/wrk2: source tarball + SHA-256, built) |
| `bench/db/phase2.sql` | the `users` table |
| `bench/tests/test_phase2.py` | unit tests of the workloads and of the wrk and oha parsers (they also pass on top of the phase-1 branch) |
| `bench/loadgen_experiment.py`, `.github/workflows/loadgen-experiment.yml` | the temporary experiment of §7.3; delete after the decision |

Changes to shared files, for the integration pull request (none are on this
branch):

1. `bench/common.py`: `PHASE2_ENDPOINTS = ("world", "worlds", "world-update",
   "form", "me")` added to `ENDPOINTS`; `validate_manifest` accepts
   `db_setup` (a file in the folder) and the `phase2` block (§2.1).
2. `bench/config.json`: `load_generator` becomes the chosen tool (moved from
   `loadgens.json`); `endpoint_workloads` maps `world`, `worlds`,
   `world-update`, `form` and `me` to the builders of `workload.py`;
   `tier1.endpoints` becomes `text, json, db-single, html, queries,
   fortunes, world, worlds, form, me, updates, world-update` (reads first).
3. `bench/loadgen.py`: `run_load` dispatches to `loadgen_wrk.run_load`
   (the parser and command move there); `install-bombardier.sh` is replaced
   by `install-loadgen.sh`.
4. `bench/containers.py`: apply `db_setup` after `start_database`; record
   the tables it creates; `reset_tables` also truncates them.
5. New `bench/sessions.py`: `form_sessions(base_url, n)` (GET /form, parse
   the hidden fields and cookies) and `login_sessions(base_url, n)`; used by
   conformance and by `measure_round` before the phase-2 warm-up.
6. `bench/conformance.py`: one call per declared phase-2 endpoint into a
   new `bench/conformance_phase2.py` (checks of §3, §4, §6, reusing phase
   1's `statements()` and `html_tokens()`).
7. `bench/measure.py`: phase-2 endpoints get their workload; the five
   `tier1.<name>` runs join `METRICS`, `LOAD_RUNS` and `CAPACITY_RUNS`.
8. `bench/rankings.py`: an **Application** category (geometric mean of the
   five capacity ratios), weighted like the others (1/7 each with phase 1's
   six). `report.py`/`aggregate.py`: the five columns, with the CSRF design
   and session store under the `/form` and `/me` headings.
9. README (What is measured, Method, Fairness, Limitations) and
   CONTRIBUTING (endpoint contracts, `db_setup`, `phase2`). A history note:
   the load generator changed, so absolute requests/s before and after are
   not comparable; ratios to Axum are measured with the same tool.

The phase-1 mechanism needs no change of its own: an implementation that
does not declare a phase-2 endpoint is not checked or measured on it and is
"incomplete" in the Application category, exactly as phase 1 does for
Database.

## 9. Per-framework notes

What each implementation is expected to use. Statuses are the framework's
defaults for the cases of §3 (the implementation may keep them: 400 or 422
both conform). Sources are official docs or the framework's source at the
measured version; **(?)** marks what could not be confirmed and must be
checked while implementing.

| Implementation | `/world/{id}` non-integer | Validation (query, JSON, form) and default status | CSRF (design: mechanism) | Session for `/me` (store) |
| --- | --- | --- | --- | --- |
| Axum 0.8.9 | `Path<i32>`: 400 | none built in; `validator`/`garde` or manual; `Json` syntax 400, data 422, `Form` 422 | token: `axum_csrf` 0.12 (most-used; cookie + hashed form token) | `tower-sessions` 0.15 + `tower-sessions-sqlx-store` 0.16 `PostgresStore` (postgresql); axum-login does not support SQLx 0.9 yet |
| Actix Web 4.19 | `web::Path<i32>`: 404 (default `PathConfig`) | manual or `validator`; `Json`/`Query`/`Form` errors 400 | token: `actix-csrf` 0.8 (double-submit cookie; last release 2024-11) | `actix-session` 0.11 `CookieSessionStore` (cookie-signed or -encrypted; no PostgreSQL store) |
| Loco 1.3.1 | axum `Path`: 400 | built in: `QueryValidate`/`JsonValidate`/`FormValidate` (`validator` 0.20): 400 for a failed rule; a body they cannot deserialize is Axum's `Json`/`Form` rejection: 422 | token: `axum_csrf` (Loco has none; it is built on Axum) | built-in `auth_session` feature, default signed cookie (cookie-signed); its `database` store is the alternative. Enable the feature (the folder has only `auth`) |
| Topcoat 0.12.1 | `path_param!(id: i32)`: the app chooses (`else not_found`) | `#[query_params(error = bad_request)]`: 400; `Json`/`Form`: 400; range checks manual | fetch-metadata: built-in `OriginPolicy` (Sec-Fetch-Site, then Origin vs Host), on by default, 403 | built-in `session` feature: tokens hashed in an app table read through Toasty (postgresql). Enable `session` and `cookie`; the cookie is `__Host-`/`Secure` (the harness replays it over HTTP) |
| Rullst 13 (as generated) | `routes!` on axum `Path`: 400 | `Validate` + `ValidatedJson`/`ValidatedForm`: 422; query: `Validate` on `Query<T>` by hand **(?)** | token: built-in `csrf_middleware`, double-submit `rullst_csrf` cookie, masked `_token` field or `X-CSRF-Token` (already in the generated router) | `make:auth` session registry: `rullst_session` cookie sealed with `APP_KEY`, one primary-key lookup per request, at most one write per hour (postgresql) |
| Rullst (minimal) | as above | as above | token: the same `csrf_middleware`, on the `/form` and `/login` routes only | as above (no production middleware otherwise) |
| Ruby on Rails 8.1.4.1 | `constraints: {id: /\d+/}`: 404 | no typed query validation; `ActiveModel` validations, 422 by convention; malformed JSON 400 | token: `protect_from_forgery`, token in the encrypted cookie session, masked `authenticity_token`, Origin checked when present; failure 422. Header-only mode exists only from 8.2 | `bin/rails generate authentication`: `sessions` row via signed cookie, 1 SELECT (+ `users` **(?)**) (postgresql) |
| Laravel 13.42 | `whereNumber('id')`: 404 | `$request->validate`: 422 (JSON only when the request expects JSON, else a 302 back: render the `api` group's errors as JSON, §2.6); malformed JSON becomes empty input: 422; `integer:strict` for JSON numbers (§2.7) | token: `PreventRequestForgery` (web group): accepts `Sec-Fetch-Site: same-origin`, else session token `_token`/`X-CSRF-TOKEN`; failure 419 | session guard + default `database` driver: SELECT and UPDATE of `sessions` on every request, + `users` (postgresql). bcrypt hashes need the `$2y$` prefix |
| Django 6.1.3 | `<int:id>`: 404 | Django forms (`Form(request.GET)`, `Form(request.POST)`); status chosen by the view; malformed JSON needs a `try` | token: `CsrfViewMiddleware`, secret in the `csrftoken` cookie, masked `csrfmiddlewaretoken`; Origin checked when present; no session needed; 403 | `contrib.auth` + default database sessions (`django_session`): 1 SELECT session + 1 SELECT user, no write **(?)** (postgresql). Hashers need `bcrypt$`/`argon2` prefixes |
| Phoenix 1.8.16 | `:id` is a string; `Repo.get` cast error: 400 (phoenix_ecto) | Ecto changesets (schemaless for query/forms); 422 by the generator's convention; malformed JSON 400; `cast/3` turns `"5"` into 5 (§2.7) | token: `protect_from_forgery` (`:browser` pipeline), token in the signed cookie session, `_csrf_token`; 403 | `mix phx.gen.auth`: session cookie holds a token, 1 SELECT joining `users_tokens` and users (postgresql); bcrypt `$2b$` **(?)** |
| Spring Boot 4.1.2 | `@PathVariable int`: 400; `{id:\d+}`: 404 | `@RequestParam @Min @Max`, `@Valid @RequestBody`, `@ModelAttribute @Valid`: 400 (needs `spring-boot-starter-validation`); Jackson coerces `"5"` unless `allow-coercion-of-scalars=false` (§2.7) | token: Spring Security CSRF, token in the `HttpSession`, XOR-masked `_csrf`; 403 (needs `spring-boot-starter-security`) | Spring Security form login, `SecurityContext` in Tomcat's in-memory session **(?)** (memory; one JVM process). `{bcrypt}` prefix for `DelegatingPasswordEncoder` |
| ASP.NET Core 10 | `{id:int}`: 404; unconstrained `int id`: 400 | DataAnnotations (`[Range]`) on minimal APIs/Razor Pages: 400; the web JSON defaults read `"5"` as a number unless `NumberHandling = Strict` (§2.7) | token: built-in antiforgery (cookie token + `__RequestVerificationToken`, Data Protection, bound to the user); 400 | cookie authentication (`AddCookie`, `SignInAsync`) (cookie-encrypted). Identity's hasher reads only its PBKDF2 format: verify bcrypt with BCrypt.Net-Next **(?)** |
| NestJS 12.5 (NodeAdapter) | `ParseIntPipe`: 400 | `ValidationPipe` + class-validator: 400 (`errorHttpStatusCode` to change) | fetch-metadata: built-in `app.enableCsrfProtection()` (since 12.1; Sec-Fetch-Site/Origin; 403) | `express-session` + `connect-pg-simple` (postgresql; table in `db.sql`), Nest middleware of `/form`, `/login` and `/me` only (`MiddlewareConsumer.forRoutes`). `@nestjs/authentication` runs on NodeAdapter but always registers a global interceptor (`AuthenticationScopeInterceptor`) that would wrap every handler, so it is not used |
| FastAPI 0.163 | `id: int`: 422 | `Query(ge=, le=)`, Pydantic bodies, `Form()` (needs `python-multipart`): 422 | token: `asgi-csrf` 0.11 (listed in Starlette's docs; signed `csrftoken` cookie, form field; 403); the token does not rotate; `always_protect` for `/form` and `/login` (cookieless posts are otherwise not checked) | Starlette `SessionMiddleware` (cookie-signed; no server-side store) |
| Fastify 5.12.8 | `params` schema `integer`: 400 | JSON schema for `querystring`/`body`: 400; Ajv coerces `"5"` unless the body's validator has `coerceTypes: false` (§2.7); urlencoded needs `@fastify/formbody` | token: `@fastify/csrf-protection` 7 with `@fastify/cookie` (secret in `_csrf` cookie, token `_csrf`; 403) | `@fastify/secure-session` (cookie-encrypted). `@fastify/session` has no PostgreSQL store |
| Gin 1.12 (Go 1.27) | `ShouldBindUri`: the handler chooses (400) | `ShouldBindQuery`/`ShouldBindJSON`/`ShouldBind` with validator tags; the handler chooses | fetch-metadata: Go standard library `http.CrossOriginProtection`, its `Check` called by a middleware of the browser route group (`/form`, `/login`, `/me`; 403), not `Handler` around the engine (decision 2); `gorilla/csrf` has an unfixed advisory | `gin-contrib/sessions` v1.1 cookie store (cookie-signed); its PostgreSQL store is built on a stale 2022 package |

Sources (one or more per row; checked on 2026-11-19):

- Axum: [path rejection](https://docs.rs/crate/axum/0.8.9/source/src/extract/path/mod.rs), [rejections](https://docs.rs/crate/axum/0.8.9/source/src/extract/rejection.rs), [axum_csrf](https://crates.io/crates/axum_csrf), [tower-sessions](https://docs.rs/tower-sessions/0.15.0/tower_sessions/), [tower-sessions-sqlx-store](https://crates.io/crates/tower-sessions-sqlx-store)
- Actix Web: [path.rs](https://docs.rs/crate/actix-web/4.19.0/source/src/types/path.rs), [errors](https://docs.rs/crate/actix-web/4.19.0/source/src/error/mod.rs), [actix-csrf](https://docs.rs/actix-csrf/0.8.0/actix_csrf/), [actix-session storage](https://docs.rs/actix-session/0.11.0/actix_session/storage/index.html)
- Loco: [validate extractors](https://docs.rs/crate/loco-rs/1.3.1/source/src/controller/extractor/validate.rs), [middleware](https://loco.rs/docs/reference/middleware/), [auth session](https://docs.rs/crate/loco-rs/1.3.1/source/src/auth/session.rs), [changelog](https://docs.rs/crate/loco-rs/1.3.1/source/CHANGELOG.md)
- Topcoat: [path_param](https://docs.rs/crate/topcoat-router-macro/0.12.1/source/docs/path_param.md), [query_params](https://docs.rs/crate/topcoat-router-macro/0.12.1/source/docs/query_params.md), [OriginPolicy](https://docs.rs/topcoat/0.12.1/topcoat/router/struct.OriginPolicy.html), [origin.rs](https://docs.rs/crate/topcoat-router/0.12.1/source/src/origin.rs), [sessions](https://docs.rs/crate/topcoat/0.12.1/source/docs/session.md)
- Rullst: [csrf.rs](https://github.com/Rullst/Rullst/blob/main/rullst-core/src/security/csrf.rs), [validation.rs](https://github.com/Rullst/Rullst/blob/main/rullst-core/src/validation.rs), [session registry](https://github.com/Rullst/Rullst/blob/main/rullst-auth/src/auth/session_registry.rs), [make:auth sessions](https://github.com/Rullst/Rullst/blob/main/cargo-rullst/src/generators/auth/sessions.rs)
- Rails: [routing](https://guides.rubyonrails.org/routing.html), [rescue_responses](https://guides.rubyonrails.org/configuring.html), [RequestForgeryProtection 8.1](https://api.rubyonrails.org/v8.1/classes/ActionController/RequestForgeryProtection/ClassMethods.html) (edge: [header_only](https://edgeapi.rubyonrails.org/classes/ActionController/RequestForgeryProtection/ClassMethods.html)), [authentication generator](https://raw.githubusercontent.com/rails/rails/v8.1.1/railties/lib/rails/generators/rails/authentication/templates/app/controllers/concerns/authentication.rb.tt), [security guide](https://guides.rubyonrails.org/security.html)
- Laravel: [routing](https://laravel.com/docs/13.x/routing), [validation](https://laravel.com/docs/13.x/validation), [CSRF](https://laravel.com/docs/13.x/csrf), [PreventRequestForgery](https://raw.githubusercontent.com/laravel/framework/13.x/src/Illuminate/Foundation/Http/Middleware/PreventRequestForgery.php), [session](https://laravel.com/docs/13.x/session), [Store::save](https://raw.githubusercontent.com/laravel/framework/13.x/src/Illuminate/Session/Store.php), [hashing](https://laravel.com/docs/13.x/hashing)
- Django: [URL converters](https://docs.djangoproject.com/en/6.1/topics/http/urls/), [CSRF](https://docs.djangoproject.com/en/6.1/ref/csrf/), [csrf.py](https://raw.githubusercontent.com/django/django/stable/6.1.x/django/middleware/csrf.py), [sessions](https://docs.djangoproject.com/en/6.1/topics/http/sessions/), [passwords](https://docs.djangoproject.com/en/6.1/topics/auth/passwords/)
- Phoenix: [phoenix_ecto plug](https://raw.githubusercontent.com/phoenixframework/phoenix_ecto/main/lib/phoenix_ecto/plug.ex), [fallback controller template](https://raw.githubusercontent.com/phoenixframework/phoenix/v1.8.1/priv/templates/phx.gen.json/fallback_controller.ex), [Plug.CSRFProtection](https://plug.hexdocs.pm/Plug.CSRFProtection.html), [phx.gen.auth](https://phoenix.hexdocs.pm/mix_phx_gen_auth.html)
- Spring: [MVC exception mapping](https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/web/servlet/mvc/support/DefaultHandlerExceptionResolver.html), [method validation](https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-controller/ann-validation.html), [CSRF](https://docs.spring.io/spring-security/reference/servlet/exploits/csrf.html), [session persistence](https://docs.spring.io/spring-security/reference/servlet/authentication/persistence.html), [password storage](https://docs.spring.io/spring-security/reference/features/authentication/password-storage.html)
- ASP.NET Core: [route constraints](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/routing?view=aspnetcore-10.0#route-constraints), [parameter binding](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis/parameter-binding?view=aspnetcore-10.0), [minimal API validation](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/minimal-apis?view=aspnetcore-10.0), [antiforgery](https://learn.microsoft.com/en-us/aspnet/core/security/anti-request-forgery?view=aspnetcore-10.0), [cookie authentication](https://learn.microsoft.com/en-us/aspnet/core/security/authentication/cookie?view=aspnetcore-10.0)
- NestJS: [NodeAdapter](https://docs.nestjs.com/http/performance), [pipes](https://docs.nestjs.com/pipes), [validation](https://docs.nestjs.com/techniques/validation), [CSRF](https://docs.nestjs.com/security/csrf), [authentication](https://docs.nestjs.com/security/authentication), [session](https://docs.nestjs.com/techniques/session)
- FastAPI: [path params](https://fastapi.tiangolo.com/tutorial/path-params/), [errors](https://fastapi.tiangolo.com/tutorial/handling-errors/), [forms](https://fastapi.tiangolo.com/tutorial/request-forms/), [Starlette middleware](https://starlette.dev/middleware/), [asgi-csrf](https://github.com/simonw/asgi-csrf)
- Fastify: [validation](https://fastify.dev/docs/latest/Reference/Validation-and-Serialization/), [content-type parser](https://fastify.dev/docs/latest/Reference/ContentTypeParser/), [@fastify/csrf-protection](https://github.com/fastify/csrf-protection), [@fastify/secure-session](https://github.com/fastify/fastify-secure-session), [@fastify/session](https://github.com/fastify/session)
- Gin: [bind URI](https://gin-gonic.com/en/docs/binding/bind-uri/), [binding and validation](https://gin-gonic.com/en/docs/binding/binding-and-validation/), [CrossOriginProtection](https://pkg.go.dev/net/http#CrossOriginProtection), [GO-2025-3884](https://osv.dev/vulnerability/GO-2025-3884), [gin-contrib/sessions](https://github.com/gin-contrib/sessions)

Notes that change implementation work:

- Spring Boot needs `spring-boot-starter-security` and
  `spring-boot-starter-validation`; scope the security filter chain to
  `/form`, `/login` and `/me` with `securityMatcher` so the existing
  endpoints keep their stack (§2.3).
- Loco needs the `auth_session` feature, Topcoat `session` and `cookie`,
  FastAPI `python-multipart`, `itsdangerous` and `asgi-csrf`, Fastify
  `@fastify/formbody`, `@fastify/cookie`, `@fastify/csrf-protection` and
  `@fastify/secure-session`.
- Laravel's bcrypt check fails on `$2b$`: replace the prefix with `$2y$`
  (same algorithm) or use the `argon2id` driver with the argon2 column.
- ASP.NET Core's antiforgery token is bound to the user: `/form` stays
  anonymous.
- Topcoat, Gin and NestJS (fetch-metadata designs) allow requests without
  `Sec-Fetch-Site` and `Origin`; the harness sends them (§2.4) so the check
  runs.
- Found while implementing (the folders do this): JSON numbers must be
  strict (§2.7: Spring, ASP.NET Core, Fastify and Laravel need a setting,
  FastAPI, Django, Rails and Phoenix a type check); Laravel renders the
  `api` group's validation errors as JSON (§2.6); Phoenix's `:browser`
  pipeline accepts `json` for `/me` (§6.1); Laravel and Django are
  configured with the stored bcrypt cost so a login does not rehash (§2.2);
  the generators' login rate limits are relaxed for the 125 logins (§10.1).
- Scoping (decision 2): Gin runs `CrossOriginProtection` and the session
  middleware on its browser route group; NestJS applies `express-session`
  to `/form`, `/login` and `/me` with `MiddlewareConsumer.forRoutes`, while
  `app.enableCsrfProtection()` is global (§5.1).

## 10. Implementation checklist per framework (phase 1 and 2 in one pass)

All 16 folders are done on `feat/v2` and pass conformance; the checklist
stays as the contract for changes and new folders. The Axum folder
(`frameworks/axum`) is the reference implementation: read its
`src/browser.rs`, `db.sql`, `bench.json` and README before starting. For
every folder, in one pull request per group of frameworks:

1. **Phase 1** (as on `feat/v2-phase1`): `/queries?queries=N`,
   `/updates?queries=N`, `/fortunes` with the TechEmpower round 23 rules; the
   `fortune` table; declare them in `"endpoints"`. (The six Rust folders
   already have them.)
2. **Phase 2:** the five endpoints of §3, §4 and §6, plus `GET /login` and
   `POST /login`, with the mechanisms of §9; `db.sql` for framework-owned
   tables (if any); the `phase2` block and the five names in bench.json
   (`harness.py validate` checks the block).
3. Run `python3 bench/harness.py conformance --framework <name>` in the
   fork's CI (the pull request check), not locally. `harness.py db-check`
   (also in CI) dry-runs `db.sql` without building the image.
4. README: the mechanisms, their source (built-in, generator, stdlib,
   documented, library), anything global that now also runs for the
   existing endpoints, and why where a choice was made.

### 10.1 What the harness does and checks (the exact contract)

The harness is `bench/sessions.py` (the browser) and
`bench/conformance_phase2.py` (the checks); when in doubt, they are the
contract.

- **Browser.** It keeps every cookie a response sets, by name, and sends
  them all with later requests of that session; `Path`, `Domain`, `Secure`,
  `HttpOnly`, `SameSite` and `__Host-`/`__Secure-` prefixes are ignored (plain
  HTTP to 127.0.0.1); a cookie with `Max-Age<=0` or a past `Expires` is
  dropped. It does not follow redirects.
- **Forms.** It parses the **first `<form>` whose `action` path is the
  page's path (`/form`, `/login`) or empty** (an absolute
  `http://127.0.0.1:8080/form` also matches), and submits **every
  `<input type="hidden">`** of it (name and value as given, entities
  decoded), plus its own fields. `GET /form`'s form must have
  `method="post"` and inputs named `name` and `randomNumber`. The page may
  set any cookies.
- **Form posts** (`POST /form`, `POST /login`) send
  `Content-Type: application/x-www-form-urlencoded`,
  `Origin: http://127.0.0.1:8080`, `Sec-Fetch-Site: same-origin`, the
  session's cookies, the hidden fields, then the fields. `Host` is
  `127.0.0.1:8080` (allowed-host lists must accept it, as in phase 1).
- **One pair, many requests.** A session's cookies and hidden fields are
  obtained once per round and replayed for every request of the round
  (2,000 different posts cycled over 125 sessions, about 10-20 s of load):
  the token must not rotate per request, sessions must not expire or be
  limited within a round, and nothing may throttle 125 logins from 127.0.0.1
  within a few seconds (login rate limits, jails, captchas must not trigger;
  say in the README if one had to be configured). Two generators add one
  that would: Rails 8's authentication generator puts
  `rate_limit to: 10, within: 3.minutes, only: :create` on the login (the
  Rails folder leaves it out), and Rullst's generated `credential_rate_limit`
  allows 10 credential submissions per client per minute (the Rullst folder
  raises its generated constant, `CREDENTIAL_ATTEMPTS_PER_MINUTE`, to 1,000
  and keeps the limiter; rullst-minimal leaves it out with the rest of the
  production stack). Rullst's Login Jail (`rullst-security`'s `LoginGuard`)
  is not part of the generated application, so it needs no setting.
- **Logins.** In every round, after Tier 4 (§8): `GET /login` then `POST /login`
  for `user1`..`user125`, 8 at a time; a status other than 200, 204, 302 or
  303, or no cookie and no bearer token, fails the round. Hashing cost is
  not timed but slows the start of every round: use the framework's
  standard hasher with the column whose prefix it reads (§2.2), not a
  weaker one, configured with the stored parameters so that a login does not
  rehash and rewrite the password (§2.2).
- **`GET /me`** is sent with `Accept: application/json` and the session's
  cookies (or `Authorization: Bearer`).
- **`PUT /world/{id}`** is sent with `Content-Type: application/json` and,
  only with `write_csrf`, the cookie `<cookie>=<value from GET /form>` and
  the header `<header>: <same value>`.
- **Failures under load:** on the five endpoints every response that is not
  2xx counts as an error (a redirect included); above 1% errors (median over
  rounds) the implementation gets no Application score.

Conformance, beyond the statuses listed in §3, §4 and §6:

- JSON objects must have exactly the documented keys with integer values
  (`{"id": 7.0}` fails); `application/json` media type; a 200 response to
  `GET /world/{id}` must keep the connection alive.
- `GET /worlds` is also checked with `?page=2&unknown=1` (ids 21..40), and
  one request must run exactly one `SELECT` naming `world`.
- Refused `PUT` bodies (`{"randomNumber": "5"}` among them, §2.7): the row
  keeps its value **and** no `UPDATE` changed a row of `world`
  (`pg_stat_statements`), so validate before saving. The checks that count
  `UPDATE`s send values that differ from the stored ones.
- Phase 1's `/updates`: every returned row must be the stored one after the
  request, and the `UPDATE` statements must change at least as many rows as
  there are returned ids whose value changed (an ORM may skip a row whose
  new random value equals the old one, 1 in 10,000, or a repeated id that
  ends where it started).
- After an error response the harness opens a new connection: a server may
  close it after a 4xx without `Connection: close`.
- `POST /form` success: `text/html` with `charset=utf-8` declared (the name
  has non-ASCII characters), compared as tokens with the page of §4 (escape
  forms and trailing whitespace may differ, an unescaped `<b>` fails). The
  valid post is sent 4 times with the same pair; the invalid ones (empty
  name, 65 characters, `randomNumber=0` and `abc`) with a valid pair before
  the forged ones. With `design: token`, the **longest hidden value** is
  taken to be the token and its middle character changed.
- `GET /me`: the conformance check renames user 7 three times with `psql`
  (names with `<&>`; JSON-escape them normally) and restores it; 20 requests
  must run at least 20 `SELECT`s naming `users`, even when the session holds
  the principal.

### 10.2 Per framework

| Folder | Phase 2 work |
| --- | --- |
| axum | **done** (reference): `Path`, `Query`, `Json`, `Form` extractors with ranges checked by hand; `axum_csrf` 0.12; `tower-sessions` 0.15 + `tower-sessions-sqlx-store` 0.16 `PostgresStore` (table in `db.sql`, no `migrate()` at start); Argon2id login; `/me` loads the user with SQLx; Askama |
| actix | `web::Path/Query/Json/Form`; manual ranges; `actix-csrf`; `actix-session` cookie store; SQLx; Askama |
| loco | Loco controllers with `QueryValidate`/`JsonValidate`/`FormValidate` (400, or Axum's 422 for a body that does not deserialize); `axum_csrf` layer on the form routes; enable `auth_session` (default cookie store); SeaORM for `world`, `users`; Tera |
| topcoat | `path_param!`, `#[query_params]`, `content::Json`/`Form`; `OriginPolicy` (on by default); enable `session` + `cookie`, session table in `db.sql` read with Toasty; `view!` |
| rullst | `routes!` with typed params; `Validate` + `ValidatedJson`/`ValidatedForm`; generated `csrf_middleware` (already on); `"write_csrf": {"cookie": "rullst_csrf", "header": "X-CSRF-Token"}` for the PUT (decision 7; the README states the finding: an unauthenticated JSON write needs the CSRF pair or a `MachineEndpointPolicy` endpoint); `make:auth` session registry (table in `db.sql`), Argon2 column; the generated `credential_rate_limit` on `POST /login` raised to 1,000 per minute for the 125 logins (§10.1; Login Jail is not part of the generated application); `html!` |
| rullst-minimal | same handlers; `csrf_middleware` only on `/form` and `/login`; same session registry, without `credential_rate_limit`; no production `Server` stack; `write_csrf: null` |
| rails | routes with constraints; ActiveModel form objects for `/worlds` and `/form`; `protect_from_forgery` (default); `bin/rails generate authentication` adapted to `users` (`password_bcrypt` via `has_secure_password` attribute mapping); `sessions` table in `db.sql`; the generated login `rate_limit` left out (§10.1); a JSON-integer check on the PUT body (§2.7); ERB; exempt `PUT /world/{id}` (`ActionController::API` or `skip_forgery_protection`) |
| laravel | `whereNumber`; `$request->validate`; `/form`, `/login`, `/me` in the `web` group; **keep the `cookie` session driver** (decision 4, pending: `phase2.session.store` `cookie-encrypted`; say why in the README, §6.2), so no `sessions` table; `PUT /world/{id}` in the `api` routes, `integer:strict` on its body (§2.7) and the `api` group's errors rendered as JSON 422 (§2.6); `Auth::attempt` with a `$2y$` hash and `BCRYPT_ROUNDS=10` (no rehash, §2.2); Blade |
| django | `<int:id>`; Django forms for `/worlds`, `/form`, PUT body; `CsrfViewMiddleware` (on) and `csrf_exempt` for the PUT; custom user model on `users` (`db_table`), `contrib.auth` login with a cost-10 `BCryptPasswordHasher` subclass (no rehash, §2.2), `django_session` in `db.sql`; a JSON-integer check on the PUT body (§2.7); templates |
| phoenix | router `:id` + Ecto cast; schemaless changesets (an `is_integer` check on the PUT body, §2.7); `:browser` pipeline with `protect_from_forgery` for `/form`, `/login`, `/me`, accepting `json` as well as `html` (§6.1), `:api` for the PUT; `phx.gen.auth`-style token table (`users_tokens` in `db.sql`) adapted to `users`; HEEx |
| spring-boot | `@PathVariable`, `@RequestParam @Min @Max`, `@Valid` bodies (validation starter); Spring Security (starter) with `securityMatcher` on `/form`, `/login`, `/me`, form login, default CSRF, in-memory session; `spring.jackson.mapper.allow-coercion-of-scalars=false` (§2.7); JPA; Thymeleaf |
| aspnet-core | route `{id:int}`; DataAnnotations validation; antiforgery on `/form` (fetched anonymously, §5.1); cookie authentication; BCrypt.Net-Next for the login check; `NumberHandling = Strict` (§2.7); EF Core; Razor Pages |
| nestjs | `ParseIntPipe`, `ValidationPipe` + class-validator DTOs; `app.enableCsrfProtection()` (global: Nest has no per-route form, §5.1); `express-session` + `connect-pg-simple` (`session` table in `db.sql`) applied to `/form`, `/login` and `/me` with `MiddlewareConsumer.forRoutes` (`@nestjs/authentication`'s global interceptor would wrap every handler); TypeORM; hbs |
| fastapi | `id: int`, `Query(ge, le)`, Pydantic model with `StrictInt` for PUT (§2.7), `Form()`; `asgi-csrf` with `always_protect` for `/form` and `/login` (its token does not rotate, §5.1); Starlette `SessionMiddleware`; pwdlib/bcrypt for login; SQLModel; Jinja2 |
| fastify | JSON schemas for params, querystring, body (the body without type coercion, §2.7); `@fastify/formbody`, `@fastify/cookie`, `@fastify/csrf-protection`, `@fastify/secure-session`; node-postgres; EJS |
| gin | `ShouldBindUri/Query/JSON/ShouldBind` with validator tags; `http.CrossOriginProtection` (`Check`) and the `gin-contrib/sessions` cookie store as middleware of the browser route group (`/form`, `/login`, `/me`; decision 2); GORM; html/template |

Multi-process servers (Node.js cluster, Python and Ruby workers, PHP-FPM):
the CSRF secret and the session signing or encryption key must be the same
in every process (a fixed key from the environment, set in the Dockerfile or
bench.json `env`), or a session obtained from one process fails on another.

## 11. Decisions on the open questions (maintainer, 2026-11-19)

Each decision lives in one place, so a change is local. **(pending)** marks
the two that still await the maintainer's confirmation (4 and 5, unchanged
by the integration of the 16 folders).

1. **Invalid input: 400 or 422**, and conformance verifies nothing was
   written (§2.6, §3.3). In `bench/conformance_phase2.py` (`INVALID`).
2. **Browser stack scope:** sessions, CSRF and authentication only on the new
   routes where the framework documents how (§2.3); Rullst as generated
   keeps its global production stack as generated. As implemented: route
   groups, pipelines, matchers or mounted sub-applications in most folders
   (Gin: the browser route group; NestJS: `forRoutes` for the session
   middleware); global where the framework has no per-route form (NestJS's
   `app.enableCsrfProtection()`, §5.1), said in the folder README.
3. **No CSRF-free control endpoint** in this phase.
4. **(pending) Laravel keeps the `cookie` session driver** (§6.2); the
   folder README and the results say why. In the Laravel folder only.
5. **(pending) Hot-rows contention run added** (§3.4). In
   `bench/config.json` (`"hot_rows"`); removing the key removes the run.
6. **wrk 4.2.0 for every endpoint**, built on the runner from the
   SHA-256-pinned source tarball (§7.4). The README's History says v3
   numbers are not comparable with v2's bombardier numbers.
7. **Rullst as generated sends its CSRF cookie and `X-CSRF-Token` header**
   on `PUT /world/{id}` (`write_csrf`, §2.1); its README documents it.
8. **No Application score for a run with more than 1% errors** (§2.5). In
   `bench/rankings.py` (`MAX_ERROR_RATE`).
9. **Each framework's default production session store**, labelled next to
   each result (§6.2).
10. **The Application category weighs the same as the others** in the
    overall score, which since the 2026-11-19 revision is computed for review
    and published only when `scoring.publish_overall` is true.
11. **wrk is built on the runner** (`bench/install-loadgen.sh`), as in 6.

## 12. Tie margins and three jobs (2026-11-20)

**Why.** A light validation trial (fork run 44673073257, one job and two
rounds per implementation) passed every gate, and its review found that the
tie margins understated the noise. They came from the A/A control alone,
one identical copy of Axum per job, compared with Axum on the same runner:
±0.03-0.33% per category. The ratios of the same implementations to Axum
differed much more between trials on different CPU models (NestJS's `/json`:
0.45× on a Xeon 6975P-C, 0.31× on an EPYC 7763), so a 10-20% gap between two
implementations measured on different CPUs could be ranked as a difference.
The A/A control cannot show that noise: its two sides are identical, so a
CPU model that favours one framework over Axum moves nothing in it.

**Three jobs.** The official run measures every implementation on 3 jobs
(runners) of 5 rounds: `publication.min_jobs` is 3 in `bench/config.json`,
`benchmark.yml` takes its defaults for the scheduled and manual runs from
`publication`, and the publication gate refuses fewer jobs, also for job
files recorded with an older, lower minimum (`aggregate.MIN_JOBS`).
`max_parallel` stays at most 8, so a full run takes about 1.5 times as long
as with 2 jobs.

**The rule** (`bench/rankings.py`: `job_spread`, `pooled_floor`,
`effective_spread`, `pair_margin`, `rank_entries`). In each category:

1. Every implementation has one score per job, computed like its pooled score
   from that job's rounds and the Axum rounds paired with them (the median
   of the per-round ratios, then the category's geometric mean or cost
   ratio). A job without a score in the category (not comparable, errors,
   corrected out) does not count.
2. Its **own spread** `s` is the half-range of the logarithms of its per-job
   scores, `(max ln - min ln) / 2`, with at least two scored jobs.
3. The **pooled floor** `f` is the median of `s` over the ranked
   implementations with at least two scored jobs.
4. Its **effective spread** `e` is `s`, except: `max(s, f)` when its scored
   jobs all ran on one CPU model or on one the runner did not report (the
   spread then cannot include the difference between CPU models), and `f`
   with a single scored job.
5. Two scores `A` and `B` tie when `|ln A - ln B| <= max(a, sqrt(e_A^2 +
   e_B^2), f)`, with `a` the A/A margin (the largest `|ln|` of the control's
   scores, per job and pooled, as before).
6. Positions keep the existing procedure: scores in order, each compared with
   the best score of the current group. In that comparison the lower score
   counts with the largest effective spread among itself and the group's
   other members. Without that, a precise score could be separated from a
   group that a noisy score with the same value had joined, and equal scores
   would get different positions (the recompute of the two trials did that in
   Startup: FastAPI and Phoenix, both 0.93, at 1 and 11).
7. A score is marked "≈ Axum" when `|ln score| <= max(a, e, f)`: Axum's ratio
   to itself is 1.00 in every job, so it adds no spread.
8. The overall score and the other weightings use the same rule with the
   per-job weighted geometric means of the category scores. Startup keeps its
   0.25 s readiness-interval rule as well.

The rule is at least as conservative as the one asked for (the largest of
the A/A margin, the root of the sum of squares of the two spreads, and the
floor): steps 4 and 6 can only raise a margin. Why these choices:

- **Half-range, not the standard deviation.** With two or three jobs a
  standard deviation is unstable and with two it is the half-range times
  √2; the half-range is what the maintainer's rule named and needs no
  distribution. As a rough guide: for normally distributed per-job log
  scores with standard deviation σ, the expected half-range of three is
  about 0.85σ; a pooled score, the median over three jobs' rounds, varies by
  about 0.67σ with the CPU models it drew, and the difference of two pooled
  scores by about 0.95σ. The margin `sqrt(e_A^2 + e_B^2)` is then about
  1.2σ, about 1.3 standard deviations of that difference: a modest margin
  for one pair, which the floor and steps 4 and 6 raise where three jobs
  are likely to underestimate the noise. It is not a significance test.
- **The floor is the median, not the mean or the maximum**, so one
  implementation whose jobs differed for another reason (a crash in one
  round, an outlier runner) does not set every margin, while every
  implementation still gets at least the typical spread between runners.
- **A single job falls back to the floor instead of refusing to rank.** The
  publication gate already refuses fewer than three jobs, so a single-job
  score only appears in a review report (a light trial or a job that lost its
  scores in one category); there the floor is the best available estimate of
  the noise it carries, and the report says "floor (one job)" next to it.
  With no implementation measured on two jobs there is no floor and the
  margin is the A/A margin alone, as before; the gate then also refuses
  ("no between-job spread").

**Shown.** Above the rankings: the rule, and each category's A/A margin and
floor. In each ranked cell: "±" with the margin of the comparison that set
its position (the first position has none). In `benchmarks_results.md`, per
category: each job's score with its CPU model, the spread used (and why it
is the floor), the comparison that set the position, and the "≈ Axum"
margin; the "Runner CPUs" column names the CPU model of every job. In the
JSON: `tie_rule` per category, overall and weighting, and `spread`,
`tie_check` and `reference_margin` per entry (README, "Machine-readable
results").

**Connection-pool note.** The generated README section also says, with the
numbers of the run, that the Database and Application rankings partly
measure connection-pool defaults: SQLx (Axum, Actix Web, Loco, Rullst) tests
each connection with a round trip before handing it out
(`test_before_acquire`, on by default), and the unranked `axum-no-ping`
diagnostic shows that cost (Database about 1.25 and Application about 1.15
in the validation trial).

**Tests.** `bench/tests/test_ties.py`: the spread and the floor; the three
terms of the margin; a gap just inside and just outside the margin; the A/A
margin alone being too small; jobs all on one CPU model; a single job; no
implementation with two jobs; equal scores with different spreads; the "≈"
check; every category, the overall score and the weightings; the aggregate
and the rendered tables; the connection-pool note.
