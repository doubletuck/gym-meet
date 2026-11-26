package doubletuck.meet.repository;

import doubletuck.meet.domain.Judge;
import doubletuck.meet.domain.Competition;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface JudgeRepository extends JpaRepository<Judge, Long> {

    List<Judge> findByCompetition(Competition competition);

    List<Judge> findByCompetitionId(Long competitionId);

    void deleteByCompetition(Competition competition);
}
