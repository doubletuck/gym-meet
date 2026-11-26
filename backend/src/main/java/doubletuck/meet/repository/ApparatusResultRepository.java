package doubletuck.meet.repository;

import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Ranking;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository
public interface ApparatusResultRepository extends JpaRepository<ApparatusResult, Long> {

    List<ApparatusResult> findByRanking(Ranking ranking);

    List<ApparatusResult> findByParticipant(Participant participant);

    boolean existsByParticipant(Participant participant);

    void deleteByRankingIn(Collection<Ranking> rankings);

    // Fetches each result's athlete and club with it, rather than one query per athlete
    @Query("select r from ApparatusResult r join fetch r.participant p join fetch p.athlete left join fetch p.club "
            + "where r.ranking in :rankings")
    List<ApparatusResult> findResultsByRankingIn(Collection<Ranking> rankings);
}
