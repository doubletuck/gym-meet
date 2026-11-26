package doubletuck.meet.dto;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import org.jspecify.annotations.Nullable;

import java.time.LocalDate;

/**
 * A ranking with no competition of its own in its division, listed as a page of its own: a mixed
 * team's qualification, which ranks the men's and women's Competition I.
 *
 * @param slug    unique within the event, discipline and age category with its competitions:
 *                {@code qualification} for a qualifying ranking, {@code final} otherwise
 * @param name    "Qualification" or "Final"
 * @param date    the first day of the competitions it ranks
 * @param endDate their last day, when they were held over several days
 */
public record RankingSummaryResponse(
        Long id,
        String slug,
        String name,
        Discipline discipline,
        AgeCategory ageCategory,
        RankingType type,
        RankingPurpose purpose,
        LocalDate date,
        @Nullable LocalDate endDate) {
}
