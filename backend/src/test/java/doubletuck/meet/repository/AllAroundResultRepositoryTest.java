package doubletuck.meet.repository;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.RankStatus;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
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
class AllAroundResultRepositoryTest {

    @Autowired
    private AllAroundResultRepository allAroundResultRepository;

    @Autowired
    private RankingTestData data;

    private Event event;
    private Ranking qualifying;
    private Participant biles;
    private AllAroundResult bilesResult;

    @BeforeEach
    void setUp() {
        event = data.event("2026-world-championships");
        Competition qualification = data.competition(event, CompetitionType.C1, Discipline.WAG);
        qualifying = data.ranking(RankingType.AA, null, RankingPurpose.QUALIFYING, qualification);
        biles = data.participant(event, Discipline.WAG, "Biles", "USA");
        bilesResult = result(qualifying, biles, 1, RankStatus.RANKED, QualificationResult.Q);
    }

    @Test
    void testSave_PersistsAllFields() {
        AllAroundResult found = allAroundResultRepository.findById(bilesResult.getId()).orElseThrow();

        assertEquals(qualifying.getId(), found.getRanking().getId());
        assertEquals(biles.getId(), found.getParticipant().getId());
        assertEquals(58.5, found.getTotalScore());
        assertEquals(1, found.getRank());
        assertEquals(RankStatus.RANKED, found.getRankStatus());
        assertEquals(QualificationResult.Q, found.getQualificationResult());
    }

    @Test
    void testSave_UnrankedWithStatus() {
        Participant third = data.participant(event, Discipline.WAG, "Chiles", "USA");
        AllAroundResult result = result(qualifying, third, null, RankStatus.NOC_LIMIT, QualificationResult.NR);

        AllAroundResult found = allAroundResultRepository.findById(result.getId()).orElseThrow();

        assertNull(found.getRank());
        assertEquals(RankStatus.NOC_LIMIT, found.getRankStatus());
    }

    @Test
    void testFindByParticipant_ResultsAcrossRankings() {
        Ranking allAroundFinal = data.ranking(RankingType.AA, null, RankingPurpose.FINAL,
                data.competition(event, CompetitionType.C2, Discipline.WAG));
        result(allAroundFinal, biles, 1, RankStatus.RANKED, null);

        assertEquals(2, allAroundResultRepository.findByParticipant(biles).size());
        assertTrue(allAroundResultRepository.existsByParticipant(biles));
    }

    @Test
    void testFindResultsByRanking_FetchesTheAthlete() {
        List<AllAroundResult> found = allAroundResultRepository.findResultsByRanking(qualifying);

        assertEquals(1, found.size());
        assertEquals("Biles", found.get(0).getParticipant().getAthlete().getSurname());
    }

    @Test
    void testCreate_FailsBecauseDuplicateRankingAndParticipant() {
        AllAroundResult duplicate = new AllAroundResult();
        duplicate.setRanking(qualifying);
        duplicate.setParticipant(biles);

        assertThrows(DataIntegrityViolationException.class,
                () -> allAroundResultRepository.saveAndFlush(duplicate));
    }

    private AllAroundResult result(Ranking ranking, Participant participant, Integer rank, RankStatus status,
            QualificationResult qualification) {
        AllAroundResult result = new AllAroundResult();
        result.setRanking(ranking);
        result.setParticipant(participant);
        result.setTotalScore(58.5);
        result.setRank(rank);
        result.setRankStatus(status);
        result.setQualificationResult(qualification);
        return allAroundResultRepository.save(result);
    }
}
