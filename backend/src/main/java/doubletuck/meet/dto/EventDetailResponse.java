package doubletuck.meet.dto;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;
import org.jspecify.annotations.Nullable;

import java.time.LocalDate;
import java.util.List;

/** An event and its sessions, grouped by discipline and age category. */
public record EventDetailResponse(
        String slug,
        String title,
        LocalDate startDate,
        LocalDate endDate,
        String city,
        String countryCode,
        @Nullable String venue,
        EventLevel level,
        @Nullable String figEventNumber,
        @Nullable String apparatusSuppliers,
        List<DivisionSessions> divisions) {

    /** One discipline and age category's sessions, in competition order. */
    public record DivisionSessions(Discipline discipline, AgeCategory ageCategory,
            List<SessionSummaryResponse> sessions) {
    }

    public static EventDetailResponse from(Event event, List<DivisionSessions> divisions) {
        return new EventDetailResponse(event.getSlug(), event.getTitle(), event.getStartDate(), event.getEndDate(),
                event.getCity(), event.getCountryCode(), event.getVenue(), event.getLevel(),
                event.getFigEventNumber(), event.getApparatusSuppliers(), divisions);
    }
}
