package bench;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ThreadLocalRandom;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class WorldService {

    private final WorldRepository worlds;

    public WorldService(WorldRepository worlds) {
        this.worlds = worlds;
    }

    static int randomId() {
        return ThreadLocalRandom.current().nextInt(1, 10_001);
    }

    /** A new random number, different from the current one so that every row is written. */
    static int newRandomNumber(int current) {
        int value;
        do {
            value = randomId();
        } while (value == current);
        return value;
    }

    /** GET /queries: one SELECT per random id. */
    public List<World> read(int count) {
        List<World> result = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            result.add(worlds.fetchById(randomId()).orElseThrow());
        }
        return result;
    }

    /**
     * GET /updates: one transaction. The ids are sorted, so concurrent requests
     * lock rows in the same order; each row is read with its own SELECT and given
     * a new value, and Hibernate's dirty checking writes it with an UPDATE (flushed
     * before the next query on world, and at commit).
     */
    @Transactional
    public List<World> update(int count) {
        int[] ids = new int[count];
        Arrays.setAll(ids, i -> randomId());
        Arrays.sort(ids);
        List<World> result = new ArrayList<>(count);
        for (int id : ids) {
            World world = worlds.fetchById(id).orElseThrow();
            world.setRandomNumber(newRandomNumber(world.getRandomNumber()));
            result.add(world);
        }
        return result;
    }

    /** PUT /world/{id}: load the row, set the field; the transaction's commit writes it. */
    @Transactional
    public Optional<World> setRandomNumber(int id, int randomNumber) {
        Optional<World> world = worlds.findById(id);
        world.ifPresent(row -> row.setRandomNumber(randomNumber));
        return world;
    }
}
