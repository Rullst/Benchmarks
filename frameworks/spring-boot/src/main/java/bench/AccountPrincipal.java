package bench;

import java.util.List;

import org.springframework.security.core.userdetails.User;

/** The signed-in user Spring Security keeps in the HTTP session: the username and the row's id. */
public class AccountPrincipal extends User {

    private static final long serialVersionUID = 1L;

    private final int id;

    public AccountPrincipal(int id, String username, String password) {
        super(username, password, List.of());
        this.id = id;
    }

    public int getId() {
        return id;
    }
}
