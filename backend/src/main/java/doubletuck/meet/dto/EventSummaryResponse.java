package doubletuck.meet.dto;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;

import java.time.LocalDate;
import java.util.List;

/** An event in the events list, with the disciplines and age categories it has results for. */
public record EventSummaryResponse(
        String slug,
        String title,
        LocalDate startDate,
        LocalDate endDate,
        String city,
        String countryCode,
        EventLevel level,
        List<Division> divisions) {

    public record Division(Discipline discipline, AgeCategory ageCategory) {
    }

    public static EventSummaryResponse from(Event event, List<Division> divisions) {
        return new EventSummaryResponse(event.getSlug(), event.getTitle(), event.getStartDate(), event.getEndDate(),
                event.getCity(), event.getCountryCode(), event.getLevel(), divisions);
    }
}
