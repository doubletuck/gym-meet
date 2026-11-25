package doubletuck.meet.service;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Routine;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.Session;
import doubletuck.meet.domain.TeamResult;
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
import doubletuck.meet.repository.ScoreRepository;
import doubletuck.meet.repository.SessionRepository;
import doubletuck.meet.repository.TeamResultRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.function.Function;

/** Rebuilds a session's results page from what was imported, ranked as published. */
@Service
@Transactional(readOnly = true)
public class SessionResultsService {

    private final SessionRepository sessionRepository;
    private final ScoreRepository scoreRepository;
    private final AllAroundResultRepository allAroundResultRepository;
    private final TeamResultRepository teamResultRepository;
    private final ApparatusResultRepository apparatusResultRepository;

    public SessionResultsService(SessionRepository sessionRepository, ScoreRepository scoreRepository,
            AllAroundResultRepository allAroundResultRepository, TeamResultRepository teamResultRepository,
            ApparatusResultRepository apparatusResultRepository) {
        this.sessionRepository = sessionRepository;
        this.scoreRepository = scoreRepository;
        this.allAroundResultRepository = allAroundResultRepository;
        this.teamResultRepository = teamResultRepository;
        this.apparatusResultRepository = apparatusResultRepository;
    }

    public Optional<SessionResultsResponse> findResults(Long sessionId) {
        return sessionRepository.findById(sessionId).map(this::results);
    }

    private SessionResultsResponse results(Session session) {
        List<Apparatus> order = SessionNaming.apparatusOrder(session.getDiscipline());
        // Standings ranking another session's routines show them, without repeating its score tables
        List<Score> scores = scoreRepository.findResultsBySession(session.sessionWithScores());
        boolean ownScores = session.getScoresSession() == null;
        List<Session> division = sessionRepository.findByEventAndDisciplineAndAgeCategory(session.getEvent(),
                session.getDiscipline(), session.getAgeCategory());
        List<Part> parts = SplitRound.parts(session, division).stream()
                .map(part -> new Part(part.getPart(), scoreRepository.findResultsBySession(part),
                        allAroundResultRepository.findResultsBySession(part)))
                .toList();
        List<ApparatusResult> standings = apparatusResultRepository.findResultsBySession(session);

        List<ApparatusScores> apparatus = !ownScores ? List.of() : order.stream()
                .map(app -> new ApparatusScores(app, scores.stream()
                        .filter(score -> score.getApparatus() == app)
                        .sorted(byRank(Score::getRank, Score::getTotalScore, Score::getParticipant))
                        .map(SessionResultsService::scoreRow)
                        .toList()))
                .filter(list -> !list.scores().isEmpty())
                .toList();

        List<AllAroundRow> allAround = allAroundResultRepository.findResultsBySession(session).stream()
                .sorted(byRank(AllAroundResult::getRank, AllAroundResult::getTotalScore,
                        AllAroundResult::getParticipant))
                .map(result -> allAroundRow(result, scores, parts, order))
                .toList();

        List<TeamRow> teams = teamResultRepository.findBySession(session).stream()
                .sorted(Comparator.comparing(TeamResult::getRank, Comparator.nullsLast(Comparator.naturalOrder())))
                .map(result -> teamRow(result, scores, order))
                .toList();

        List<ApparatusStandings> apparatusStandings = order.stream()
                .map(app -> new ApparatusStandings(app, standings.stream()
                        .filter(result -> result.getApparatus() == app)
                        .sorted(byRank(ApparatusResult::getRank, ApparatusResult::getTotalScore,
                                ApparatusResult::getParticipant))
                        .map(result -> standingRow(result, parts))
                        .toList()))
                .filter(list -> !list.rows().isEmpty())
                .toList();

        return new SessionResultsResponse(
                new SessionResultsResponse.EventRef(session.getEvent().getSlug(), session.getEvent().getTitle()),
                SessionSummaryResponse.from(session, division), apparatus, allAround, teams, apparatusStandings);
    }

    private static ScoreRow scoreRow(Score score) {
        Participant participant = score.getParticipant();
        return new ScoreRow(score.getRank(), participant.getBibNumber(), athlete(participant), participant.getNoc(),
                club(participant), routine(score.getRoutine()), routine(score.getSecondRoutine()), score.getCombinedBonus(),
                score.getTotalScore(), score.getQualificationRank(), score.getQualificationResult(),
                score.getTeamScoreRole());
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
    private static ApparatusStandingRow standingRow(ApparatusResult result, List<Part> parts) {
        Participant participant = result.getParticipant();
        List<PartScore> partScores = parts.stream()
                .flatMap(part -> part.scores().stream()
                        .filter(score -> score.getParticipant().equals(participant)
                                && score.getApparatus() == result.getApparatus() && score.getTotalScore() != null)
                        .findFirst().stream()
                        .map(score -> new PartScore(part.number(), score.getTotalScore())))
                .toList();
        return new ApparatusStandingRow(result.getRank(), participant.getBibNumber(), athlete(participant),
                participant.getNoc(), club(participant), result.getTotalScore(), partScores);
    }

    private static TeamRow teamRow(TeamResult result, List<Score> scores, List<Apparatus> order) {
        Map<Apparatus, Double> apparatusTotals = new LinkedHashMap<>();
        for (Apparatus app : order) {
            List<Double> counted = scores.stream()
                    .filter(score -> score.getApparatus() == app && score.getTeamScoreRole() == TeamScoreRole.COUNTING
                            && score.getParticipant().getNoc().equals(result.getNoc()))
                    .map(score -> score.getRoutine().getScore())
                    .filter(Objects::nonNull)
                    .toList();
            if (!counted.isEmpty()) {
                apparatusTotals.put(app, sum(counted));
            }
        }
        return new TeamRow(result.getRank(), result.getNoc(), result.getTotalScore(), result.getSjPenalty(),
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
            Function<T, Participant> participant) {
        return Comparator.comparing(rank, Comparator.nullsLast(Comparator.naturalOrder()))
                .thenComparing(total, Comparator.nullsLast(Comparator.reverseOrder()))
                .thenComparing(row -> participant.apply(row).getAthlete().getSurname());
    }
}
