package doubletuck.meet.controller;

import doubletuck.meet.domain.Athlete;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.importer.EventImporter;
import doubletuck.meet.repository.AthleteRepository;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.repository.RankingRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import java.util.Objects;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** The 2026 Youth Olympic Games' mixed team through the API, from the fixture cut down to CHN, JPN and GER. */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class MixedTeamApiTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private EventImporter eventImporter;

    @Autowired
    private CompetitionRepository competitionRepository;

    @Autowired
    private RankingRepository rankingRepository;

    @Autowired
    private AthleteRepository athleteRepository;

    @BeforeEach
    void load() {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.YOG_MAG, ApiTestFixtures.YOG_WAG, ApiTestFixtures.YOG_MIX);
    }

    @Test
    void testFindEvent_MixedDivisionListsItsQualificationThenTheRounds() throws Exception {
        mockMvc.perform(get("/api/events/2026-youth-olympic-games"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.divisions[*].discipline", contains("MAG", "WAG", "MIX")))
                .andExpect(jsonPath("$.divisions[0].rankings", empty()))
                .andExpect(jsonPath("$.divisions[2].rankings[0].slug").value("qualification"))
                .andExpect(jsonPath("$.divisions[2].rankings[0].name").value("Qualification"))
                .andExpect(jsonPath("$.divisions[2].rankings[0].date").value("2026-11-07"))
                .andExpect(jsonPath("$.divisions[2].rankings[0].endDate").value("2026-11-08"))
                .andExpect(jsonPath("$.divisions[2].competitions[*].name",
                        contains("Team Final, Round 1", "Team Final, Round 2", "Team Final, Round 3")))
                .andExpect(jsonPath("$.divisions[2].competitions[*].slug",
                        contains("team-final-round-1", "team-final-round-2", "team-final-round-3")));
    }

    @Test
    void testFindRankingResults_MixedQualification_TeamsAndTheirCountingScores() throws Exception {
        mockMvc.perform(get("/api/rankings/{id}/results", mixedQualification().getId()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.ranking.discipline").value("MIX"))
                .andExpect(jsonPath("$.teams[0].noc").value("CHN"))
                .andExpect(jsonPath("$.teams[0].total").value(81.898))
                .andExpect(jsonPath("$.teams[0].qualification").value("Q"))
                .andExpect(jsonPath("$.teams[0].apparatusTotals[*].discipline",
                        contains("MAG", "MAG", "MAG", "WAG", "WAG", "WAG")))
                .andExpect(jsonPath("$.teams[0].apparatusTotals[*].apparatus",
                        contains("FX", "PB", "HB", "UB", "BB", "FX")))
                // GER's two men tie on floor: the team's floor is the one score, not their sum
                .andExpect(jsonPath("$.teams[?(@.noc == 'GER')].apparatusTotals[0].total").value(12.366))
                .andExpect(jsonPath("$.apparatus[0].discipline").value("MAG"))
                .andExpect(jsonPath("$.apparatus[0].apparatus").value("FX"))
                .andExpect(jsonPath("$.apparatus[0].scores[0].athlete.surname").value("Yang"))
                .andExpect(jsonPath("$.apparatus[-1].discipline").value("WAG"))
                .andExpect(jsonPath("$.apparatus[-1].apparatus").value("FX"));
    }

    @Test
    void testFindRankingResults_ACompetitionsOwnRanking_NotFound() throws Exception {
        Ranking own = rankingRepository.findAll().stream()
                .filter(ranking -> ranking.getDiscipline() == Discipline.MAG).findFirst().orElseThrow();

        mockMvc.perform(get("/api/rankings/{id}/results", own.getId())).andExpect(status().isNotFound());
    }

    @Test
    void testFindResults_MenCompetitionI_ShowsTheMensTeamsNotTheMixed() throws Exception {
        mockMvc.perform(get("/api/competitions/{id}/results", competition(Discipline.MAG, CompetitionType.C1, null)))
                .andExpect(jsonPath("$.teams[0].noc").value("CHN"))
                .andExpect(jsonPath("$.teams[0].total").value(159.228))
                .andExpect(jsonPath("$.teams[*].total", not(hasItem(81.898))));
    }

    @Test
    void testFindResults_FinalRound_ThenThePlacesEarlierRoundsPrinted() throws Exception {
        mockMvc.perform(get("/api/competitions/{id}/results", competition(Discipline.MIX, CompetitionType.C4, 3)))
                .andExpect(jsonPath("$.competition.name").value("Team Final, Round 3"))
                .andExpect(jsonPath("$.competition.round").value(3))
                .andExpect(jsonPath("$.teams[0].noc").value("CHN"))
                .andExpect(jsonPath("$.teams[0].round").doesNotExist())
                .andExpect(jsonPath("$.teams[0].apparatusTotals[*].apparatus", contains("FX", "BB")))
                .andExpect(jsonPath("$.apparatus[*].discipline", contains("MAG", "MAG", "WAG", "WAG")))
                .andExpect(jsonPath("$.apparatus[*].apparatus", contains("FX", "HB", "UB", "BB")));
    }

    @Test
    void testFindAthlete_CountedInQualificationOnly_SharesTheMixedTeamsResults() throws Exception {
        // XIE Guying's bars counted for CHN in qualification; she didn't compete in a final round
        mockMvc.perform(get("/api/athletes/{id}", athleteId("Xie")))
                .andExpect(jsonPath("$.entries[0].mixedTeam.noc").value("CHN"))
                .andExpect(jsonPath("$.entries[0].mixedTeam.results[*].slug",
                        contains("qualification", "team-final-round-1", "team-final-round-2", "team-final-round-3")))
                .andExpect(jsonPath("$.entries[0].mixedTeam.results[0].discipline").value("MIX"))
                .andExpect(jsonPath("$.entries[0].mixedTeam.results[3].rank").value(1))
                .andExpect(jsonPath("$.entries[0].mixedTeam.results[3].purpose").value("FINAL"))
                .andExpect(jsonPath("$.entries[0].competitions[*].competition.discipline", not(hasItem("MIX"))));
    }

    @Test
    void testFindAthlete_NotCounting_NoMixedTeam() throws Exception {
        // LI Lezheng, entered for CHN, counted for no mixed team result
        mockMvc.perform(get("/api/athletes/{id}", athleteId("Li")))
                .andExpect(jsonPath("$.entries[0].mixedTeam").doesNotExist());
    }

    private Ranking mixedQualification() {
        return rankingRepository.findAll().stream()
                .filter(ranking -> ranking.getDiscipline() == Discipline.MIX && ranking.getCompetitions().stream()
                        .allMatch(competition -> competition.getType() == CompetitionType.C1))
                .findFirst().orElseThrow();
    }

    private Long competition(Discipline discipline, CompetitionType type, Integer round) {
        return competitionRepository.findAll().stream()
                .filter(c -> c.getDiscipline() == discipline && c.getType() == type && Objects.equals(c.getRound(), round))
                .map(Competition::getId)
                .findFirst().orElseThrow();
    }

    private Long athleteId(String surname) {
        return athleteRepository.findAll().stream()
                .filter(athlete -> athlete.getSurname().equals(surname))
                .map(Athlete::getId)
                .findFirst().orElseThrow();
    }
}
