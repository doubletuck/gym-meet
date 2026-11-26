package doubletuck.meet.importer;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventFormat;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.Team;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.domain.TeamScoreRole;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.repository.RankingRepository;
import doubletuck.meet.repository.TeamRepository;
import doubletuck.meet.service.CompetitionService;
import lombok.Getter;

import java.nio.file.Path;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * State shared by the steps importing one manifest: the event and slice
 * (discipline + age category) being imported, its format, and the participants,
 * competitions, rankings and results created so far.
 */
@Getter
class ImportContext {

    /**
     * @param discipline the apparatus's discipline in a mixed team's ranking (both have floor); null
     *                   elsewhere
     */
    record PublishedTeamTotal(TeamResult teamResult, Discipline discipline, Apparatus apparatus, double total,
            String location) {
    }

    /** A score's placings as its SCORES row gives them, turned into apparatus rankings once all are read. */
    record ScorePlacing(Score score, Integer rank, Integer qualificationRank, QualificationResult qualification,
            String location) {
    }

    private record CompetitionKey(CompetitionType type, Apparatus apparatus, Integer round, Integer part) {
    }

    private record RankingKey(List<Competition> competitions, RankingType type, Apparatus apparatus,
            RankingPurpose purpose) {
    }

    private final Path directory;
    private final ImportManifest manifest;
    private final Event event;
    private final Discipline discipline;
    private final AgeCategory ageCategory;
    private final EventFormat format;
    private final ImportReport report;
    private final CompetitionService competitionService;
    private final CompetitionRepository competitionRepository;
    private final RankingRepository rankingRepository;
    private final TeamRepository teamRepository;

    private final Map<String, Participant> participantsByBib = new HashMap<>();
    private final Map<CompetitionKey, Competition> competitions = new LinkedHashMap<>();
    private final Map<RankingKey, Ranking> rankings = new LinkedHashMap<>();
    private final Map<String, Team> teams = new HashMap<>();
    private final List<Score> scores = new ArrayList<>();
    private final List<ScorePlacing> scorePlacings = new ArrayList<>();
    // Team roles stated by the scores file (SCORES' Team Role column), by score
    private final Map<Score, TeamScoreRole> statedTeamRoles = new IdentityHashMap<>();
    private final List<TeamResult> teamResults = new ArrayList<>();
    private final List<AllAroundResult> allAroundResults = new ArrayList<>();
    // From the SUMMARY files only: a split competition's combined apparatus standings
    private final List<ApparatusResult> apparatusResults = new ArrayList<>();
    private final List<PublishedTeamTotal> publishedTeamTotals = new ArrayList<>();

    ImportContext(Path directory, ImportManifest manifest, EventFormat format, ImportReport report,
            CompetitionService competitionService, CompetitionRepository competitionRepository,
            RankingRepository rankingRepository, TeamRepository teamRepository) {
        this.directory = directory;
        this.manifest = manifest;
        this.event = format.getEvent();
        this.discipline = format.getDiscipline();
        this.ageCategory = format.getAgeCategory();
        this.format = format;
        this.report = report;
        this.competitionService = competitionService;
        this.competitionRepository = competitionRepository;
        this.rankingRepository = rankingRepository;
        this.teamRepository = teamRepository;
    }

    Path file(String name) {
        return directory.resolve(name);
    }

    /** Whether this is a mixed team's slice, whose gymnasts are the event's men and women. */
    boolean isMixed() {
        return discipline == Discipline.MIX;
    }

    Participant participant(CsvRow row) {
        String bib = row.requiredText("Bib");
        Participant participant = participantsByBib.get(bib);
        if (participant == null) {
            throw row.error("bib " + bib + (isMixed() ? " is not a MAG or WAG entry of the event; import the MAG "
                    + "and WAG manifests first" : " is not in the participants file"));
        }
        String noc = row.text("NOC Code");
        if (noc != null && !noc.equals(participant.getNoc())) {
            report.warn(row.location() + ": NOC " + noc + " differs from bib " + bib + "'s entry NOC "
                    + participant.getNoc());
        }
        return participant;
    }

    /**
     * The competition a SCORES row was earned in, creating it the first time it's
     * seen. Scores are what establish a competition and its date.
     */
    Competition competitionForScores(CompetitionType type, Apparatus apparatus, Integer round, Integer part,
            LocalDate date, CsvRow row) {
        CompetitionKey key = new CompetitionKey(type, competitionApparatus(type, apparatus), round, part);
        Competition competition = competitions.get(key);
        if (competition == null) {
            competition = create(key, date);
        } else if (!competition.getDate().equals(date)) {
            report.warn(row.location() + ": competition date " + date + " differs from " + competition.getDate()
                    + " already recorded for the " + describe(key) + " competition");
        }
        return competition;
    }

    /**
     * The competitions whose routines a RANKING row ranks, named by its {@code Competition},
     * {@code Round} and {@code Part}: one, except a mixed team's ranking of C1, which has no
     * routines of its own and ranks the event's MAG and WAG Competition I of its age category,
     * imported before it. A competition must already exist from the scores, except a split
     * competition's whole row (part null), which holds only combined standings and is created
     * here, dated on its first part.
     */
    List<Competition> competitionsForResults(CompetitionType type, Integer round, Integer part, CsvRow row) {
        if (isMixed() && type == CompetitionType.C1) {
            List<Competition> ranked = new ArrayList<>();
            for (Discipline other : List.of(Discipline.MAG, Discipline.WAG)) {
                ranked.add(competitionRepository.findByEventAndDisciplineAndAgeCategory(event, other, ageCategory)
                        .stream()
                        .filter(competition -> competition.getType() == CompetitionType.C1
                                && competition.getApparatus() == null && competition.getPart() == null)
                        .findFirst()
                        .orElseThrow(() -> row.error("a mixed team's C1 ranking ranks the " + other
                                + " Competition I, which isn't imported; import the " + other + " manifest first")));
            }
            return ranked;
        }
        CompetitionKey key = new CompetitionKey(type, null, round, part);
        Competition competition = competitions.get(key);
        if (competition != null) {
            return List.of(competition);
        }
        if (part == null) {
            LocalDate firstPartDate = competitions.entrySet().stream()
                    .filter(entry -> entry.getKey().type() == key.type() && entry.getKey().apparatus() == null
                            && entry.getKey().part() != null)
                    .map(entry -> entry.getValue().getDate())
                    .min(Comparator.naturalOrder())
                    .orElse(null);
            if (firstPartDate != null) {
                return List.of(create(key, firstPartDate));
            }
        }
        throw row.error("no scores were imported for the " + describe(key) + " competition this row ranks");
    }

    Ranking ranking(Competition competition, RankingType type, Apparatus apparatus, RankingPurpose purpose) {
        return ranking(List.of(competition), type, apparatus, purpose);
    }

    /**
     * The ranking of these competitions' routines of this type, apparatus and purpose,
     * creating it the first time it's needed.
     */
    Ranking ranking(List<Competition> ranked, RankingType type, Apparatus apparatus, RankingPurpose purpose) {
        return rankings.computeIfAbsent(new RankingKey(List.copyOf(ranked), type, apparatus, purpose), key -> {
            Ranking ranking = new Ranking();
            ranking.setEvent(event);
            ranking.setDiscipline(discipline);
            ranking.setAgeCategory(ageCategory);
            ranking.setType(type);
            ranking.setApparatus(apparatus);
            ranking.setPurpose(purpose);
            ranking.getCompetitions().addAll(ranked);
            report.count("rankings");
            return rankingRepository.save(ranking);
        });
    }

    /** The NOC's team in this slice, creating it the first time it's seen. */
    Team team(String noc) {
        return teams.computeIfAbsent(noc, name -> {
            Team team = new Team();
            team.setEvent(event);
            team.setDiscipline(discipline);
            team.setAgeCategory(ageCategory);
            team.setName(name);
            team.setNoc(name);
            report.count("teams");
            return teamRepository.save(team);
        });
    }

    /**
     * The competitions a judge served on: normally one, but a Superior Jury role
     * (no apparatus) in a competition held per apparatus -- the apparatus finals --
     * presides over all of them, and a judge with no round given in a competition held
     * in elimination rounds served every round. Empty when no scores were imported for it.
     */
    List<Competition> competitionsForJudge(CompetitionType type, Apparatus apparatus, Integer round) {
        boolean everyApparatus = apparatus == null && isPerApparatus(type);
        return competitions.entrySet().stream()
                .filter(entry -> entry.getKey().type() == type && entry.getKey().part() == null
                        && (everyApparatus || entry.getKey().apparatus() == competitionApparatus(type, apparatus))
                        && (round == null || round.equals(entry.getKey().round())))
                .map(Map.Entry::getValue)
                .toList();
    }

    /** Whether the competition is a split competition's whole row, holding the combined standings of its parts. */
    boolean isWholeOfParts(Competition competition) {
        return competition.getPart() == null && competitions.values().stream()
                .anyMatch(part -> isPartOf(part, competition));
    }

    static boolean isPartOf(Competition part, Competition whole) {
        return whole.getPart() == null && part.getPart() != null && part.getType() == whole.getType()
                && Objects.equals(part.getApparatus(), whole.getApparatus())
                && Objects.equals(part.getRound(), whole.getRound());
    }

    private boolean isPerApparatus(CompetitionType type) {
        return type == CompetitionType.C3 || (type == CompetitionType.C1 && format.isApparatusOnly());
    }

    private Apparatus competitionApparatus(CompetitionType type, Apparatus apparatus) {
        return isPerApparatus(type) ? apparatus : null;
    }

    private Competition create(CompetitionKey key, LocalDate date) {
        Competition competition = new Competition();
        competition.setEvent(event);
        competition.setDate(date);
        competition.setType(key.type());
        competition.setDiscipline(discipline);
        competition.setAgeCategory(ageCategory);
        competition.setApparatus(key.apparatus());
        competition.setRound(key.round());
        competition.setPart(key.part());
        competition = competitionService.createCompetition(competition);
        competitions.put(key, competition);
        report.count("competitions");
        return competition;
    }

    private static String describe(CompetitionKey key) {
        return key.type() + (key.apparatus() != null ? " " + key.apparatus() : "")
                + (key.round() != null ? " round " + key.round() : "")
                + (key.part() != null ? " part " + key.part() : "");
    }
}
