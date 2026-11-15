# ASP.NET Core

| | |
| --- | --- |
| Version | ASP.NET Core 10.0.15 (.NET 10 LTS), Entity Framework Core 10.0.15, Npgsql and its EF Core provider 10.0.3 (exact versions in `packages.lock.json`) |
| Build | `dotnet restore --locked-mode` and `dotnet publish --configuration Release` (framework-dependent) with the .NET SDK 10.0.404 |
| Server | Kestrel on `0.0.0.0:$PORT` (`app.Run(url)`); the pipeline has only routing and the endpoints |
| Workers | the .NET thread pool, sized by the runtime for the 2 vCPUs; Server GC (the Web SDK's default, with DATAS since .NET 9), heap limit at the runtime's default of 75% of the container's memory |
| Endpoints | Minimal APIs for `/text`, `/json` and `/db-single`; a Razor Page (`Pages/Hello.cshtml`, `@page "/html"`) for `/html` |
| Database | EF Core `DbContext` registered with `AddDbContext`, `FindAsync(1)`; Npgsql `Maximum Pool Size` = `DB_POOL_SIZE` (16) in a connection string built from `DATABASE_URL` in `Program.cs`; no migrations |
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
