package doubletuck.meet.service;

import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.dto.RankingSummaryResponse;

import java.time.LocalDate;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;

/** Rankings listed as pages of their own: those ranking no competition of their own division. */
public final class RankingSummaries {

    private RankingSummaries() {
    }

    /** Whether the ranking ranks only other divisions' competitions (a mixed team's qualification). */
    public static boolean isOwnPage(Ranking ranking) {
        return ranking.getCompetitions().stream()
                .noneMatch(competition -> competition.getDiscipline() == ranking.getDiscipline());
    }

    /** The event's rankings that are pages of their own, by date. */
    public static List<Ranking> ownPages(Collection<Ranking> rankings) {
        return rankings.stream().filter(RankingSummaries::isOwnPage)
                .sorted(Comparator.comparing(RankingSummaries::firstDay).thenComparing(Ranking::getId))
                .toList();
    }

    public static RankingSummaryResponse of(Ranking ranking) {
        boolean qualifying = ranking.getPurpose() == RankingPurpose.QUALIFYING;
        LocalDate first = firstDay(ranking);
        LocalDate last = ranking.getCompetitions().stream().map(Competition::getDate)
                .max(Comparator.naturalOrder()).orElse(first);
        return new RankingSummaryResponse(ranking.getId(), qualifying ? "qualification" : "final",
                qualifying ? "Qualification" : "Final", ranking.getDiscipline(), ranking.getAgeCategory(),
                ranking.getType(), ranking.getPurpose(), first, last.isAfter(first) ? last : null);
    }

    private static LocalDate firstDay(Ranking ranking) {
        return ranking.getCompetitions().stream().map(Competition::getDate).min(Comparator.naturalOrder())
                .orElseThrow();
    }
}
