package bench;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "fortune")
public class Fortune {

    @Id
    private Integer id;

    private String message;

    protected Fortune() {
    }

    Fortune(int id, String message) {
        this.id = id;
        this.message = message;
    }

    public Integer getId() {
        return id;
    }

    public String getMessage() {
        return message;
    }
}
