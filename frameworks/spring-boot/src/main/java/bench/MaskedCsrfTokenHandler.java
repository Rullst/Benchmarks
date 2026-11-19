package bench;

import java.util.function.Supplier;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.security.web.csrf.CsrfTokenRequestHandler;
import org.springframework.security.web.csrf.XorCsrfTokenRequestAttributeHandler;

/**
 * Spring Security's default CSRF request handler (XorCsrfTokenRequestAttributeHandler),
 * unchanged except for one case: in Spring Security 7.1.2, a submitted masked token
 * that is valid Base64 of the right length but whose unmasked bytes are not UTF-8
 * (a token changed in one character, for instance) makes it throw an
 * IllegalArgumentException, which the servlet container answers with a 500. Here that
 * token counts as a wrong one, so CsrfFilter refuses the request with a 403.
 */
final class MaskedCsrfTokenHandler implements CsrfTokenRequestHandler {

    private final XorCsrfTokenRequestAttributeHandler delegate = new XorCsrfTokenRequestAttributeHandler();

    @Override
    public void handle(HttpServletRequest request, HttpServletResponse response, Supplier<CsrfToken> csrfToken) {
        delegate.handle(request, response, csrfToken);
    }

    @Override
    public String resolveCsrfTokenValue(HttpServletRequest request, CsrfToken csrfToken) {
        try {
            return delegate.resolveCsrfTokenValue(request, csrfToken);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }
}
