package doubletuck.meet.importer;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.BonusDetail;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.EntryStatus;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventFormat;
import doubletuck.meet.domain.EventLevel;
import doubletuck.meet.domain.ImportRun;
import doubletuck.meet.domain.Judge;
import doubletuck.meet.domain.JudgeFunction;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.RankStatus;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.ScoreStatus;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.domain.TeamContributionRole;
import doubletuck.meet.domain.TeamResultScore;
import doubletuck.meet.domain.TeamScoreRole;
import doubletuck.meet.domain.TitleFormat;
import doubletuck.meet.repository.AllAroundResultRepository;
import doubletuck.meet.repository.ApparatusResultRepository;
import doubletuck.meet.repository.EventFormatRepository;
import doubletuck.meet.repository.EventRepository;
import doubletuck.meet.repository.ImportRunRepository;
import doubletuck.meet.repository.JudgeRepository;
import doubletuck.meet.repository.ParticipantRepository;
import doubletuck.meet.repository.ScoreRepository;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.repository.RankingRepository;
import doubletuck.meet.repository.TeamRepository;
import doubletuck.meet.repository.TeamResultRepository;
import doubletuck.meet.repository.TeamResultScoreRepository;
import doubletuck.meet.service.ApparatusRanks;
import doubletuck.meet.service.CompetitionService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import java.io.IOException;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.function.Function;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Imports fixtures cut down from the real results files (a few athletes each,
 * otherwise unchanged) and checks what was stored against the published results.
 */
@DataJpaTest
@ActiveProfiles("test")
@Import({ EventImporter.class, ParticipantImporter.class, ScoreImporter.class, RankingImporter.class, FormatChecker.class,
        JudgeImporter.class, ResultReconciler.class, AthleteMatcher.class, CompetitionService.class, ImportLog.class })
class EventImporterTest {

    private static final String WORLDS_WAG = "worlds/2026-WORLD-CHAMPIONSHIPS-WAG-SR-IMPORT.json";
    private static final String WORLDS_MAG = "worlds/2026-WORLD-CHAMPIONSHIPS-MAG-SR-IMPORT.json";
    private static final String COTTBUS_WAG = "cottbus/2026-APPARATUS-WORLD-CUP-COTTBUS-WAG-SR-IMPORT.json";
    private static final String BAKU_WAG = "baku/2026-APPARATUS-WORLD-CUP-BAKU-WAG-SR-IMPORT.json";
    private static final String US_MAG = "us/2026-US-CHAMPIONSHIPS-MAG-SR-IMPORT.json";
    private static final String EUROPEANS_MAG = "europeans/2026-EUROPEAN-CHAMPIONSHIPS-MAG-SR-IMPORT.json";
    private static final String ASIAN_WAG = "asian/2026-ASIAN-CHAMPIONSHIPS-WAG-SR-IMPORT.json";
    private static final String OCEANIA_MAG = "oceania/2026-OCEANIA-CHAMPIONSHIPS-MAG-SR-IMPORT.json";
    private static final String OCEANIA_WAG = "oceania/2026-OCEANIA-CHAMPIONSHIPS-WAG-SR-IMPORT.json";

    @Autowired
    private EventImporter eventImporter;

    @Autowired
    private EventRepository eventRepository;

    @Autowired
    private CompetitionRepository competitionRepository;

    @Autowired
    private EventFormatRepository eventFormatRepository;

    @Autowired
    private RankingRepository rankingRepository;

    @Autowired
    private TeamResultScoreRepository teamResultScoreRepository;

    @Autowired
    private TeamRepository teamRepository;

    @Autowired
    private ParticipantRepository participantRepository;

    @Autowired
    private ScoreRepository scoreRepository;

    @Autowired
    private TeamResultRepository teamResultRepository;

    @Autowired
    private AllAroundResultRepository allAroundResultRepository;

    @Autowired
    private ApparatusResultRepository apparatusResultRepository;

    @Autowired
    private JudgeRepository judgeRepository;

    @Autowired
    private ImportRunRepository importRunRepository;

    @Autowired
    private ImportLog importLog;

    @Test
    void testImport_BothDisciplinesShareOneEvent() {
        importFixture(WORLDS_WAG);
        importFixture(WORLDS_MAG);

        List<Event> events = eventRepository.findAll();
        assertEquals(1, events.size());
        Event worlds = events.get(0);
        assertEquals("54th Artistic Gymnastics World Championships", worlds.getTitle());
        assertEquals("17247", worlds.getFigEventNumber());
        assertEquals(LocalDate.of(2026, 10, 17), worlds.getStartDate());
        assertEquals("NED", worlds.getCountryCode());
        assertEquals("Spieth", worlds.getApparatusSuppliers());
        assertEquals(EventLevel.WORLD_CHAMPIONSHIPS, worlds.getLevel());
        assertTrue(competitionRepository.findByEvent(worlds).stream().anyMatch(s -> s.getDiscipline() == Discipline.WAG));
        assertTrue(competitionRepository.findByEvent(worlds).stream().anyMatch(s -> s.getDiscipline() == Discipline.MAG));
    }

    @Test
    void testImport_SameTitleOverlappingDates_SharesOneEventSpanningBoth(@TempDir Path dir) throws IOException {
        Path seniors = writeMinimalMeet(dir.resolve("seniors"), "5.5", "101");
        Files.writeString(seniors, Files.readString(seniors)
                .replace("\"endDate\": \"2026-03-01\"", "\"endDate\": \"2026-03-02\""));
        eventImporter.importManifest(seniors, false);
        // Juniors from the 2nd to the 3rd
        Path juniors = writeMinimalMeet(dir.resolve("juniors"), "5.5", "101");
        for (Path file : List.of(juniors, juniors.resolveSibling("MINI-MAG-SR-PARTICIPANTS.csv"),
                juniors.resolveSibling("MINI-MAG-SR-SCORES-C1-FX.csv"))) {
            Files.writeString(file, Files.readString(file).replace("2026-03-01", "2026-03-02")
                    .replace("\"ageCategory\": \"SR\"", "\"ageCategory\": \"JR\"").replace(",SR,", ",JR,")
                    .replace("\"endDate\": \"2026-03-02\"", "\"endDate\": \"2026-03-03\"")
                    .replace("DE VRIES", "JANSEN").replace("BAKKER", "VISSER"));
        }

        ImportReport report = eventImporter.importManifest(juniors, false);

        List<Event> events = eventRepository.findAll();
        assertEquals(1, events.size());
        assertEquals(LocalDate.of(2026, 3, 1), events.get(0).getStartDate());
        assertEquals(LocalDate.of(2026, 3, 3), events.get(0).getEndDate());
        assertEquals(1, report.getCount("event dates widened"));
    }

    @Test
    void testImport_RecordsTheRun(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");
        eventImporter.importManifest(manifest, false);
        eventImporter.importManifest(manifest, true);

        List<ImportRun> runs = importRunRepository.findAll();
        assertEquals(2, runs.size());
        ImportRun last = runs.get(1);
        assertEquals("MINI-MAG-SR-IMPORT.json", last.getManifest());
        assertEquals("mini", last.getEvent().getSlug());
        assertEquals(Discipline.MAG, last.getDiscipline());
        assertFalse(runs.get(0).isReplaced());
        assertTrue(last.isReplaced());
        assertEquals(0, last.getWarningCount());
        assertTrue(last.getReport().startsWith("MINI-MAG-SR-IMPORT.json"), last.getReport());
    }

    @Test
    void testImportStatus_UpToDateUntilAListedFileChanges(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");
        assertEquals(ImportLog.State.NOT_IMPORTED, importLog.status(manifest).state());

        eventImporter.importManifest(manifest, false);
        assertEquals(ImportLog.State.UP_TO_DATE, importLog.status(manifest).state());

        Path scores = dir.resolve("MINI-MAG-SR-SCORES-C1-FX.csv");
        Files.writeString(scores, Files.readString(scores).replace("8.500", "8.600"));
        assertEquals(ImportLog.State.CHANGED, importLog.status(manifest).state());
    }

    @Test
    void testImport_EventSlugComesFromTheManifestName() {
        importFixture(WORLDS_WAG);

        assertEquals("2026-world-championships", eventRepository.findAll().get(0).getSlug());
    }

    @Test
    void testImport_EventShortNameComesFromTheManifest() {
        importFixture(WORLDS_WAG);

        assertEquals("Worlds 2026", eventRepository.findAll().get(0).getShortName());
    }

    @Test
    void testImport_ImportedAgainWithAnotherShortName_UpdatesIt(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");
        eventImporter.importManifest(manifest, false);
        Files.writeString(manifest, Files.readString(manifest).replace("\"shortName\": \"Mini\"",
                "\"shortName\": \"Mini 2026\""));

        ImportReport report = eventImporter.importManifest(manifest, true);

        assertEquals("Mini 2026", eventRepository.findAll().get(0).getShortName());
        assertEquals(1, report.getCount("event short names updated"));
    }

    @Test
    void testImport_NoShortName_Fails(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");
        Files.writeString(manifest, Files.readString(manifest).replace("\"shortName\": \"Mini\", ", ""));

        ImportException e = assertThrows(ImportException.class, () -> eventImporter.importManifest(manifest, false));
        assertTrue(e.getMessage().contains("shortName is required"), e.getMessage());
    }

    @Test
    void testImport_SlugTakenByAnotherEvent_AddsTheDiscipline(@TempDir Path dir) throws IOException {
        eventImporter.importManifest(writeMinimalMeet(dir.resolve("first"), "5.5", "101"), false);
        Path second = writeMinimalMeet(dir.resolve("second"), "5.5", "101");
        for (Path file : List.of(second, second.resolveSibling("MINI-MAG-SR-PARTICIPANTS.csv"),
                second.resolveSibling("MINI-MAG-SR-SCORES-C1-FX.csv"))) {
            Files.writeString(file, Files.readString(file).replace("2026-03-01", "2026-04-01"));
        }

        eventImporter.importManifest(second, false);

        assertEquals(List.of("mini", "mini-mag"), eventRepository.findAll().stream().map(Event::getSlug).sorted()
                .toList());
    }

    @Test
    void testImport_SlugGivenInTheManifest_IsUsed(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");
        giveSlug(manifest, "mini-meet-mag-sr");

        eventImporter.importManifest(manifest, false);

        assertEquals("mini-meet-mag-sr", eventRepository.findAll().get(0).getSlug());
    }

    @Test
    void testImport_SlugGivenInTheManifest_NotLowercaseWords_IsRejected(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");
        giveSlug(manifest, "Mini Meet");

        ImportException e = assertThrows(ImportException.class, () -> eventImporter.importManifest(manifest, false));
        assertTrue(e.getMessage().contains("slug Mini Meet"), e.getMessage());
    }

    @Test
    void testImport_SlugGivenInTheManifest_TakenByAnotherEvent_IsRejected(@TempDir Path dir) throws IOException {
        Path first = writeMinimalMeet(dir.resolve("first"), "5.5", "101");
        giveSlug(first, "mini-meet");
        eventImporter.importManifest(first, false);
        Path second = writeMinimalMeet(dir.resolve("second"), "5.5", "101");
        for (Path file : List.of(second, second.resolveSibling("MINI-MAG-SR-PARTICIPANTS.csv"),
                second.resolveSibling("MINI-MAG-SR-SCORES-C1-FX.csv"))) {
            Files.writeString(file, Files.readString(file).replace("2026-03-01", "2026-04-01"));
        }
        giveSlug(second, "mini-meet");

        ImportException e = assertThrows(ImportException.class, () -> eventImporter.importManifest(second, false));
        assertTrue(e.getMessage().contains("already has the slug mini-meet"), e.getMessage());
    }

    @Test
    void testImport_StoresEveryScoreRowWithoutWarnings() {
        ImportReport report = importFixture(WORLDS_WAG);

        assertEquals(rowCount(WORLDS_WAG, ImportManifest::scores), scoreRepository.count());
        assertEquals(rowCount(WORLDS_WAG, ImportManifest::participants), participantRepository.count());
        assertEquals(List.of(), report.getWarnings());
    }

    @Test
    void testImport_CreatesOneSessionPerRoundAndPerApparatusFinal() {
        importFixture(WORLDS_WAG);

        List<Competition> sessions = competitionRepository.findAll();
        assertEquals(LocalDate.of(2026, 10, 18), competition(sessions, CompetitionType.C1, null).getDate());
        assertEquals(LocalDate.of(2026, 10, 21), competition(sessions, CompetitionType.C4, null).getDate());
        assertEquals(LocalDate.of(2026, 10, 23), competition(sessions, CompetitionType.C2, null).getDate());
        assertEquals(LocalDate.of(2026, 10, 25), competition(sessions, CompetitionType.C3, Apparatus.BB).getDate());
        assertTrue(sessions.stream().allMatch(s -> s.getPart() == null));
    }

    @Test
    void testImport_ScoreFieldsAsPublished() {
        importFixture(WORLDS_WAG);

        Score zhang = score("Zhang", "Qingying", CompetitionType.C1, Apparatus.BB);
        assertEquals(6.8, zhang.getRoutine().getDifficulty());
        assertEquals(8.3, zhang.getRoutine().getExecution());
        assertEquals(15.1, zhang.getRoutine().getScore());
        assertEquals(15.1, zhang.getTotalScore());
        assertEquals(ScoreStatus.COMPLETED, zhang.getRoutine().getStatus());
        assertFalse(zhang.getRoutine().getDifficultyInquiry());
        assertEquals(1, rank(zhang));
        assertEquals(1, qualificationRank(zhang));
        assertEquals(QualificationResult.Q, qualification(zhang));
        assertNull(zhang.getSecondRoutine());

        assertEquals(QualificationResult.NR, qualification(score("Ke", "Qinqin", CompetitionType.C1, Apparatus.BB)));
    }

    @Test
    void testImport_TwoVaultEntry() {
        importFixture(WORLDS_MAG);

        Score jarman = score("Jarman", "Jake", CompetitionType.C1, Apparatus.VT);
        assertEquals(5.6, jarman.getRoutine().getDifficulty());
        assertEquals(14.9, jarman.getRoutine().getScore());
        assertEquals(5.2, jarman.getSecondRoutine().getDifficulty());
        assertEquals(14.366, jarman.getSecondRoutine().getScore());
        assertEquals(ScoreStatus.COMPLETED, jarman.getSecondRoutine().getStatus());
        assertEquals(14.633, jarman.getTotalScore());
        assertEquals(1, rank(jarman));
        assertEquals(1, qualificationRank(jarman));
        assertEquals(QualificationResult.Q, qualification(jarman));
    }

    @Test
    void testImport_QualificationVault_RankedTwice() {
        importFixture(WORLDS_MAG);

        Competition qualification = competition(competitionRepository.findAll(), CompetitionType.C1, null);
        List<Ranking> vault = rankingRepository.findByCompetition(qualification).stream()
                .filter(ranking -> ranking.getApparatus() == Apparatus.VT).toList();
        // The single-vault list (every vaulter, on the first vault) decides nothing; the two-vault list the final
        assertEquals(List.of(RankingPurpose.QUALIFYING, RankingPurpose.INFORMATIONAL),
                vault.stream().map(Ranking::getPurpose).sorted().toList());
        Ranking twoVaults = vault.stream().filter(ranking -> ranking.getPurpose() == RankingPurpose.QUALIFYING)
                .findFirst().orElseThrow();
        ApparatusResult jarman = apparatusResultRepository.findByRanking(twoVaults).stream()
                .filter(result -> result.getParticipant().getAthlete().getSurname().equals("Jarman"))
                .findFirst().orElseThrow();
        assertEquals(14.633, jarman.getTotalScore());
        assertEquals(RankStatus.RANKED, jarman.getRankStatus());
        assertTrue(apparatusResultRepository.findByRanking(twoVaults).size()
                < scoreRepository.findByCompetition(qualification).stream()
                        .filter(score -> score.getApparatus() == Apparatus.VT).count());
    }

    @Test
    void testImport_ApparatusFinalPlacings_AreFinalRankings() {
        importFixture(WORLDS_WAG);

        Competition beamFinal = competition(competitionRepository.findAll(), CompetitionType.C3, Apparatus.BB);
        assertEquals(List.of(RankingPurpose.FINAL), rankingRepository.findByCompetition(beamFinal).stream()
                .map(Ranking::getPurpose).toList());
    }

    @Test
    void testImport_DidNotStart() {
        importFixture(WORLDS_MAG);

        Score tulloch = score("Tulloch", "Courtney", CompetitionType.C1, Apparatus.PH);
        assertEquals(ScoreStatus.DNS, tulloch.getRoutine().getStatus());
        assertNull(tulloch.getRoutine().getScore());
        assertNull(tulloch.getTotalScore());
        assertNull(rank(tulloch));
    }

    @Test
    void testImport_MarksScoresDroppedFromTeamTotal() {
        importFixture(WORLDS_WAG);

        assertEquals(TeamScoreRole.COUNTING, teamRole(score("Zhang", "Qingying", CompetitionType.C1, Apparatus.BB)));
        assertEquals(TeamScoreRole.COUNTING, teamRole(score("Qiu", "Qiyuan", CompetitionType.C1, Apparatus.BB)));
        assertEquals(TeamScoreRole.COUNTING, teamRole(score("Ke", "Qinqin", CompetitionType.C1, Apparatus.BB)));
        assertEquals(TeamScoreRole.DROPPED, teamRole(score("Zhang", "Yihan", CompetitionType.C1, Apparatus.BB)));
    }

    @Test
    void testImport_IndividualEnteredAlongsideTeam_DoesNotCountTowardTeam() {
        ImportReport report = importFixture(EUROPEANS_MAG);

        // MURABITO competed as an individual: the best floor score, but not the team's. Worked out from the
        // totals, a score left out can't be told apart from a team member's dropped one
        assertEquals(TeamScoreRole.DROPPED, teamRole(score("Murabito", "Luca", CompetitionType.C1, Apparatus.FX)));
        assertEquals(TeamScoreRole.COUNTING, teamRole(score("Langenegger", "Florian", CompetitionType.C1, Apparatus.FX)));
        assertEquals(List.of(), report.getWarnings());
    }

    @Test
    void testImport_TeamRolesStatedInTheScoresFile_AreStoredAsGiven() {
        ImportReport report = importFixture(OCEANIA_MAG);

        assertEquals(List.of(), report.getWarnings());
        // A team member on some apparatus and the country's individual on others
        assertEquals(TeamScoreRole.INDIVIDUAL, teamRole(score("Malik", "Ritam", CompetitionType.C1, Apparatus.FX)));
        assertEquals(TeamScoreRole.COUNTING, teamRole(score("Malik", "Ritam", CompetitionType.C1, Apparatus.VT)));
        assertEquals(TeamScoreRole.DROPPED, teamRole(score("Malik", "Ritam", CompetitionType.C1, Apparatus.PB)));
        // Out-scoring a team member doesn't make an individual's score count
        assertEquals(TeamScoreRole.DROPPED, teamRole(score("Hardy", "James", CompetitionType.C1, Apparatus.FX)));
        assertEquals(TeamScoreRole.DROPPED, teamRole(score("Greene", "Keegan", CompetitionType.C1, Apparatus.FX)));
        assertEquals(TeamScoreRole.INDIVIDUAL, teamRole(score("Greene", "Keegan", CompetitionType.C1, Apparatus.HB)));
    }

    @Test
    void testImport_StatedCountingScoresNotAddingUpToTheTotal_Warns(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(OCEANIA_MAG, dir);
        Path floor = dir.resolve("2026-OCEANIA-CHAMPIONSHIPS-MAG-SR-SCORES-C1-FX.csv");
        Files.writeString(floor, Files.readString(floor).replace(",13.000,INDIVIDUAL", ",13.000,COUNTING"));

        ImportReport report = eventImporter.importManifest(manifest, false);

        assertEquals(1, report.getWarnings().size(), report.getWarnings().toString());
        assertTrue(report.getWarnings().get(0).contains("AUS team: its counting FX scores add up to 53.399, not "
                + "the published 40.399"), report.getWarnings().get(0));
        assertEquals(TeamScoreRole.COUNTING, teamRole(score("Malik", "Ritam", CompetitionType.C1, Apparatus.FX)));
    }

    @Test
    void testImport_StatedTeamRoles_IndividualAndDidNotStart() {
        ImportReport report = importFixture(OCEANIA_WAG);

        assertEquals(List.of(), report.getWarnings());
        // The fifth vaulter scored below every team member, and was still no part of the team
        assertEquals(TeamScoreRole.INDIVIDUAL, teamRole(score("Stewart", "Lucy", CompetitionType.C1, Apparatus.VT)));
        assertEquals(TeamScoreRole.DROPPED, teamRole(score("Bayles", "Asher", CompetitionType.C1, Apparatus.UB)));
        assertEquals(TeamScoreRole.INDIVIDUAL, teamRole(score("Bayles", "Asher", CompetitionType.C1, Apparatus.BB)));
        assertEquals(ScoreStatus.DNS, score("Bayles", "Asher", CompetitionType.C1, Apparatus.BB).getRoutine().getStatus());
    }

    @Test
    void testImport_TeamFinalRankingRoutinesOfASessionWithoutTeams_WorksOutTheRoles(@TempDir Path dir)
            throws IOException {
        Path manifest = copyFixture(OCEANIA_WAG, dir);
        try (var files = Files.list(dir)) {
            for (Path file : files.filter(f -> f.getFileName().toString().contains("-SCORES-")).toList()) {
                Files.writeString(file, Files.readString(file).replaceAll("(?m),[^,\\n]*$", ""));
            }
        }

        ImportReport report = eventImporter.importManifest(manifest, false);

        assertEquals(List.of(), report.getWarnings());
        // The team final had no routines of its own: its ranking is of the all-around final's routines
        assertTrue(competitionRepository.findAll().stream().noneMatch(c -> c.getType() == CompetitionType.C4));
        Competition allAroundFinal = competition(competitionRepository.findAll(), CompetitionType.C1, null);
        assertTrue(rankingRepository.findByCompetition(allAroundFinal).stream().anyMatch(ranking ->
                ranking.getType() == RankingType.TEAM && ranking.getPurpose() == RankingPurpose.FINAL));
        assertEquals(TeamScoreRole.COUNTING, teamRole(score("Whitehead", "Emily", CompetitionType.C1, Apparatus.VT)));
        // Worked out from the totals, the fifth vaulter can't be told from a dropped team member
        assertEquals(TeamScoreRole.DROPPED, teamRole(score("Stewart", "Lucy", CompetitionType.C1, Apparatus.VT)));
    }

    @Test
    void testImport_NamesStoredInWrittenForm() {
        importFixture(WORLDS_WAG);

        assertTrue(participantRepository.findAll().stream().map(p -> p.getAthlete().getSurname())
                .anyMatch("Hamames-Moallic"::equals));
        assertTrue(judgeRepository.findAll().stream().noneMatch(judge -> judge.getSurname().matches(".*\\p{Lu}{2}.*")));
    }

    @Test
    void testImport_TeamAndAllAroundResults() {
        importFixture(WORLDS_WAG);
        List<Competition> sessions = competitionRepository.findAll();

        TeamResult china = teamResult(competition(sessions, CompetitionType.C1, null), "CHN")
                .orElseThrow();
        assertEquals(1, china.getRank());
        assertEquals(164.996, china.getTotalScore());
        assertEquals(QualificationResult.Q, china.getQualificationResult());

        AllAroundResult ke = allAroundResults(competition(sessions, CompetitionType.C2, null)).stream()
                .filter(result -> result.getParticipant().getAthlete().getSurname().equals("Ke"))
                .findFirst().orElseThrow();
        assertEquals(3, ke.getRank());
        assertEquals(55.032, ke.getTotalScore());
    }

    @Test
    void testImport_FinalsSuperiorJuryServesEveryApparatusFinal() {
        importFixture(WORLDS_WAG);

        List<Competition> finals = competitionRepository.findAll().stream().filter(s -> s.getType() == CompetitionType.C3).toList();
        assertFalse(finals.isEmpty());
        for (Competition apparatusFinal : finals) {
            List<Judge> judges = judgeRepository.findByCompetition(apparatusFinal);
            assertTrue(judges.stream().anyMatch(judge -> judge.getFunction() == JudgeFunction.VICE_PRESIDENT
                    && judge.getApparatus() == null), "no Vice-President on " + apparatusFinal.getApparatus());
        }
    }

    @Test
    void testImport_ApparatusFormatQualificationHasOneSessionPerApparatus() {
        importFixture(COTTBUS_WAG);

        List<Competition> qualifications = competitionRepository.findAll().stream()
                .filter(s -> s.getType() == CompetitionType.C1).toList();
        assertEquals(4, qualifications.size());
        assertTrue(qualifications.stream().allMatch(s -> s.getApparatus() != null));
        assertEquals(LocalDate.of(2026, 2, 19), competition(qualifications, CompetitionType.C1, Apparatus.UB).getDate());
        assertEquals(LocalDate.of(2026, 2, 20), competition(qualifications, CompetitionType.C1, Apparatus.BB).getDate());
    }

    @Test
    void testImport_CombinedVaultSjPenaltyAndTechnicalDelegate() {
        importFixture(BAKU_WAG);

        // (12.100 + 13.066) / 2 + 0.2 - 0.3: the penalty comes off the two-vault result, not either vault
        Score makovickova = score("Makovickova", "Patricie", CompetitionType.C1, Apparatus.VT);
        assertEquals(12.100, makovickova.getRoutine().getScore());
        assertEquals(13.066, makovickova.getSecondRoutine().getScore());
        assertEquals(0.2, makovickova.getCombinedBonus());
        assertEquals(-0.3, makovickova.getCombinedSjPenalty());
        assertEquals(12.483, makovickova.getTotalScore());
        assertNull(score("Kalmykova", "Anna", CompetitionType.C1, Apparatus.VT).getCombinedSjPenalty());

        for (Competition competition : competitionRepository.findAll()) {
            assertTrue(judgeRepository.findByCompetition(competition).stream().anyMatch(judge ->
                    judge.getFunction() == JudgeFunction.TD && judge.getApparatus() == null
                            && judge.getNocCode() == null), "no Technical Delegate on " + competition.getType());
        }
    }

    @Test
    void testImport_SplitRoundHasPartSessionsAndWholeRoundSession() {
        ImportReport report = importFixture(US_MAG);
        List<Competition> sessions = competitionRepository.findAll();

        assertEquals(3, sessions.size());
        Competition wholeRound = sessions.stream().filter(s -> s.getPart() == null).findFirst().orElseThrow();
        assertEquals(LocalDate.of(2026, 8, 6), wholeRound.getDate());
        assertTrue(scoreRepository.findByCompetition(wholeRound).isEmpty());

        AllAroundResult moldauer = allAroundResults(wholeRound).stream()
                .filter(result -> result.getParticipant().getAthlete().getSurname().equals("Moldauer"))
                .findFirst().orElseThrow();
        assertEquals(5, moldauer.getRank());
        assertEquals(163.896, moldauer.getTotalScore());

        ApparatusResult hoopes = apparatusResults(wholeRound, Apparatus.PH)
                .stream().filter(result -> result.getParticipant().getAthlete().getSurname().equals("Hoopes"))
                .findFirst().orElseThrow();
        assertEquals(30.816, hoopes.getTotalScore());
        assertEquals(List.of(), report.getWarnings());
    }

    @Test
    void testImport_NationalEntryWithClubAndNoBirthYear() {
        importFixture(US_MAG);

        Participant hoopes = participantRepository.findAll().stream()
                .filter(p -> p.getAthlete().getSurname().equals("Hoopes")).findFirst().orElseThrow();
        assertEquals("Air Force", hoopes.getClub().getName());
        assertEquals("USA", hoopes.getClub().getCountry());
        assertNull(hoopes.getAthlete().getBirthYear());
        assertNull(hoopes.getAthlete().getLicenseNumber());
    }

    @Test
    void testImport_EntryStatus_ReadWhenPresentElseCompetitor(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        addEntryStatus(dir, "RESERVE");

        eventImporter.importManifest(manifest, false);

        assertEquals(EntryStatus.RESERVE, participant("999").getEntryStatus());
        assertEquals(EntryStatus.COMPETITOR, participant("401").getEntryStatus());
    }

    @Test
    void testImport_EntryStatus_HorsConcours(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        addEntryStatus(dir, "HORS_CONCOURS");

        eventImporter.importManifest(manifest, false);

        assertEquals(EntryStatus.HORS_CONCOURS, participant("999").getEntryStatus());
    }

    @Test
    void testImport_EntryStatusColumnAbsent_EveryoneIsACompetitor() {
        importFixture(WORLDS_WAG);

        assertTrue(participantRepository.findAll().stream()
                .allMatch(p -> p.getEntryStatus() == EntryStatus.COMPETITOR));
    }

    @Test
    void testImport_UnknownEntryStatus_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        addEntryStatus(dir, "SPARE");

        ImportException e = assertThrows(ImportException.class, () -> eventImporter.importManifest(manifest, false));
        assertTrue(e.getMessage().contains("unrecognised Entry Status 'SPARE'"), e.getMessage());
    }

    @Test
    void testImport_ItemizedBonusBecomesBonusDetail() {
        importFixture(US_MAG);

        Score burkhart = scoreRepository.findAll().stream()
                .filter(s -> s.getParticipant().getAthlete().getSurname().equals("Burkhart")
                        && s.getApparatus() == Apparatus.VT && s.getCompetition().getPart() == 1)
                .findFirst().orElseThrow();
        assertEquals(0.217, burkhart.getRoutine().getBonus());
        List<BonusDetail> details = burkhart.getRoutine().getBonusDetail();
        assertEquals("Difficulty bonus", details.get(0).getDescription());
        assertEquals(0.217, details.get(0).getBonus());
        assertEquals("Execution bonus", details.get(1).getDescription());
    }

    @Test
    void testImport_AlreadyImportedWithoutReplace_Fails() {
        importFixture(WORLDS_WAG);

        ImportException e = assertThrows(ImportException.class, () -> importFixture(WORLDS_WAG));
        assertTrue(e.getMessage().contains("already imported"), e.getMessage());
    }

    @Test
    void testImport_ReplaceReimportsWithoutDuplicates() {
        importFixture(WORLDS_WAG);
        long scores = scoreRepository.count();
        long participants = participantRepository.count();
        long competitions = competitionRepository.count();
        long rankings = rankingRepository.count();
        long teams = teamRepository.count();
        long links = teamResultScoreRepository.count();

        eventImporter.importManifest(fixture(WORLDS_WAG), true);

        assertEquals(scores, scoreRepository.count());
        assertEquals(participants, participantRepository.count());
        assertEquals(competitions, competitionRepository.count());
        assertEquals(rankings, rankingRepository.count());
        assertEquals(teams, teamRepository.count());
        assertEquals(links, teamResultScoreRepository.count());
    }

    @Test
    void testImport_ReplaceKeepsTheOtherDisciplineSharingTheEvent() {
        importFixture(WORLDS_MAG);
        long magScores = scoreRepository.count();
        importFixture(WORLDS_WAG);

        eventImporter.importManifest(fixture(WORLDS_WAG), true);

        assertEquals(magScores, scoreRepository.findAll().stream()
                .filter(s -> s.getCompetition().getDiscipline() == Discipline.MAG).count());
    }

    @Test
    void testImport_TeamTotalThatDoesNotAddUp_WarnsAndLeavesScoresCounting(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        Path teamSummary = dir.resolve("2026-WORLD-CHAMPIONSHIPS-WAG-SR-RANKING-QUAL-TEAM.csv");
        Files.writeString(teamSummary, Files.readString(teamSummary).replace(",43.966,", ",43.000,"));

        ImportReport report = eventImporter.importManifest(manifest, false);

        // The changed apparatus total also no longer adds up to the team total
        assertEquals(2, report.getWarnings().size(), report.getWarnings().toString());
        assertTrue(report.getWarnings().get(0).contains("CHN team: no group of its athletes adds up"),
                report.getWarnings().get(0));
        assertTrue(report.getWarnings().get(0).contains("BB 43.0"), report.getWarnings().get(0));
        assertTrue(report.getWarnings().get(1).contains("CHN team total 164.996 differs"), report.getWarnings().get(1));
        assertEquals(TeamScoreRole.COUNTING, teamRole(score("Zhang", "Yihan", CompetitionType.C1, Apparatus.BB)));
    }

    @Test
    void testImport_TeamPenalty_StoredAndCountedInTheTotal(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        Path teamSummary = dir.resolve("2026-WORLD-CHAMPIONSHIPS-WAG-SR-RANKING-QUAL-TEAM.csv");
        Files.writeString(teamSummary, Files.readString(teamSummary).replace(",,164.996,", ",-1.000,163.996,"));

        ImportReport report = eventImporter.importManifest(manifest, false);

        assertEquals(List.of(), report.getWarnings());
        TeamResult china = teamResult(competition(competitionRepository.findAll(), CompetitionType.C1, null), "CHN").orElseThrow();
        assertEquals(-1.0, china.getSjPenalty());
        assertEquals(163.996, china.getTotalScore());
    }

    @Test
    void testImport_TeamTotalNotItsApparatusTotalsAndPenalty_Warns(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        Path teamSummary = dir.resolve("2026-WORLD-CHAMPIONSHIPS-WAG-SR-RANKING-QUAL-TEAM.csv");
        Files.writeString(teamSummary, Files.readString(teamSummary).replace(",,164.996,", ",,163.996,"));

        ImportReport report = eventImporter.importManifest(manifest, false);

        assertEquals(1, report.getWarnings().size());
        assertTrue(report.getWarnings().get(0).contains("CHN team total 163.996 differs from its apparatus totals "
                + "and penalty, 164.996"), report.getWarnings().get(0));
    }

    @Test
    void testImport_AllAroundPenalty_CountedInTheTotal(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        Path summary = dir.resolve("2026-WORLD-CHAMPIONSHIPS-WAG-SR-RANKING-FINAL-AA.csv");
        Files.writeString(summary, Files.readString(summary).replace(",14.033,,55.032", ",14.033,-0.300,54.732"));

        ImportReport report = eventImporter.importManifest(manifest, false);

        assertEquals(List.of(), report.getWarnings());
        AllAroundResult ke = allAroundResults(competition(competitionRepository.findAll(), CompetitionType.C2, null)).stream()
                .filter(result -> result.getParticipant().getAthlete().getSurname().equals("Ke"))
                .findFirst().orElseThrow();
        assertEquals(-0.3, ke.getSjPenalty());
    }

    @Test
    void testImport_DifficultyInquiryAndNocPrintedOnlyOnFirstRow(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "!5.5", "101");

        eventImporter.importManifest(manifest, false);

        Score score = scoreRepository.findAll().get(0);
        assertTrue(score.getRoutine().getDifficultyInquiry());
        assertEquals(5.5, score.getRoutine().getDifficulty());
        assertTrue(participantRepository.findAll().stream().allMatch(p -> p.getNoc().equals("NED")));
    }

    @Test
    void testImport_TitlesDecidedInCompetitionI_AreItsFinalRankings() {
        // As at the 2026 Asian Championships and South American Games: team and all-around titles decided in
        // Competition I, published as finals; only the apparatus have finals of their own
        ImportReport report = importFixture(ASIAN_WAG);

        assertEquals(List.of(), report.getWarnings());
        List<Competition> competitions = competitionRepository.findAll();
        assertEquals(List.of(CompetitionType.C1, CompetitionType.C3),
                competitions.stream().map(Competition::getType).distinct().sorted().toList());
        Competition c1 = competition(competitions, CompetitionType.C1, null);
        List<Ranking> rankings = rankingRepository.findByCompetition(c1);
        assertTrue(rankings.stream().anyMatch(r -> r.getType() == RankingType.AA
                && r.getPurpose() == RankingPurpose.FINAL));
        assertTrue(rankings.stream().anyMatch(r -> r.getType() == RankingType.TEAM
                && r.getPurpose() == RankingPurpose.FINAL));
        assertTrue(rankings.stream().noneMatch(r -> r.getType() != RankingType.APPARATUS
                && r.getPurpose() == RankingPurpose.QUALIFYING));
        assertEquals(9, allAround("Yeap", RankingPurpose.FINAL).getRank());
        assertEquals(RankStatus.RANKED, allAround("Yeap", RankingPurpose.FINAL).getRankStatus());
        // Third of her country, left out of the final's places
        assertNull(allAround("Seow", RankingPurpose.FINAL).getRank());
        assertEquals(RankStatus.NOC_LIMIT, allAround("Seow", RankingPurpose.FINAL).getRankStatus());
        TeamResult china = teamResultRepository.findByCompetitionAndNoc(c1, "CHN").stream()
                .filter(result -> result.getRanking().getPurpose() == RankingPurpose.FINAL).findFirst().orElseThrow();
        assertEquals(1, china.getRank());
        assertEquals(168.498, china.getTotalScore());
    }

    @Test
    void testImport_FinalsRankingTheQualificationsRoutines_TotalsCheckedAgainstThem(@TempDir Path dir)
            throws IOException {
        Path manifest = copyFixture(ASIAN_WAG, dir);
        Path summary = dir.resolve("2026-ASIAN-CHAMPIONSHIPS-WAG-SR-RANKING-FINAL-AA.csv");
        Files.writeString(summary, Files.readString(summary).replace(",56.299\n", ",56.300\n"));

        ImportReport report = eventImporter.importManifest(manifest, false);

        assertEquals(1, report.getWarnings().size(), report.getWarnings().toString());
        assertTrue(report.getWarnings().get(0).contains("bib 502 C1 all-around total 56.3 differs from the sum of "
                + "its scores, 56.299"), report.getWarnings().get(0));
    }

    @Test
    void testImport_FinalsRankingARoundWithNoScores_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(ASIAN_WAG, dir);
        Path summary = dir.resolve("2026-ASIAN-CHAMPIONSHIPS-WAG-SR-RANKING-FINAL-AA.csv");
        Files.writeString(summary, Files.readString(summary).replace(",C1,,FINAL,", ",C4,,FINAL,"));

        ImportException e = assertThrows(ImportException.class, () -> eventImporter.importManifest(manifest, false));
        assertTrue(e.getMessage().contains("no scores were imported for the C4 competition this row ranks"),
                e.getMessage());
    }

    @Test
    void testImport_FinalsRankingTheQualificationsRoutines_ReplaceReimports() {
        importFixture(ASIAN_WAG);
        long competitions = competitionRepository.count();

        eventImporter.importManifest(fixture(ASIAN_WAG), true);
        competitionRepository.flush();

        assertEquals(competitions, competitionRepository.count());
    }

    @Test
    void testImport_ScoreForUnknownBib_Fails(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "999");

        ImportException e = assertThrows(ImportException.class, () -> eventImporter.importManifest(manifest, false));
        assertTrue(e.getMessage().contains("MINI-MAG-SR-SCORES-C1-FX.csv line 2: bib 999"), e.getMessage());
    }

    /** Adds an Entry Status column, blank for every entry, and an entry with the given status and no results. */
    private static void addEntryStatus(Path dir, String status) throws IOException {
        Path participants = dir.resolve("2026-WORLD-CHAMPIONSHIPS-WAG-SR-PARTICIPANTS.csv");
        List<String> lines = Files.readAllLines(participants);
        List<String> withStatus = new ArrayList<>();
        withStatus.add(lines.get(0) + ",Entry Status");
        lines.stream().skip(1).map(line -> line + ",").forEach(withStatus::add);
        withStatus.add("54th Artistic Gymnastics World Championships,WAG,SR,2026-10-17,999,ALG,999,,"
                + "SPARE Ana,SPARE,Ana,2008,," + status);
        Files.write(participants, withStatus);
    }

    private Participant participant(String bib) {
        return participantRepository.findAll().stream().filter(p -> bib.equals(p.getBibNumber())).findFirst()
                .orElseThrow();
    }

    @Test
    void testImport_StoresTheEventFormat_ReplacedOnImportingAgain() {
        importFixture(ASIAN_WAG);
        eventImporter.importManifest(fixture(ASIAN_WAG), true);

        List<EventFormat> formats = eventFormatRepository.findAll();
        assertEquals(1, formats.size());
        assertEquals(List.of(TitleFormat.C1, TitleFormat.C1, TitleFormat.FINAL), List.of(
                formats.get(0).getTeamFormat(), formats.get(0).getAllAroundFormat(),
                formats.get(0).getApparatusFormat()));
    }

    @Test
    void testImport_FormatMissing_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        replaceIn(manifest, ",\n        \"apparatusFormat\" : \"FINAL\"", "");

        assertImportFails(manifest, "event apparatusFormat 'null' is missing or not recognised");
    }

    @Test
    void testImport_FinalRankingOfAnotherCompetitionThanTheFormatSays_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        replaceIn(manifest, "\"teamFormat\" : \"FINAL\"", "\"teamFormat\" : \"C1\"");

        assertImportFails(manifest, "the TEAM FINAL ranking ranks [C4], but with the team format C1 it ranks C1");
    }

    @Test
    void testImport_TitleDecidedInCompetitionIRankedAsQualifying_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(ASIAN_WAG, dir);
        Path ranking = dir.resolve("2026-ASIAN-CHAMPIONSHIPS-WAG-SR-RANKING-FINAL-AA.csv");
        Files.move(ranking, ranking.resolveSibling("2026-ASIAN-CHAMPIONSHIPS-WAG-SR-RANKING-QUAL-AA.csv"));
        replaceIn(ranking.resolveSibling("2026-ASIAN-CHAMPIONSHIPS-WAG-SR-RANKING-QUAL-AA.csv"), ",FINAL,",
                ",QUALIFYING,");
        replaceIn(manifest, "RANKING-FINAL-AA", "RANKING-QUAL-AA");

        assertImportFails(manifest, "the AA QUALIFYING ranking qualifies for a C2, but the all-around format is C1");
    }

    @Test
    void testImport_HeldTitleWithoutAFinalRanking_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        replaceIn(manifest, "\"2026-WORLD-CHAMPIONSHIPS-WAG-SR-RANKING-FINAL-AA.csv\",", "");

        assertImportFails(manifest, "the all-around format is FINAL, but there is no AA FINAL ranking of a C2 "
                + "competition");
    }

    @Test
    void testImport_FinalHeldForATitleNotDecidedInOne_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        replaceIn(manifest, "\"aaFormat\" : \"FINAL\"", "\"aaFormat\" : \"NONE\"");
        replaceIn(manifest, "\"2026-WORLD-CHAMPIONSHIPS-WAG-SR-RANKING-FINAL-AA.csv\",", "");
        replaceIn(manifest, "\"2026-WORLD-CHAMPIONSHIPS-WAG-SR-RANKING-QUAL-AA.csv\",", "");

        assertImportFails(manifest, "there is a C2 competition, but the all-around format is NONE");
    }

    @Test
    void testImport_BlankRankWithoutRankStatus_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(OCEANIA_MAG, dir);
        replaceIn(dir.resolve("2026-OCEANIA-CHAMPIONSHIPS-MAG-SR-RANKING-FINAL-AA.csv"), ",INCOMPLETE,", ",,");

        assertImportFails(manifest, "'Rank Status' is required where 'Rank' is blank");
    }

    @Test
    void testImport_RankStatusWithARank_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(ASIAN_WAG, dir);
        replaceIn(dir.resolve("2026-ASIAN-CHAMPIONSHIPS-WAG-SR-RANKING-FINAL-AA.csv"), ",FINAL,1,,",
                ",FINAL,1,UNPLACED,");

        assertImportFails(manifest, "Rank Status UNPLACED is given with rank 1");
    }

    @Test
    void testImport_PurposeNotTheFiles_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(WORLDS_WAG, dir);
        replaceIn(dir.resolve("2026-WORLD-CHAMPIONSHIPS-WAG-SR-RANKING-QUAL-TEAM.csv"), ",QUALIFYING,", ",FINAL,");

        assertImportFails(manifest, "Purpose FINAL should be QUALIFYING in a RANKING-QUAL-TEAM.csv");
    }

    @Test
    void testImport_ApparatusTitlesDecidedInCompetitionI_ItsPlacingsAreFinal(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");

        eventImporter.importManifest(manifest, false);

        List<Ranking> rankings = rankingRepository.findAll();
        assertEquals(1, rankings.size());
        assertEquals(RankingType.APPARATUS, rankings.get(0).getType());
        assertEquals(RankingPurpose.FINAL, rankings.get(0).getPurpose());
        assertEquals(1, rank(scoreRepository.findAll().get(0)));
    }

    @Test
    void testImport_QualificationMarkersWhereNoApparatusFinalFollows_Fails(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");
        Path scores = dir.resolve("MINI-MAG-SR-SCORES-C1-FX.csv");
        replaceIn(scores, ",Total\n", ",Total,Qualification\n");
        replaceIn(scores, ",14.000\n", ",14.000,Q\n");

        assertImportFails(manifest, "MINI-MAG-SR-SCORES-C1-FX.csv line 2: 'Qualification' or 'Qualification Rank' "
                + "is filled, but this competition qualifies no one to an apparatus final (apparatus format C1)");
    }

    @Test
    void testImport_OldRoundCode_Fails(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");
        replaceIn(dir.resolve("MINI-MAG-SR-SCORES-C1-FX.csv"), ",C1,,FX,", ",QUAL,,FX,");

        assertImportFails(manifest, "unrecognised Competition 'QUAL'");
    }

    @Test
    void testImport_OldRoundColumn_Fails(@TempDir Path dir) throws IOException {
        Path manifest = writeMinimalMeet(dir, "5.5", "101");
        replaceIn(dir.resolve("MINI-MAG-SR-SCORES-C1-FX.csv"), ",Competition,", ",Round,");

        assertImportFails(manifest, "'Competition' is required");
    }

    @Test
    void testImport_OldSummaryFileName_Fails(@TempDir Path dir) throws IOException {
        Path manifest = copyFixture(ASIAN_WAG, dir);
        Path ranking = dir.resolve("2026-ASIAN-CHAMPIONSHIPS-WAG-SR-RANKING-FINAL-TEAM.csv");
        Files.move(ranking, ranking.resolveSibling("2026-ASIAN-CHAMPIONSHIPS-WAG-SR-SUMMARY-FINAL-TEAM.csv"));
        replaceIn(manifest, "RANKING-FINAL-TEAM", "SUMMARY-FINAL-TEAM");

        assertImportFails(manifest, "a ranking file's name has RANKING-QUAL- or RANKING-FINAL-");
    }

    private void assertImportFails(Path manifest, String message) {
        ImportException e = assertThrows(ImportException.class, () -> eventImporter.importManifest(manifest, false));
        assertTrue(e.getMessage().contains(message), e.getMessage());
    }

    private static void replaceIn(Path file, String from, String to) throws IOException {
        String text = Files.readString(file);
        assertTrue(text.contains(from), file.getFileName() + " has no " + from);
        Files.writeString(file, text.replace(from, to));
    }

    private ImportReport importFixture(String manifest) {
        return eventImporter.importManifest(fixture(manifest), false);
    }

    private Path fixture(String manifest) {
        try {
            return Path.of(getClass().getResource("/import/" + manifest).toURI());
        } catch (URISyntaxException e) {
            throw new IllegalStateException(e);
        }
    }

    private Path copyFixture(String manifest, Path dir) throws IOException {
        Path source = fixture(manifest);
        try (var files = Files.list(source.getParent())) {
            for (Path file : files.toList()) {
                Files.copy(file, dir.resolve(file.getFileName()));
            }
        }
        return dir.resolve(source.getFileName());
    }

    private long rowCount(String manifest, Function<ImportManifest, List<String>> files) {
        Path path = fixture(manifest);
        return files.apply(ImportManifest.read(path)).stream()
                .mapToLong(file -> CsvRow.read(path.getParent().resolve(file)).size()).sum();
    }

    private AllAroundResult allAround(String surname, RankingPurpose purpose) {
        return allAroundResultRepository.findAll().stream()
                .filter(result -> result.getParticipant().getAthlete().getSurname().equals(surname)
                        && result.getRanking().getPurpose() == purpose)
                .findFirst().orElseThrow(() -> new AssertionError("no " + purpose + " result for " + surname));
    }

    private Score score(String surname, String givenName, CompetitionType type, Apparatus apparatus) {
        return scoreRepository.findAll().stream()
                .filter(s -> s.getParticipant().getAthlete().getSurname().equals(surname)
                        && s.getParticipant().getAthlete().getGivenName().equals(givenName)
                        && s.getCompetition().getType() == type && s.getApparatus() == apparatus)
                .findFirst().orElseThrow(() -> new AssertionError("no score for " + surname + " " + givenName));
    }

    /** The score's placings in its competition's apparatus rankings. */
    private ApparatusRanks ranks(Score score) {
        return new ApparatusRanks(score.getCompetition().getType(), apparatusResultRepository.findAll().stream()
                .filter(result -> ranks(result.getRanking(), score.getCompetition()))
                .toList());
    }

    private Integer rank(Score score) {
        return ranks(score).rank(score);
    }

    private Integer qualificationRank(Score score) {
        return ranks(score).qualificationRank(score);
    }

    private QualificationResult qualification(Score score) {
        return ranks(score).qualification(score);
    }

    /** How the score figured in its team's result: counting, dropped, or no part of a team (individual). */
    private TeamScoreRole teamRole(Score score) {
        List<TeamResultScore> links = teamResultScoreRepository.findByScoreIn(List.of(score));
        if (links.isEmpty()) {
            return TeamScoreRole.INDIVIDUAL;
        }
        return links.get(0).getRole() == TeamContributionRole.COUNTING ? TeamScoreRole.COUNTING
                : TeamScoreRole.DROPPED;
    }

    private Optional<TeamResult> teamResult(Competition competition, String noc) {
        return teamResultRepository.findByCompetitionAndNoc(competition, noc).stream().findFirst();
    }

    private List<AllAroundResult> allAroundResults(Competition competition) {
        return allAroundResultRepository.findAll().stream()
                .filter(result -> ranks(result.getRanking(), competition)).toList();
    }

    private Optional<ApparatusResult> apparatusResults(Competition competition, Apparatus apparatus) {
        return apparatusResultRepository.findAll().stream()
                .filter(result -> ranks(result.getRanking(), competition)
                        && result.getRanking().getApparatus() == apparatus)
                .findFirst();
    }

    private static boolean ranks(Ranking ranking, Competition competition) {
        return ranking.getCompetitions().stream().anyMatch(c -> c.getId().equals(competition.getId()));
    }

    private static Competition competition(List<Competition> competitions, CompetitionType type, Apparatus apparatus) {
        return competitions.stream()
                .filter(c -> c.getType() == type && c.getApparatus() == apparatus)
                .findFirst()
                .orElseThrow(() -> new AssertionError("no " + type + " " + apparatus + " competition"));
    }

    private static void giveSlug(Path manifest, String slug) throws IOException {
        Files.writeString(manifest, Files.readString(manifest)
                .replace("\"title\": \"Mini Meet\"", "\"slug\": \"%s\", \"title\": \"Mini Meet\"".formatted(slug)));
    }

    // Two NED athletes, the NOC printed only on the first, and one floor score
    private static Path writeMinimalMeet(Path dir, String difficulty, String scoredBib) throws IOException {
        Files.createDirectories(dir);
        Files.writeString(dir.resolve("MINI-MAG-SR-IMPORT.json"), """
                {
                    "event": { "title": "Mini Meet", "shortName": "Mini", "disciplines": "MAG", "ageCategory": "SR",
                               "level": "INTERNATIONAL_TOURNAMENTS", "startDate": "2026-03-01",
                               "endDate": "2026-03-01", "city": "Utrecht", "country": "NED",
                               "teamFormat": "NONE", "aaFormat": "NONE", "apparatusFormat": "C1" },
                    "participants": [ "MINI-MAG-SR-PARTICIPANTS.csv" ],
                    "scores": [ "MINI-MAG-SR-SCORES-C1-FX.csv" ]
                }
                """);
        Files.writeString(dir.resolve("MINI-MAG-SR-PARTICIPANTS.csv"), """
                Event Name,Discipline,Age Category,Event Start Date,Order,NOC Code,Bib Number,FIG License,Name,Surname,Given Name,Birth Year
                Mini Meet,MAG,SR,2026-03-01,1,NED,101,,DE VRIES Jan,DE VRIES,Jan,2001
                Mini Meet,MAG,SR,2026-03-01,2,,102,,BAKKER Piet,BAKKER,Piet,2003
                """);
        Files.writeString(dir.resolve("MINI-MAG-SR-SCORES-C1-FX.csv"), """
                Event Name,Discipline,Age Category,Competition Start Date,Competition,Part,Apparatus,Rank,Bib,Name,NOC Code,Status,D,E,B,Penalty,SJ Penalty,Total
                Mini Meet,MAG,SR,2026-03-01,C1,,FX,1,%s,DE VRIES Jan,NED,COMPLETED,%s,8.500,,,,14.000
                """.formatted(scoredBib, difficulty));
        return dir.resolve("MINI-MAG-SR-IMPORT.json");
    }
}
