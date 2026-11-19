using System.ComponentModel.DataAnnotations;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace AspNetCoreBench.Pages;

/// <summary>
/// GET /form renders the form with its antiforgery field; POST /form is
/// checked by Razor Pages' antiforgery filter (400), then bound and
/// validated with DataAnnotations (the form re-rendered when invalid), then
/// answered with the _FormResult partial.
/// </summary>
public class FormModel : PageModel
{
    [BindProperty]
    [Required]
    [StringLength(64, MinimumLength = 1)]
    public string? Name { get; set; }

    [BindProperty]
    [Required]
    [Range(1, 10000)]
    public int? RandomNumber { get; set; }

    public void OnGet()
    {
    }

    public IActionResult OnPost() => ModelState.IsValid ? Partial("_FormResult", this) : Page();
}
