# Gin

| | |
| --- | --- |
| Version | gin 1.12.0, GORM 1.31.2, gorm.io/driver/postgres 1.6.3, pgx 5.13.0 (exact versions in `go.mod` and `go.sum`) |
| Build | `CGO_ENABLED=0 go build -trimpath -ldflags="-s -w"` with Go 1.27.4 |
| Server | `router.Run` (`net/http`) with `GIN_MODE=release`; one process, and the Go runtime sets `GOMAXPROCS` to the CPUs it may use (2) |
| Database | GORM with its PostgreSQL driver (pgx 5 through `database/sql`), `db.Take(&world, 1)`; one pool of `DB_POOL_SIZE` connections (16), with as many idle connections kept open |
| Templates | `html/template` through `router.LoadHTMLGlob("templates/*")` and `c.HTML` (`templates/hello.html`) |
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
