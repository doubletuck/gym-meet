package doubletuck.meet.importer;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Judge;
import doubletuck.meet.domain.JudgeFunction;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.TeamContributionRole;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.domain.TeamResultScore;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.repository.EventRepository;
import doubletuck.meet.repository.JudgeRepository;
import doubletuck.meet.repository.RankingRepository;
import doubletuck.meet.repository.TeamResultRepository;
import doubletuck.meet.repository.TeamResultScoreRepository;
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
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.*;

/**
 * The 2026 Youth Olympic Games' mixed team (competition-models.md §8), from the real files cut down to
 * three NOCs: a ranking over the MAG and WAG Competition I, elimination rounds, gymnasts entered by the
 * MAG and WAG manifests, and a men's and a women's floor.
 */
@DataJpaTest
@ActiveProfiles("test")
@Import({ EventImporter.class, ParticipantImporter.class, ScoreImporter.class, RankingImporter.class, FormatChecker.class,
        JudgeImporter.class, ResultReconciler.class, AthleteMatcher.class, CompetitionService.class, ImportLog.class })
class MixedTeamImportTest {

    private static final String MAG = "2026-YOUTH-OLYMPIC-GAMES-MAG-JR-IMPORT.json";
    private static final String WAG = "2026-YOUTH-OLYMPIC-GAMES-WAG-JR-IMPORT.json";
    private static final String MIX = "2026-YOUTH-OLYMPIC-GAMES-MIX-JR-IMPORT.json";

    @Autowired
    private EventImporter eventImporter;

    @Autowired
    private ImportLog importLog;

    @Autowired
    private EventRepository eventRepository;

    @Autowired
    private CompetitionRepository competitionRepository;

    @Autowired
    private RankingRepository rankingRepository;

    @Autowired
    private TeamResultRepository teamResultRepository;

    @Autowired
    private TeamResultScoreRepository teamResultScoreRepository;

    @Autowired
    private JudgeRepository judgeRepository;

    @Test
    void testImport_OneEventWithThreeDivisions_SpanningTheirDays() {
        for (String manifest : List.of(MAG, WAG, MIX)) {
            assertEquals(List.of(), eventImporter.importManifest(fixture(manifest), false).getWarnings(), manifest);
        }

        Event event = eventRepository.findBySlug("2026-youth-olympic-games").orElseThrow();
        assertEquals(1, eventRepository.count());
        assertEquals(LocalDate.of(2026, 11, 7), event.getStartDate());
        assertEquals(LocalDate.of(2026, 11, 11), event.getEndDate());
    }

    @Test
    void testImport_QualificationRanksTheMenAndWomensCompetitionI_LinkingOnlyCountingScores() {
        importAll();
        Ranking qualification = mixedRanking(RankingPurpose.QUALIFYING, CompetitionType.C1);

        assertEquals(Set.of(Discipline.MAG, Discipline.WAG), qualification.getCompetitions().stream()
                .map(Competition::getDiscipline).collect(Collectors.toSet()));
        TeamResult china = teamResult(qualification, "CHN");
        assertEquals(81.898, china.getTotalScore());
        assertEquals(1, china.getRank());
        // The best score on each of the men's floor, parallel bars and high bar and the women's bars, beam and
        // floor: YANG on all three men's, XIE, ZHONG and CHEN once each. LI and ZHAO, entered but not counting,
        // aren't members
        assertEquals(List.of("113 FX", "113 HB", "113 PB", "211 FX", "212 UB", "213 BB"), links(china));
        assertTrue(teamResultScoreRepository.findByTeamResultIn(List.of(china)).stream()
                .allMatch(link -> link.getRole() == TeamContributionRole.COUNTING));
    }

    @Test
    void testImport_QualificationTieForTheBestScore_BothCount() {
        importAll();

        // CSUKA and MIHAI both scored 12.366 on floor, GER's men's floor total
        TeamResult germany = teamResult(mixedRanking(RankingPurpose.QUALIFYING, CompetitionType.C1), "GER");
        assertTrue(links(germany).containsAll(List.of("130 FX", "132 FX")), links(germany).toString());
    }

    @Test
    void testImport_FinalRounds_EachACompetitionWithItsPairsRoutines() {
        importAll();
        List<Competition> rounds = competitionRepository.findAll().stream()
                .filter(competition -> competition.getDiscipline() == Discipline.MIX)
                .sorted(Comparator.comparing(Competition::getRound))
                .toList();

        assertEquals(List.of(1, 2, 3), rounds.stream().map(Competition::getRound).toList());
        assertTrue(rounds.stream().allMatch(competition -> competition.getType() == CompetitionType.C4
                && competition.getDate().equals(LocalDate.of(2026, 11, 11))));
        assertEquals(RankingPurpose.QUALIFYING, rankingOf(rounds.get(0)).getPurpose());
        assertEquals(RankingPurpose.QUALIFYING, rankingOf(rounds.get(1)).getPurpose());
        TeamResult gold = teamResult(rankingOf(rounds.get(2)), "CHN");
        assertEquals(RankingPurpose.FINAL, gold.getRanking().getPurpose());
        assertEquals(1, gold.getRank());
        assertEquals(27.832, gold.getTotalScore());
        // YANG's men's floor and CHEN's women's beam
        assertEquals(List.of("113 FX", "211 BB"), links(gold));
    }

    @Test
    void testImport_OneJudgesSheetServesEveryRound_PanelsByDiscipline() {
        importAll();
        List<Judge> judges = judgeRepository.findAll().stream()
                .filter(judge -> judge.getCompetition().getDiscipline() == Discipline.MIX).toList();

        assertEquals(Set.of(1, 2, 3), judges.stream().map(judge -> judge.getCompetition().getRound())
                .collect(Collectors.toSet()));
        // The same official on the men's and the women's floor panel
        List<Judge> lineJudge = judges.stream()
                .filter(judge -> judge.getSurname().equals("Ahmed") && judge.getGivenName().equals("Gasser")
                        && judge.getCompetition().getRound() == 1)
                .toList();
        assertEquals(Set.of(Discipline.MAG, Discipline.WAG), lineJudge.stream().map(Judge::getDiscipline)
                .collect(Collectors.toSet()));
        assertTrue(lineJudge.stream().allMatch(judge -> judge.getFunction() == JudgeFunction.L1));
        assertTrue(judgeRepository.findAll().stream()
                .filter(judge -> judge.getCompetition().getDiscipline() != Discipline.MIX)
                .allMatch(judge -> judge.getDiscipline() == null));
    }

    @Test
    void testImport_BeforeTheMenAndWomen_Fails() {
        eventImporter.importManifest(fixture(MAG), false);

        ImportException e = assertThrows(ImportException.class, () -> eventImporter.importManifest(fixture(MIX), false));
        assertTrue(e.getMessage().contains("import the MAG and WAG manifests first"), e.getMessage());
    }

    @Test
    void testImport_GymnastInTheOtherDisciplinesFile_Fails(@TempDir Path dir) throws IOException {
        copyFixtures(dir);
        Path file = dir.resolve("2026-YOUTH-OLYMPIC-GAMES-MIX-JR-SCORES-C4-MAG-FX.csv");
        Files.writeString(file, Files.readString(file).replace(",113,YANG Lanbin,", ",211,CHEN Ziyan,"));
        eventImporter.importManifest(dir.resolve(MAG), false);
        eventImporter.importManifest(dir.resolve(WAG), false);

        ImportException e = assertThrows(ImportException.class,
                () -> eventImporter.importManifest(dir.resolve(MIX), false));
        assertTrue(e.getMessage().contains("bib 211 is a WAG gymnast in a MAG file"), e.getMessage());
    }

    @Test
    void testImport_ReplacingTheWomen_RemovesTheMixedTeamToImportAgain() {
        importAll();

        ImportReport report = eventImporter.importManifest(fixture(WAG), true);

        assertTrue(report.getWarnings().stream().anyMatch(warning -> warning.contains("mixed team")),
                report.getWarnings().toString());
        assertTrue(competitionRepository.findAll().stream()
                .noneMatch(competition -> competition.getDiscipline() == Discipline.MIX));
        assertTrue(rankingRepository.findAll().stream()
                .noneMatch(ranking -> ranking.getDiscipline() == Discipline.MIX));
        assertEquals(ImportLog.State.REMOVED, importLog.status(fixture(MIX)).state());

        eventImporter.importManifest(fixture(MIX), false);
        assertEquals(ImportLog.State.UP_TO_DATE, importLog.status(fixture(MIX)).state());
        assertEquals(AgeCategory.JR, mixedRanking(RankingPurpose.QUALIFYING, CompetitionType.C1).getAgeCategory());
    }

    private void importAll() {
        for (String manifest : List.of(MAG, WAG, MIX)) {
            eventImporter.importManifest(fixture(manifest), false);
        }
    }

    private Ranking mixedRanking(RankingPurpose purpose, CompetitionType type) {
        return rankingRepository.findAll().stream()
                .filter(ranking -> ranking.getDiscipline() == Discipline.MIX && ranking.getPurpose() == purpose
                        && ranking.getCompetitions().stream().allMatch(competition -> competition.getType() == type))
                .findFirst()
                .orElseThrow();
    }

    private Ranking rankingOf(Competition competition) {
        return rankingRepository.findByCompetition(competition).getFirst();
    }

    private TeamResult teamResult(Ranking ranking, String noc) {
        return teamResultRepository.findByRanking(ranking).stream()
                .filter(result -> result.getTeam().getNoc().equals(noc))
                .findFirst()
                .orElseThrow();
    }

    /** The team result's linked scores, as "bib apparatus", in order. */
    private List<String> links(TeamResult result) {
        return teamResultScoreRepository.findByTeamResultIn(List.of(result)).stream()
                .map(TeamResultScore::getScore)
                .map(score -> score.getParticipant().getBibNumber() + " " + score.getApparatus())
                .sorted()
                .toList();
    }

    private Path fixture(String manifest) {
        try {
            return Path.of(getClass().getResource("/import/yog/" + manifest).toURI());
        } catch (URISyntaxException e) {
            throw new IllegalStateException(e);
        }
    }

    private void copyFixtures(Path dir) throws IOException {
        try (var files = Files.list(fixture(MAG).getParent())) {
            for (Path file : files.toList()) {
                Files.copy(file, dir.resolve(file.getFileName()));
            }
        }
    }
}
