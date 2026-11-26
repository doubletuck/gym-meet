package doubletuck.meet.dto;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;
import org.jspecify.annotations.Nullable;

import java.time.LocalDate;
import java.util.List;

/** An event and its competitions, grouped by discipline and age category. */
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
        List<DivisionCompetitions> divisions) {

    /** One discipline and age category's competitions, in the order they're held. */
    public record DivisionCompetitions(Discipline discipline, AgeCategory ageCategory,
            List<CompetitionSummaryResponse> competitions) {
    }

    public static EventDetailResponse from(Event event, List<DivisionCompetitions> divisions) {
        return new EventDetailResponse(event.getSlug(), event.getTitle(), event.getStartDate(), event.getEndDate(),
                event.getCity(), event.getCountryCode(), event.getVenue(), event.getLevel(),
                event.getFigEventNumber(), event.getApparatusSuppliers(), divisions);
    }
}
