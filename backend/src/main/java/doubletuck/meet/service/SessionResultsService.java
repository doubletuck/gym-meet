package doubletuck.meet.service;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Routine;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.Session;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.dto.SessionResultsResponse;
import doubletuck.meet.dto.SessionResultsResponse.AllAroundRow;
import doubletuck.meet.dto.SessionResultsResponse.ApparatusScores;
import doubletuck.meet.dto.SessionResultsResponse.ApparatusStandingRow;
import doubletuck.meet.dto.SessionResultsResponse.ApparatusStandings;
import doubletuck.meet.dto.SessionResultsResponse.AthleteRef;
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
        List<Score> scores = scoreRepository.findResultsBySession(session);

        List<ApparatusScores> apparatus = order.stream()
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
                .map(result -> allAroundRow(result, scores, order))
                .toList();

        List<TeamRow> teams = teamResultRepository.findBySession(session).stream()
                .sorted(Comparator.comparing(TeamResult::getRank, Comparator.nullsLast(Comparator.naturalOrder())))
                .map(result -> teamRow(result, scores, order))
                .toList();

        List<ApparatusResult> standings = apparatusResultRepository.findResultsBySession(session);
        List<ApparatusStandings> apparatusStandings = order.stream()
                .map(app -> new ApparatusStandings(app, standings.stream()
                        .filter(result -> result.getApparatus() == app)
                        .sorted(byRank(ApparatusResult::getRank, ApparatusResult::getTotalScore,
                                ApparatusResult::getParticipant))
                        .map(result -> new ApparatusStandingRow(result.getRank(),
                                result.getParticipant().getBibNumber(), athlete(result.getParticipant()),
                                result.getParticipant().getNoc(), result.getTotalScore()))
                        .toList()))
                .filter(list -> !list.rows().isEmpty())
                .toList();

        return new SessionResultsResponse(
                new SessionResultsResponse.EventRef(session.getEvent().getSlug(), session.getEvent().getTitle()),
                SessionSummaryResponse.from(session), apparatus, allAround, teams, apparatusStandings);
    }

    private static ScoreRow scoreRow(Score score) {
        Participant participant = score.getParticipant();
        return new ScoreRow(score.getRank(), participant.getBibNumber(), athlete(participant), participant.getNoc(),
                routine(score.getRoutine()), routine(score.getSecondRoutine()), score.getCombinedBonus(),
                score.getTotalScore(), score.getQualificationRank(), score.getQualificationResult(),
                score.getCountsTowardTeamResult());
    }

    private static SessionResultsResponse.Routine routine(Routine routine) {
        if (routine == null) {
            return null;
        }
        return new SessionResultsResponse.Routine(routine.getStatus(), routine.getDifficulty(),
                Boolean.TRUE.equals(routine.getDifficultyInquiry()), routine.getExecution(), routine.getBonus(),
                routine.getBonusDetail(), routine.getPenalty(), routine.getSjPenalty(), routine.getScore());
    }

    private static AllAroundRow allAroundRow(AllAroundResult result, List<Score> scores, List<Apparatus> order) {
        Participant participant = result.getParticipant();
        Map<Apparatus, Double> apparatusScores = new LinkedHashMap<>();
        order.forEach(app -> scores.stream()
                .filter(score -> score.getParticipant().equals(participant) && score.getApparatus() == app)
                .map(score -> score.getRoutine().getScore())
                .filter(Objects::nonNull)
                .findFirst()
                .ifPresent(score -> apparatusScores.put(app, score)));
        return new AllAroundRow(result.getRank(), participant.getBibNumber(), athlete(participant),
                participant.getNoc(), result.getTotalScore(), result.getQualificationResult(), apparatusScores);
    }

    private static TeamRow teamRow(TeamResult result, List<Score> scores, List<Apparatus> order) {
        Map<Apparatus, Double> apparatusTotals = new LinkedHashMap<>();
        for (Apparatus app : order) {
            List<Double> counted = scores.stream()
                    .filter(score -> score.getApparatus() == app && score.getCountsTowardTeamResult()
                            && score.getParticipant().getNoc().equals(result.getNoc()))
                    .map(score -> score.getRoutine().getScore())
                    .filter(Objects::nonNull)
                    .toList();
            if (!counted.isEmpty()) {
                // Summed in decimal: binary doubles would print 41.232000000000006
                BigDecimal sum = counted.stream().map(BigDecimal::valueOf).reduce(BigDecimal.ZERO, BigDecimal::add);
                apparatusTotals.put(app, sum.setScale(3, RoundingMode.HALF_UP).doubleValue());
            }
        }
        return new TeamRow(result.getRank(), result.getNoc(), result.getTotalScore(),
                result.getQualificationResult(), apparatusTotals);
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
