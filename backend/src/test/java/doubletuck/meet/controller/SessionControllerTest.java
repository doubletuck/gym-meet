package doubletuck.meet.controller;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Round;
import doubletuck.meet.importer.EventImporter;
import doubletuck.meet.repository.ScoreRepository;
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

    @Autowired
    private ScoreRepository scoreRepository;

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
                // FIG entry lists name no clubs
                .andExpect(jsonPath("$.allAround[0].club").value(nullValue()))
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
    void testFindResults_SplitRoundCombinedSession_HasEachPart() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);
        Long wholeRound = ApiTestFixtures.sessionId(sessionRepository, Discipline.MAG, Round.AA, null, null);

        mockMvc.perform(get("/api/sessions/{id}/results", wholeRound))
                .andExpect(jsonPath("$.session.date").value("2026-08-06"))
                .andExpect(jsonPath("$.session.endDate").value("2026-08-08"))
                // Each part's scores summed, as the combined floor standings publish it
                .andExpect(jsonPath("$.allAround[0].apparatusScores.FX").value(26.7))
                // Vault's standings are the two-vault title, so its sum is the only combined all-around vault
                .andExpect(jsonPath("$.allAround[0].apparatusScores.VT").value(26.35))
                .andExpect(jsonPath("$.allAround[0].club").value("U of Oklahoma"))
                .andExpect(jsonPath("$.allAround[0].parts[*].part", contains(1, 2)))
                .andExpect(jsonPath("$.allAround[0].parts[0].total").value(81.773))
                .andExpect(jsonPath("$.allAround[0].parts[0].apparatusScores.FX").value(13.7))
                .andExpect(jsonPath("$.allAround[0].parts[1].total").value(82.123))
                .andExpect(jsonPath("$.allAround[0].parts[1].apparatusScores.FX").value(13.0))
                .andExpect(jsonPath("$.apparatusStandings[?(@.apparatus == 'PH')].rows[?(@.athlete.surname == "
                        + "'Hoopes')].parts[*].score", contains(15.641, 15.175)));
    }

    @Test
    void testFindResults_SplitRoundCombinedSession_ApparatusSkippedInAPart_ShowsTheOtherPartAlone()
            throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);
        Long wholeRound = ApiTestFixtures.sessionId(sessionRepository, Discipline.MAG, Round.AA, null, null);
        Long partTwo = ApiTestFixtures.sessionId(sessionRepository, Discipline.MAG, Round.AA, null, 2);
        // As if Moldauer hadn't vaulted on day 2
        scoreRepository.delete(scoreRepository.findBySessionId(partTwo).stream()
                .filter(score -> score.getApparatus() == Apparatus.VT
                        && score.getParticipant().getAthlete().getSurname().equals("Moldauer"))
                .findFirst().orElseThrow());

        mockMvc.perform(get("/api/sessions/{id}/results", wholeRound))
                .andExpect(jsonPath("$.allAround[0].apparatusScores.VT").value(13.75))
                .andExpect(jsonPath("$.allAround[0].parts[0].apparatusScores.VT").value(13.75))
                .andExpect(jsonPath("$.allAround[0].parts[1].apparatusScores.VT").doesNotExist());
    }

    @Test
    void testFindResults_SplitRoundPart_HasNoParts() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);
        Long partOne = ApiTestFixtures.sessionId(sessionRepository, Discipline.MAG, Round.AA, null, 1);

        mockMvc.perform(get("/api/sessions/{id}/results", partOne))
                .andExpect(jsonPath("$.session.endDate").value(nullValue()))
                .andExpect(jsonPath("$.allAround[?(@.athlete.surname == 'Moldauer')].apparatusScores.FX")
                        .value(13.7))
                .andExpect(jsonPath("$.allAround[0].parts", empty()))
                .andExpect(jsonPath("$.apparatus[0].scores[?(@.athlete.surname == 'Moldauer')].club")
                        .value("U of Oklahoma"));
    }

    @Test
    void testFindResults_FinalRankingTheQualificationsRoutines_ShowsThemWithoutScoreTables() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.ASIAN_WAG);
        Long allAroundFinal = ApiTestFixtures.sessionId(sessionRepository, Discipline.WAG, Round.AA, null, null);
        Long teamFinal = ApiTestFixtures.sessionId(sessionRepository, Discipline.WAG, Round.TEAM, null, null);

        mockMvc.perform(get("/api/sessions/{id}/results", allAroundFinal))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.session.slug").value("all-around-final"))
                .andExpect(jsonPath("$.apparatus", empty()))
                .andExpect(jsonPath("$.allAround", hasSize(6)))
                .andExpect(jsonPath("$.allAround[?(@.athlete.surname == 'Yeap')].rank").value(9))
                .andExpect(jsonPath("$.allAround[0].athlete.surname").value("Ke"))
                .andExpect(jsonPath("$.allAround[0].apparatusScores.BB").value(14.933))
                .andExpect(jsonPath("$.allAround[0].qualification").value(nullValue()));
        mockMvc.perform(get("/api/sessions/{id}/results", teamFinal))
                .andExpect(jsonPath("$.apparatus", empty()))
                .andExpect(jsonPath("$.teams[0].noc").value("CHN"))
                .andExpect(jsonPath("$.teams[0].total").value(168.498))
                .andExpect(jsonPath("$.teams[0].apparatusTotals.BB").value(44.899));
    }

    @Test
    void testFindResults_Unknown_NotFound() throws Exception {
        mockMvc.perform(get("/api/sessions/{id}/results", -1)).andExpect(status().isNotFound());
    }
}
