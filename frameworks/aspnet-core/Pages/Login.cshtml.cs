using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.EntityFrameworkCore;

namespace AspNetCoreBench.Pages;

/// <summary>
/// POST /login: antiforgery, then the bcrypt hash of users checked with
/// BCrypt.Net-Next (ASP.NET Core Identity's hasher reads only its own PBKDF2
/// format), then cookie authentication signs the user in.
/// </summary>
public class LoginModel(BenchContext db) : PageModel
{
    [BindProperty]
    [Required]
    public string? Username { get; set; }

    [BindProperty]
    [Required]
    public string? Password { get; set; }

    public void OnGet()
    {
    }

    public async Task<IActionResult> OnPostAsync()
    {
        if (!ModelState.IsValid)
        {
            return Page();
        }
        var account = await db.Users.AsNoTracking().FirstOrDefaultAsync(u => u.Username == Username);
        if (account is null || !BCrypt.Net.BCrypt.Verify(Password, account.PasswordBcrypt))
        {
            return Page();
        }
        var identity = new ClaimsIdentity(
            [new Claim(ClaimTypes.NameIdentifier, account.Id.ToString(CultureInfo.InvariantCulture))],
            CookieAuthenticationDefaults.AuthenticationScheme);
        await HttpContext.SignInAsync(CookieAuthenticationDefaults.AuthenticationScheme, new ClaimsPrincipal(identity));
        return LocalRedirect("/me");
    }
}
