package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Athlete;
import doubletuck.meet.domain.BonusDetail;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Routine;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.ScoreStatus;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import jakarta.validation.ConstraintViolationException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.ActiveProfiles;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
class ScoreRepositoryTest {

    @Autowired
    private ScoreRepository scoreRepository;

    @Autowired
    private CompetitionRepository competitionRepository;

    @Autowired
    private ParticipantRepository participantRepository;

    @Autowired
    private EventRepository eventRepository;

    @Autowired
    private AthleteRepository athleteRepository;

    private Event testEvent;
    private Competition testCompetition;
    private Participant testParticipant;
    private Score testScore;

    @BeforeEach
    void setUp() {
        testEvent = savedEvent();

        testCompetition = new Competition();
        testCompetition.setEvent(testEvent);
        testCompetition.setDate(LocalDate.of(2026, 4, 21));
        testCompetition.setType(CompetitionType.C1);
        testCompetition.setDiscipline(Discipline.WAG);
        testCompetition.setAgeCategory(AgeCategory.SR);
        testCompetition = competitionRepository.save(testCompetition);

        Athlete athlete = new Athlete();
        athlete.setDiscipline(Discipline.WAG);
        athlete.setSurname("Biles");
        athlete.setGivenName("Simone");
        athlete.setBirthYear((short) 2000);
        athlete = athleteRepository.save(athlete);

        testParticipant = new Participant();
        testParticipant.setEvent(testEvent);
        testParticipant.setAthlete(athlete);
        testParticipant.setNoc("USA");
        testParticipant = participantRepository.save(testParticipant);

        testScore = new Score();
        testScore.setParticipant(testParticipant);
        testScore.setCompetition(testCompetition);
        testScore.setApparatus(Apparatus.VT);
        Routine vault = new Routine(ScoreStatus.COMPLETED);
        vault.setDifficulty(5.0);
        vault.setExecution(9.033);
        vault.setScore(14.033);
        testScore.setRoutine(vault);
        testScore.setTotalScore(14.033);
        testScore = scoreRepository.save(testScore);
    }

    @Test
    void testSave_PersistsAllFields() {
        Optional<Score> found = scoreRepository.findById(testScore.getId());

        assertTrue(found.isPresent());
        assertEquals(testParticipant.getId(), found.get().getParticipant().getId());
        assertEquals(testCompetition.getId(), found.get().getCompetition().getId());
        assertEquals(Apparatus.VT, found.get().getApparatus());
        assertEquals(5.0, found.get().getRoutine().getDifficulty());
        assertEquals(9.033, found.get().getRoutine().getExecution());
        assertEquals(14.033, found.get().getRoutine().getScore());
        assertEquals(ScoreStatus.COMPLETED, found.get().getRoutine().getStatus());
        assertEquals(14.033, found.get().getTotalScore());
        assertFalse(found.get().getRoutine().getDifficultyInquiry());
        assertNull(found.get().getSecondRoutine());
    }

    @Test
    void testSave_PersistsDifficultyInquiry() {
        testScore.getRoutine().setDifficultyInquiry(true);
        scoreRepository.saveAndFlush(testScore);

        Score found = scoreRepository.findById(testScore.getId()).orElseThrow();

        assertTrue(found.getRoutine().getDifficultyInquiry());
    }

    @Test
    void testSave_PersistsBonusDetailAsJson() {
        Score beamScore = new Score();
        beamScore.setParticipant(testParticipant);
        beamScore.setCompetition(testCompetition);
        beamScore.setApparatus(Apparatus.BB);
        Routine beam = new Routine(ScoreStatus.COMPLETED);
        beam.addBonusDetail(new BonusDetail(0.1, "Difficulty bonus"));
        beam.addBonusDetail(new BonusDetail(0.05, "Connection bonus"));
        beamScore.setRoutine(beam);
        beamScore = scoreRepository.save(beamScore);

        Score found = scoreRepository.findById(beamScore.getId()).orElseThrow();

        assertEquals(2, found.getRoutine().getBonusDetail().size());
        assertEquals(0.1, found.getRoutine().getBonusDetail().get(0).getBonus());
        assertEquals("Difficulty bonus", found.getRoutine().getBonusDetail().get(0).getDescription());
    }

    @Test
    void testSave_TwoVaultEntryPersistsBothRoutinesAndResult() {
        scoreRepository.delete(testScore);
        scoreRepository.flush();

        Score twoVaults = new Score();
        twoVaults.setParticipant(testParticipant);
        twoVaults.setCompetition(testCompetition);
        twoVaults.setApparatus(Apparatus.VT);

        Routine first = new Routine(ScoreStatus.COMPLETED);
        first.setDifficulty(5.6);
        first.setExecution(8.533);
        first.setPenalty(-0.1);
        first.setScore(14.033);
        twoVaults.setRoutine(first);

        Routine second = new Routine(ScoreStatus.COMPLETED);
        second.setDifficulty(5.0);
        second.setExecution(9.133);
        second.setSjPenalty(-0.5);
        second.setScore(13.633);
        second.addBonusDetail(new BonusDetail(0.1, "Landing bonus"));
        twoVaults.setSecondRoutine(second);

        twoVaults.setCombinedBonus(0.2);
        twoVaults.setCombinedSjPenalty(-0.3);
        twoVaults.setTotalScore(14.033);
        twoVaults = scoreRepository.saveAndFlush(twoVaults);

        Score found = scoreRepository.findById(twoVaults.getId()).orElseThrow();

        assertEquals(14.033, found.getRoutine().getScore());
        assertEquals(-0.1, found.getRoutine().getPenalty());
        assertNull(found.getRoutine().getSjPenalty());
        assertNotNull(found.getSecondRoutine());
        assertEquals(5.0, found.getSecondRoutine().getDifficulty());
        assertEquals(-0.5, found.getSecondRoutine().getSjPenalty());
        assertEquals(13.633, found.getSecondRoutine().getScore());
        assertEquals(ScoreStatus.COMPLETED, found.getSecondRoutine().getStatus());
        assertEquals("Landing bonus", found.getSecondRoutine().getBonusDetail().get(0).getDescription());
        assertEquals(0.2, found.getCombinedBonus());
        assertEquals(-0.3, found.getCombinedSjPenalty());
    }

    @Test
    void testSave_SecondVaultNotStartedLoadsAsDnsRoutine() {
        testScore.setSecondRoutine(new Routine(ScoreStatus.DNS));
        scoreRepository.saveAndFlush(testScore);

        Score found = scoreRepository.findById(testScore.getId()).orElseThrow();

        assertNotNull(found.getSecondRoutine());
        assertEquals(ScoreStatus.DNS, found.getSecondRoutine().getStatus());
        assertNull(found.getSecondRoutine().getScore());
    }

    @Test
    void testCreate_FailsBecauseRoutineMissing() {
        Score noRoutine = new Score();
        noRoutine.setParticipant(testParticipant);
        noRoutine.setCompetition(testCompetition);
        noRoutine.setApparatus(Apparatus.BB);

        assertThrows(ConstraintViolationException.class, () -> scoreRepository.saveAndFlush(noRoutine));
    }

    @Test
    void testCreate_FailsBecauseSecondRoutineStatusMissing() {
        Routine second = new Routine();
        second.setScore(13.0);
        testScore.setSecondRoutine(second);

        assertThrows(ConstraintViolationException.class, () -> scoreRepository.saveAndFlush(testScore));
    }

    @Test
    void testFindByParticipantCompetitionAndApparatus_Found() {
        Optional<Score> found = scoreRepository.findByParticipantAndCompetitionAndApparatus(
                testParticipant, testCompetition, Apparatus.VT);

        assertTrue(found.isPresent());
        assertEquals(testScore.getId(), found.get().getId());
    }

    @Test
    void testFindByParticipantCompetitionAndApparatus_WrongApparatus_NotFound() {
        Optional<Score> found = scoreRepository.findByParticipantAndCompetitionAndApparatus(
                testParticipant, testCompetition, Apparatus.BB);

        assertTrue(found.isEmpty());
    }

    @Test
    void testFindByCompetition_ReturnsAllApparatusScoresInCompetition() {
        Score beamScore = new Score();
        beamScore.setParticipant(testParticipant);
        beamScore.setCompetition(testCompetition);
        beamScore.setApparatus(Apparatus.BB);
        beamScore.setRoutine(new Routine(ScoreStatus.COMPLETED));
        scoreRepository.save(beamScore);

        List<Score> found = scoreRepository.findByCompetition(testCompetition);

        assertEquals(2, found.size());
    }

    @Test
    void testFindByCompetitionId_MatchesFindByCompetition() {
        List<Score> found = scoreRepository.findByCompetitionId(testCompetition.getId());

        assertEquals(1, found.size());
        assertEquals(testScore.getId(), found.get(0).getId());
    }

    @Test
    void testFindByParticipant_ReturnsScoresAcrossCompetitions() {
        Competition aaFinal = new Competition();
        aaFinal.setEvent(testEvent);
        aaFinal.setDate(LocalDate.of(2026, 4, 23));
        aaFinal.setType(CompetitionType.C2);
        aaFinal.setDiscipline(Discipline.WAG);
        aaFinal.setAgeCategory(AgeCategory.SR);
        aaFinal = competitionRepository.save(aaFinal);

        Score aaVaultScore = new Score();
        aaVaultScore.setParticipant(testParticipant);
        aaVaultScore.setCompetition(aaFinal);
        aaVaultScore.setApparatus(Apparatus.VT);
        aaVaultScore.setRoutine(new Routine(ScoreStatus.COMPLETED));
        scoreRepository.save(aaVaultScore);

        List<Score> found = scoreRepository.findByParticipant(testParticipant);

        assertEquals(2, found.size());
    }

    @Test
    void testCreate_FailsBecauseDuplicateParticipantCompetitionAndApparatus() {
        Score duplicate = new Score();
        duplicate.setParticipant(testParticipant);
        duplicate.setCompetition(testCompetition);
        duplicate.setApparatus(Apparatus.VT);
        duplicate.setRoutine(new Routine(ScoreStatus.COMPLETED));

        assertThrows(DataIntegrityViolationException.class, () -> scoreRepository.saveAndFlush(duplicate));
    }

    private Event savedEvent() {
        Event event = new Event();
        event.setTitle("2026 European Championships");
        event.setShortName("Test");
        event.setSlug("2026-european-championships");
        event.setStartDate(LocalDate.of(2026, 4, 20));
        event.setEndDate(LocalDate.of(2026, 4, 26));
        event.setCity("Stuttgart");
        event.setCountryCode("GER");
        event.setLevel(EventLevel.CONTINENTAL_CHAMPIONSHIPS);
        return eventRepository.save(event);
    }
}
