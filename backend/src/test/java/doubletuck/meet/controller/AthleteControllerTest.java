package doubletuck.meet.controller;

import doubletuck.meet.domain.Athlete;
import doubletuck.meet.importer.EventImporter;
import doubletuck.meet.repository.AthleteRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class AthleteControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private EventImporter eventImporter;

    @Autowired
    private AthleteRepository athleteRepository;

    @Test
    void testSearch_MatchesEveryWordInAnyOrderIgnoringCase() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_WAG);

        for (String query : new String[] { "nemour", "Kaylia NEMOUR", "nem kay" }) {
            mockMvc.perform(get("/api/athletes").param("q", query))
                    .andExpect(status().isOk())
                    .andExpect(header().string("Cache-Control", "max-age=300, public"))
                    .andExpect(jsonPath("$", hasSize(1)))
                    .andExpect(jsonPath("$[0].surname").value("Nemour"))
                    .andExpect(jsonPath("$[0].givenName").value("Kaylia"))
                    .andExpect(jsonPath("$[0].discipline").value("WAG"))
                    .andExpect(jsonPath("$[0].noc").value("ALG"));
        }
    }

    @Test
    void testSearch_NoMatchOrBlank_Empty() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_WAG);

        mockMvc.perform(get("/api/athletes").param("q", "nemour zzz")).andExpect(jsonPath("$", empty()));
        mockMvc.perform(get("/api/athletes").param("q", " ")).andExpect(jsonPath("$", empty()));
        mockMvc.perform(get("/api/athletes").param("q", "%")).andExpect(jsonPath("$", empty()));
        mockMvc.perform(get("/api/athletes")).andExpect(status().isBadRequest());
    }

    @Test
    void testFindAthlete_PersonalBestsAndEachCompetitionOfTheMeet() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_WAG);

        mockMvc.perform(get("/api/athletes/{id}", athleteId("Nemour")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.surname").value("Nemour"))
                .andExpect(jsonPath("$.birthYear").value(2006))
                // Bars: 15.333 in the final beats 14.933 in qualification
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'UB')].score").value(15.333))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'UB')].routine.difficulty").value(7.0))
                .andExpect(jsonPath("$.personalBests[1].vault").value(nullValue()))
                // Floor: 13.266 in the all-around final beats 12.900 in qualification, which had a penalty
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'FX')].score").value(13.266))
                .andExpect(jsonPath("$.personalBests[3].routine.penalty").value(nullValue()))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'UB')].competition.slug")
                        .value("uneven-bars-final"))
                .andExpect(jsonPath("$.allAroundBest.total").value(55.999))
                .andExpect(jsonPath("$.allAroundBest.competition.slug").value("qualification"))
                .andExpect(jsonPath("$.entries", hasSize(1)))
                .andExpect(jsonPath("$.entries[0].event.slug").value("2026-world-championships"))
                .andExpect(jsonPath("$.entries[0].noc").value("ALG"))
                .andExpect(jsonPath("$.entries[0].club").value(nullValue()))
                .andExpect(jsonPath("$.entries[0].competitions[*].competition.slug",
                        contains("qualification", "all-around-final", "uneven-bars-final", "beam-final")))
                .andExpect(jsonPath("$.entries[0].competitions[1].allAround.total").value(54.998))
                .andExpect(jsonPath("$.entries[0].competitions[1].allAround.rank").value(4))
                .andExpect(jsonPath("$.entries[0].competitions[1].scores[*].apparatus", contains("VT", "UB", "BB", "FX")))
                .andExpect(jsonPath("$.entries[0].competitions[2].scores[0].routine.score").value(15.333));
    }

    @Test
    void testFindAthlete_VaultBest_SaysWhichVault() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_MAG);

        // 14.900 on his first vault in qualification, the all-around final and the vault final: the earliest counts
        mockMvc.perform(get("/api/athletes/{id}", athleteId("Jarman")))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'VT')].score").value(14.9))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'VT')].vault").value(1))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'VT')].routine.execution").value(9.3))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'VT')].competition.slug").value("qualification"));
    }

    @Test
    void testFindAthlete_TeamResultInEachCompetitionThatRanksTeams() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_MAG);

        mockMvc.perform(get("/api/athletes/{id}", athleteId("Jarman")))
                .andExpect(jsonPath("$.entries[0].competitions[0].competition.slug").value("qualification"))
                .andExpect(jsonPath("$.entries[0].competitions[1].competition.slug").value("team-final"))
                .andExpect(jsonPath("$.entries[0].competitions[2].competition.slug").value("all-around-final"))
                .andExpect(jsonPath("$.entries[0].competitions[0].team.noc").value("GBR"))
                .andExpect(jsonPath("$.entries[0].competitions[0].team.rank").value(2))
                .andExpect(jsonPath("$.entries[0].competitions[0].team.total").value(251.46))
                .andExpect(jsonPath("$.entries[0].competitions[0].team.qualification").value("Q"))
                .andExpect(jsonPath("$.entries[0].competitions[0].team.purpose").value("QUALIFYING"))
                .andExpect(jsonPath("$.entries[0].competitions[0].team.rankStatus").value("RANKED"))
                .andExpect(jsonPath("$.entries[0].competitions[1].team.purpose").value("FINAL"))
                .andExpect(jsonPath("$.entries[0].competitions[1].team.rank").value(4))
                .andExpect(jsonPath("$.entries[0].competitions[1].team.total").value(247.395))
                .andExpect(jsonPath("$.entries[0].competitions[1].team.qualification").value(nullValue()))
                .andExpect(jsonPath("$.entries[0].competitions[2].team").value(nullValue()));
    }

    @Test
    void testFindAthlete_FinalsRankingTheQualificationsRoutines_ShownWithTheQualification() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.ASIAN_WAG);

        // The team and all-around finals ranked the qualification's routines: one entry, with the final placings
        mockMvc.perform(get("/api/athletes/{id}", athleteId("Yeap")))
                .andExpect(jsonPath("$.entries[0].competitions[*].competition.slug", contains("qualification")))
                .andExpect(jsonPath("$.entries[0].competitions[0].scores", hasSize(4)))
                .andExpect(jsonPath("$.entries[0].competitions[0].competition.name")
                        .value("Team and All-Around Final · Apparatus Qualification"))
                .andExpect(jsonPath("$.entries[0].competitions[0].allAround.rank").value(9))
                // Competition I decided the all-around: its placings are medal placings
                .andExpect(jsonPath("$.entries[0].competitions[0].allAround.purpose").value("FINAL"))
                .andExpect(jsonPath("$.entries[0].competitions[0].team.noc").value("MAS"))
                .andExpect(jsonPath("$.entries[0].competitions[0].team.rank").value(5))
                .andExpect(jsonPath("$.allAroundBest.competition.slug").value("qualification"));
    }

    @Test
    void testFindAthlete_SplitCompetition_BestAllAroundIsOneDayNotTheCombinedTotal() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);

        mockMvc.perform(get("/api/athletes/{id}", athleteId("Moldauer")))
                .andExpect(jsonPath("$.entries[0].club").value("U of Oklahoma"))
                .andExpect(jsonPath("$.entries[0].competitions[*].competition.slug",
                        contains("all-around-and-apparatus-final", "all-around-and-apparatus-final-part-1",
                                "all-around-and-apparatus-final-part-2")))
                .andExpect(jsonPath("$.entries[0].competitions[0].allAround.total").value(163.896))
                .andExpect(jsonPath("$.entries[0].competitions[0].apparatusStandings[?(@.apparatus == 'FX')].total")
                        .value(26.7))
                .andExpect(jsonPath("$.allAroundBest.total").value(82.123))
                .andExpect(jsonPath("$.allAroundBest.competition.slug")
                        .value("all-around-and-apparatus-final-part-2"));
    }

    @Test
    void testFindAthlete_PartialAllAround_NotABest() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);

        // A pommel horse specialist: US results print his one-apparatus "all-around" total
        mockMvc.perform(get("/api/athletes/{id}", athleteId("Hoopes")))
                .andExpect(jsonPath("$.allAroundBest").value(nullValue()))
                .andExpect(jsonPath("$.personalBests[*].apparatus", contains("PH")))
                .andExpect(jsonPath("$.personalBests[0].score").value(15.641));
    }

    @Test
    void testFindAthlete_Unknown_NotFound() throws Exception {
        mockMvc.perform(get("/api/athletes/{id}", -1)).andExpect(status().isNotFound());
    }

    private Long athleteId(String surname) {
        return athleteRepository.findAll().stream()
                .filter(athlete -> athlete.getSurname().equals(surname))
                .map(Athlete::getId)
                .findFirst()
                .orElseThrow();
    }
}
