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
    void testFindAthlete_PersonalBestsAndEachSessionOfTheMeet() throws Exception {
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
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'UB')].session.slug")
                        .value("uneven-bars-final"))
                .andExpect(jsonPath("$.allAroundBest.total").value(55.999))
                .andExpect(jsonPath("$.allAroundBest.session.slug").value("qualification"))
                .andExpect(jsonPath("$.entries", hasSize(1)))
                .andExpect(jsonPath("$.entries[0].event.slug").value("2026-world-championships"))
                .andExpect(jsonPath("$.entries[0].noc").value("ALG"))
                .andExpect(jsonPath("$.entries[0].club").value(nullValue()))
                .andExpect(jsonPath("$.entries[0].sessions[*].session.slug",
                        contains("qualification", "all-around-final", "uneven-bars-final", "beam-final")))
                .andExpect(jsonPath("$.entries[0].sessions[1].allAround.total").value(54.998))
                .andExpect(jsonPath("$.entries[0].sessions[1].allAround.rank").value(4))
                .andExpect(jsonPath("$.entries[0].sessions[1].scores[*].apparatus", contains("VT", "UB", "BB", "FX")))
                .andExpect(jsonPath("$.entries[0].sessions[2].scores[0].routine.score").value(15.333));
    }

    @Test
    void testFindAthlete_VaultBest_SaysWhichVault() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_MAG);

        // 14.900 on his first vault in qualification, the all-around final and the vault final: the earliest counts
        mockMvc.perform(get("/api/athletes/{id}", athleteId("Jarman")))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'VT')].score").value(14.9))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'VT')].vault").value(1))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'VT')].routine.execution").value(9.3))
                .andExpect(jsonPath("$.personalBests[?(@.apparatus == 'VT')].session.slug").value("qualification"));
    }

    @Test
    void testFindAthlete_TeamResultInEachSessionThatRanksTeams() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_MAG);

        mockMvc.perform(get("/api/athletes/{id}", athleteId("Jarman")))
                .andExpect(jsonPath("$.entries[0].sessions[0].session.slug").value("qualification"))
                .andExpect(jsonPath("$.entries[0].sessions[1].session.slug").value("team-final"))
                .andExpect(jsonPath("$.entries[0].sessions[2].session.slug").value("all-around-final"))
                .andExpect(jsonPath("$.entries[0].sessions[0].team.noc").value("GBR"))
                .andExpect(jsonPath("$.entries[0].sessions[0].team.rank").value(2))
                .andExpect(jsonPath("$.entries[0].sessions[0].team.total").value(251.46))
                .andExpect(jsonPath("$.entries[0].sessions[0].team.qualification").value("Q"))
                .andExpect(jsonPath("$.entries[0].sessions[1].team.rank").value(4))
                .andExpect(jsonPath("$.entries[0].sessions[1].team.total").value(247.395))
                .andExpect(jsonPath("$.entries[0].sessions[1].team.qualification").value(nullValue()))
                .andExpect(jsonPath("$.entries[0].sessions[2].team").value(nullValue()));
    }

    @Test
    void testFindAthlete_SplitRound_BestAllAroundIsOneDayNotTheCombinedTotal() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);

        mockMvc.perform(get("/api/athletes/{id}", athleteId("Moldauer")))
                .andExpect(jsonPath("$.entries[0].club").value("U of Oklahoma"))
                .andExpect(jsonPath("$.entries[0].sessions[*].session.slug",
                        contains("all-around-final", "all-around-final-part-1", "all-around-final-part-2")))
                .andExpect(jsonPath("$.entries[0].sessions[0].allAround.total").value(163.896))
                .andExpect(jsonPath("$.entries[0].sessions[0].apparatusStandings[?(@.apparatus == 'FX')].total")
                        .value(26.7))
                .andExpect(jsonPath("$.allAroundBest.total").value(82.123))
                .andExpect(jsonPath("$.allAroundBest.session.slug").value("all-around-final-part-2"));
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
