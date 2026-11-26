package doubletuck.meet.repository;

import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.domain.TeamResultScore;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository
public interface TeamResultScoreRepository extends JpaRepository<TeamResultScore, TeamResultScore.Key> {

    List<TeamResultScore> findByTeamResult(TeamResult teamResult);

    List<TeamResultScore> findByTeamResultIn(Collection<TeamResult> teamResults);

    List<TeamResultScore> findByScoreIn(Collection<Score> scores);

    void deleteByTeamResultIn(Collection<TeamResult> teamResults);
}
