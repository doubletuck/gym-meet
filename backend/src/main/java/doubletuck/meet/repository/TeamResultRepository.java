package doubletuck.meet.repository;

import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.TeamResult;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository
public interface TeamResultRepository extends JpaRepository<TeamResult, Long> {

    List<TeamResult> findByRanking(Ranking ranking);

    List<TeamResult> findByRankingIn(Collection<Ranking> rankings);

    /** A NOC's team results in the rankings of this competition's routines. */
    @Query("select t from TeamResult t join t.ranking r join r.competitions c "
            + "where c = :competition and t.team.noc = :noc")
    List<TeamResult> findByCompetitionAndNoc(Competition competition, String noc);

    void deleteByRankingIn(Collection<Ranking> rankings);
}
