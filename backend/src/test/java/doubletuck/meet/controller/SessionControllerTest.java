package doubletuck.meet.controller;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Round;
import doubletuck.meet.importer.EventImporter;
import doubletuck.meet.repository.SessionRepository;
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
class SessionControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private EventImporter eventImporter;

    @Autowired
    private SessionRepository sessionRepository;

    @Test
    void testFindResults_ApparatusFinalRankedAsPublished() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_WAG);
        Long beamFinal = ApiTestFixtures.sessionId(sessionRepository, Discipline.WAG, Round.EVENT, Apparatus.BB, null);

        mockMvc.perform(get("/api/sessions/{id}/results", beamFinal))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "max-age=300, public"))
                .andExpect(jsonPath("$.event.slug").value("2026-world-championships"))
                .andExpect(jsonPath("$.session.slug").value("beam-final"))
                .andExpect(jsonPath("$.apparatus", hasSize(1)))
                .andExpect(jsonPath("$.apparatus[0].scores[0].rank").value(1))
                .andExpect(jsonPath("$.apparatus[0].scores[0].athlete.surname").value("Nemour"))
                .andExpect(jsonPath("$.apparatus[0].scores[0].routine.difficulty").value(6.3))
                .andExpect(jsonPath("$.apparatus[0].scores[0].routine.execution").value(8.266))
                .andExpect(jsonPath("$.apparatus[0].scores[0].total").value(14.566))
                .andExpect(jsonPath("$.apparatus[0].scores[1].athlete.surname").value("Zhang"))
                .andExpect(jsonPath("$.apparatus[0].scores[1].total").value(14.566))
                .andExpect(jsonPath("$.allAround", empty()))
                .andExpect(jsonPath("$.teams", empty()));
    }

    @Test
    void testFindResults_QualificationHasEveryApparatusAllAroundAndTeams() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_WAG);
        Long qualification = ApiTestFixtures.sessionId(sessionRepository, Discipline.WAG, Round.QUAL, null, null);

        mockMvc.perform(get("/api/sessions/{id}/results", qualification))
                .andExpect(jsonPath("$.apparatus[*].apparatus", contains("VT", "UB", "BB", "FX")))
                .andExpect(jsonPath("$.teams[0].noc").value("CHN"))
                .andExpect(jsonPath("$.teams[0].rank").value(1))
                .andExpect(jsonPath("$.teams[0].total").value(164.996))
                .andExpect(jsonPath("$.teams[0].qualification").value("Q"))
                .andExpect(jsonPath("$.teams[0].apparatusTotals.BB").value(43.966))
                .andExpect(jsonPath("$.allAround[?(@.athlete.surname == 'Nemour')].total").value(55.999))
                .andExpect(jsonPath("$.allAround[?(@.athlete.surname == 'Nemour')].apparatusScores.UB")
                        .value(14.933))
                .andExpect(jsonPath("$.apparatus[2].scores[?(@.athlete.givenName == 'Yihan')].countsTowardTeam")
                        .value(false))
                .andExpect(jsonPath("$.apparatus[2].scores[?(@.athlete.surname == 'Ke')].qualification")
                        .value("NR"));
    }

    @Test
    void testFindResults_TwoVaultEntryAndDidNotStart() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_MAG);
        Long qualification = ApiTestFixtures.sessionId(sessionRepository, Discipline.MAG, Round.QUAL, null, null);

        // MAG apparatus order: FX, PH, SR, VT, PB, HB
        mockMvc.perform(get("/api/sessions/{id}/results", qualification))
                .andExpect(jsonPath("$.apparatus[3].apparatus").value("VT"))
                .andExpect(jsonPath("$.apparatus[3].scores[0].athlete.surname").value("Jarman"))
                .andExpect(jsonPath("$.apparatus[3].scores[0].routine.score").value(14.9))
                .andExpect(jsonPath("$.apparatus[3].scores[0].secondRoutine.score").value(14.366))
                .andExpect(jsonPath("$.apparatus[3].scores[0].total").value(14.633))
                .andExpect(jsonPath("$.apparatus[3].scores[0].qualificationRank").value(1))
                .andExpect(jsonPath("$.apparatus[1].apparatus").value("PH"))
                .andExpect(jsonPath("$.apparatus[1].scores[-1].athlete.surname").value("Tulloch"))
                .andExpect(jsonPath("$.apparatus[1].scores[-1].rank").value(nullValue()))
                .andExpect(jsonPath("$.apparatus[1].scores[-1].routine.status").value("DNS"));
    }

    @Test
    void testFindResults_SplitRoundCombinedStandings() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);
        Long wholeRound = ApiTestFixtures.sessionId(sessionRepository, Discipline.MAG, Round.AA, null, null);

        mockMvc.perform(get("/api/sessions/{id}/results", wholeRound))
                .andExpect(jsonPath("$.session.slug").value("all-around-final"))
                .andExpect(jsonPath("$.apparatus", empty()))
                .andExpect(jsonPath("$.allAround[0].athlete.surname").value("Moldauer"))
                .andExpect(jsonPath("$.allAround[0].total").value(163.896))
                .andExpect(jsonPath("$.apparatusStandings[?(@.apparatus == 'PH')].rows[?(@.athlete.surname == "
                        + "'Hoopes')].total").value(30.816));
    }

    @Test
    void testFindResults_Unknown_NotFound() throws Exception {
        mockMvc.perform(get("/api/sessions/{id}/results", -1)).andExpect(status().isNotFound());
    }
}
