package doubletuck.meet.importer;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.repository.AllAroundResultRepository;
import doubletuck.meet.repository.ApparatusResultRepository;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.repository.EventRepository;
import doubletuck.meet.repository.JudgeRepository;
import doubletuck.meet.repository.ParticipantRepository;
import doubletuck.meet.repository.RankingRepository;
import doubletuck.meet.repository.ScoreRepository;
import doubletuck.meet.repository.TeamRepository;
import doubletuck.meet.repository.TeamResultRepository;
import doubletuck.meet.repository.TeamResultScoreRepository;
import doubletuck.meet.service.CompetitionService;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.file.Path;
import java.util.List;

/**
 * Imports one {@code IMPORT.json} manifest -- one discipline and age category
 * of a competition -- in a single transaction, so a problem anywhere in its
 * files leaves nothing behind.
 */
@Service
public class EventImporter {

    private final EventRepository eventRepository;
    private final CompetitionRepository competitionRepository;
    private final RankingRepository rankingRepository;
    private final TeamRepository teamRepository;
    private final ParticipantRepository participantRepository;
    private final ScoreRepository scoreRepository;
    private final JudgeRepository judgeRepository;
    private final TeamResultRepository teamResultRepository;
    private final TeamResultScoreRepository teamResultScoreRepository;
    private final AllAroundResultRepository allAroundResultRepository;
    private final ApparatusResultRepository apparatusResultRepository;
    private final CompetitionService competitionService;
    private final ParticipantImporter participantImporter;
    private final ScoreImporter scoreImporter;
    private final SummaryImporter summaryImporter;
    private final JudgeImporter judgeImporter;
    private final ResultReconciler resultReconciler;
    private final ImportLog importLog;

    EventImporter(EventRepository eventRepository, CompetitionRepository competitionRepository,
            RankingRepository rankingRepository, TeamRepository teamRepository,
            ParticipantRepository participantRepository, ScoreRepository scoreRepository,
            JudgeRepository judgeRepository, TeamResultRepository teamResultRepository,
            TeamResultScoreRepository teamResultScoreRepository, AllAroundResultRepository allAroundResultRepository,
            ApparatusResultRepository apparatusResultRepository, CompetitionService competitionService,
            ParticipantImporter participantImporter, ScoreImporter scoreImporter, SummaryImporter summaryImporter,
            JudgeImporter judgeImporter, ResultReconciler resultReconciler, ImportLog importLog) {
        this.eventRepository = eventRepository;
        this.competitionRepository = competitionRepository;
        this.rankingRepository = rankingRepository;
        this.teamRepository = teamRepository;
        this.participantRepository = participantRepository;
        this.scoreRepository = scoreRepository;
        this.judgeRepository = judgeRepository;
        this.teamResultRepository = teamResultRepository;
        this.teamResultScoreRepository = teamResultScoreRepository;
        this.allAroundResultRepository = allAroundResultRepository;
        this.apparatusResultRepository = apparatusResultRepository;
        this.competitionService = competitionService;
        this.participantImporter = participantImporter;
        this.scoreImporter = scoreImporter;
        this.summaryImporter = summaryImporter;
        this.judgeImporter = judgeImporter;
        this.resultReconciler = resultReconciler;
        this.importLog = importLog;
    }

    /**
     * @param replace when the event already has competitions for this discipline
     *                and age category, delete them (and their results) and
     *                import again; otherwise that is an error
     */
    @Transactional
    public ImportReport importManifest(Path manifestFile, boolean replace) {
        ImportManifest manifest = ImportManifest.read(manifestFile);
        ImportReport report = new ImportReport(manifestFile.getFileName().toString());
        Discipline discipline = required(Discipline.find(manifest.event().disciplines()), "disciplines",
                manifest.event().disciplines(), manifestFile);
        AgeCategory ageCategory = required(AgeCategory.find(manifest.event().ageCategory()), "ageCategory",
                manifest.event().ageCategory(), manifestFile);
        if (manifest.event().shortName() == null || manifest.event().shortName().isBlank()) {
            throw new ImportException(manifestFile.getFileName() + ": event shortName is required");
        }
        Event event = resolveEvent(manifest.event(), manifestFile, discipline, ageCategory, report);

        List<Competition> existing = competitionRepository.findByEventAndDisciplineAndAgeCategory(event,
                discipline, ageCategory);
        boolean replaced = !existing.isEmpty();
        if (replaced) {
            if (!replace) {
                throw new ImportException(manifestFile.getFileName() + ": " + event.getTitle() + " " + discipline
                        + " " + ageCategory + " is already imported; import with replace to load it again");
            }
            deleteSlice(event, discipline, ageCategory, existing, report);
        }

        ImportContext context = new ImportContext(manifestFile.getParent(), manifest, event, discipline,
                ageCategory, report, competitionService, rankingRepository, teamRepository);
        manifest.participants().forEach(file -> participantImporter.importFile(context, file));
        manifest.scores().forEach(file -> scoreImporter.importFile(context, file));
        scoreImporter.rankScores(context);
        manifest.summaries().forEach(file -> summaryImporter.importFile(context, file));
        manifest.judges().forEach(file -> judgeImporter.importFile(context, file));
        resultReconciler.reconcile(context);
        importLog.record(manifestFile, manifest, event, discipline, ageCategory, replaced, report);
        return report;
    }

    private Event resolveEvent(ImportManifest.ManifestEvent source, Path manifestFile, Discipline discipline,
            AgeCategory ageCategory, ImportReport report) {
        String figEventNumber = source.figEventNumber() == null || source.figEventNumber().isBlank() ? null
                : source.figEventNumber().trim();
        if (figEventNumber != null) {
            Event event = eventRepository.findByFigEventNumber(figEventNumber).orElse(null);
            if (event != null) {
                if (!event.getTitle().equalsIgnoreCase(source.title())
                        || !event.getStartDate().equals(source.startDate())) {
                    report.warn("existing event " + event.getId() + " (" + event.getTitle() + ", "
                            + event.getStartDate()
                            + ") matched by FIG event number has a different title or start date than the manifest");
                }
                return updateShortName(event, source, report);
            }
        } else {
            List<Event> overlapping = eventRepository
                    .findByTitleIgnoreCaseAndStartDateLessThanEqualAndEndDateGreaterThanEqual(source.title(),
                            source.endDate(), source.startDate());
            if (overlapping.size() > 1) {
                throw new ImportException(manifestFile.getFileName() + ": " + overlapping.size()
                        + " events titled " + source.title() + " overlap the manifest's dates");
            }
            if (!overlapping.isEmpty()) {
                return updateShortName(widenDates(overlapping.getFirst(), source, report), source, report);
            }
        }

        Event event = new Event();
        event.setSlug(newSlug(source.slug(), manifestFile, discipline, ageCategory));
        event.setFigEventNumber(figEventNumber);
        event.setTitle(source.title());
        event.setShortName(source.shortName().trim());
        event.setStartDate(source.startDate());
        event.setEndDate(source.endDate());
        event.setCity(source.city());
        event.setCountryCode(source.country());
        event.setVenue(source.venue());
        event.setApparatusSuppliers(source.apparatusSuppliers());
        event.setLevel(required(EventLevel.find(source.level()), "level", source.level(), manifestFile));
        report.count("events created");
        return eventRepository.save(event);
    }

    private Event updateShortName(Event event, ImportManifest.ManifestEvent source, ImportReport report) {
        String shortName = source.shortName().trim();
        if (!shortName.equals(event.getShortName())) {
            event.setShortName(shortName);
            report.count("event short names updated");
        }
        return event;
    }

    /**
     * A meet's disciplines can run on different days under one title -- the
     * 2026 US Championships' MAG on 6-8 August and WAG on 7-9 August -- so the
     * event comes to span all of them.
     */
    private Event widenDates(Event event, ImportManifest.ManifestEvent source, ImportReport report) {
        if (source.startDate().isBefore(event.getStartDate()) || source.endDate().isAfter(event.getEndDate())) {
            if (source.startDate().isBefore(event.getStartDate())) {
                event.setStartDate(source.startDate());
            }
            if (source.endDate().isAfter(event.getEndDate())) {
                event.setEndDate(source.endDate());
            }
            report.count("event dates widened");
        }
        return event;
    }

    /**
     * The new event's slug: the manifest's, when it gives one -- the 2026 European
     * Championships are four events in one folder, each named in its manifest.
     * Otherwise its manifest's prefix without the discipline and age category, so
     * 2026-WORLD-CHAMPIONSHIPS-WAG-SR-IMPORT.json gives 2026-world-championships.
     * When another event already has that, the discipline is added.
     */
    private String newSlug(String given, Path manifestFile, Discipline discipline, AgeCategory ageCategory) {
        String fileName = manifestFile.getFileName().toString();
        String slug;
        if (given != null && !given.isBlank()) {
            slug = given.trim();
            if (!slug.matches(Event.SLUG_PATTERN)) {
                throw new ImportException(fileName + ": slug " + slug + " isn't lowercase words separated by hyphens");
            }
        } else {
            String suffix = "-" + discipline.name() + "-" + ageCategory.name() + "-IMPORT.JSON";
            if (!fileName.toUpperCase().endsWith(suffix)) {
                throw new ImportException(fileName + ": manifest name doesn't end in " + suffix);
            }
            slug = fileName.substring(0, fileName.length() - suffix.length()).toLowerCase();
            if (eventRepository.findBySlug(slug).isPresent()) {
                slug = slug + "-" + discipline.name().toLowerCase();
            }
        }
        if (eventRepository.findBySlug(slug).isPresent()) {
            throw new ImportException(fileName + ": another event already has the slug " + slug);
        }
        return slug;
    }

    /**
     * Deletes the slice's rankings (with their results and team score links), teams,
     * and competitions with everything on them, then the event's participants in
     * this discipline left with no results at all -- which includes this slice's
     * entries, since participants aren't tied to an age category.
     */
    private void deleteSlice(Event event, Discipline discipline, AgeCategory ageCategory,
            List<Competition> competitions, ImportReport report) {
        List<Ranking> rankings = rankingRepository.findByEventAndDisciplineAndAgeCategory(event, discipline,
                ageCategory);
        List<TeamResult> teamResults = teamResultRepository.findByRankingIn(rankings);
        teamResultScoreRepository.deleteByTeamResultIn(teamResults);
        teamResultRepository.deleteByRankingIn(rankings);
        allAroundResultRepository.deleteByRankingIn(rankings);
        apparatusResultRepository.deleteByRankingIn(rankings);
        rankingRepository.deleteAll(rankings);
        teamRepository.deleteAll(teamRepository.findByEventAndDisciplineAndAgeCategory(event, discipline,
                ageCategory));
        for (Competition competition : competitions) {
            scoreRepository.deleteByCompetition(competition);
            judgeRepository.deleteByCompetition(competition);
        }
        competitionRepository.deleteAll(competitions);
        competitionRepository.flush();
        report.count("competitions replaced", competitions.size());

        for (Participant participant : participantRepository.findByEvent(event)) {
            if (participant.getAthlete().getDiscipline() == discipline
                    && !scoreRepository.existsByParticipant(participant)
                    && !allAroundResultRepository.existsByParticipant(participant)
                    && !apparatusResultRepository.existsByParticipant(participant)) {
                participantRepository.delete(participant);
                report.count("participants replaced");
            }
        }
        participantRepository.flush();
    }

    private static <T> T required(T value, String field, String text, Path manifestFile) {
        if (value == null) {
            throw new ImportException(manifestFile.getFileName() + ": event " + field + " '" + text
                    + "' is missing or not recognised");
        }
        return value;
    }
}
