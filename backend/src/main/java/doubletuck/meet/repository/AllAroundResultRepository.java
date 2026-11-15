package doubletuck.meet.repository;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Session;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface AllAroundResultRepository extends JpaRepository<AllAroundResult, Long> {

    Optional<AllAroundResult> findByParticipantAndSession(Participant participant, Session session);

    List<AllAroundResult> findBySession(Session session);

    List<AllAroundResult> findByParticipant(Participant participant);

    boolean existsByParticipant(Participant participant);

    void deleteBySession(Session session);

    // Fetches each result's athlete and club with it, rather than one query per athlete
    @Query("select r from AllAroundResult r join fetch r.participant p join fetch p.athlete left join fetch p.club "
            + "where r.session = :session")
    List<AllAroundResult> findResultsBySession(Session session);
}
