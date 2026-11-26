package doubletuck.meet.importer;

import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.EventFormat;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.TitleFormat;
import org.springframework.stereotype.Component;

import java.util.Collection;
import java.util.EnumSet;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Checks a slice's competitions and rankings against its declared format: each held title
 * has its final ranking, ranking the competition the format says decided it; qualifying
 * rankings exist only for titles decided in a later final; and no final is held for a title
 * that wasn't decided in one.
 */
@Component
class FormatChecker {

    void check(ImportContext context) {
        EventFormat format = context.getFormat();
        Collection<Ranking> rankings = context.getRankings().values();
        Collection<Competition> competitions = context.getCompetitions().values();
        for (RankingType type : RankingType.values()) {
            TitleFormat titleFormat = format.formatOf(type);
            CompetitionType decidingFinal = decidingFinal(type);
            for (Ranking ranking : rankings) {
                if (ranking.getType() == type && ranking.getPurpose() != RankingPurpose.INFORMATIONAL) {
                    checkRanking(context, ranking, titleFormat, decidingFinal);
                }
            }
            if (titleFormat != TitleFormat.FINAL
                    && competitions.stream().anyMatch(competition -> competition.getType() == decidingFinal)) {
                throw error(context, "there is a " + decidingFinal + " competition, but the " + title(type)
                        + " format is " + titleFormat + "; a " + decidingFinal + " is held only for a FINAL format");
            }
            if (titleFormat != TitleFormat.NONE && rankings.stream()
                    .noneMatch(ranking -> ranking.getType() == type && ranking.getPurpose() == RankingPurpose.FINAL)) {
                throw error(context, "the " + title(type) + " format is " + titleFormat + ", but there is no "
                        + type + " FINAL ranking" + (titleFormat == TitleFormat.FINAL
                                ? " of a " + decidingFinal + " competition" : " of C1"));
            }
        }
    }

    private static void checkRanking(ImportContext context, Ranking ranking, TitleFormat titleFormat,
            CompetitionType decidingFinal) {
        String description = ranking.getType() + (ranking.getApparatus() != null ? " " + ranking.getApparatus() : "")
                + " " + ranking.getPurpose() + " ranking";
        if (titleFormat == TitleFormat.NONE) {
            throw error(context, "the " + description + " ranks a title not held (" + title(ranking.getType())
                    + " format NONE)");
        }
        CompetitionType expected;
        if (ranking.getPurpose() == RankingPurpose.QUALIFYING) {
            if (titleFormat != TitleFormat.FINAL) {
                throw error(context, "the " + description + " qualifies for a " + decidingFinal + ", but the "
                        + title(ranking.getType()) + " format is " + titleFormat
                        + "; a title Competition I decided has a FINAL ranking of C1");
            }
            expected = CompetitionType.C1;
        } else {
            expected = titleFormat == TitleFormat.C1 ? CompetitionType.C1 : decidingFinal;
        }
        Set<CompetitionType> ranked = ranking.getCompetitions().stream().map(Competition::getType)
                .collect(Collectors.toCollection(() -> EnumSet.noneOf(CompetitionType.class)));
        if (!ranked.equals(EnumSet.of(expected))) {
            throw error(context, "the " + description + " ranks " + ranked + ", but with the "
                    + title(ranking.getType()) + " format " + titleFormat + " it ranks " + expected);
        }
    }

    private static CompetitionType decidingFinal(RankingType type) {
        return switch (type) {
            case TEAM -> CompetitionType.C4;
            case AA -> CompetitionType.C2;
            case APPARATUS -> CompetitionType.C3;
        };
    }

    private static String title(RankingType type) {
        return switch (type) {
            case TEAM -> "team";
            case AA -> "all-around";
            case APPARATUS -> "apparatus";
        };
    }

    private static ImportException error(ImportContext context, String message) {
        return new ImportException(context.getEvent().getTitle() + " " + context.getDiscipline() + " "
                + context.getAgeCategory() + ": " + message);
    }
}
