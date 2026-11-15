using System.ComponentModel.DataAnnotations.Schema;
using Microsoft.EntityFrameworkCore;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);

var poolSize = int.TryParse(Environment.GetEnvironmentVariable("DB_POOL_SIZE"), out var size) ? size : 16;
var databaseUrl = Environment.GetEnvironmentVariable("DATABASE_URL")
    ?? "postgres://bench:bench@127.0.0.1:5432/bench";
builder.Services.AddDbContext<BenchContext>(options =>
    options.UseNpgsql(Database.ConnectionString(databaseUrl, poolSize)));
builder.Services.AddRazorPages();

var app = builder.Build();

app.MapGet("/text", () => "Hello World");
app.MapGet("/json", () => new { message = "Hello World" });
app.MapGet("/db-single", async (BenchContext db) => await db.Worlds.FindAsync(1));
app.MapRazorPages();

var port = Environment.GetEnvironmentVariable("PORT") ?? "8080";
app.Run($"http://0.0.0.0:{port}");

public sealed class BenchContext(DbContextOptions<BenchContext> options) : DbContext(options)
{
    public DbSet<World> Worlds => Set<World>();
}

[Table("world")]
public sealed class World
{
    [Column("id")]
    public int Id { get; set; }

    [Column("randomnumber")]
    public int RandomNumber { get; set; }
}

static class Database
{
    /// <summary>
    /// Translates postgres://user:password@host:port/database into an Npgsql
    /// connection string with "Maximum Pool Size" set to the harness's pool size.
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
        };
        return builder.ConnectionString;
    }
}
