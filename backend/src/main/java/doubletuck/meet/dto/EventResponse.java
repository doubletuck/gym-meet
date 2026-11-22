package doubletuck.meet.dto;

import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;

import java.time.Instant;
import java.time.LocalDate;

public record EventResponse(
        Long id,
        String figEventNumber,
        String slug,
        String title,
        String shortName,
        LocalDate startDate,
        LocalDate endDate,
        String city,
        String countryCode,
        String venue,
        String apparatusSuppliers,
        EventLevel level,
        Instant creationTimestamp,
        Instant lastUpdateTimestamp) {

    public static EventResponse from(Event event) {
        return new EventResponse(
                event.getId(),
                event.getFigEventNumber(),
                event.getSlug(),
                event.getTitle(),
                event.getShortName(),
                event.getStartDate(),
                event.getEndDate(),
                event.getCity(),
                event.getCountryCode(),
                event.getVenue(),
                event.getApparatusSuppliers(),
                event.getLevel(),
                event.getCreationTimestamp(),
                event.getLastUpdateTimestamp());
    }
}
