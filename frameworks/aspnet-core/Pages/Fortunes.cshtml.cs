using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace AspNetCoreBench.Pages;

public class FortunesModel(BenchContext db) : PageModel
{
    public List<Fortune> Fortunes { get; private set; } = [];

    /// <summary>Every fortune (no ORDER BY), plus one added here, sorted by ordinal comparison.</summary>
    public async Task OnGetAsync()
    {
        var fortunes = await db.Fortunes.AsNoTracking().ToListAsync();
        fortunes.Add(new Fortune { Id = 0, Message = "Additional fortune added at request time." });
        fortunes.Sort((a, b) => string.CompareOrdinal(a.Message, b.Message));
        Fortunes = fortunes;
    }
}
