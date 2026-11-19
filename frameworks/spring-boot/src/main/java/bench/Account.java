package bench;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** A row of the phase-2 `users` table. */
@Entity
@Table(name = "users")
public class Account {

    @Id
    private Integer id;

    private String username;

    @Column(name = "display_name")
    private String displayName;

    @Column(name = "password_bcrypt")
    private String passwordBcrypt;

    protected Account() {
    }

    public Integer getId() {
        return id;
    }

    public String getUsername() {
        return username;
    }

    public String getDisplayName() {
        return displayName;
    }

    public String getPasswordBcrypt() {
        return passwordBcrypt;
    }
}
