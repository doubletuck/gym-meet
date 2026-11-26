package doubletuck.meet.service;

import doubletuck.meet.domain.Event;
import doubletuck.meet.dto.EventRequest;
import doubletuck.meet.dto.EventResponse;
import doubletuck.meet.exception.ConflictException;
import doubletuck.meet.repository.EventRepository;
import doubletuck.meet.repository.ParticipantRepository;
import doubletuck.meet.repository.CompetitionRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

@Service
public class EventService {

    private final EventRepository eventRepository;
    private final CompetitionRepository competitionRepository;
    private final ParticipantRepository participantRepository;

    @Autowired
    public EventService(EventRepository eventRepository, CompetitionRepository competitionRepository,
            ParticipantRepository participantRepository) {
        this.eventRepository = eventRepository;
        this.competitionRepository = competitionRepository;
        this.participantRepository = participantRepository;
    }

    @Transactional
    public EventResponse create(EventRequest request) {
        checkForDuplicate(request, null);
        Event event = new Event();
        applyRequest(event, request);
        return EventResponse.from(eventRepository.save(event));
    }

    @Transactional
    public Optional<EventResponse> update(Long id, EventRequest request) {
        return eventRepository.findById(id).map(existing -> {
            checkForDuplicate(request, id);
            applyRequest(existing, request);
            return EventResponse.from(eventRepository.save(existing));
        });
    }

    @Transactional
    public boolean deleteById(Long id) {
        if (eventRepository.findById(id).isEmpty()) {
            return false;
        }
        if (!competitionRepository.findByEventId(id).isEmpty() || !participantRepository.findByEventId(id).isEmpty()) {
            throw new ConflictException(
                    "Event " + id + " has dependent competitions or participants and cannot be deleted");
        }
        eventRepository.deleteById(id);
        return true;
    }

    private void checkForDuplicate(EventRequest request, Long excludeId) {
        if (request.figEventNumber() != null && !request.figEventNumber().isBlank()) {
            eventRepository.findByFigEventNumber(request.figEventNumber())
                    .filter(event -> !event.getId().equals(excludeId))
                    .ifPresent(event -> {
                        throw new ConflictException(
                                "An event with FIG event number '" + request.figEventNumber() + "' already exists");
                    });
        }
        eventRepository.findBySlug(request.slug())
                .filter(event -> !event.getId().equals(excludeId))
                .ifPresent(event -> {
                    throw new ConflictException("An event with slug '" + request.slug() + "' already exists");
                });
        eventRepository.findByTitleIgnoreCaseAndStartDate(request.title(), request.startDate())
                .filter(event -> !event.getId().equals(excludeId))
                .ifPresent(event -> {
                    throw new ConflictException("An event titled '" + request.title() + "' starting "
                            + request.startDate() + " already exists");
                });
    }

    private void applyRequest(Event event, EventRequest request) {
        event.setFigEventNumber(request.figEventNumber());
        event.setSlug(request.slug());
        event.setTitle(request.title());
        event.setShortName(request.shortName());
        event.setStartDate(request.startDate());
        event.setEndDate(request.endDate());
        event.setCity(request.city());
        event.setCountryCode(request.countryCode());
        event.setVenue(request.venue());
        event.setApparatusSuppliers(request.apparatusSuppliers());
        event.setLevel(request.level());
    }
}
