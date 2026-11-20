package bench;

import java.util.List;
import java.util.Optional;

import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface WorldRepository extends JpaRepository<World, Integer> {

    /**
     * One row by id with a JPQL query, which always runs its SELECT; findById
     * would return a row already loaded in the persistence context without one,
     * so a repeated id in /updates (one transaction) would not be read again.
     */
    @Query("SELECT w FROM World w WHERE w.id = :id")
    Optional<World> fetchById(@Param("id") int id);

    /** GET /worlds: the filter, ORDER BY, LIMIT and OFFSET in one query (a List, so no count query). */
    List<World> findByIdBetweenOrderByIdAsc(int min, int max, Pageable page);
}
