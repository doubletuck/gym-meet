package doubletuck.meet.repository;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.Competition;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ScoreRepository extends JpaRepository<Score, Long> {

    Optional<Score> findByParticipantAndCompetitionAndApparatus(Participant participant, Competition competition,
            Apparatus apparatus);

    List<Score> findByCompetition(Competition competition);

    List<Score> findByCompetitionId(Long competitionId);

    List<Score> findByParticipant(Participant participant);

    boolean existsByParticipant(Participant participant);

    void deleteByCompetition(Competition competition);

    // Fetches each result's athlete and club with it, rather than one query per athlete
    @Query("select r from Score r join fetch r.participant p join fetch p.athlete left join fetch p.club "
            + "where r.competition = :competition")
    List<Score> findResultsByCompetition(Competition competition);
}
