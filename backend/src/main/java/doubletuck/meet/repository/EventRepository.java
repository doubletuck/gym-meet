package doubletuck.meet.repository;

import doubletuck.meet.domain.Event;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public interface EventRepository extends JpaRepository<Event, Long> {

    Optional<Event> findByFigEventNumber(String figEventNumber);

    Optional<Event> findBySlug(String slug);

    Optional<Event> findByTitleIgnoreCaseAndStartDate(String title, LocalDate startDate);

    /** Events with this title whose dates overlap {@code start} to {@code end}. */
    List<Event> findByTitleIgnoreCaseAndStartDateLessThanEqualAndEndDateGreaterThanEqual(String title,
            LocalDate end, LocalDate start);
}
