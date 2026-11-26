package doubletuck.meet.repository;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Ranking;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;

@Repository
public interface AllAroundResultRepository extends JpaRepository<AllAroundResult, Long> {

    List<AllAroundResult> findByRanking(Ranking ranking);

    List<AllAroundResult> findByParticipant(Participant participant);

    boolean existsByParticipant(Participant participant);

    void deleteByRankingIn(Collection<Ranking> rankings);

    // Fetches each result's athlete and club with it, rather than one query per athlete
    @Query("select r from AllAroundResult r join fetch r.participant p join fetch p.athlete left join fetch p.club "
            + "where r.ranking = :ranking")
    List<AllAroundResult> findResultsByRanking(Ranking ranking);
}
