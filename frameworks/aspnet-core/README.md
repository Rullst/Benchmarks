# ASP.NET Core

| | |
| --- | --- |
| Version | ASP.NET Core 10.0.15 (.NET 10 LTS), Entity Framework Core 10.0.15, Npgsql and its EF Core provider 10.0.3, BCrypt.Net-Next 4.2.1 (exact versions in `packages.lock.json`) |
| Build | `dotnet restore --locked-mode` and `dotnet publish --configuration Release` (framework-dependent) with the .NET SDK 10.0.404 |
| Server | Kestrel on `0.0.0.0:$PORT` (`app.Run(url)`); the pipeline has routing, the authentication and authorization middleware, and the endpoints |
| Workers | the .NET thread pool, sized by the runtime for the 2 vCPUs; Server GC (the Web SDK's default, with DATAS since .NET 9), heap limit at the runtime's default of 75% of the container's memory |
| Endpoints | Minimal APIs for `/text`, `/json`, `/db-single`, `/queries`, `/updates`, `/world/{id:int}` (GET and PUT), `/worlds` and `/me`; Razor Pages for `/html`, `/fortunes`, `/form` and `/login` (`Pages/`) |
| Database | EF Core `DbContext` registered with `AddDbContext` (`world`, `fortune` and `users` entities); Npgsql `Maximum Pool Size` = `DB_POOL_SIZE` (16) in a connection string built from `DATABASE_URL` in `Program.cs`; no migrations |
| Validation | route constraint `{id:int}` (a non-integer id matches no route: 404); DataAnnotations, checked by Minimal API validation (`AddValidation()`, .NET 10) for `/worlds` and the PUT body, and by Razor Pages model binding for `/form` and `/login`; Minimal API failures answer 400 |
| CSRF | built-in antiforgery: Razor Pages validate the token of every POST handler; the form tag helper (`asp-antiforgery="true"`) adds the `__RequestVerificationToken` field |
| Sessions | cookie authentication (`AddCookie`, `SignInAsync`): the authentication ticket in a cookie encrypted with Data Protection |
| Templates | Razor Pages, compiled into the assembly at build time |
| Logging | the template's levels (`Default` Information, `Microsoft.AspNetCore` Warning) plus `Microsoft.EntityFrameworkCore.Database.Command` at Warning, so nothing is logged per request; start-up messages at Information |
| Image | `mcr.microsoft.com/dotnet/aspnet:10.0.15-noble`, running as the image's non-root `app` user |

The SDK is not installed where this folder was written, so the Dockerfile has
a `lockfile` stage that runs `dotnet restore` and exports
`packages.lock.json`; the image restores from the committed file in locked
mode.

Why:

- .NET 10 is the current LTS release. .NET 11.0.0 came out in November 2026,
  but the Npgsql EF Core provider for it is still a release candidate
  (`11.0.0-rc.3`), so .NET 10 is the newest release with a stable PostgreSQL
  provider. EF Core is referenced directly at 10.0.15, its patch for this
  runtime, instead of the lowest version the provider accepts (10.0.4).
- [APIs overview](https://learn.microsoft.com/aspnet/core/fundamentals/apis):
  "For new projects, we recommend using Minimal APIs".
- [Choose an ASP.NET Core web UI](https://learn.microsoft.com/aspnet/core/tutorials/choose-web-ui):
  Razor Pages is "a page-based model for building server rendered web UI",
  which is what `/html` is: one page rendered on the server from a template
  and a model. The same page recommends Blazor for new project development;
  Blazor can render this page statically too, but through its component
  router and an endpoint renderer built for interactive and streaming
  rendering, and its endpoints require the antiforgery middleware. Razor
  Pages is the framework's model for a plain server-rendered page.
- [DbContext configuration](https://learn.microsoft.com/ef/core/dbcontext-configuration/):
  `AddDbContext` is the typical ASP.NET Core registration. DbContext pooling
  (`AddDbContextPool`) is an [advanced performance topic](https://learn.microsoft.com/ef/core/performance/advanced-performance-topics#dbcontext-pooling)
  that the EF Core documentation says to benchmark before adopting; it is not
  used. Connection pooling is Npgsql's own, on by default.
- The Dockerfile follows Microsoft's
  [Containerize a .NET app](https://learn.microsoft.com/dotnet/core/docker/build-container)
  pattern: SDK build stage, `aspnet` runtime stage, `USER $APP_UID`.
- The project templates' HTTPS redirection and HSTS are left out: the suite
  serves plain HTTP on loopback. EF Core logs every SQL command at Information
  by default, which would be a log line per request, so that one category is
  raised to Warning.

Database and application endpoints:

- `/queries`: one `AsNoTracking().FirstAsync(w => w.Id == id)` per random
  id (`FindAsync` on one `DbContext` would return a repeated id from the
  change tracker without a query).
- `/updates`: the random ids are sorted, each row is read with its own
  tracked query and given a new value (different from the current one, so
  each row is written), then one `SaveChangesAsync()` sends the `UPDATE`s in
  one batch and one transaction (EF Core's default). Sorting makes
  concurrent requests lock rows in the same order.
- `GET /world/{id:int}`: `FindAsync(id)`, 404 without a row. `PUT
  /world/{id:int}`: the body (`WorldUpdate`, `[Required] [Range(1, 10000)]
  int? RandomNumber`) is validated before the handler, which loads the row,
  sets the field and calls `SaveChangesAsync()`. System.Text.Json's web
  defaults read numbers from JSON strings, so `ConfigureHttpJsonOptions` sets
  `NumberHandling = Strict`: `{"randomNumber": "5"}` is a 400.
- `GET /worlds`: `[Range]` on the handler's query parameters (with their
  defaults), checked by Minimal API validation; `min > max` is checked by
  hand (`Results.ValidationProblem`, 400). One query: `Where`, `OrderBy`,
  `Skip`, `Take`.
- `/fortunes`: a Razor Page with no layout (the folder has no `_ViewStart`),
  `ToListAsync()` (no `ORDER BY`), sorted with `string.CompareOrdinal`.
  Razor's default HTML encoder also writes every non-ASCII character as a
  character reference (`&#x30D5;`), which the check decodes; the encoder's
  allowed ranges are left at their default.

Browser routes:

- `/form` and `/login` are Razor Pages. A `POST` first passes Razor Pages'
  antiforgery check (400 on failure), then model binding validates the
  DataAnnotations of the page's `[BindProperty]`s; invalid fields re-render
  the form (200). A valid form is answered with the `_FormResult` partial
  (`text/html; charset=utf-8`).
- The antiforgery cookie token stays the same for the browser and every
  request token generated from it validates, so a form page's pair is
  reusable. Antiforgery tokens are bound to the signed-in user, so `/form` is
  used anonymously (the harness never signs in before it).
- `POST /login`: the account is read with EF Core and the password checked
  with BCrypt.Net-Next against `users.password_bcrypt` (`$2b$`); ASP.NET Core
  Identity's `PasswordHasher` reads only its own PBKDF2 format, and Identity's
  user store would need its own tables. Success signs in with cookie
  authentication (a `NameIdentifier` claim with the id) and redirects (302) to
  `/me`; a wrong password re-renders the page (200) and signs nobody in.
- `GET /me` (`RequireAuthorization()`): the cookie handler decrypts the
  ticket; the handler reads the user's row by the id claim on every request.
  Without a session, the cookie handler answers 401 (an API endpoint in .NET
  10) or redirects to `/login`.
- One process, so Data Protection's key ring (antiforgery and the
  authentication cookie) is the same for every request. No login throttling
  exists in this setup.
- Global: `UseAuthentication()` and `UseAuthorization()` run for every
  request (ASP.NET Core has no documented way to scope them to some routes);
  for the other endpoints that is a look for the authentication cookie (none
  is sent) and no authorization policy. The antiforgery services were already
  registered by `AddRazorPages()`.
