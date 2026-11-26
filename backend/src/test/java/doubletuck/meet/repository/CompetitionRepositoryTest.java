package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
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
class CompetitionRepositoryTest {

    @Autowired
    private CompetitionRepository competitionRepository;

    @Autowired
    private EventRepository eventRepository;

    private Event testEvent;
    private Competition testCompetition;

    @BeforeEach
    void setUp() {
        testEvent = savedEvent("2026 European Championships");

        testCompetition = new Competition();
        testCompetition.setEvent(testEvent);
        testCompetition.setDate(LocalDate.of(2026, 4, 21));
        testCompetition.setType(CompetitionType.C1);
        testCompetition.setDiscipline(Discipline.WAG);
        testCompetition.setAgeCategory(AgeCategory.SR);
        testCompetition = competitionRepository.save(testCompetition);
    }

    @Test
    void testSave_PersistsAllFields() {
        Optional<Competition> found = competitionRepository.findById(testCompetition.getId());

        assertTrue(found.isPresent());
        assertEquals(testEvent.getId(), found.get().getEvent().getId());
        assertEquals(LocalDate.of(2026, 4, 21), found.get().getDate());
        assertEquals(CompetitionType.C1, found.get().getType());
        assertEquals(Discipline.WAG, found.get().getDiscipline());
        assertEquals(AgeCategory.SR, found.get().getAgeCategory());
        assertNull(found.get().getPart());
    }

    @Test
    void testFindByEventRoundDisciplineAndAgeCategory_Found() {
        Optional<Competition> found = competitionRepository.findByEventAndTypeAndDisciplineAndAgeCategoryAndApparatusAndRoundAndPart(
                testEvent, CompetitionType.C1, Discipline.WAG, AgeCategory.SR, null, null, null);

        assertTrue(found.isPresent());
        assertEquals(testCompetition.getId(), found.get().getId());
    }

    @Test
    void testFindByEventRoundDisciplineAndAgeCategory_WrongRound_NotFound() {
        Optional<Competition> found = competitionRepository.findByEventAndTypeAndDisciplineAndAgeCategoryAndApparatusAndRoundAndPart(
                testEvent, CompetitionType.C2, Discipline.WAG, AgeCategory.SR, null, null, null);

        assertTrue(found.isEmpty());
    }

    @Test
    void testFindByEventRoundDisciplineAndAgeCategory_WrongDiscipline_NotFound() {
        Optional<Competition> found = competitionRepository.findByEventAndTypeAndDisciplineAndAgeCategoryAndApparatusAndRoundAndPart(
                testEvent, CompetitionType.C1, Discipline.MAG, AgeCategory.SR, null, null, null);

        assertTrue(found.isEmpty());
    }

    @Test
    void testFindByEventRoundDisciplineAndAgeCategory_WrongAgeCategory_NotFound() {
        Optional<Competition> found = competitionRepository.findByEventAndTypeAndDisciplineAndAgeCategoryAndApparatusAndRoundAndPart(
                testEvent, CompetitionType.C1, Discipline.WAG, AgeCategory.JR, null, null, null);

        assertTrue(found.isEmpty());
    }

    @Test
    void testFindByEventRoundDisciplineAndAgeCategory_WrongPart_NotFound() {
        Optional<Competition> found = competitionRepository.findByEventAndTypeAndDisciplineAndAgeCategoryAndApparatusAndRoundAndPart(
                testEvent, CompetitionType.C1, Discipline.WAG, AgeCategory.SR, null, null, 1);

        assertTrue(found.isEmpty());
    }

    @Test
    void testFindByEventRoundDisciplineAndAgeCategoryAndPart_DistinguishesMultiDayParts() {
        Competition aaDay1 = new Competition();
        aaDay1.setEvent(testEvent);
        aaDay1.setDate(LocalDate.of(2026, 8, 15));
        aaDay1.setType(CompetitionType.C2);
        aaDay1.setDiscipline(Discipline.WAG);
        aaDay1.setAgeCategory(AgeCategory.SR);
        aaDay1.setPart(1);
        aaDay1 = competitionRepository.save(aaDay1);

        Competition aaDay2 = new Competition();
        aaDay2.setEvent(testEvent);
        aaDay2.setDate(LocalDate.of(2026, 8, 16));
        aaDay2.setType(CompetitionType.C2);
        aaDay2.setDiscipline(Discipline.WAG);
        aaDay2.setAgeCategory(AgeCategory.SR);
        aaDay2.setPart(2);
        aaDay2 = competitionRepository.save(aaDay2);

        Optional<Competition> foundDay1 = competitionRepository.findByEventAndTypeAndDisciplineAndAgeCategoryAndApparatusAndRoundAndPart(
                testEvent, CompetitionType.C2, Discipline.WAG, AgeCategory.SR, null, null, 1);
        Optional<Competition> foundDay2 = competitionRepository.findByEventAndTypeAndDisciplineAndAgeCategoryAndApparatusAndRoundAndPart(
                testEvent, CompetitionType.C2, Discipline.WAG, AgeCategory.SR, null, null, 2);

        assertTrue(foundDay1.isPresent());
        assertEquals(aaDay1.getId(), foundDay1.get().getId());
        assertTrue(foundDay2.isPresent());
        assertEquals(aaDay2.getId(), foundDay2.get().getId());
        assertNotEquals(foundDay1.get().getId(), foundDay2.get().getId());
    }

    @Test
    void testFindByEvent_ReturnsAllCompetitionsForEvent() {
        Competition teamFinal = new Competition();
        teamFinal.setEvent(testEvent);
        teamFinal.setDate(LocalDate.of(2026, 4, 22));
        teamFinal.setType(CompetitionType.C4);
        teamFinal.setDiscipline(Discipline.WAG);
        teamFinal.setAgeCategory(AgeCategory.SR);
        competitionRepository.save(teamFinal);

        List<Competition> found = competitionRepository.findByEvent(testEvent);

        assertEquals(2, found.size());
    }

    @Test
    void testFindByEventId_MatchesFindByEvent() {
        List<Competition> found = competitionRepository.findByEventId(testEvent.getId());

        assertEquals(1, found.size());
        assertEquals(testCompetition.getId(), found.get(0).getId());
    }

    @Test
    void testFindByEvent_DoesNotReturnOtherEventsCompetitions() {
        Event otherEvent = savedEvent("2026 Mediterranean Games");
        Competition otherCompetition = new Competition();
        otherCompetition.setEvent(otherEvent);
        otherCompetition.setDate(LocalDate.of(2026, 6, 1));
        otherCompetition.setType(CompetitionType.C1);
        otherCompetition.setDiscipline(Discipline.WAG);
        otherCompetition.setAgeCategory(AgeCategory.SR);
        competitionRepository.save(otherCompetition);

        List<Competition> found = competitionRepository.findByEvent(testEvent);

        assertEquals(1, found.size());
        assertEquals(testCompetition.getId(), found.get(0).getId());
    }

    /**
     * uk_competition is UNIQUE NULLS NOT DISTINCT, so a null apparatus, round or part
     * counts as equal to another null and these duplicates are rejected by
     * the database itself.
     */
    @Test
    void testCreate_DuplicateQualCompetition_CaughtByDatabaseConstraint() {
        Competition duplicate = new Competition();
        duplicate.setEvent(testEvent);
        duplicate.setDate(LocalDate.of(2026, 4, 21));
        duplicate.setType(CompetitionType.C1);
        duplicate.setDiscipline(Discipline.WAG);
        duplicate.setAgeCategory(AgeCategory.SR);

        assertThrows(DataIntegrityViolationException.class, () -> competitionRepository.saveAndFlush(duplicate));
    }

    @Test
    void testCreate_DuplicateEventCompetitionSameApparatus_CaughtByDatabaseConstraint() {
        Competition fxFinal = new Competition();
        fxFinal.setEvent(testEvent);
        fxFinal.setDate(LocalDate.of(2026, 4, 22));
        fxFinal.setType(CompetitionType.C3);
        fxFinal.setDiscipline(Discipline.WAG);
        fxFinal.setAgeCategory(AgeCategory.SR);
        fxFinal.setApparatus(Apparatus.FX);
        competitionRepository.saveAndFlush(fxFinal);

        Competition duplicate = new Competition();
        duplicate.setEvent(testEvent);
        duplicate.setDate(LocalDate.of(2026, 4, 22));
        duplicate.setType(CompetitionType.C3);
        duplicate.setDiscipline(Discipline.WAG);
        duplicate.setAgeCategory(AgeCategory.SR);
        duplicate.setApparatus(Apparatus.FX);

        assertThrows(DataIntegrityViolationException.class, () -> competitionRepository.saveAndFlush(duplicate));
    }

    @Test
    void testCreate_DuplicateAaCompetitionSamePart_CaughtByDatabaseConstraint() {
        Competition aaDay1 = new Competition();
        aaDay1.setEvent(testEvent);
        aaDay1.setDate(LocalDate.of(2026, 8, 15));
        aaDay1.setType(CompetitionType.C2);
        aaDay1.setDiscipline(Discipline.WAG);
        aaDay1.setAgeCategory(AgeCategory.SR);
        aaDay1.setPart(1);
        competitionRepository.saveAndFlush(aaDay1);

        Competition duplicate = new Competition();
        duplicate.setEvent(testEvent);
        duplicate.setDate(LocalDate.of(2026, 8, 15));
        duplicate.setType(CompetitionType.C2);
        duplicate.setDiscipline(Discipline.WAG);
        duplicate.setAgeCategory(AgeCategory.SR);
        duplicate.setPart(1);

        assertThrows(DataIntegrityViolationException.class, () -> competitionRepository.saveAndFlush(duplicate));
    }

    @Test
    void testCreate_SplitRoundPartsAndWholeRoundCompetitionCoexist() {
        for (Integer part : new Integer[] { 1, 2, null }) {
            Competition aa = new Competition();
            aa.setEvent(testEvent);
            aa.setDate(LocalDate.of(2026, 8, 15));
            aa.setType(CompetitionType.C2);
            aa.setDiscipline(Discipline.WAG);
            aa.setAgeCategory(AgeCategory.SR);
            aa.setPart(part);
            assertDoesNotThrow(() -> competitionRepository.saveAndFlush(aa));
        }
    }

    private Event savedEvent(String title) {
        Event event = new Event();
        event.setTitle(title);
        event.setShortName("Test");
        event.setSlug(title.toLowerCase().replaceAll("[^a-z0-9]+", "-"));
        event.setStartDate(LocalDate.of(2026, 4, 20));
        event.setEndDate(LocalDate.of(2026, 4, 26));
        event.setCity("Stuttgart");
        event.setCountryCode("GER");
        event.setLevel(EventLevel.CONTINENTAL_CHAMPIONSHIPS);
        return eventRepository.save(event);
    }
}
