package bench;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class BenchController {

    public record Message(String message) {
    }

    private final WorldRepository worlds;

    public BenchController(WorldRepository worlds) {
        this.worlds = worlds;
    }

    @GetMapping(value = "/text", produces = MediaType.TEXT_PLAIN_VALUE)
    public String text() {
        return "Hello World";
    }

    @GetMapping("/json")
    public Message json() {
        return new Message("Hello World");
    }

    @GetMapping("/db-single")
    public World dbSingle() {
        return worlds.findById(1).orElseThrow();
    }
}
