package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface CompetitionRepository extends JpaRepository<Competition, Long> {

    /** A null apparatus, round or part matches only a competition where it is also null. */
    Optional<Competition> findByEventAndTypeAndDisciplineAndAgeCategoryAndApparatusAndRoundAndPart(Event event,
            CompetitionType type, Discipline discipline, AgeCategory ageCategory, Apparatus apparatus, Integer round,
            Integer part);

    List<Competition> findByEvent(Event event);

    List<Competition> findByEventId(Long eventId);

    @Query("select distinct new doubletuck.meet.repository.EventDivision(c.event.id, c.discipline, c.ageCategory) "
            + "from Competition c")
    List<EventDivision> findEventDivisions();

    List<Competition> findByEventAndDisciplineAndAgeCategory(Event event, Discipline discipline,
            AgeCategory ageCategory);
}
