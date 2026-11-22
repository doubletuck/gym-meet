package doubletuck.meet.service;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Athlete;
import doubletuck.meet.domain.AthleteNameVariant;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Routine;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.ScoreStatus;
import doubletuck.meet.domain.Session;
import doubletuck.meet.dto.AthleteResponse;
import doubletuck.meet.dto.AthleteResponse.AllAroundBest;
import doubletuck.meet.dto.AthleteResponse.ApparatusScore;
import doubletuck.meet.dto.AthleteResponse.ApparatusStanding;
import doubletuck.meet.dto.AthleteResponse.Entry;
import doubletuck.meet.dto.AthleteResponse.EntrySession;
import doubletuck.meet.dto.AthleteResponse.EntryEvent;
import doubletuck.meet.dto.AthleteResponse.PersonalBest;
import doubletuck.meet.dto.AthleteSummaryResponse;
import doubletuck.meet.dto.SessionSummaryResponse;
import doubletuck.meet.repository.AllAroundResultRepository;
import doubletuck.meet.repository.ApparatusResultRepository;
import doubletuck.meet.repository.AthleteNameVariantRepository;
import doubletuck.meet.repository.AthleteRepository;
import doubletuck.meet.repository.ParticipantRepository;
import doubletuck.meet.repository.ScoreRepository;
import doubletuck.meet.repository.SessionRepository;
import org.jspecify.annotations.Nullable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/** Reads athletes for the public site: search, and an athlete's career. */
@Service
@Transactional(readOnly = true)
public class AthleteQueryService {

    static final int SEARCH_LIMIT = 50;

    private final AthleteRepository athleteRepository;
    private final AthleteNameVariantRepository nameVariantRepository;
    private final ParticipantRepository participantRepository;
    private final ScoreRepository scoreRepository;
    private final AllAroundResultRepository allAroundResultRepository;
    private final ApparatusResultRepository apparatusResultRepository;
    private final SessionRepository sessionRepository;

    public AthleteQueryService(AthleteRepository athleteRepository,
            AthleteNameVariantRepository nameVariantRepository, ParticipantRepository participantRepository,
            ScoreRepository scoreRepository, AllAroundResultRepository allAroundResultRepository,
            ApparatusResultRepository apparatusResultRepository, SessionRepository sessionRepository) {
        this.athleteRepository = athleteRepository;
        this.nameVariantRepository = nameVariantRepository;
        this.participantRepository = participantRepository;
        this.scoreRepository = scoreRepository;
        this.allAroundResultRepository = allAroundResultRepository;
        this.apparatusResultRepository = apparatusResultRepository;
        this.sessionRepository = sessionRepository;
    }

    /**
     * Athletes whose name, or a spelling of it a source printed, contains every
     * word of {@code query}, ignoring case and word order; at most
     * {@value #SEARCH_LIMIT}, by name.
     */
    public List<AthleteSummaryResponse> search(String query) {
        List<String> words = Arrays.stream(query.toLowerCase(Locale.ROOT).trim().split("\\s+"))
                .filter(word -> !word.isEmpty())
                .toList();
        if (words.isEmpty()) {
            return List.of();
        }
        // The database narrows by the longest word; the rest are checked here
        String longest = words.stream().max(Comparator.comparingInt(String::length)).orElseThrow();
        List<Athlete> candidates = athleteRepository.findByNameLike("%" + escapeLike(longest) + "%");
        Map<Athlete, List<String>> names = new HashMap<>();
        candidates.forEach(athlete -> names.computeIfAbsent(athlete, a -> new ArrayList<>())
                .add(fullName(athlete.getGivenName(), athlete.getSurname())));
        if (!candidates.isEmpty()) {
            for (AthleteNameVariant variant : nameVariantRepository.findByAthleteIn(candidates)) {
                names.get(variant.getAthlete()).add(fullName(variant.getGivenName(), variant.getSurname()));
            }
        }
        List<Athlete> found = candidates.stream()
                .filter(athlete -> names.get(athlete).stream().anyMatch(name -> words.stream().allMatch(name::contains)))
                .sorted(Comparator.comparing(Athlete::getSurname, String.CASE_INSENSITIVE_ORDER)
                        .thenComparing(Athlete::getGivenName, String.CASE_INSENSITIVE_ORDER))
                .limit(SEARCH_LIMIT)
                .toList();
        if (found.isEmpty()) {
            return List.of();
        }

        Map<Athlete, String> latestNoc = participantRepository.findWithEventByAthleteIn(found).stream()
                .collect(Collectors.groupingBy(Participant::getAthlete, Collectors.collectingAndThen(
                        Collectors.maxBy(Comparator.comparing(p -> p.getEvent().getStartDate())),
                        latest -> latest.map(Participant::getNoc).orElse(null))));
        return found.stream()
                .map(athlete -> new AthleteSummaryResponse(athlete.getId(), athlete.getSurname(),
                        athlete.getGivenName(), athlete.getDiscipline(), latestNoc.get(athlete)))
                .toList();
    }

    public Optional<AthleteResponse> findAthlete(Long id) {
        return athleteRepository.findById(id).map(this::career);
    }

    private AthleteResponse career(Athlete athlete) {
        List<String> otherNames = nameVariantRepository.findByAthlete(athlete).stream()
                .map(variant -> variant.getGivenName() + " " + variant.getSurname())
                .distinct()
                .toList();
        List<Apparatus> order = SessionNaming.apparatusOrder(athlete.getDiscipline());

        List<Entry> entries = new ArrayList<>();
        List<PersonalBest> bests = new ArrayList<>();
        AllAroundBest allAroundBest = null;
        List<Participant> participants = participantRepository.findWithEventByAthleteIn(List.of(athlete)).stream()
                .sorted(Comparator.comparing((Participant p) -> p.getEvent().getStartDate()).reversed())
                .toList();
        for (Participant participant : participants) {
            Event event = participant.getEvent();
            EntryEvent eventRef = new EntryEvent(event.getSlug(), event.getTitle(),
                    event.getShortName(), event.getStartDate(), event.getEndDate());
            List<Score> scores = scoreRepository.findByParticipant(participant);
            List<AllAroundResult> allAround = allAroundResultRepository.findByParticipant(participant);
            List<ApparatusResult> standings = apparatusResultRepository.findByParticipant(participant);

            Set<Session> sessions = new LinkedHashSet<>();
            scores.forEach(score -> sessions.add(score.getSession()));
            allAround.forEach(result -> sessions.add(result.getSession()));
            standings.forEach(result -> sessions.add(result.getSession()));
            Map<Session, List<Session>> divisions = new HashMap<>();

            List<EntrySession> entrySessions = new ArrayList<>();
            for (Session session : sessions.stream().sorted(SessionNaming.order()).toList()) {
                List<Session> division = divisions.computeIfAbsent(session, s -> sessionRepository
                        .findByEventAndDisciplineAndAgeCategory(event, s.getDiscipline(), s.getAgeCategory()));
                SessionSummaryResponse summary = SessionSummaryResponse.from(session, division);
                List<Score> sessionScores = scores.stream()
                        .filter(score -> score.getSession().equals(session))
                        .sorted(Comparator.comparingInt(score -> order.indexOf(score.getApparatus())))
                        .toList();
                AllAroundResult sessionAllAround = allAround.stream()
                        .filter(result -> result.getSession().equals(session))
                        .findFirst()
                        .orElse(null);
                entrySessions.add(new EntrySession(summary,
                        sessionAllAround == null ? null : new AthleteResponse.AllAroundResult(
                                sessionAllAround.getRank(), sessionAllAround.getTotalScore(),
                                sessionAllAround.getQualificationResult()),
                        sessionScores.stream().map(AthleteQueryService::apparatusScore).toList(),
                        standings.stream()
                                .filter(result -> result.getSession().equals(session))
                                .sorted(Comparator.comparingInt(result -> order.indexOf(result.getApparatus())))
                                .map(result -> new ApparatusStanding(result.getApparatus(), result.getRank(),
                                        result.getTotalScore()))
                                .toList()));

                for (Score score : sessionScores) {
                    boolean twoVaults = score.getSecondRoutine() != null;
                    addBest(bests, score, score.getRoutine(), twoVaults ? 1 : null, eventRef, summary);
                    addBest(bests, score, score.getSecondRoutine(), twoVaults ? 2 : null, eventRef, summary);
                }
                if (sessionAllAround != null && sessionAllAround.getTotalScore() != null
                        && completeAllAround(sessionScores, order)
                        && (allAroundBest == null || sessionAllAround.getTotalScore() > allAroundBest.total())) {
                    allAroundBest = new AllAroundBest(sessionAllAround.getTotalScore(), eventRef, summary);
                }
            }
            entries.add(new Entry(eventRef, participant.getNoc(),
                    participant.getClub() == null ? null : participant.getClub().getName(),
                    participant.getEntryStatus(), entrySessions));
        }

        return new AthleteResponse(athlete.getId(), athlete.getSurname(), athlete.getGivenName(),
                athlete.getDiscipline(), athlete.getBirthYear(), otherNames, personalBests(bests, order),
                allAroundBest, entries);
    }

    private static void addBest(List<PersonalBest> bests, Score score, @Nullable Routine routine,
            @Nullable Integer vault, EntryEvent event, SessionSummaryResponse session) {
        if (routine != null && routine.getStatus() == ScoreStatus.COMPLETED && routine.getScore() != null) {
            bests.add(new PersonalBest(score.getApparatus(), routine.getScore(), SessionResultsService.routine(routine),
                    vault, event, session));
        }
    }

    /**
     * The best on each apparatus; on a tie, the earlier. A split round's
     * combined session holds no scores, so its totals never count.
     */
    private static List<PersonalBest> personalBests(List<PersonalBest> routines, List<Apparatus> order) {
        return order.stream()
                .flatMap(app -> routines.stream()
                        .filter(best -> best.apparatus() == app)
                        .max(Comparator.comparingDouble(PersonalBest::score)
                                .thenComparing(best -> best.session().date(), Comparator.reverseOrder()))
                        .stream())
                .toList();
    }

    /**
     * Whether the total is a whole all-around: a score on every apparatus in the
     * one session. A split round's combined total and a partial total (which some
     * national results print) aren't.
     */
    private static boolean completeAllAround(List<Score> sessionScores, List<Apparatus> order) {
        return order.stream().allMatch(app -> sessionScores.stream()
                .anyMatch(score -> score.getApparatus() == app && score.getRoutine() != null
                        && score.getRoutine().getStatus() == ScoreStatus.COMPLETED));
    }

    private static ApparatusScore apparatusScore(Score score) {
        return new ApparatusScore(score.getApparatus(), score.getRank(),
                SessionResultsService.routine(score.getRoutine()),
                SessionResultsService.routine(score.getSecondRoutine()), score.getCombinedBonus(),
                score.getTotalScore(), score.getQualificationRank(), score.getQualificationResult());
    }

    private static String fullName(String givenName, String surname) {
        return (givenName + " " + surname).toLowerCase(Locale.ROOT);
    }

    private static String escapeLike(String text) {
        return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }
}
