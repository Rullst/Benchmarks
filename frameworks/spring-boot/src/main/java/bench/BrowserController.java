package bench;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.server.ResponseStatusException;

/**
 * The browser routes (/form, /login, /me). Spring Security (SecurityConfig)
 * checks the CSRF token of every POST to them and processes POST /login itself
 * (form login); these handlers render the pages and answer /me.
 */
@Controller
public class BrowserController {

    /** POST /form fields, bound and validated by Spring MVC (400 when invalid). */
    public record FormInput(
            @NotNull @Size(min = 1, max = 64) String name,
            @NotNull @Min(1) @Max(10_000) Integer randomNumber) {
    }

    public record Me(int id, String username, String displayName) {
    }

    private final AccountRepository accounts;

    public BrowserController(AccountRepository accounts) {
        this.accounts = accounts;
    }

    @GetMapping("/form")
    public String form() {
        return "form";
    }

    @PostMapping("/form")
    public String submitForm(@Valid @ModelAttribute FormInput input, Model model) {
        model.addAttribute("name", input.name());
        model.addAttribute("randomNumber", input.randomNumber());
        return "form-result";
    }

    @GetMapping("/login")
    public String login() {
        return "login";
    }

    /** GET /me: the principal comes from the HTTP session; the user's row is read on every request. */
    @GetMapping(value = "/me", produces = MediaType.APPLICATION_JSON_VALUE)
    @ResponseBody
    public Me me(@AuthenticationPrincipal AccountPrincipal principal) {
        Account account = accounts.findById(principal.getId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED));
        return new Me(account.getId(), account.getUsername(), account.getDisplayName());
    }
}
