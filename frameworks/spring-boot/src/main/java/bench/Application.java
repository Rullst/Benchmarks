package bench;

import java.net.URI;
import java.util.Map;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {

    public static void main(String[] args) {
        SpringApplication application = new SpringApplication(Application.class);
        String databaseUrl = System.getenv("DATABASE_URL");
        if (databaseUrl != null && !databaseUrl.isBlank()) {
            application.setDefaultProperties(datasourceProperties(databaseUrl));
        }
        application.run(args);
    }

    /**
     * Translates postgres://user:password@host:port/database into the JDBC URL and
     * credentials Spring Boot's spring.datasource.* properties expect.
     */
    static Map<String, Object> datasourceProperties(String databaseUrl) {
        URI uri = URI.create(databaseUrl);
        String[] credentials = uri.getUserInfo() == null ? new String[] {""} : uri.getUserInfo().split(":", 2);
        int port = uri.getPort() > 0 ? uri.getPort() : 5432;
        return Map.of(
                "spring.datasource.url", "jdbc:postgresql://" + uri.getHost() + ":" + port + uri.getPath(),
                "spring.datasource.username", credentials[0],
                "spring.datasource.password", credentials.length > 1 ? credentials[1] : "");
    }
}
