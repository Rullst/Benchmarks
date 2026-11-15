using Microsoft.AspNetCore.Mvc.RazorPages;

namespace AspNetCoreBench.Pages;

public class HelloModel : PageModel
{
    public string Name { get; private set; } = "";

    public void OnGet()
    {
        Name = "World";
    }
}
