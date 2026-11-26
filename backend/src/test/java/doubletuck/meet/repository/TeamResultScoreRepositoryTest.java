package doubletuck.meet.repository;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.Team;
import doubletuck.meet.domain.TeamContributionRole;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.domain.TeamResultScore;
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
class TeamResultScoreRepositoryTest {

    @Autowired
    private TeamResultScoreRepository teamResultScoreRepository;

    @Autowired
    private TeamResultRepository teamResultRepository;

    @Autowired
    private RankingTestData data;

    private TeamResult menTeam;
    private TeamResult mixedTeam;
    private Score zhaoFloor;

    @BeforeEach
    void setUp() {
        Event event = data.event("2026-youth-olympic-games");
        Competition men = data.competition(event, CompetitionType.C1, Discipline.MAG);
        Competition women = data.competition(event, CompetitionType.C1, Discipline.WAG);
        menTeam = teamResult(data.ranking(RankingType.TEAM, null, RankingPurpose.QUALIFYING, men),
                data.team(event, Discipline.MAG, "CHN"));
        mixedTeam = teamResult(data.ranking(RankingType.TEAM, null, RankingPurpose.QUALIFYING, men, women),
                data.team(event, Discipline.MIX, "CHN"));
        Participant zhao = data.participant(event, Discipline.MAG, "Zhao", "CHN");
        zhaoFloor = data.score(zhao, men, Apparatus.FX, 13.666);
    }

    @Test
    void testSave_OneScoreCountingForOneTeamAndDroppedByAnother() {
        teamResultScoreRepository.save(new TeamResultScore(menTeam, zhaoFloor, TeamContributionRole.COUNTING));
        teamResultScoreRepository.save(new TeamResultScore(mixedTeam, zhaoFloor, TeamContributionRole.DROPPED));

        List<TeamResultScore> links = teamResultScoreRepository.findByScoreIn(List.of(zhaoFloor));

        assertEquals(2, links.size());
        assertEquals(TeamContributionRole.COUNTING, teamResultScoreRepository.findByTeamResult(menTeam).get(0)
                .getRole());
        assertEquals(TeamContributionRole.DROPPED, teamResultScoreRepository.findByTeamResult(mixedTeam).get(0)
                .getRole());
    }

    @Test
    void testDeleteByTeamResultIn_RemovesOnlyThoseLinks() {
        teamResultScoreRepository.save(new TeamResultScore(menTeam, zhaoFloor, TeamContributionRole.COUNTING));
        teamResultScoreRepository.save(new TeamResultScore(mixedTeam, zhaoFloor, TeamContributionRole.DROPPED));

        teamResultScoreRepository.deleteByTeamResultIn(List.of(mixedTeam));

        assertEquals(1, teamResultScoreRepository.findByTeamResultIn(List.of(menTeam, mixedTeam)).size());
    }

    private TeamResult teamResult(Ranking ranking, Team team) {
        TeamResult result = new TeamResult();
        result.setRanking(ranking);
        result.setTeam(team);
        return teamResultRepository.save(result);
    }
}
