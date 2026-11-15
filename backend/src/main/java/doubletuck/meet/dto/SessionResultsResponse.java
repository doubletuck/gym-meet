package doubletuck.meet.dto;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.BonusDetail;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.ScoreStatus;
import org.jspecify.annotations.Nullable;

import java.util.List;
import java.util.Map;

/**
 * A session's results as published. Which parts are filled depends on the
 * round: an apparatus final has one {@code apparatus} list; a championship
 * qualification has every apparatus plus {@code allAround} and {@code teams};
 * a split round's combined session has {@code allAround} and
 * {@code apparatusStandings} but no scores of its own.
 *
 * @param apparatus  each apparatus's scores in Olympic order, ranked as published
 * @param allAround  all-around standings
 * @param teams      team standings
 * @param apparatusStandings a split round's combined standings on each apparatus
 */
public record SessionResultsResponse(
        EventRef event,
        SessionSummaryResponse session,
        List<ApparatusScores> apparatus,
        List<AllAroundRow> allAround,
        List<TeamRow> teams,
        List<ApparatusStandings> apparatusStandings) {

    public record EventRef(String slug, String title) {
    }

    public record AthleteRef(Long id, String surname, String givenName) {
    }

    public record ApparatusScores(Apparatus apparatus, List<ScoreRow> scores) {
    }

    /**
     * One athlete's result on one apparatus.
     *
     * @param rank               placement on the apparatus as published; for vault in
     *                           qualification, on the first vault
     * @param secondRoutine      vault's second attempt, or null when only one was expected
     * @param total              the result the apparatus is decided on: for two vaults,
     *                           their published combination
     * @param qualificationRank  placement in the ranking that decides the apparatus final
     * @param countsTowardTeam   false for a score dropped from its team's total
     */
    public record ScoreRow(
            @Nullable Integer rank,
            @Nullable String bib,
            AthleteRef athlete,
            String noc,
            Routine routine,
            @Nullable Routine secondRoutine,
            @Nullable Double combinedBonus,
            @Nullable Double total,
            @Nullable Integer qualificationRank,
            @Nullable QualificationResult qualification,
            boolean countsTowardTeam) {
    }

    /** @param difficultyInquiry the D score was under inquiry, printed with a leading "!" */
    public record Routine(
            ScoreStatus status,
            @Nullable Double difficulty,
            boolean difficultyInquiry,
            @Nullable Double execution,
            @Nullable Double bonus,
            @Nullable List<BonusDetail> bonusDetail,
            @Nullable Double penalty,
            @Nullable Double sjPenalty,
            @Nullable Double score) {
    }

    /**
     * @param apparatusScores each apparatus's score in this session, for those the athlete scored on; empty
     *                        for a split round's combined total
     */
    public record AllAroundRow(
            @Nullable Integer rank,
            @Nullable String bib,
            AthleteRef athlete,
            String noc,
            @Nullable Double total,
            @Nullable QualificationResult qualification,
            Map<Apparatus, Double> apparatusScores) {
    }

    /** @param apparatusTotals the sum of the scores counting toward the team on each apparatus */
    public record TeamRow(
            @Nullable Integer rank,
            String noc,
            @Nullable Double total,
            @Nullable QualificationResult qualification,
            Map<Apparatus, Double> apparatusTotals) {
    }

    public record ApparatusStandings(Apparatus apparatus, List<ApparatusStandingRow> rows) {
    }

    public record ApparatusStandingRow(@Nullable Integer rank, @Nullable String bib, AthleteRef athlete, String noc,
            @Nullable Double total) {
    }
}
