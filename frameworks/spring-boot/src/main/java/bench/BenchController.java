package bench;

import java.util.List;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class BenchController {

    public record Message(String message) {
    }

    /** PUT /world/{id} body, checked by Bean Validation before the handler runs. */
    public record WorldUpdate(@NotNull @Min(1) @Max(10_000) Integer randomNumber) {
    }

    private final WorldRepository worlds;
    private final WorldService service;

    public BenchController(WorldRepository worlds, WorldService service) {
        this.worlds = worlds;
        this.service = service;
    }

    /** The queries parameter: an integer clamped to 1..500, otherwise 1. */
    static int queryCount(String value) {
        try {
            return Math.clamp(Long.parseLong(value), 1, 500);
        } catch (NumberFormatException e) {
            return 1;
        }
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

    @GetMapping("/queries")
    public List<World> queries(@RequestParam(name = "queries", required = false) String queries) {
        return service.read(queryCount(queries));
    }

    @GetMapping("/updates")
    public List<World> updates(@RequestParam(name = "queries", required = false) String queries) {
        return service.update(queryCount(queries));
    }

    /** GET /world/{id}: a non-integer id is a type mismatch (400); no row is 404. */
    @GetMapping("/world/{id}")
    public World world(@PathVariable("id") int id) {
        return worlds.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    }

    /**
     * GET /worlds: Spring MVC's built-in method validation checks the
     * constraints on the parameters (400); min <= max is checked by hand.
     */
    @GetMapping("/worlds")
    public List<World> worlds(
            @RequestParam(name = "min", defaultValue = "1") @Min(1) @Max(10_000) int min,
            @RequestParam(name = "max", defaultValue = "10000") @Min(1) @Max(10_000) int max,
            @RequestParam(name = "limit", defaultValue = "20") @Min(1) @Max(100) int limit,
            @RequestParam(name = "page", defaultValue = "1") @Min(1) @Max(1_000) int page) {
        if (min > max) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "min must not exceed max");
        }
        return worlds.findByIdBetweenOrderByIdAsc(min, max, PageRequest.of(page - 1, limit));
    }

    /** PUT /world/{id}: the body is validated (400) before the row is loaded, changed and saved. */
    @PutMapping("/world/{id}")
    public World updateWorld(@PathVariable("id") int id, @Valid @RequestBody WorldUpdate body) {
        return service.setRandomNumber(id, body.randomNumber())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    }
}
