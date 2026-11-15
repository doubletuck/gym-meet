package doubletuck.meet.controller;

import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.EventLevel;
import doubletuck.meet.dto.EventDetailResponse;
import doubletuck.meet.dto.EventRequest;
import doubletuck.meet.dto.EventResponse;
import doubletuck.meet.dto.EventSummaryResponse;
import doubletuck.meet.service.EventQueryService;
import doubletuck.meet.service.EventService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/events")
public class EventController {

    private final EventService eventService;
    private final EventQueryService eventQueryService;

    public EventController(EventService eventService, EventQueryService eventQueryService) {
        this.eventService = eventService;
        this.eventQueryService = eventQueryService;
    }

    @GetMapping
    public ResponseEntity<List<EventSummaryResponse>> findEvents(
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) EventLevel level,
            @RequestParam(required = false) Discipline discipline) {
        return PublicResponses.ok(eventQueryService.findEvents(year, level, discipline));
    }

    @GetMapping("/{slug}")
    public ResponseEntity<EventDetailResponse> findEvent(@PathVariable String slug) {
        return eventQueryService.findEvent(slug)
                .map(PublicResponses::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<EventResponse> create(@Valid @RequestBody EventRequest request) {
        EventResponse created = eventService.create(request);
        return new ResponseEntity<>(created, HttpStatus.CREATED);
    }

    @PutMapping("/{id}")
    public ResponseEntity<EventResponse> update(@PathVariable Long id, @Valid @RequestBody EventRequest request) {
        return eventService.update(id, request)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteById(@PathVariable Long id) {
        boolean deleted = eventService.deleteById(id);
        return deleted ? ResponseEntity.noContent().build() : ResponseEntity.notFound().build();
    }
}
