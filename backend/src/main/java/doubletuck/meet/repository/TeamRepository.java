package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Team;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface TeamRepository extends JpaRepository<Team, Long> {

    Optional<Team> findByEventAndDisciplineAndAgeCategoryAndName(Event event, Discipline discipline,
            AgeCategory ageCategory, String name);

    List<Team> findByEventAndDisciplineAndAgeCategory(Event event, Discipline discipline, AgeCategory ageCategory);
}
