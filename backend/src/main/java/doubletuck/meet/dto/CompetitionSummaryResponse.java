package doubletuck.meet.dto;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.RankingPurpose;
import org.jspecify.annotations.Nullable;

import java.time.LocalDate;

/**
 * A competition as listed: on an event's page, in an athlete's career and on its own results page.
 *
 * @param slug      unique within the event, discipline and age category, e.g. {@code beam-final}
 * @param name      named from its rankings, e.g. "Team and All-Around Final · Apparatus Qualification"
 * @param shortName as briefly as a tile under an apparatus can put it, e.g. "Qualification", "AA Final"
 * @param round     an elimination round within the competition, with scores reset each round
 * @param purposes  what the competition's team, all-around and apparatus rankings are for
 * @param date      the day it was held; for a split competition's combined row, its first part's
 * @param endDate   a split competition's combined row's last day, when its parts were held over
 *                  several days
 */
public record CompetitionSummaryResponse(
        Long id,
        String slug,
        String name,
        String shortName,
        Discipline discipline,
        AgeCategory ageCategory,
        CompetitionType type,
        @Nullable Apparatus apparatus,
        @Nullable Integer round,
        @Nullable Integer part,
        RankingPurposes purposes,
        LocalDate date,
        @Nullable LocalDate endDate) {

    /**
     * What a competition's rankings of each type are for: where its routines are ranked more than once
     * for a title, the purpose deciding the most (final, then qualifying, then informational); null where
     * it has no ranking of that type.
     */
    public record RankingPurposes(@Nullable RankingPurpose team, @Nullable RankingPurpose allAround,
            @Nullable RankingPurpose apparatus) {
    }
}
