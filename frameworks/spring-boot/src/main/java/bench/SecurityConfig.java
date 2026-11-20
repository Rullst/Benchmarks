package bench;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Spring Security for the browser routes only (securityMatcher): CSRF
 * protection (its default: a token in the HTTP session, XOR-masked in the
 * _csrf field; MaskedCsrfTokenHandler only turns a 500 on a garbled token
 * into the 403 of a wrong one), form login and the session. The other
 * endpoints match no filter chain and keep their stack.
 */
@Configuration
public class SecurityConfig {

    @Bean
    SecurityFilterChain browserRoutes(HttpSecurity http) throws Exception {
        http.securityMatcher("/form", "/login", "/me")
                .csrf(csrf -> csrf.csrfTokenRequestHandler(new MaskedCsrfTokenHandler()))
                .authorizeHttpRequests(requests -> requests
                        .requestMatchers("/me").authenticated()
                        .anyRequest().permitAll())
                .formLogin(login -> login
                        .loginPage("/login")
                        .defaultSuccessUrl("/me", true)
                        .permitAll());
        return http.build();
    }

    /**
     * Accounts from the users table. The stored hash gets the {bcrypt} prefix
     * that Spring Security's default DelegatingPasswordEncoder reads.
     */
    @Bean
    UserDetailsService accounts(AccountRepository accounts) {
        return username -> accounts.findByUsername(username)
                .map(account -> new AccountPrincipal(account.getId(), account.getUsername(),
                        "{bcrypt}" + account.getPasswordBcrypt()))
                .orElseThrow(() -> new UsernameNotFoundException(username));
    }
}
