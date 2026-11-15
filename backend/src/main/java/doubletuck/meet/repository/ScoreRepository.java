package doubletuck.meet.repository;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.Session;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ScoreRepository extends JpaRepository<Score, Long> {

    Optional<Score> findByParticipantAndSessionAndApparatus(Participant participant, Session session,
            Apparatus apparatus);

    List<Score> findBySession(Session session);

    List<Score> findBySessionId(Long sessionId);

    List<Score> findByParticipant(Participant participant);

    boolean existsByParticipant(Participant participant);

    void deleteBySession(Session session);

    // Fetches each result's athlete and club with it, rather than one query per athlete
    @Query("select r from Score r join fetch r.participant p join fetch p.athlete left join fetch p.club "
            + "where r.session = :session")
    List<Score> findResultsBySession(Session session);
}
