package doubletuck.meet.repository;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
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
class ApparatusResultRepositoryTest {

    @Autowired
    private ApparatusResultRepository apparatusResultRepository;

    @Autowired
    private RankingTestData data;

    private Ranking singleVault;
    private Ranking twoVaults;
    private Participant athlete;

    @BeforeEach
    void setUp() {
        Event event = data.event("2026-world-championships");
        Competition qualification = data.competition(event, CompetitionType.C1, Discipline.WAG);
        singleVault = data.ranking(RankingType.APPARATUS, Apparatus.VT, RankingPurpose.INFORMATIONAL, qualification);
        twoVaults = data.ranking(RankingType.APPARATUS, Apparatus.VT, RankingPurpose.QUALIFYING, qualification);
        athlete = data.participant(event, Discipline.WAG, "Andrade", "BRA");
    }

    @Test
    void testSave_PersistsAllFields() {
        ApparatusResult result = result(twoVaults, 3, 14.85, QualificationResult.Q);

        ApparatusResult found = apparatusResultRepository.findById(result.getId()).orElseThrow();

        assertEquals(twoVaults.getId(), found.getRanking().getId());
        assertEquals(athlete.getId(), found.getParticipant().getId());
        assertEquals(14.85, found.getTotalScore());
        assertEquals(3, found.getRank());
        assertEquals(RankStatus.RANKED, found.getRankStatus());
        assertEquals(QualificationResult.Q, found.getQualificationResult());
    }

    @Test
    void testFindResultsByRankingIn_TheSameScoreRankedTwice() {
        result(singleVault, 14, 14.7, null);
        result(twoVaults, 3, 14.85, QualificationResult.Q);

        List<ApparatusResult> found = apparatusResultRepository.findResultsByRankingIn(List.of(singleVault, twoVaults));

        assertEquals(2, found.size());
        assertTrue(apparatusResultRepository.existsByParticipant(athlete));
    }

    @Test
    void testCreate_FailsBecauseDuplicateRankingAndParticipant() {
        result(singleVault, 14, 14.7, null);
        ApparatusResult duplicate = new ApparatusResult();
        duplicate.setRanking(singleVault);
        duplicate.setParticipant(athlete);

        assertThrows(DataIntegrityViolationException.class,
                () -> apparatusResultRepository.saveAndFlush(duplicate));
    }

    private ApparatusResult result(Ranking ranking, int rank, double total, QualificationResult qualification) {
        ApparatusResult result = new ApparatusResult();
        result.setRanking(ranking);
        result.setParticipant(athlete);
        result.setTotalScore(total);
        result.setRank(rank);
        result.setRankStatus(RankStatus.RANKED);
        result.setQualificationResult(qualification);
        return apparatusResultRepository.save(result);
    }
}
