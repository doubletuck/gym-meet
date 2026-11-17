package doubletuck.meet.dto;

import doubletuck.meet.domain.Discipline;
import org.jspecify.annotations.Nullable;

/**
 * An athlete in search results.
 *
 * @param noc the country of their most recent entry; null when they have none
 */
public record AthleteSummaryResponse(
        Long id,
        String surname,
        String givenName,
        Discipline discipline,
        @Nullable String noc) {
}
