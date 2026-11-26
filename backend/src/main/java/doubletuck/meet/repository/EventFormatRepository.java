package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventFormat;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface EventFormatRepository extends JpaRepository<EventFormat, Long> {

    Optional<EventFormat> findByEventAndDisciplineAndAgeCategory(Event event, Discipline discipline,
            AgeCategory ageCategory);
}
