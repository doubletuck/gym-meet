package doubletuck.meet.repository;

import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.RankStatus;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.Team;
import doubletuck.meet.domain.TeamResult;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.ActiveProfiles;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
@Import(RankingTestData.class)
class TeamResultRepositoryTest {

    @Autowired
    private TeamResultRepository teamResultRepository;

    @Autowired
    private RankingTestData data;

    private Event event;
    private Competition qualification;
    private Ranking qualifying;
    private Team usa;
    private TeamResult usaResult;

    @BeforeEach
    void setUp() {
        event = data.event("2026-world-championships");
        qualification = data.competition(event, CompetitionType.C1, Discipline.WAG);
        qualifying = data.ranking(RankingType.TEAM, null, RankingPurpose.QUALIFYING, qualification);
        usa = data.team(event, Discipline.WAG, "USA");
        usaResult = result(qualifying, usa, 1, QualificationResult.Q);
    }

    @Test
    void testSave_PersistsAllFields() {
        TeamResult found = teamResultRepository.findById(usaResult.getId()).orElseThrow();

        assertEquals(qualifying.getId(), found.getRanking().getId());
        assertEquals("USA", found.getTeam().getNoc());
        assertEquals(168.5, found.getTotalScore());
        assertEquals(-0.3, found.getSjPenalty());
        assertEquals(1, found.getRank());
        assertEquals(RankStatus.RANKED, found.getRankStatus());
        assertEquals(QualificationResult.Q, found.getQualificationResult());
    }

    @Test
    void testFindByRanking_OnlyThatRanking() {
        Ranking teamFinal = data.ranking(RankingType.TEAM, null, RankingPurpose.FINAL,
                data.competition(event, CompetitionType.C4, Discipline.WAG));
        result(teamFinal, usa, 2, null);

        assertEquals(List.of(usaResult.getId()), teamResultRepository.findByRanking(qualifying).stream()
                .map(TeamResult::getId).toList());
    }

    @Test
    void testFindByCompetitionAndNoc_EveryRankingOfTheCompetitionsRoutines() {
        Ranking finalRanking = data.ranking(RankingType.TEAM, null, RankingPurpose.FINAL, qualification);
        TeamResult usaFinal = result(finalRanking, usa, 1, null);
        result(qualifying, data.team(event, Discipline.WAG, "CHN"), 2, QualificationResult.Q);

        List<Long> found = teamResultRepository.findByCompetitionAndNoc(qualification, "USA").stream()
                .map(TeamResult::getId).toList();

        assertEquals(2, found.size());
        assertTrue(found.containsAll(List.of(usaResult.getId(), usaFinal.getId())));
    }

    @Test
    void testDeleteByRankingIn_RemovesThoseRankingsResults() {
        teamResultRepository.deleteByRankingIn(List.of(qualifying));

        assertTrue(teamResultRepository.findByRanking(qualifying).isEmpty());
    }

    @Test
    void testCreate_FailsBecauseDuplicateRankingAndTeam() {
        TeamResult duplicate = new TeamResult();
        duplicate.setRanking(qualifying);
        duplicate.setTeam(usa);

        assertThrows(DataIntegrityViolationException.class, () -> teamResultRepository.saveAndFlush(duplicate));
    }

    private TeamResult result(Ranking ranking, Team team, int rank, QualificationResult qualification) {
        TeamResult result = new TeamResult();
        result.setRanking(ranking);
        result.setTeam(team);
        result.setTotalScore(168.5);
        result.setSjPenalty(-0.3);
        result.setRank(rank);
        result.setRankStatus(RankStatus.RANKED);
        result.setQualificationResult(qualification);
        return teamResultRepository.save(result);
    }
}
