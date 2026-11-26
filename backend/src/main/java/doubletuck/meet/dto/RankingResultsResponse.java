package doubletuck.meet.dto;

import doubletuck.meet.dto.CompetitionResultsResponse.ApparatusScores;
import doubletuck.meet.dto.CompetitionResultsResponse.EventRef;
import doubletuck.meet.dto.CompetitionResultsResponse.TeamRow;

import java.util.List;

/**
 * A ranking's results as published, for a ranking with no competition of its own in its division
 * (a mixed team's qualification).
 *
 * @param teams     team standings, as on a competition's results
 * @param apparatus the scores counting toward the teams, each discipline's apparatus in Olympic order
 *                  (the men's, then the women's), from the competitions the ranking ranks
 */
public record RankingResultsResponse(
        EventRef event,
        RankingSummaryResponse ranking,
        List<TeamRow> teams,
        List<ApparatusScores> apparatus) {
}
