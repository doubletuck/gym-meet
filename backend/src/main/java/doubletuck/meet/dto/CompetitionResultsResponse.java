package doubletuck.meet.dto;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.BonusDetail;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.RankStatus;
import doubletuck.meet.domain.ScoreStatus;
import doubletuck.meet.domain.TeamScoreRole;
import org.jspecify.annotations.Nullable;

import java.util.List;
import java.util.Map;

/**
 * A competition's results as published. Which parts are filled depends on the
 * competition: an apparatus final has one {@code apparatus} list; a Competition I
 * at a championship has every apparatus plus {@code allAround} and {@code teams};
 * a split competition's combined row has {@code allAround} and
 * {@code apparatusStandings} but no scores of its own.
 *
 * @param apparatus  each apparatus's scores in Olympic order, ranked as published
 * @param allAround  all-around standings
 * @param teams      team standings
 * @param apparatusStandings a split competition's combined standings on each apparatus
 */
public record CompetitionResultsResponse(
        EventRef event,
        CompetitionSummaryResponse competition,
        List<ApparatusScores> apparatus,
        List<AllAroundRow> allAround,
        List<TeamRow> teams,
        List<ApparatusStandings> apparatusStandings) {

    public record EventRef(String slug, String title) {
    }

    public record AthleteRef(Long id, String surname, String givenName) {
    }

    /** @param discipline the gymnasts' discipline: a mixed competition has a men's and a women's floor */
    public record ApparatusScores(Discipline discipline, Apparatus apparatus, List<ScoreRow> scores) {
    }

    /** @param total the scores counting toward the team on the discipline's apparatus */
    public record ApparatusTotal(Discipline discipline, Apparatus apparatus, double total) {
    }

    /**
     * One athlete's result on one apparatus.
     *
     * @param rank               placement on the apparatus as published; for vault in
     *                           qualification, on the first vault
     * @param club               the club the athlete entered for, where the entry list names one
     *                           (national meets)
     * @param secondRoutine      vault's second attempt, or null when only one was expected
     * @param total              the result the apparatus is decided on: for two vaults,
     *                           their published combination
     * @param qualificationRank  placement in the ranking that decides the apparatus final
     * @param teamRole           what the score does for its team: counting toward the
     *                           team's total, dropped from it, or an individual's
     */
    public record ScoreRow(
            @Nullable Integer rank,
            @Nullable String bib,
            AthleteRef athlete,
            String noc,
            @Nullable String club,
            Routine routine,
            @Nullable Routine secondRoutine,
            @Nullable Double combinedBonus,
            @Nullable Double total,
            @Nullable Integer qualificationRank,
            @Nullable QualificationResult qualification,
            TeamScoreRole teamRole) {
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
     * @param club            as on {@link ScoreRow}
     * @param sjPenalty       a penalty on the result as a whole (negative), already deducted from the total
     * @param rankStatus      why the result has a rank, or why it has none
     * @param apparatusScores each apparatus's score in this competition, for those the athlete scored on; for
     *                        a split competition's combined row, the sum of the parts' scores, over the parts
     *                        the athlete competed it in
     * @param parts           for a split competition's combined row, the athlete's result in each part;
     *                        otherwise empty
     */
    public record AllAroundRow(
            @Nullable Integer rank,
            RankStatus rankStatus,
            @Nullable String bib,
            AthleteRef athlete,
            String noc,
            @Nullable String club,
            @Nullable Double total,
            @Nullable Double sjPenalty,
            @Nullable QualificationResult qualification,
            Map<Apparatus, Double> apparatusScores,
            List<PartResult> parts) {
    }

    public record PartResult(int part, @Nullable Double total, Map<Apparatus, Double> apparatusScores) {
    }

    /**
     * @param sjPenalty       a penalty on the team as a whole (negative), already deducted from the total
     * @param rankStatus      as on {@link AllAroundRow}
     * @param apparatusTotals each apparatus's total in Olympic order (a mixed team's: the men's, then the
     *                        women's): the sum of the scores counting toward the team, or for a mixed team,
     *                        which counts one score an apparatus, the best of them
     * @param round           on a final round's page, the earlier elimination round that printed this place,
     *                        for a team it eliminated; null otherwise
     * @param members         the gymnasts with a score in the team's result, in bib order, each with the
     *                        scores that made up the apparatus totals and those left out of them
     */
    public record TeamRow(
            @Nullable Integer rank,
            RankStatus rankStatus,
            String noc,
            @Nullable Double total,
            @Nullable Double sjPenalty,
            @Nullable QualificationResult qualification,
            List<ApparatusTotal> apparatusTotals,
            @Nullable Integer round,
            List<TeamMember> members) {
    }

    /** @param noc the country the gymnast competed for */
    public record TeamMember(AthleteRef athlete, String noc, List<MemberScore> scores) {
    }

    /**
     * @param score the routine's score, as added into the apparatus total: for vault, the first vault
     * @param role  {@code COUNTING} or {@code DROPPED}
     */
    public record MemberScore(Discipline discipline, Apparatus apparatus, @Nullable Double score,
            TeamScoreRole role) {
    }

    public record ApparatusStandings(Apparatus apparatus, List<ApparatusStandingRow> rows) {
    }

    /**
     * @param parts the athlete's result on the apparatus in each part of the competition: for two vaults, their
     *              combination
     */
    public record ApparatusStandingRow(@Nullable Integer rank, @Nullable String bib, AthleteRef athlete, String noc,
            @Nullable String club, @Nullable Double total, List<PartScore> parts) {
    }

    public record PartScore(int part, @Nullable Double score) {
    }
}
