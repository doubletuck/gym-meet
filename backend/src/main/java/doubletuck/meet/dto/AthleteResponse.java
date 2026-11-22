package doubletuck.meet.dto;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.EntryStatus;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.dto.SessionResultsResponse.Routine;
import org.jspecify.annotations.Nullable;

import java.time.LocalDate;
import java.util.List;

/**
 * An athlete's career: their best results, then every meet they entered.
 *
 * @param otherNames         other spellings sources have printed, as "Given Surname"
 * @param personalBests      their best routine score on each apparatus, in Olympic order
 * @param allAroundBest      their best all-around total from a complete all-around in one session; null
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

    /** Named apart from SessionResultsResponse.EventRef: the API's schemas are named by simple class name. */
    public record EntryEvent(String slug, String title, String shortName, LocalDate startDate, LocalDate endDate) {
    }

    /**
     * @param routine the routine's breakdown, as on the session's results
     * @param vault   which of the session's two vaults it was; null on other apparatus, or where only one
     *                vault was expected
     * @param session where it was scored, for a link to its results page
     */
    public record PersonalBest(Apparatus apparatus, double score, Routine routine, @Nullable Integer vault,
            EntryEvent event, SessionSummaryResponse session) {
    }

    public record AllAroundBest(double total, EntryEvent event, SessionSummaryResponse session) {
    }

    /**
     * @param club        the club they entered for, where the entry list names one
     * @param entryStatus a competitor, a reserve, withdrawn, or hors concours; reserves, withdrawn and hors
     *                    concours athletes usually have no sessions
     * @param sessions    the sessions they have results in, in competition order
     */
    public record Entry(EntryEvent event, String noc, @Nullable String club, EntryStatus entryStatus,
            List<EntrySession> sessions) {
    }

    /**
     * @param allAround          their all-around result in the session, if it has one
     * @param scores             their scores in the session, in Olympic order
     * @param apparatusStandings a split round's combined session: their place and total on each apparatus
     */
    public record EntrySession(SessionSummaryResponse session, @Nullable AllAroundResult allAround,
            List<ApparatusScore> scores, List<ApparatusStanding> apparatusStandings) {
    }

    public record AllAroundResult(@Nullable Integer rank, @Nullable Double total,
            @Nullable QualificationResult qualification) {
    }

    /** As in {@link SessionResultsResponse.ScoreRow}, without the athlete. */
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
