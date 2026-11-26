package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
@Import(RankingTestData.class)
class RankingRepositoryTest {

    @Autowired
    private RankingRepository rankingRepository;

    @Autowired
    private RankingTestData data;

    private Event event;
    private Competition qualification;

    @BeforeEach
    void setUp() {
        event = data.event("2026-asian-games");
        qualification = data.competition(event, CompetitionType.C1, Discipline.WAG);
    }

    @Test
    void testSave_PersistsAllFields() {
        Ranking ranking = data.ranking(RankingType.APPARATUS, Apparatus.VT, RankingPurpose.QUALIFYING, qualification);

        Ranking found = rankingRepository.findById(ranking.getId()).orElseThrow();

        assertEquals(event.getId(), found.getEvent().getId());
        assertEquals(Discipline.WAG, found.getDiscipline());
        assertEquals(AgeCategory.SR, found.getAgeCategory());
        assertEquals(RankingType.APPARATUS, found.getType());
        assertEquals(Apparatus.VT, found.getApparatus());
        assertEquals(RankingPurpose.QUALIFYING, found.getPurpose());
        assertEquals(List.of(qualification.getId()), found.getCompetitions().stream().map(Competition::getId).toList());
    }

    @Test
    void testFindByCompetition_RankingsOfItsRoutinesOnly() {
        Competition teamFinal = data.competition(event, CompetitionType.C4, Discipline.WAG);
        Ranking allAround = data.ranking(RankingType.AA, null, RankingPurpose.FINAL, qualification);
        Ranking teams = data.ranking(RankingType.TEAM, null, RankingPurpose.QUALIFYING, qualification);
        data.ranking(RankingType.TEAM, null, RankingPurpose.FINAL, teamFinal);

        List<Long> found = rankingRepository.findByCompetition(qualification).stream().map(Ranking::getId).toList();

        assertEquals(2, found.size());
        assertTrue(found.containsAll(List.of(allAround.getId(), teams.getId())));
    }

    @Test
    void testFindByCompetition_RankingAcrossCompetitions_FoundFromEach() {
        Competition women = qualification;
        Competition men = data.competition(event, CompetitionType.C1, Discipline.MAG);
        Ranking mixed = data.ranking(RankingType.TEAM, null, RankingPurpose.QUALIFYING, men, women);

        assertEquals(List.of(mixed.getId()), rankingRepository.findByCompetition(men).stream().map(Ranking::getId)
                .toList());
        assertEquals(List.of(mixed.getId()), rankingRepository.findByCompetition(women).stream().map(Ranking::getId)
                .toList());
    }

    @Test
    void testFindByEventAndDisciplineAndAgeCategory_OnlyThatSlice() {
        Ranking women = data.ranking(RankingType.AA, null, RankingPurpose.FINAL, qualification);
        data.ranking(RankingType.AA, null, RankingPurpose.FINAL,
                data.competition(event, CompetitionType.C1, Discipline.MAG));

        List<Ranking> found = rankingRepository.findByEventAndDisciplineAndAgeCategory(event, Discipline.WAG,
                AgeCategory.SR);

        assertEquals(List.of(women.getId()), found.stream().map(Ranking::getId).toList());
    }
}
