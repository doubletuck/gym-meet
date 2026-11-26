package doubletuck.meet.service;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.Routine;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.TeamContributionRole;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.domain.TeamResultScore;
import doubletuck.meet.domain.TeamScoreRole;
import doubletuck.meet.dto.SessionResultsResponse;
import doubletuck.meet.dto.SessionResultsResponse.AllAroundRow;
import doubletuck.meet.dto.SessionResultsResponse.ApparatusScores;
import doubletuck.meet.dto.SessionResultsResponse.ApparatusStandingRow;
import doubletuck.meet.dto.SessionResultsResponse.ApparatusStandings;
import doubletuck.meet.dto.SessionResultsResponse.AthleteRef;
import doubletuck.meet.dto.SessionResultsResponse.PartResult;
import doubletuck.meet.dto.SessionResultsResponse.PartScore;
import doubletuck.meet.dto.SessionResultsResponse.ScoreRow;
import doubletuck.meet.dto.SessionResultsResponse.TeamRow;
import doubletuck.meet.dto.SessionSummaryResponse;
import doubletuck.meet.repository.AllAroundResultRepository;
import doubletuck.meet.repository.ApparatusResultRepository;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.repository.RankingRepository;
import doubletuck.meet.repository.ScoreRepository;
import doubletuck.meet.repository.TeamResultRepository;
import doubletuck.meet.repository.TeamResultScoreRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Function;

/**
 * Rebuilds a competition's results page (the API's "session") from what was imported, ranked as
 * published: its scores, and the team, all-around and combined apparatus rankings of its routines.
 */
@Service
@Transactional(readOnly = true)
public class SessionResultsService {

    // Where a competition's routines are ranked more than once for one title, the page shows
    // the ranking that decided the most
    private static final List<RankingPurpose> PREFERENCE = List.of(RankingPurpose.FINAL, RankingPurpose.QUALIFYING,
            RankingPurpose.INFORMATIONAL);

    private final CompetitionRepository competitionRepository;
    private final RankingRepository rankingRepository;
    private final ScoreRepository scoreRepository;
    private final AllAroundResultRepository allAroundResultRepository;
    private final TeamResultRepository teamResultRepository;
    private final TeamResultScoreRepository teamResultScoreRepository;
    private final ApparatusResultRepository apparatusResultRepository;

    public SessionResultsService(CompetitionRepository competitionRepository, RankingRepository rankingRepository,
            ScoreRepository scoreRepository, AllAroundResultRepository allAroundResultRepository,
            TeamResultRepository teamResultRepository, TeamResultScoreRepository teamResultScoreRepository,
            ApparatusResultRepository apparatusResultRepository) {
        this.competitionRepository = competitionRepository;
        this.rankingRepository = rankingRepository;
        this.scoreRepository = scoreRepository;
        this.allAroundResultRepository = allAroundResultRepository;
        this.teamResultRepository = teamResultRepository;
        this.teamResultScoreRepository = teamResultScoreRepository;
        this.apparatusResultRepository = apparatusResultRepository;
    }

    public Optional<SessionResultsResponse> findResults(Long competitionId) {
        return competitionRepository.findById(competitionId).map(this::results);
    }

    private SessionResultsResponse results(Competition competition) {
        List<Apparatus> order = CompetitionNaming.apparatusOrder(competition.getDiscipline());
        List<Score> scores = scoreRepository.findResultsByCompetition(competition);
        List<Ranking> rankings = rankingRepository.findByCompetition(competition);
        List<Competition> division = competitionRepository.findByEventAndDisciplineAndAgeCategory(
                competition.getEvent(), competition.getDiscipline(), competition.getAgeCategory());
        List<Competition> partCompetitions = SplitRound.parts(competition, division);
        List<Part> parts = partCompetitions.stream()
                .map(part -> new Part(part.getPart(), scoreRepository.findResultsByCompetition(part),
                        preferred(rankingRepository.findByCompetition(part), RankingType.AA)
                                .map(allAroundResultRepository::findResultsByRanking).orElse(List.of())))
                .toList();

        List<Ranking> apparatusRankings = rankings.stream()
                .filter(ranking -> ranking.getType() == RankingType.APPARATUS).toList();
        List<ApparatusResult> apparatusResults = apparatusRankings.isEmpty() ? List.of()
                : apparatusResultRepository.findResultsByRankingIn(apparatusRankings);
        ApparatusRanks ranks = new ApparatusRanks(competition.getType(), apparatusResults);

        Optional<Ranking> teamRanking = preferred(rankings, RankingType.TEAM);
        List<TeamResult> teamResults = teamRanking.map(teamResultRepository::findByRanking).orElse(List.of());
        // How each score figured for its team: in the preferred team ranking where it's part of a
        // team there, otherwise in the competition's other team rankings (the qualifying standings
        // of teams not in the final)
        List<Ranking> teamRankings = rankings.stream()
                .filter(ranking -> ranking.getType() == RankingType.TEAM)
                .sorted(Comparator.comparingInt((Ranking ranking) -> PREFERENCE.indexOf(ranking.getPurpose()))
                        .reversed())
                .toList();
        Map<TeamResult, List<TeamResultScore>> contributions = new HashMap<>();
        Map<Long, TeamContributionRole> roleByScore = new HashMap<>();
        for (Ranking ranking : teamRankings) {
            List<TeamResult> results = teamResultRepository.findByRanking(ranking);
            if (results.isEmpty()) {
                continue;
            }
            for (TeamResultScore link : teamResultScoreRepository.findByTeamResultIn(results)) {
                roleByScore.put(link.getScore().getId(), link.getRole());
                if (teamRanking.isPresent() && ranking.getId().equals(teamRanking.get().getId())) {
                    contributions.computeIfAbsent(link.getTeamResult(), result -> new ArrayList<>()).add(link);
                }
            }
        }

        List<ApparatusScores> apparatus = order.stream()
                .map(app -> new ApparatusScores(app, scores.stream()
                        .filter(score -> score.getApparatus() == app)
                        .map(score -> scoreRow(score, ranks, teamRole(score, teamRanking.isPresent(), roleByScore)))
                        .sorted(byRank(ScoreRow::rank, ScoreRow::total, ScoreRow::athlete))
                        .toList()))
                .filter(list -> !list.scores().isEmpty())
                .toList();

        List<AllAroundRow> allAround = preferred(rankings, RankingType.AA)
                .map(allAroundResultRepository::findResultsByRanking).orElse(List.of()).stream()
                .sorted(byRank(AllAroundResult::getRank, AllAroundResult::getTotalScore,
                        result -> athlete(result.getParticipant())))
                .map(result -> allAroundRow(result, scores, parts, order))
                .toList();

        List<TeamRow> teams = teamResults.stream()
                .sorted(Comparator.comparing(TeamResult::getRank, Comparator.nullsLast(Comparator.naturalOrder())))
                .map(result -> teamRow(result, contributions.getOrDefault(result, List.of()), order))
                .toList();

        // Only a split competition's whole row holds combined apparatus standings; elsewhere a
        // competition's apparatus rankings are its scores' own placings, shown with the scores
        List<ApparatusStandings> apparatusStandings = partCompetitions.isEmpty() ? List.of() : order.stream()
                .map(app -> new ApparatusStandings(app, apparatusResults.stream()
                        .filter(result -> result.getRanking().getApparatus() == app)
                        .sorted(byRank(ApparatusResult::getRank, ApparatusResult::getTotalScore,
                                result -> athlete(result.getParticipant())))
                        .map(result -> standingRow(result, app, parts))
                        .toList()))
                .filter(list -> !list.rows().isEmpty())
                .toList();

        return new SessionResultsResponse(
                new SessionResultsResponse.EventRef(competition.getEvent().getSlug(),
                        competition.getEvent().getTitle()),
                SessionSummaryResponse.from(competition, division), apparatus, allAround, teams, apparatusStandings);
    }

    /** Of a competition's rankings of one type, the one deciding the most. */
    static Optional<Ranking> preferred(List<Ranking> rankings, RankingType type) {
        return rankings.stream()
                .filter(ranking -> ranking.getType() == type)
                .min(Comparator.comparingInt((Ranking ranking) -> PREFERENCE.indexOf(ranking.getPurpose()))
                        .thenComparing(Ranking::getId));
    }

    /**
     * What the score did for its team in the competition's team ranking: counting or dropped
     * when linked to a team result, an individual's score when the competition ranks teams but
     * the score isn't part of one, and counting where no teams are ranked.
     */
    private static TeamScoreRole teamRole(Score score, boolean teamsRanked, Map<Long, TeamContributionRole> roles) {
        TeamContributionRole role = roles.get(score.getId());
        if (role != null) {
            return role == TeamContributionRole.COUNTING ? TeamScoreRole.COUNTING : TeamScoreRole.DROPPED;
        }
        return teamsRanked ? TeamScoreRole.INDIVIDUAL : TeamScoreRole.COUNTING;
    }

    private static ScoreRow scoreRow(Score score, ApparatusRanks ranks, TeamScoreRole teamRole) {
        Participant participant = score.getParticipant();
        return new ScoreRow(ranks.rank(score), participant.getBibNumber(), athlete(participant), participant.getNoc(),
                club(participant), routine(score.getRoutine()), routine(score.getSecondRoutine()), score.getCombinedBonus(),
                score.getTotalScore(), ranks.qualificationRank(score), ranks.qualification(score), teamRole);
    }

    static SessionResultsResponse.Routine routine(Routine routine) {
        if (routine == null) {
            return null;
        }
        return new SessionResultsResponse.Routine(routine.getStatus(), routine.getDifficulty(),
                Boolean.TRUE.equals(routine.getDifficultyInquiry()), routine.getExecution(), routine.getBonus(),
                routine.getBonusDetail(), routine.getPenalty(), routine.getSjPenalty(), routine.getScore());
    }

    /** A part of a split round, with its scores and all-around results. */
    private record Part(int number, List<Score> scores, List<AllAroundResult> allAround) {
    }

    private static AllAroundRow allAroundRow(AllAroundResult result, List<Score> scores, List<Part> parts,
            List<Apparatus> order) {
        Participant participant = result.getParticipant();
        Map<Apparatus, Double> apparatusScores = apparatusScores(participant, scores, order);
        List<PartResult> partResults = new ArrayList<>();
        for (Part part : parts) {
            Double total = part.allAround().stream()
                    .filter(other -> other.getParticipant().equals(participant))
                    .map(AllAroundResult::getTotalScore)
                    .filter(Objects::nonNull)
                    .findFirst()
                    .orElse(null);
            Map<Apparatus, Double> partScores = apparatusScores(participant, part.scores(), order);
            if (total != null || !partScores.isEmpty()) {
                partResults.add(new PartResult(part.number(), total, partScores));
            }
        }
        if (!parts.isEmpty() && partResults.size() == parts.size()) {
            // A combined session has no scores of its own. Its apparatus standings can't stand in: vault's
            // is the two-vault title, not the all-around's one vault a day
            for (Apparatus app : order) {
                List<Double> each = partResults.stream().map(part -> part.apparatusScores().get(app))
                        .filter(Objects::nonNull).toList();
                if (!each.isEmpty()) {
                    apparatusScores.put(app, sum(each));
                }
            }
        }
        return new AllAroundRow(result.getRank(), participant.getBibNumber(), athlete(participant),
                participant.getNoc(), club(participant), result.getTotalScore(), result.getSjPenalty(),
                result.getQualificationResult(), apparatusScores, partResults);
    }

    private static Map<Apparatus, Double> apparatusScores(Participant participant, List<Score> scores,
            List<Apparatus> order) {
        Map<Apparatus, Double> apparatusScores = new LinkedHashMap<>();
        order.forEach(app -> routineScore(participant, app, scores)
                .ifPresent(score -> apparatusScores.put(app, score)));
        return apparatusScores;
    }

    private static Optional<Double> routineScore(Participant participant, Apparatus apparatus, List<Score> scores) {
        return scores.stream()
                .filter(score -> score.getParticipant().equals(participant) && score.getApparatus() == apparatus)
                .map(score -> score.getRoutine().getScore())
                .filter(Objects::nonNull)
                .findFirst();
    }

    /** Each part's score is the result the apparatus is decided on: for two vaults, their combination. */
    private static ApparatusStandingRow standingRow(ApparatusResult result, Apparatus apparatus, List<Part> parts) {
        Participant participant = result.getParticipant();
        List<PartScore> partScores = parts.stream()
                .flatMap(part -> part.scores().stream()
                        .filter(score -> score.getParticipant().equals(participant)
                                && score.getApparatus() == apparatus && score.getTotalScore() != null)
                        .findFirst().stream()
                        .map(score -> new PartScore(part.number(), score.getTotalScore())))
                .toList();
        return new ApparatusStandingRow(result.getRank(), participant.getBibNumber(), athlete(participant),
                participant.getNoc(), club(participant), result.getTotalScore(), partScores);
    }

    private static TeamRow teamRow(TeamResult result, List<TeamResultScore> contributions, List<Apparatus> order) {
        Map<Apparatus, Double> apparatusTotals = new LinkedHashMap<>();
        for (Apparatus app : order) {
            List<Double> counted = contributions.stream()
                    .filter(link -> link.getRole() == TeamContributionRole.COUNTING
                            && link.getScore().getApparatus() == app)
                    .map(link -> link.getScore().getRoutine().getScore())
                    .filter(Objects::nonNull)
                    .toList();
            if (!counted.isEmpty()) {
                apparatusTotals.put(app, sum(counted));
            }
        }
        return new TeamRow(result.getRank(), result.getTeam().getNoc(), result.getTotalScore(), result.getSjPenalty(),
                result.getQualificationResult(), apparatusTotals);
    }

    // Summed in decimal: binary doubles would print 41.232000000000006
    private static double sum(List<Double> scores) {
        BigDecimal sum = scores.stream().map(BigDecimal::valueOf).reduce(BigDecimal.ZERO, BigDecimal::add);
        return sum.setScale(3, RoundingMode.HALF_UP).doubleValue();
    }

    private static String club(Participant participant) {
        return participant.getClub() == null ? null : participant.getClub().getName();
    }

    private static AthleteRef athlete(Participant participant) {
        return new AthleteRef(participant.getAthlete().getId(), participant.getAthlete().getSurname(),
                participant.getAthlete().getGivenName());
    }

    /** As published: by rank, unranked rows (e.g. did not start) last, ordered by total then name. */
    private static <T> Comparator<T> byRank(Function<T, Integer> rank, Function<T, Double> total,
            Function<T, AthleteRef> athlete) {
        return Comparator.comparing(rank, Comparator.nullsLast(Comparator.naturalOrder()))
                .thenComparing(total, Comparator.nullsLast(Comparator.reverseOrder()))
                .thenComparing(row -> athlete.apply(row).surname());
    }
}
