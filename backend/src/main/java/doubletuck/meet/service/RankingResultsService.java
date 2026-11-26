package doubletuck.meet.service;

import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.TeamContributionRole;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.domain.TeamResultScore;
import doubletuck.meet.domain.TeamScoreRole;
import doubletuck.meet.dto.CompetitionResultsResponse.ApparatusScores;
import doubletuck.meet.dto.CompetitionResultsResponse.EventRef;
import doubletuck.meet.dto.CompetitionResultsResponse.ScoreRow;
import doubletuck.meet.dto.CompetitionResultsResponse.TeamRow;
import doubletuck.meet.dto.RankingResultsResponse;
import doubletuck.meet.repository.RankingRepository;
import doubletuck.meet.repository.TeamResultRepository;
import doubletuck.meet.repository.TeamResultScoreRepository;
import doubletuck.meet.service.CompetitionNaming.ApparatusColumn;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * Rebuilds the page of a ranking with no competition of its own (a mixed team's qualification):
 * its team standings and the scores that counted toward them, ranked as published.
 */
@Service
@Transactional(readOnly = true)
public class RankingResultsService {

    private final RankingRepository rankingRepository;
    private final TeamResultRepository teamResultRepository;
    private final TeamResultScoreRepository teamResultScoreRepository;

    public RankingResultsService(RankingRepository rankingRepository, TeamResultRepository teamResultRepository,
            TeamResultScoreRepository teamResultScoreRepository) {
        this.rankingRepository = rankingRepository;
        this.teamResultRepository = teamResultRepository;
        this.teamResultScoreRepository = teamResultScoreRepository;
    }

    /** Empty when there's no such ranking, or it isn't a page of its own. */
    public Optional<RankingResultsResponse> findResults(Long rankingId) {
        return rankingRepository.findById(rankingId)
                .filter(ranking -> ranking.getType() == RankingType.TEAM && RankingSummaries.isOwnPage(ranking))
                .map(this::results);
    }

    private RankingResultsResponse results(Ranking ranking) {
        List<ApparatusColumn> columns = CompetitionNaming.columns(ranking.getDiscipline());
        List<TeamResult> results = teamResultRepository.findByRanking(ranking);
        Map<TeamResult, List<TeamResultScore>> links = results.isEmpty() ? Map.of()
                : teamResultScoreRepository.findByTeamResultIn(results).stream()
                        .collect(Collectors.groupingBy(TeamResultScore::getTeamResult));
        List<TeamRow> teams = results.stream()
                .sorted(Comparator.comparing(TeamResult::getRank, Comparator.nullsLast(Comparator.naturalOrder())))
                .map(result -> CompetitionResultsService.teamRow(result, links.getOrDefault(result, List.of()),
                        columns, null))
                .toList();
        // No apparatus placings of its own: a counting score's placing is its competition's
        ApparatusRanks noRanks = new ApparatusRanks(CompetitionType.C1, List.of());
        List<Score> counting = links.values().stream().flatMap(List::stream)
                .filter(link -> link.getRole() == TeamContributionRole.COUNTING)
                .map(TeamResultScore::getScore)
                .distinct()
                .toList();
        List<ApparatusScores> apparatus = columns.stream()
                .map(column -> new ApparatusScores(column.discipline(), column.apparatus(), counting.stream()
                        .filter(score -> CompetitionResultsService.isIn(score, column))
                        .map(score -> CompetitionResultsService.scoreRow(score, noRanks, TeamScoreRole.COUNTING))
                        .sorted(Comparator.comparing(ScoreRow::total, Comparator.nullsLast(Comparator.reverseOrder()))
                                .thenComparing(row -> row.athlete().surname()))
                        .toList()))
                .filter(list -> !list.scores().isEmpty())
                .toList();
        return new RankingResultsResponse(new EventRef(ranking.getEvent().getSlug(), ranking.getEvent().getTitle()),
                RankingSummaries.of(ranking), teams, apparatus);
    }
}
