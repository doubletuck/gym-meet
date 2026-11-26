package doubletuck.meet.service;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.dto.EventDetailResponse;
import doubletuck.meet.dto.EventSummaryResponse;
import doubletuck.meet.dto.CompetitionSummaryResponse;
import doubletuck.meet.repository.EventDivision;
import doubletuck.meet.repository.EventRepository;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.repository.RankingRepository;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/** Reads events for the public site. */
@Service
@Transactional(readOnly = true)
public class EventQueryService {

    private final EventRepository eventRepository;
    private final CompetitionRepository competitionRepository;
    private final RankingRepository rankingRepository;

    public EventQueryService(EventRepository eventRepository, CompetitionRepository competitionRepository,
            RankingRepository rankingRepository) {
        this.eventRepository = eventRepository;
        this.competitionRepository = competitionRepository;
        this.rankingRepository = rankingRepository;
    }

    /**
     * Events newest first, each with the divisions it has results for.
     *
     * @param year       an event starting or ending in this year, or null for any
     * @param level      or null for any
     * @param discipline an event with results in this discipline, or null for any
     */
    public List<EventSummaryResponse> findEvents(Integer year, EventLevel level, Discipline discipline) {
        Map<Long, List<EventSummaryResponse.Division>> divisions = competitionRepository.findEventDivisions().stream()
                .sorted(Comparator.comparing(EventDivision::discipline).thenComparing(EventDivision::ageCategory))
                .collect(Collectors.groupingBy(EventDivision::eventId,
                        Collectors.mapping(d -> new EventSummaryResponse.Division(d.discipline(), d.ageCategory()),
                                Collectors.toList())));

        return eventRepository.findAll(Sort.by(Sort.Direction.DESC, "startDate")).stream()
                .filter(event -> year == null || event.getStartDate().getYear() == year
                        || event.getEndDate().getYear() == year)
                .filter(event -> level == null || event.getLevel() == level)
                .map(event -> EventSummaryResponse.from(event, divisions.getOrDefault(event.getId(), List.of())))
                .filter(event -> discipline == null
                        || event.divisions().stream().anyMatch(d -> d.discipline() == discipline))
                .toList();
    }

    public Optional<EventDetailResponse> findEvent(String slug) {
        return eventRepository.findBySlug(slug).map(this::detail);
    }

    private record DivisionKey(Discipline discipline, AgeCategory ageCategory) {
    }

    private EventDetailResponse detail(Event event) {
        List<Competition> all = competitionRepository.findByEvent(event);
        CompetitionSummaries summaries = new CompetitionSummaries(all,
                rankingRepository.findWithCompetitionsByEvent(event));
        Map<DivisionKey, List<CompetitionSummaryResponse>> competitions = all.stream()
                .sorted(Comparator.comparing(Competition::getDiscipline).thenComparing(Competition::getAgeCategory)
                        .thenComparing(CompetitionNaming.order()))
                .collect(Collectors.groupingBy(competition -> new DivisionKey(competition.getDiscipline(),
                                competition.getAgeCategory()), LinkedHashMap::new,
                        Collectors.mapping(summaries::of, Collectors.toList())));
        List<EventDetailResponse.DivisionCompetitions> divisions = competitions.entrySet().stream()
                .map(entry -> new EventDetailResponse.DivisionCompetitions(entry.getKey().discipline(),
                        entry.getKey().ageCategory(), entry.getValue()))
                .toList();
        return EventDetailResponse.from(event, divisions);
    }
}
