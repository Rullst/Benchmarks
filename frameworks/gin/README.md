# Gin

| | |
| --- | --- |
| Version | gin 1.12.0, gin-contrib/sessions 1.1.4, GORM 1.31.2, gorm.io/driver/postgres 1.6.3, pgx 5.13.0, golang.org/x/crypto 0.58.0 (exact versions in `go.mod` and `go.sum`) |
| Build | `CGO_ENABLED=0 go build -trimpath -ldflags="-s -w"` with Go 1.27.4 |
| Server | `router.Run` (`net/http`) with `GIN_MODE=release`; one process, and the Go runtime sets `GOMAXPROCS` to the CPUs it may use (2) |
| Database | GORM with its PostgreSQL driver (pgx 5 through `database/sql`), models `World`, `Fortune` and `User` (`users`); one pool of `DB_POOL_SIZE` connections (16), with as many idle connections kept open |
| Templates | `html/template` through `router.LoadHTMLGlob("templates/*")` and `c.HTML` (`templates/`) |
| Validation | `ShouldBindUri`, `ShouldBindQuery` (defaults in the `form` tags), `ShouldBindJSON` and `ShouldBind` with `binding` tags (go-playground/validator); the handlers answer 400, as Gin's binding examples do |
| CSRF | Go's standard `net/http.CrossOriginProtection` (Go 1.25+), its `Check` called by a middleware of the `/form`, `/login` and `/me` group |
| Sessions | `gin-contrib/sessions` with its cookie store (a gorilla/sessions cookie signed with HMAC), middleware of the `/form`, `/login` and `/me` group |
| Logging | none: `gin.New()` with `gin.Recovery()` (what `gin.Default()` adds, without its Logger), and GORM's logger silenced |
| Image | `gcr.io/distroless/static-debian13:nonroot` |

Why:

- Release mode: Gin's [deployment page](https://gin-gonic.com/en/docs/deployment/)
  documents `GIN_MODE`, and in debug mode Gin prints "Switch to "release"
  mode in production" with `export GIN_MODE=release`.
- Middleware: [Using middleware](https://gin-gonic.com/en/docs/middleware/using-middleware/)
  starts from `gin.New()` and adds `gin.Logger()` and `gin.Recovery()`; the
  Logger is the access log, so only Recovery is kept.
- Templates: [HTML rendering](https://gin-gonic.com/en/docs/rendering/html-rendering/)
  loads templates with `LoadHTMLGlob` and renders them with `c.HTML`, using
  Go's `html/template`.
- Database: Gin has no database layer. GORM, with its pgx-based PostgreSQL
  driver, is the most widely used Go ORM and the usual choice in Gin
  applications. It runs with its defaults ([Connecting to a Database](https://gorm.io/docs/connecting_to_the_database.html));
  pgx caches the prepared statement per connection by default. The pool is
  sized as in GORM's [connection pool](https://gorm.io/docs/generic_interface.html#Connection-Pool)
  example (`SetMaxOpenConns`, `SetMaxIdleConns`); `database/sql` would
  otherwise keep only 2 idle connections and reconnect under load.
  `Take` is GORM's primary-key lookup without the `ORDER BY` that `First`
  adds: `SELECT * FROM "world" WHERE "world"."id" = $1 LIMIT $2`.
- `go.mod` and `go.sum` come from the Dockerfile's `lockfile` stage
  (`go mod tidy` in the same Go image).

Database and application endpoints:

- `/queries`: one `Take` per random id. `/updates`: the random ids are
  sorted, each row is read with its own `Take` and given a new value
  (different from the current one), then one `db.Transaction` writes them
  with one `Model(&world).Update("randomnumber", …)` each, in ascending id
  order, so concurrent requests lock rows in the same order.
- `GET /world/:id`: `ShouldBindUri` into an `int32` (400 for `abc`), `Take`,
  404 for `gorm.ErrRecordNotFound`. `PUT /world/:id`: `ShouldBindJSON` into a
  `*int32` with `binding:"required,min=1,max=10000"` (a JSON string, a missing
  value or malformed JSON is a 400) before `Take`, the field set, and `Save`
  (GORM's default transaction).
- `GET /worlds`: `ShouldBindQuery` with `form:"min,default=1"` and the ranges
  and `gtefield=Min` as validator tags. One query: `Where("id BETWEEN ? AND
  ?")`, `Order("id")`, `Limit`, `Offset`, `Find`.
- `/fortunes`: `Find(&fortunes)` (no `ORDER BY`), sorted with `<` on the
  messages (byte order of UTF-8 strings, which is code-point order), rendered
  by `html/template`.

Browser routes (`browser.go`):

- CSRF: the spec's choice for Go is the standard library's
  `http.CrossOriginProtection`; Gin has no CSRF protection of its own, and
  `gorilla/csrf` has an unfixed advisory (GO-2025-3884). It refuses unsafe
  requests whose `Sec-Fetch-Site` (or, without it, `Origin` compared with
  `Host`) shows another origin, with 403. There is no token, so the forms have
  no hidden field. Its documentation shows `Handler`, which wraps a whole
  handler; it also exposes `Check(*http.Request)`, which a small Gin
  middleware calls on the browser route group only (aborting with 403, as
  `Handler` answers), so the other endpoints, `PUT /world/:id` included, keep
  their stack, as Gin's route-group middleware is meant for.
- Sessions: Gin has no session package of its own; `gin-contrib/sessions` is
  the one its middleware list points to. Its PostgreSQL store is built on a
  package last released in 2022, so the suite's rule takes its cookie store:
  the session values signed with HMAC-SHA256 (gorilla/securecookie) in the
  `session` cookie. The key is drawn at start-up: one process checks every
  cookie it signs. The middleware is on the `/form`, `/login` and `/me` route
  group only.
- `POST /login` checks the password with `golang.org/x/crypto/bcrypt`
  against `users.password_bcrypt`, stores the id in the session and
  redirects (303) to `/me`; a wrong password is a 401. `GET /me` checks the
  cookie's signature and reads the user's row (`Select("id", "username",
  "display_name").Take`) on every request; without a session, 401. No login
  throttling exists in this setup.
