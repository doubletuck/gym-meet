package doubletuck.meet.service;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.exception.ConflictException;
import doubletuck.meet.repository.EventRepository;
import doubletuck.meet.repository.CompetitionRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.test.context.ActiveProfiles;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
class CompetitionServiceTest {

    @Autowired
    private CompetitionRepository competitionRepository;

    @Autowired
    private EventRepository eventRepository;

    private CompetitionService competitionService;
    private Event testEvent;

    @BeforeEach
    void setUp() {
        competitionService = new CompetitionService(competitionRepository);

        testEvent = new Event();
        testEvent.setTitle("2026 European Championships");
        testEvent.setShortName("Test");
        testEvent.setSlug("2026-european-championships");
        testEvent.setStartDate(LocalDate.of(2026, 4, 20));
        testEvent.setEndDate(LocalDate.of(2026, 4, 26));
        testEvent.setCity("Stuttgart");
        testEvent.setCountryCode("GER");
        testEvent.setLevel(EventLevel.CONTINENTAL_CHAMPIONSHIPS);
        testEvent = eventRepository.save(testEvent);
    }

    @Test
    void testCreateCompetition_Succeeds() {
        Competition competition = competitionOf(CompetitionType.C1, null, null);

        Competition saved = competitionService.createCompetition(competition);

        assertNotNull(saved.getId());
    }

    @Test
    void testCreateCompetition_DuplicateQualCompetition_ThrowsConflictException() {
        competitionService.createCompetition(competitionOf(CompetitionType.C1, null, null));

        assertThrows(ConflictException.class,
                () -> competitionService.createCompetition(competitionOf(CompetitionType.C1, null, null)));
    }

    @Test
    void testCreateCompetition_DuplicateEventCompetitionSameApparatus_ThrowsConflictException() {
        competitionService.createCompetition(competitionOf(CompetitionType.C3, Apparatus.FX, null));

        assertThrows(ConflictException.class,
                () -> competitionService.createCompetition(competitionOf(CompetitionType.C3, Apparatus.FX, null)));
    }

    @Test
    void testCreateCompetition_EventCompetitionsDifferentApparatus_BothSucceed() {
        Competition fx = competitionService.createCompetition(competitionOf(CompetitionType.C3, Apparatus.FX, null));
        Competition ph = competitionService.createCompetition(competitionOf(CompetitionType.C3, Apparatus.PH, null));

        assertNotNull(fx.getId());
        assertNotNull(ph.getId());
        assertNotEquals(fx.getId(), ph.getId());
    }

    @Test
    void testCreateCompetition_DuplicateAaCompetitionSamePart_ThrowsConflictException() {
        competitionService.createCompetition(competitionOf(CompetitionType.C2, null, 1));

        assertThrows(ConflictException.class, () -> competitionService.createCompetition(competitionOf(CompetitionType.C2, null, 1)));
    }

    @Test
    void testCreateCompetition_MultiDayAaCompetitionsDifferentPart_BothSucceed() {
        Competition day1 = competitionService.createCompetition(competitionOf(CompetitionType.C2, null, 1));
        Competition day2 = competitionService.createCompetition(competitionOf(CompetitionType.C2, null, 2));

        assertNotNull(day1.getId());
        assertNotNull(day2.getId());
        assertNotEquals(day1.getId(), day2.getId());
    }

    @Test
    void testCreateCompetition_WholeRoundCompetitionAlongsideParts_AllSucceed() {
        Competition day1 = competitionService.createCompetition(competitionOf(CompetitionType.C2, null, 1));
        Competition day2 = competitionService.createCompetition(competitionOf(CompetitionType.C2, null, 2));
        Competition wholeRound = competitionService.createCompetition(competitionOf(CompetitionType.C2, null, null));

        assertNotNull(wholeRound.getId());
        assertNotEquals(day1.getId(), wholeRound.getId());
        assertNotEquals(day2.getId(), wholeRound.getId());
        assertThrows(ConflictException.class, () -> competitionService.createCompetition(competitionOf(CompetitionType.C2, null, null)));
    }

    @Test
    void testCreateCompetition_PerApparatusQualCompetitions_AllSucceed() {
        Competition fx = competitionService.createCompetition(competitionOf(CompetitionType.C1, Apparatus.FX, null));
        Competition vt = competitionService.createCompetition(competitionOf(CompetitionType.C1, Apparatus.VT, null));

        assertNotEquals(fx.getId(), vt.getId());
        assertThrows(ConflictException.class, () -> competitionService.createCompetition(competitionOf(CompetitionType.C1, Apparatus.FX, null)));
    }

    @Test
    void testCreateCompetition_AllApparatusCompetitionAlongsidePerApparatusCompetition_BothSucceed() {
        Competition fx = competitionService.createCompetition(competitionOf(CompetitionType.C1, Apparatus.FX, null));
        Competition allApparatus = competitionService.createCompetition(competitionOf(CompetitionType.C1, null, null));

        assertNotEquals(fx.getId(), allApparatus.getId());
    }

    @Test
    void testCreateCompetition_EliminationRounds_EachSucceedsOnce() {
        Competition round1 = competitionService.createCompetition(roundOf(1));
        Competition round2 = competitionService.createCompetition(roundOf(2));

        assertNotEquals(round1.getId(), round2.getId());
        assertThrows(ConflictException.class, () -> competitionService.createCompetition(roundOf(1)));
    }

    private Competition roundOf(int round) {
        Competition competition = competitionOf(CompetitionType.C4, null, null);
        competition.setDiscipline(Discipline.MIX);
        competition.setRound(round);
        return competition;
    }

    private Competition competitionOf(CompetitionType type, Apparatus apparatus, Integer part) {
        Competition competition = new Competition();
        competition.setEvent(testEvent);
        competition.setDate(LocalDate.of(2026, 4, 21));
        competition.setType(type);
        competition.setDiscipline(Discipline.MAG);
        competition.setAgeCategory(AgeCategory.SR);
        competition.setApparatus(apparatus);
        competition.setPart(part);
        return competition;
    }
}
