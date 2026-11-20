using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using System.Globalization;
using System.Security.Claims;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.EntityFrameworkCore;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);

var poolSize = int.TryParse(Environment.GetEnvironmentVariable("DB_POOL_SIZE"), out var size) ? size : 16;
var databaseUrl = Environment.GetEnvironmentVariable("DATABASE_URL")
    ?? "postgres://bench:bench@127.0.0.1:5432/bench";
builder.Services.AddDbContext<BenchContext>(options =>
    options.UseNpgsql(Database.ConnectionString(databaseUrl, poolSize)));
builder.Services.AddRazorPages();
// Minimal API validation (DataAnnotations on parameters and body types): 400 when invalid.
builder.Services.AddValidation();
// System.Text.Json's web defaults also read numbers from JSON strings; the
// PUT body's randomNumber must be a JSON integer.
builder.Services.ConfigureHttpJsonOptions(options =>
    options.SerializerOptions.NumberHandling = JsonNumberHandling.Strict);
// Cookie authentication for POST /login and GET /me (Razor Pages' login page).
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(options => options.LoginPath = "/login");
builder.Services.AddAuthorization();

var app = builder.Build();

app.UseAuthentication();
app.UseAuthorization();

app.MapGet("/text", () => "Hello World");
app.MapGet("/json", () => new { message = "Hello World" });
app.MapGet("/db-single", async (BenchContext db) => await db.Worlds.FindAsync(1));

// One query per random id, untracked, so that a repeated id is read again.
app.MapGet("/queries", async (string? queries, BenchContext db) =>
{
    var worlds = new World[Bench.QueryCount(queries)];
    for (var i = 0; i < worlds.Length; i++)
    {
        var id = Bench.RandomId();
        worlds[i] = await db.Worlds.AsNoTracking().FirstAsync(w => w.Id == id);
    }
    return worlds;
});

// Each row is read with its own query (tracked) and given a new value; one
// SaveChangesAsync sends the UPDATEs in one batch and one transaction. The ids
// are sorted, so concurrent requests lock rows in the same order.
app.MapGet("/updates", async (string? queries, BenchContext db) =>
{
    var ids = new int[Bench.QueryCount(queries)];
    for (var i = 0; i < ids.Length; i++)
    {
        ids[i] = Bench.RandomId();
    }
    Array.Sort(ids);
    var worlds = new World[ids.Length];
    for (var i = 0; i < ids.Length; i++)
    {
        var id = ids[i];
        var world = await db.Worlds.FirstAsync(w => w.Id == id);
        world.RandomNumber = Bench.NewRandomNumber(world.RandomNumber);
        worlds[i] = world;
    }
    await db.SaveChangesAsync();
    return worlds;
});

// {id:int}: a non-integer id matches no route (404).
app.MapGet("/world/{id:int}", async (int id, BenchContext db) =>
    await db.Worlds.FindAsync(id) is { } world ? Results.Ok(world) : Results.NotFound());

app.MapGet("/worlds", async (
    BenchContext db,
    [Range(1, 10000)] int min = 1,
    [Range(1, 10000)] int max = 10000,
    [Range(1, 100)] int limit = 20,
    [Range(1, 1000)] int page = 1) =>
{
    if (min > max)
    {
        return Results.ValidationProblem(new Dictionary<string, string[]>
        {
            ["max"] = ["max must be greater than or equal to min."],
        });
    }
    var worlds = await db.Worlds.AsNoTracking()
        .Where(w => w.Id >= min && w.Id <= max)
        .OrderBy(w => w.Id)
        .Skip((page - 1) * limit)
        .Take(limit)
        .ToListAsync();
    return Results.Ok(worlds);
});

// The body is validated before the handler runs; then the row is loaded, changed and saved.
app.MapPut("/world/{id:int}", async (int id, WorldUpdate body, BenchContext db) =>
{
    var world = await db.Worlds.FindAsync(id);
    if (world is null)
    {
        return Results.NotFound();
    }
    world.RandomNumber = body.RandomNumber!.Value;
    await db.SaveChangesAsync();
    return Results.Ok(world);
});

// The signed-in user (from the authentication cookie), read from the database on every request.
app.MapGet("/me", async (ClaimsPrincipal principal, BenchContext db) =>
{
    if (!int.TryParse(principal.FindFirst(ClaimTypes.NameIdentifier)?.Value, CultureInfo.InvariantCulture, out var id))
    {
        return Results.Unauthorized();
    }
    var me = await db.Users.AsNoTracking()
        .Where(u => u.Id == id)
        .Select(u => new Me(u.Id, u.Username, u.DisplayName))
        .FirstOrDefaultAsync();
    return me is null ? Results.Unauthorized() : Results.Ok(me);
}).RequireAuthorization();

app.MapRazorPages();

var port = Environment.GetEnvironmentVariable("PORT") ?? "8080";
app.Run($"http://0.0.0.0:{port}");

public sealed class BenchContext(DbContextOptions<BenchContext> options) : DbContext(options)
{
    public DbSet<World> Worlds => Set<World>();
    public DbSet<Fortune> Fortunes => Set<Fortune>();
    public DbSet<Account> Users => Set<Account>();
}

[Table("world")]
public sealed class World
{
    [Column("id")]
    public int Id { get; set; }

    [Column("randomnumber")]
    public int RandomNumber { get; set; }
}

[Table("fortune")]
public sealed class Fortune
{
    [Column("id")]
    public int Id { get; set; }

    [Column("message")]
    public string Message { get; set; } = "";
}

[Table("users")]
public sealed class Account
{
    [Column("id")]
    public int Id { get; set; }

    [Column("username")]
    public string Username { get; set; } = "";

    [Column("display_name")]
    public string DisplayName { get; set; } = "";

    [Column("password_bcrypt")]
    public string PasswordBcrypt { get; set; } = "";
}

/// <summary>PUT /world/{id} body: a JSON integer from 1 to 10000.</summary>
public sealed class WorldUpdate
{
    [Required]
    [Range(1, 10000)]
    public int? RandomNumber { get; set; }
}

public sealed record Me(int Id, string Username, string DisplayName);

static class Bench
{
    /// <summary>The queries parameter: an integer clamped to 1..500, otherwise 1.</summary>
    public static int QueryCount(string? value) =>
        long.TryParse(value, NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out var count)
            ? (int)Math.Clamp(count, 1, 500)
            : 1;

    public static int RandomId() => Random.Shared.Next(1, 10001);

    /// <summary>A new random number, different from the current one so that every row is written.</summary>
    public static int NewRandomNumber(int current)
    {
        int value;
        do
        {
            value = RandomId();
        } while (value == current);
        return value;
    }
}

static class Database
{
    /// <summary>
    /// Translates postgres://user:password@host:port/database into an Npgsql
    /// connection string with "Maximum Pool Size" set to the harness's pool size
    /// and Npgsql's automatic preparation turned on ("Max Auto Prepare", 0 and
    /// so off by default): EF Core does not prepare its commands, and Npgsql's
    /// performance guide offers automatic preparation for O/RMs. The application
    /// runs fewer than ten distinct statements, so 20 keeps all of them prepared;
    /// "Auto Prepare Min Usages" keeps its default (5).
    /// </summary>
    public static string ConnectionString(string databaseUrl, int maxPoolSize)
    {
        var uri = new Uri(databaseUrl);
        var credentials = uri.UserInfo.Split(':', 2);
        var builder = new NpgsqlConnectionStringBuilder
        {
            Host = uri.Host,
            Port = uri.Port > 0 ? uri.Port : 5432,
            Database = Uri.UnescapeDataString(uri.AbsolutePath.TrimStart('/')),
            Username = Uri.UnescapeDataString(credentials[0]),
            Password = credentials.Length > 1 ? Uri.UnescapeDataString(credentials[1]) : null,
            MaxPoolSize = maxPoolSize,
            MaxAutoPrepare = 20,
        };
        return builder.ConnectionString;
    }
}
