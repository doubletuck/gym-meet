package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Ranking;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface RankingRepository extends JpaRepository<Ranking, Long> {

    /** The rankings of this competition's routines, alone or combined with others'. */
    @Query("select r from Ranking r join r.competitions c where c = :competition")
    List<Ranking> findByCompetition(Competition competition);

    List<Ranking> findByEventAndDisciplineAndAgeCategory(Event event, Discipline discipline, AgeCategory ageCategory);
}
