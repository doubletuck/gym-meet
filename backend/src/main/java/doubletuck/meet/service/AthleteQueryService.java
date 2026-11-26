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
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.dto.AthleteResponse;
import doubletuck.meet.dto.AthleteResponse.AllAroundBest;
import doubletuck.meet.dto.AthleteResponse.ApparatusScore;
import doubletuck.meet.dto.AthleteResponse.ApparatusStanding;
import doubletuck.meet.dto.AthleteResponse.Entry;
import doubletuck.meet.dto.AthleteResponse.EntryCompetition;
import doubletuck.meet.dto.AthleteResponse.EntryTeam;
import doubletuck.meet.dto.AthleteResponse.EntryEvent;
import doubletuck.meet.dto.AthleteResponse.PersonalBest;
import doubletuck.meet.dto.AthleteSummaryResponse;
import doubletuck.meet.dto.CompetitionSummaryResponse;
import doubletuck.meet.repository.AllAroundResultRepository;
import doubletuck.meet.repository.ApparatusResultRepository;
import doubletuck.meet.repository.AthleteNameVariantRepository;
import doubletuck.meet.repository.AthleteRepository;
import doubletuck.meet.repository.ParticipantRepository;
import doubletuck.meet.repository.ScoreRepository;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.repository.RankingRepository;
import doubletuck.meet.repository.TeamResultRepository;
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
    private final CompetitionRepository competitionRepository;
    private final TeamResultRepository teamResultRepository;
    private final RankingRepository rankingRepository;

    public AthleteQueryService(AthleteRepository athleteRepository,
            AthleteNameVariantRepository nameVariantRepository, ParticipantRepository participantRepository,
            ScoreRepository scoreRepository, AllAroundResultRepository allAroundResultRepository,
            ApparatusResultRepository apparatusResultRepository, CompetitionRepository competitionRepository,
            TeamResultRepository teamResultRepository, RankingRepository rankingRepository) {
        this.athleteRepository = athleteRepository;
        this.nameVariantRepository = nameVariantRepository;
        this.participantRepository = participantRepository;
        this.scoreRepository = scoreRepository;
        this.allAroundResultRepository = allAroundResultRepository;
        this.apparatusResultRepository = apparatusResultRepository;
        this.competitionRepository = competitionRepository;
        this.teamResultRepository = teamResultRepository;
        this.rankingRepository = rankingRepository;
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
        List<Apparatus> order = CompetitionNaming.apparatusOrder(athlete.getDiscipline());

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
            List<ApparatusResult> apparatusResults = apparatusResultRepository.findByParticipant(participant);

            Set<Competition> competitions = new LinkedHashSet<>();
            scores.forEach(score -> competitions.add(score.getCompetition()));
            allAround.forEach(result -> competitions.addAll(result.getRanking().getCompetitions()));
            List<Competition> eventCompetitions = competitionRepository.findByEvent(event);
            CompetitionSummaries summaries = new CompetitionSummaries(eventCompetitions,
                    rankingRepository.findWithCompetitionsByEvent(event));
            // A split competition's combined apparatus standings, the only apparatus rankings not
            // shown with the scores they place
            List<ApparatusResult> combinedStandings = apparatusResults.stream()
                    .filter(result -> result.getRanking().getCompetitions().stream()
                            .anyMatch(competition -> !SplitRound.parts(competition, eventCompetitions).isEmpty()))
                    .toList();
            combinedStandings.forEach(result -> competitions.addAll(result.getRanking().getCompetitions()));

            List<EntryCompetition> entryCompetitions = new ArrayList<>();
            for (Competition competition : competitions.stream().sorted(CompetitionNaming.order()).toList()) {
                CompetitionSummaryResponse summary = summaries.of(competition);
                List<Score> competitionScores = scores.stream()
                        .filter(score -> score.getCompetition().equals(competition))
                        .sorted(Comparator.comparingInt(score -> order.indexOf(score.getApparatus())))
                        .toList();
                ApparatusRanks ranks = new ApparatusRanks(competition.getType(), apparatusResults.stream()
                        .filter(result -> result.getRanking().getCompetitions().contains(competition))
                        .toList());
                AllAroundResult competitionAllAround = allAround.stream()
                        .filter(result -> result.getRanking().getCompetitions().contains(competition))
                        .min(Comparator.comparingInt(result -> CompetitionNaming.preference(result.getRanking())))
                        .orElse(null);
                entryCompetitions.add(new EntryCompetition(summary,
                        competitionAllAround == null ? null : new AthleteResponse.AllAroundResult(
                                competitionAllAround.getRank(), competitionAllAround.getRankStatus(),
                                competitionAllAround.getTotalScore(), competitionAllAround.getQualificationResult(),
                                competitionAllAround.getRanking().getPurpose()),
                        // The country's team in the rankings of the competition's routines
                        teamResultRepository.findByCompetitionAndNoc(competition, participant.getNoc()).stream()
                                .min(Comparator.comparingInt(result -> CompetitionNaming.preference(
                                        result.getRanking())))
                                .map(AthleteQueryService::entryTeam)
                                .orElse(null),
                        competitionScores.stream().map(score -> apparatusScore(score, ranks)).toList(),
                        combinedStandings.stream()
                                .filter(result -> result.getRanking().getCompetitions().contains(competition))
                                .sorted(Comparator.comparingInt(result -> order.indexOf(
                                        result.getRanking().getApparatus())))
                                .map(result -> new ApparatusStanding(result.getRanking().getApparatus(),
                                        result.getRank(), result.getTotalScore()))
                                .toList()));

                for (Score score : competitionScores) {
                    boolean twoVaults = score.getSecondRoutine() != null;
                    addBest(bests, score, score.getRoutine(), twoVaults ? 1 : null, eventRef, summary);
                    addBest(bests, score, score.getSecondRoutine(), twoVaults ? 2 : null, eventRef, summary);
                }
                if (competitionAllAround != null && competitionAllAround.getTotalScore() != null
                        && completeAllAround(competitionScores, order)
                        && (allAroundBest == null || competitionAllAround.getTotalScore() > allAroundBest.total())) {
                    allAroundBest = new AllAroundBest(competitionAllAround.getTotalScore(), eventRef, summary);
                }
            }
            entries.add(new Entry(eventRef, participant.getNoc(),
                    participant.getClub() == null ? null : participant.getClub().getName(),
                    participant.getEntryStatus(), entryCompetitions));
        }

        return new AthleteResponse(athlete.getId(), athlete.getSurname(), athlete.getGivenName(),
                athlete.getDiscipline(), athlete.getBirthYear(), otherNames, personalBests(bests, order),
                allAroundBest, entries);
    }

    private static void addBest(List<PersonalBest> bests, Score score, @Nullable Routine routine,
            @Nullable Integer vault, EntryEvent event, CompetitionSummaryResponse competition) {
        if (routine != null && routine.getStatus() == ScoreStatus.COMPLETED && routine.getScore() != null) {
            bests.add(new PersonalBest(score.getApparatus(), routine.getScore(), CompetitionResultsService.routine(routine),
                    vault, event, competition));
        }
    }

    /**
     * The best on each apparatus; on a tie, the earlier. A split competition's
     * combined row holds no scores, so its totals never count.
     */
    private static List<PersonalBest> personalBests(List<PersonalBest> routines, List<Apparatus> order) {
        return order.stream()
                .flatMap(app -> routines.stream()
                        .filter(best -> best.apparatus() == app)
                        .max(Comparator.comparingDouble(PersonalBest::score)
                                .thenComparing(best -> best.competition().date(), Comparator.reverseOrder()))
                        .stream())
                .toList();
    }

    /**
     * Whether the total is a whole all-around: a score on every apparatus in the
     * one competition. A split competition's combined total and a partial total (which
     * some national results print) aren't.
     */
    private static boolean completeAllAround(List<Score> competitionScores, List<Apparatus> order) {
        return order.stream().allMatch(app -> competitionScores.stream()
                .anyMatch(score -> score.getApparatus() == app && score.getRoutine() != null
                        && score.getRoutine().getStatus() == ScoreStatus.COMPLETED));
    }

    private static ApparatusScore apparatusScore(Score score, ApparatusRanks ranks) {
        return new ApparatusScore(score.getApparatus(), ranks.rank(score),
                CompetitionResultsService.routine(score.getRoutine()),
                CompetitionResultsService.routine(score.getSecondRoutine()), score.getCombinedBonus(),
                score.getTotalScore(), ranks.qualificationRank(score), ranks.qualification(score));
    }

    private static EntryTeam entryTeam(TeamResult result) {
        return new EntryTeam(result.getTeam().getNoc(), result.getRank(), result.getRankStatus(),
                result.getTotalScore(), result.getQualificationResult(), result.getRanking().getPurpose());
    }

    private static String fullName(String givenName, String surname) {
        return (givenName + " " + surname).toLowerCase(Locale.ROOT);
    }

    private static String escapeLike(String text) {
        return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }
}
