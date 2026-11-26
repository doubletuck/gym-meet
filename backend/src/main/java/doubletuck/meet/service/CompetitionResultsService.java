package doubletuck.meet.service;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.Discipline;
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
import doubletuck.meet.dto.CompetitionResultsResponse;
import doubletuck.meet.dto.CompetitionResultsResponse.AllAroundRow;
import doubletuck.meet.dto.CompetitionResultsResponse.ApparatusScores;
import doubletuck.meet.dto.CompetitionResultsResponse.ApparatusStandingRow;
import doubletuck.meet.dto.CompetitionResultsResponse.ApparatusStandings;
import doubletuck.meet.dto.CompetitionResultsResponse.ApparatusTotal;
import doubletuck.meet.dto.CompetitionResultsResponse.AthleteRef;
import doubletuck.meet.dto.CompetitionResultsResponse.PartResult;
import doubletuck.meet.dto.CompetitionResultsResponse.PartScore;
import doubletuck.meet.dto.CompetitionResultsResponse.ScoreRow;
import doubletuck.meet.dto.CompetitionResultsResponse.TeamRow;
import doubletuck.meet.repository.AllAroundResultRepository;
import doubletuck.meet.repository.ApparatusResultRepository;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.repository.RankingRepository;
import doubletuck.meet.repository.ScoreRepository;
import doubletuck.meet.repository.TeamResultRepository;
import doubletuck.meet.repository.TeamResultScoreRepository;
import doubletuck.meet.service.CompetitionNaming.ApparatusColumn;
import org.jspecify.annotations.Nullable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * Rebuilds a competition's results page from what was imported, ranked as published: its scores,
 * and the team, all-around and combined apparatus rankings of its routines.
 */
@Service
@Transactional(readOnly = true)
public class CompetitionResultsService {

    private final CompetitionRepository competitionRepository;
    private final RankingRepository rankingRepository;
    private final ScoreRepository scoreRepository;
    private final AllAroundResultRepository allAroundResultRepository;
    private final TeamResultRepository teamResultRepository;
    private final TeamResultScoreRepository teamResultScoreRepository;
    private final ApparatusResultRepository apparatusResultRepository;

    public CompetitionResultsService(CompetitionRepository competitionRepository, RankingRepository rankingRepository,
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

    public Optional<CompetitionResultsResponse> findResults(Long competitionId) {
        return competitionRepository.findById(competitionId).map(this::results);
    }

    private CompetitionResultsResponse results(Competition competition) {
        List<Apparatus> order = CompetitionNaming.apparatusOrder(competition.getDiscipline());
        List<ApparatusColumn> columns = CompetitionNaming.columns(competition.getDiscipline());
        List<Score> scores = scoreRepository.findResultsByCompetition(competition);
        List<Ranking> rankings = CompetitionNaming.own(rankingRepository.findByCompetition(competition), competition);
        List<Competition> division = competitionRepository.findByEventAndDisciplineAndAgeCategory(
                competition.getEvent(), competition.getDiscipline(), competition.getAgeCategory());
        CompetitionSummaries summaries = new CompetitionSummaries(division,
                rankingRepository.findByEventAndDisciplineAndAgeCategory(competition.getEvent(),
                        competition.getDiscipline(), competition.getAgeCategory()));
        List<Competition> partCompetitions = SplitRound.parts(competition, division);
        List<Part> parts = partCompetitions.stream()
                .map(part -> new Part(part.getPart(), scoreRepository.findResultsByCompetition(part),
                        CompetitionNaming.preferred(CompetitionNaming.own(rankingRepository.findByCompetition(part),
                                part), RankingType.AA)
                                .map(allAroundResultRepository::findResultsByRanking).orElse(List.of())))
                .toList();

        List<Ranking> apparatusRankings = rankings.stream()
                .filter(ranking -> ranking.getType() == RankingType.APPARATUS).toList();
        List<ApparatusResult> apparatusResults = apparatusRankings.isEmpty() ? List.of()
                : apparatusResultRepository.findResultsByRankingIn(apparatusRankings);
        ApparatusRanks ranks = new ApparatusRanks(competition.getType(), apparatusResults);

        Optional<Ranking> teamRanking = CompetitionNaming.preferred(rankings, RankingType.TEAM);
        List<TeamResult> teamResults = teamRanking.map(teamResultRepository::findByRanking).orElse(List.of());
        // How each score figured for its team: in the preferred team ranking where it's part of a
        // team there, otherwise in the competition's other team rankings (the qualifying standings
        // of teams not in the final)
        List<Ranking> teamRankings = rankings.stream()
                .filter(ranking -> ranking.getType() == RankingType.TEAM)
                .sorted(Comparator.comparingInt(CompetitionNaming::preference).reversed())
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

        List<ApparatusScores> apparatus = columns.stream()
                .map(column -> new ApparatusScores(column.discipline(), column.apparatus(), scores.stream()
                        .filter(score -> isIn(score, column))
                        .map(score -> scoreRow(score, ranks, teamRole(score, teamRanking.isPresent(), roleByScore)))
                        .sorted(byRank(ScoreRow::rank, ScoreRow::total, ScoreRow::athlete))
                        .toList()))
                .filter(list -> !list.scores().isEmpty())
                .toList();

        List<AllAroundRow> allAround = CompetitionNaming.preferred(rankings, RankingType.AA)
                .map(allAroundResultRepository::findResultsByRanking).orElse(List.of()).stream()
                .sorted(byRank(AllAroundResult::getRank, AllAroundResult::getTotalScore,
                        result -> athlete(result.getParticipant())))
                .map(result -> allAroundRow(result, scores, parts, order))
                .toList();

        List<TeamRow> teams = new ArrayList<>(teamResults.stream()
                .sorted(Comparator.comparing(TeamResult::getRank, Comparator.nullsLast(Comparator.naturalOrder())))
                .map(result -> teamRow(result, contributions.getOrDefault(result, List.of()), columns, null))
                .toList());
        if (competition.getRound() != null && teamRanking.map(Ranking::getPurpose).orElse(null) == RankingPurpose.FINAL) {
            teams.addAll(eliminated(competition, division, teams, columns));
        }

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

        return new CompetitionResultsResponse(
                new CompetitionResultsResponse.EventRef(competition.getEvent().getSlug(),
                        competition.getEvent().getTitle()),
                summaries.of(competition), apparatus, allAround, teams, apparatusStandings);
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

    static ScoreRow scoreRow(Score score, ApparatusRanks ranks, TeamScoreRole teamRole) {
        Participant participant = score.getParticipant();
        return new ScoreRow(ranks.rank(score), participant.getBibNumber(), athlete(participant), participant.getNoc(),
                club(participant), routine(score.getRoutine()), routine(score.getSecondRoutine()), score.getCombinedBonus(),
                score.getTotalScore(), ranks.qualificationRank(score), ranks.qualification(score), teamRole);
    }

    static CompetitionResultsResponse.Routine routine(Routine routine) {
        if (routine == null) {
            return null;
        }
        return new CompetitionResultsResponse.Routine(routine.getStatus(), routine.getDifficulty(),
                Boolean.TRUE.equals(routine.getDifficultyInquiry()), routine.getExecution(), routine.getBonus(),
                routine.getBonusDetail(), routine.getPenalty(), routine.getSjPenalty(), routine.getScore());
    }

    /** A part of a split competition, with its scores and all-around results. */
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
            // A combined row has no scores of its own. Its apparatus standings can't stand in: vault's
            // is the two-vault title, not the all-around's one vault a day
            for (Apparatus app : order) {
                List<Double> each = partResults.stream().map(part -> part.apparatusScores().get(app))
                        .filter(Objects::nonNull).toList();
                if (!each.isEmpty()) {
                    apparatusScores.put(app, sum(each));
                }
            }
        }
        return new AllAroundRow(result.getRank(), result.getRankStatus(), participant.getBibNumber(), athlete(participant),
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

    /**
     * The teams a final round's earlier rounds eliminated, at the places those rounds printed: the
     * round before's, then the one before that (competition-models.md §8.4). Nothing is computed.
     */
    private List<TeamRow> eliminated(Competition competition, List<Competition> division, List<TeamRow> shown,
            List<ApparatusColumn> columns) {
        Set<String> nocs = shown.stream().map(TeamRow::noc).collect(Collectors.toCollection(HashSet::new));
        List<TeamRow> rows = new ArrayList<>();
        for (int round = competition.getRound() - 1; round >= 1; round--) {
            int number = round;
            Optional<Ranking> ranking = division.stream()
                    .filter(earlier -> earlier.getType() == competition.getType()
                            && Objects.equals(earlier.getApparatus(), competition.getApparatus())
                            && earlier.getPart() == null && Objects.equals(earlier.getRound(), number))
                    .findFirst()
                    .flatMap(earlier -> CompetitionNaming.preferred(
                            CompetitionNaming.own(rankingRepository.findByCompetition(earlier), earlier), RankingType.TEAM));
            if (ranking.isEmpty()) {
                continue;
            }
            List<TeamResult> results = teamResultRepository.findByRanking(ranking.get());
            Map<TeamResult, List<TeamResultScore>> links = teamResultScoreRepository.findByTeamResultIn(results).stream()
                    .collect(Collectors.groupingBy(TeamResultScore::getTeamResult));
            results.stream()
                    .sorted(Comparator.comparing(TeamResult::getRank, Comparator.nullsLast(Comparator.naturalOrder())))
                    .filter(result -> nocs.add(result.getTeam().getNoc()))
                    .forEach(result -> rows.add(teamRow(result, links.getOrDefault(result, List.of()), columns, number)));
        }
        return rows;
    }

    /** Whether the score is on the column's apparatus, by a gymnast of its discipline. */
    static boolean isIn(Score score, ApparatusColumn column) {
        return score.getApparatus() == column.apparatus()
                && score.getParticipant().getAthlete().getDiscipline() == column.discipline();
    }

    /**
     * @param round on a final round's page, the earlier round that printed the place; null otherwise
     */
    static TeamRow teamRow(TeamResult result, List<TeamResultScore> contributions, List<ApparatusColumn> columns,
            @Nullable Integer round) {
        // A mixed team counts one score an apparatus: two gymnasts tied for it both count
        boolean mixed = result.getRanking().getDiscipline() == Discipline.MIX;
        List<ApparatusTotal> apparatusTotals = new ArrayList<>();
        for (ApparatusColumn column : columns) {
            List<Double> counted = contributions.stream()
                    .filter(link -> link.getRole() == TeamContributionRole.COUNTING && isIn(link.getScore(), column))
                    .map(link -> link.getScore().getRoutine().getScore())
                    .filter(Objects::nonNull)
                    .toList();
            if (!counted.isEmpty()) {
                apparatusTotals.add(new ApparatusTotal(column.discipline(), column.apparatus(),
                        mixed ? Collections.max(counted) : sum(counted)));
            }
        }
        return new TeamRow(result.getRank(), result.getRankStatus(), result.getTeam().getNoc(), result.getTotalScore(),
                result.getSjPenalty(), result.getQualificationResult(), apparatusTotals, round);
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
