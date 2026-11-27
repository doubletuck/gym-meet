package doubletuck.meet.controller;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.importer.EventImporter;
import doubletuck.meet.repository.ScoreRepository;
import doubletuck.meet.repository.CompetitionRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.empty;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class CompetitionControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private EventImporter eventImporter;

    @Autowired
    private CompetitionRepository competitionRepository;

    @Autowired
    private ScoreRepository scoreRepository;

    @Test
    void testFindResults_ApparatusFinalRankedAsPublished() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_WAG);
        Long beamFinal = id(Discipline.WAG, CompetitionType.C3, Apparatus.BB, null);

        mockMvc.perform(get("/api/competitions/{id}/results", beamFinal))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "max-age=300, public"))
                .andExpect(jsonPath("$.event.slug").value("2026-world-championships"))
                .andExpect(jsonPath("$.competition.slug").value("beam-final"))
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
        Long qualification = id(Discipline.WAG, CompetitionType.C1, null, null);

        mockMvc.perform(get("/api/competitions/{id}/results", qualification))
                .andExpect(jsonPath("$.competition.name").value("Qualification"))
                .andExpect(jsonPath("$.competition.type").value("C1"))
                .andExpect(jsonPath("$.competition.purposes.team").value("QUALIFYING"))
                .andExpect(jsonPath("$.competition.purposes.allAround").value("QUALIFYING"))
                .andExpect(jsonPath("$.competition.purposes.apparatus").value("QUALIFYING"))
                .andExpect(jsonPath("$.apparatus[*].apparatus", contains("VT", "UB", "BB", "FX")))
                .andExpect(jsonPath("$.teams[0].noc").value("CHN"))
                .andExpect(jsonPath("$.teams[0].rankStatus").value("RANKED"))
                // FIG entry lists name no clubs
                .andExpect(jsonPath("$.allAround[0].club").value(nullValue()))
                .andExpect(jsonPath("$.teams[0].rank").value(1))
                .andExpect(jsonPath("$.teams[0].total").value(164.996))
                .andExpect(jsonPath("$.teams[0].qualification").value("Q"))
                .andExpect(jsonPath("$.teams[0].apparatusTotals[?(@.apparatus == 'BB')].total").value(43.966))
                // Each member's scores, in bib order: the three best on beam count, the fourth is dropped
                .andExpect(jsonPath("$.teams[0].members[*].athlete.surname",
                        contains("Du", "Ke", "Qiu", "Zhang", "Zhang")))
                .andExpect(jsonPath("$.teams[0].members[3].athlete.givenName").value("Yihan"))
                .andExpect(jsonPath("$.teams[0].members[3].noc").value("CHN"))
                .andExpect(jsonPath("$.teams[0].members[3].scores[?(@.apparatus == 'BB')].score").value(13.266))
                .andExpect(jsonPath("$.teams[0].members[3].scores[?(@.apparatus == 'BB')].role").value("DROPPED"))
                .andExpect(jsonPath("$.teams[0].members[4].scores[?(@.apparatus == 'BB')].score").value(15.1))
                .andExpect(jsonPath("$.teams[0].members[4].scores[?(@.apparatus == 'BB')].role").value("COUNTING"))
                .andExpect(jsonPath("$.allAround[?(@.athlete.surname == 'Nemour')].total").value(55.999))
                .andExpect(jsonPath("$.allAround[?(@.athlete.surname == 'Nemour')].apparatusScores.UB")
                        .value(14.933))
                .andExpect(jsonPath("$.apparatus[2].scores[?(@.athlete.givenName == 'Yihan')].teamRole")
                        .value("DROPPED"))
                .andExpect(jsonPath("$.apparatus[2].scores[?(@.athlete.surname == 'Ke')].qualification")
                        .value("NR"));
    }

    @Test
    void testFindResults_TwoVaultEntryAndDidNotStart() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_MAG);
        Long qualification = id(Discipline.MAG, CompetitionType.C1, null, null);

        // MAG apparatus order: FX, PH, SR, VT, PB, HB
        mockMvc.perform(get("/api/competitions/{id}/results", qualification))
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
    void testFindResults_SplitCompetitionCombinedStandings() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);
        Long whole = id(Discipline.MAG, CompetitionType.C1, null, null);

        mockMvc.perform(get("/api/competitions/{id}/results", whole))
                // Competition I decided every title: it's named a final
                .andExpect(jsonPath("$.competition.slug").value("all-around-and-apparatus-final"))
                .andExpect(jsonPath("$.competition.name").value("All-Around and Apparatus Final"))
                .andExpect(jsonPath("$.competition.shortName").value("Final"))
                .andExpect(jsonPath("$.competition.purposes.allAround").value("FINAL"))
                .andExpect(jsonPath("$.competition.purposes.team").value(nullValue()))
                .andExpect(jsonPath("$.apparatus", empty()))
                .andExpect(jsonPath("$.allAround[0].athlete.surname").value("Moldauer"))
                .andExpect(jsonPath("$.allAround[0].total").value(163.896))
                .andExpect(jsonPath("$.apparatusStandings[?(@.apparatus == 'PH')].rows[?(@.athlete.surname == "
                        + "'Hoopes')].total").value(30.816));
    }

    @Test
    void testFindResults_SplitCompetitionCombinedRow_HasEachPart() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);
        Long whole = id(Discipline.MAG, CompetitionType.C1, null, null);

        mockMvc.perform(get("/api/competitions/{id}/results", whole))
                .andExpect(jsonPath("$.competition.date").value("2026-08-06"))
                .andExpect(jsonPath("$.competition.endDate").value("2026-08-08"))
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
    void testFindResults_SplitCompetitionCombinedRow_ApparatusSkippedInAPart_ShowsTheOtherPartAlone()
            throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);
        Long whole = id(Discipline.MAG, CompetitionType.C1, null, null);
        Long partTwo = id(Discipline.MAG, CompetitionType.C1, null, 2);
        // As if Moldauer hadn't vaulted on day 2
        scoreRepository.delete(scoreRepository.findByCompetitionId(partTwo).stream()
                .filter(score -> score.getApparatus() == Apparatus.VT
                        && score.getParticipant().getAthlete().getSurname().equals("Moldauer"))
                .findFirst().orElseThrow());

        mockMvc.perform(get("/api/competitions/{id}/results", whole))
                .andExpect(jsonPath("$.allAround[0].apparatusScores.VT").value(13.75))
                .andExpect(jsonPath("$.allAround[0].parts[0].apparatusScores.VT").value(13.75))
                .andExpect(jsonPath("$.allAround[0].parts[1].apparatusScores.VT").doesNotExist());
    }

    @Test
    void testFindResults_SplitCompetitionPart_HasNoParts() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.US_MAG);
        Long partOne = id(Discipline.MAG, CompetitionType.C1, null, 1);

        mockMvc.perform(get("/api/competitions/{id}/results", partOne))
                .andExpect(jsonPath("$.competition.endDate").value(nullValue()))
                // Named after the whole competition; its own rankings decide nothing
                .andExpect(jsonPath("$.competition.slug").value("all-around-and-apparatus-final-part-1"))
                .andExpect(jsonPath("$.competition.name").value("All-Around and Apparatus Final, Part 1"))
                .andExpect(jsonPath("$.competition.purposes.allAround").value("INFORMATIONAL"))
                .andExpect(jsonPath("$.allAround[?(@.athlete.surname == 'Moldauer')].apparatusScores.FX")
                        .value(13.7))
                .andExpect(jsonPath("$.allAround[0].parts", empty()))
                .andExpect(jsonPath("$.apparatus[0].scores[?(@.athlete.surname == 'Moldauer')].club")
                        .value("U of Oklahoma"));
    }

    @Test
    void testFindResults_FinalRankingsOfTheQualificationsRoutines_ShownWithTheQualification() throws Exception {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.ASIAN_WAG);
        Long qualification = id(Discipline.WAG, CompetitionType.C1, null, null);
        // The team and all-around finals had no routines of their own, so they're rankings, not competitions
        assertThat(competitionRepository.findAll()).noneMatch(competition -> competition.getType() == CompetitionType.C2
                || competition.getType() == CompetitionType.C4);

        mockMvc.perform(get("/api/competitions/{id}/results", qualification))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.competition.slug").value("qualification"))
                .andExpect(jsonPath("$.competition.name")
                        .value("Team and All-Around Final · Apparatus Qualification"))
                .andExpect(jsonPath("$.competition.purposes.team").value("FINAL"))
                .andExpect(jsonPath("$.competition.purposes.allAround").value("FINAL"))
                .andExpect(jsonPath("$.apparatus", not(empty())))
                .andExpect(jsonPath("$.allAround", hasSize(7)))
                .andExpect(jsonPath("$.allAround[?(@.athlete.surname == 'Yeap')].rank").value(9))
                // Two MAS gymnasts ranked ahead of her: unranked under the two-per-country limit
                .andExpect(jsonPath("$.allAround[?(@.athlete.surname == 'Seow')].rankStatus").value("NOC_LIMIT"))
                .andExpect(jsonPath("$.allAround[0].athlete.surname").value("Ke"))
                .andExpect(jsonPath("$.allAround[0].apparatusScores.BB").value(14.933))
                .andExpect(jsonPath("$.allAround[0].qualification").value(nullValue()))
                .andExpect(jsonPath("$.teams[0].noc").value("CHN"))
                .andExpect(jsonPath("$.teams[0].total").value(168.498))
                .andExpect(jsonPath("$.teams[0].apparatusTotals[?(@.apparatus == 'BB')].total").value(44.899));
    }

    @Test
    void testFindResults_Unknown_NotFound() throws Exception {
        mockMvc.perform(get("/api/competitions/{id}/results", -1)).andExpect(status().isNotFound());
    }

    private Long id(Discipline discipline, CompetitionType type, Apparatus apparatus, Integer part) {
        return ApiTestFixtures.competitionId(competitionRepository, discipline, type, apparatus, part);
    }
}
