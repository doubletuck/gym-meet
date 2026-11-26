package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Team;
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
class TeamRepositoryTest {

    @Autowired
    private TeamRepository teamRepository;

    @Autowired
    private RankingTestData data;

    private Event event;

    @BeforeEach
    void setUp() {
        event = data.event("2026-youth-olympic-games");
    }

    @Test
    void testFindByEventAndDisciplineAndAgeCategoryAndName_Found() {
        Team team = data.team(event, Discipline.MIX, "CHN");

        Team found = teamRepository.findByEventAndDisciplineAndAgeCategoryAndName(event, Discipline.MIX,
                AgeCategory.SR, "CHN").orElseThrow();

        assertEquals(team.getId(), found.getId());
        assertEquals("CHN", found.getNoc());
    }

    @Test
    void testSave_SameNameInAnotherDiscipline_Succeeds() {
        Team men = data.team(event, Discipline.MAG, "CHN");
        Team mixed = data.team(event, Discipline.MIX, "CHN");

        assertNotEquals(men.getId(), mixed.getId());
    }

    @Test
    void testSave_TeamWithoutNoc_Succeeds() {
        Team team = new Team();
        team.setEvent(event);
        team.setDiscipline(Discipline.MIX);
        team.setAgeCategory(AgeCategory.SR);
        team.setName("Team Simone Biles");

        assertNull(teamRepository.saveAndFlush(team).getNoc());
    }

    @Test
    void testCreate_FailsBecauseDuplicateName() {
        data.team(event, Discipline.MAG, "JPN");
        Team duplicate = new Team();
        duplicate.setEvent(event);
        duplicate.setDiscipline(Discipline.MAG);
        duplicate.setAgeCategory(AgeCategory.SR);
        duplicate.setName("JPN");

        assertThrows(DataIntegrityViolationException.class, () -> teamRepository.saveAndFlush(duplicate));
    }
}
