package doubletuck.meet.dto;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.EntryStatus;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.RankStatus;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.dto.CompetitionResultsResponse.Routine;
import org.jspecify.annotations.Nullable;

import java.time.LocalDate;
import java.util.List;

/**
 * An athlete's career: their best results, then every meet they entered.
 *
 * @param otherNames         other spellings sources have printed, as "Given Surname"
 * @param personalBests      their best routine score on each apparatus, in Olympic order
 * @param allAroundBest      their best all-around total from a complete all-around in one competition; null
 *                           when they have none
 * @param entries            each meet they entered, newest first
 */
public record AthleteResponse(
        Long id,
        String surname,
        String givenName,
        Discipline discipline,
        @Nullable Short birthYear,
        List<String> otherNames,
        List<PersonalBest> personalBests,
        @Nullable AllAroundBest allAroundBest,
        List<Entry> entries) {

    /** Named apart from CompetitionResultsResponse.EventRef: the API's schemas are named by simple class name. */
    public record EntryEvent(String slug, String title, String shortName, LocalDate startDate, LocalDate endDate) {
    }

    /**
     * @param routine     the routine's breakdown, as on the competition's results
     * @param vault       which of the competition's two vaults it was; null on other apparatus, or where
     *                    only one vault was expected
     * @param competition where it was scored, for a link to its results page
     */
    public record PersonalBest(Apparatus apparatus, double score, Routine routine, @Nullable Integer vault,
            EntryEvent event, CompetitionSummaryResponse competition) {
    }

    public record AllAroundBest(double total, EntryEvent event, CompetitionSummaryResponse competition) {
    }

    /**
     * @param club        the club they entered for, where the entry list names one
     * @param entryStatus a competitor, a reserve, withdrawn, or hors concours; reserves, withdrawn and hors
     *                    concours athletes usually have no competitions
     * @param competitions the competitions they have results in, in the order they're held
     * @param mixedTeam    the mixed team they were a member of (a score of theirs counted toward it), with
     *                     its results; null when none
     */
    public record Entry(EntryEvent event, String noc, @Nullable String club, EntryStatus entryStatus,
            List<EntryCompetition> competitions, @Nullable EntryMixedTeam mixedTeam) {
    }

    /** @param results its qualification, then each final round, as on their results pages */
    public record EntryMixedTeam(String noc, List<MixedTeamResult> results) {
    }

    /**
     * A mixed team's place in one of its rankings.
     *
     * @param slug    the results page's address within the mixed division, with its {@code name}
     * @param purpose a top-three place in a {@code FINAL} ranking is a medal: the team's members all share it
     */
    public record MixedTeamResult(String slug, String name, Discipline discipline, AgeCategory ageCategory,
            @Nullable Integer rank, RankStatus rankStatus, @Nullable Double total,
            @Nullable QualificationResult qualification, RankingPurpose purpose) {
    }

    /**
     * @param allAround          their all-around result in the competition, if it has one
     * @param team               the result of the team they competed for, where the competition ranks teams
     * @param scores             their scores in the competition, in Olympic order
     * @param apparatusStandings a split competition's combined row: their place and total on each apparatus
     */
    public record EntryCompetition(CompetitionSummaryResponse competition, @Nullable AllAroundResult allAround,
            @Nullable EntryTeam team, List<ApparatusScore> scores, List<ApparatusStanding> apparatusStandings) {
    }

    /**
     * As in {@link CompetitionResultsResponse.TeamRow}, without the apparatus totals.
     *
     * @param purpose what the ranking it's from is for: a medal is a top-three rank in a final ranking
     */
    public record EntryTeam(String noc, @Nullable Integer rank, RankStatus rankStatus, @Nullable Double total,
            @Nullable QualificationResult qualification, RankingPurpose purpose) {
    }

    /** @param purpose as on {@link EntryTeam} */
    public record AllAroundResult(@Nullable Integer rank, RankStatus rankStatus, @Nullable Double total,
            @Nullable QualificationResult qualification, RankingPurpose purpose) {
    }

    /** As in {@link CompetitionResultsResponse.ScoreRow}, without the athlete. */
    public record ApparatusScore(
            Apparatus apparatus,
            @Nullable Integer rank,
            Routine routine,
            @Nullable Routine secondRoutine,
            @Nullable Double combinedBonus,
            @Nullable Double total,
            @Nullable Integer qualificationRank,
            @Nullable QualificationResult qualification) {
    }

    public record ApparatusStanding(Apparatus apparatus, @Nullable Integer rank, @Nullable Double total) {
    }
}
