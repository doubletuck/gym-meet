package doubletuck.meet.repository;

import doubletuck.meet.domain.Athlete;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Participant;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
public interface ParticipantRepository extends JpaRepository<Participant, Long> {

    Optional<Participant> findByEventAndAthlete(Event event, Athlete athlete);

    List<Participant> findByEvent(Event event);

    List<Participant> findByEventId(Long eventId);

    List<Participant> findByAthlete(Athlete athlete);

    @Query("select p from Participant p join fetch p.event left join fetch p.club where p.athlete in :athletes")
    List<Participant> findWithEventByAthleteIn(Collection<Athlete> athletes);
}
