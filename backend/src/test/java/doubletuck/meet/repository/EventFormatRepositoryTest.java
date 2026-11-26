package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventFormat;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.TitleFormat;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.ActiveProfiles;

import static org.junit.jupiter.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
@Import(RankingTestData.class)
class EventFormatRepositoryTest {

    @Autowired
    private EventFormatRepository eventFormatRepository;

    @Autowired
    private RankingTestData data;

    private Event event;

    @BeforeEach
    void setUp() {
        event = data.event("2026-south-american-games");
    }

    @Test
    void testFindByEventAndDisciplineAndAgeCategory_Found() {
        eventFormatRepository.saveAndFlush(format(Discipline.MAG, TitleFormat.C1, TitleFormat.C1, TitleFormat.FINAL));

        EventFormat found = eventFormatRepository.findByEventAndDisciplineAndAgeCategory(event, Discipline.MAG,
                AgeCategory.SR).orElseThrow();

        assertEquals(TitleFormat.C1, found.formatOf(RankingType.TEAM));
        assertEquals(TitleFormat.C1, found.formatOf(RankingType.AA));
        assertEquals(TitleFormat.FINAL, found.formatOf(RankingType.APPARATUS));
        assertFalse(found.isApparatusOnly());
        assertTrue(eventFormatRepository.findByEventAndDisciplineAndAgeCategory(event, Discipline.WAG,
                AgeCategory.SR).isEmpty());
    }

    @Test
    void testIsApparatusOnly_NoTeamOrAllAroundTitle() {
        assertTrue(format(Discipline.WAG, TitleFormat.NONE, TitleFormat.NONE, TitleFormat.FINAL).isApparatusOnly());
    }

    @Test
    void testCreate_FailsBecauseDuplicateSlice() {
        eventFormatRepository.saveAndFlush(format(Discipline.MAG, TitleFormat.C1, TitleFormat.C1, TitleFormat.FINAL));

        assertThrows(DataIntegrityViolationException.class, () -> eventFormatRepository.saveAndFlush(
                format(Discipline.MAG, TitleFormat.FINAL, TitleFormat.FINAL, TitleFormat.FINAL)));
    }

    private EventFormat format(Discipline discipline, TitleFormat team, TitleFormat allAround, TitleFormat apparatus) {
        EventFormat format = new EventFormat();
        format.setEvent(event);
        format.setDiscipline(discipline);
        format.setAgeCategory(AgeCategory.SR);
        format.setTeamFormat(team);
        format.setAllAroundFormat(allAround);
        format.setApparatusFormat(apparatus);
        return format;
    }
}
