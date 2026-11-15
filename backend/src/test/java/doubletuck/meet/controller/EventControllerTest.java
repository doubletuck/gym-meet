package doubletuck.meet.controller;

import doubletuck.meet.importer.EventImporter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@Transactional
class EventControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private EventImporter eventImporter;

    @BeforeEach
    void setUp() {
        ApiTestFixtures.load(eventImporter, ApiTestFixtures.WORLDS_WAG, ApiTestFixtures.WORLDS_MAG);
    }

    @Test
    void testFindEvents_ListsEventsWithTheirDivisions() throws Exception {
        mockMvc.perform(get("/api/events"))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "max-age=300, public"))
                .andExpect(jsonPath("$", hasSize(1)))
                .andExpect(jsonPath("$[0].slug").value("2026-world-championships"))
                .andExpect(jsonPath("$[0].level").value("WORLD_CHAMPIONSHIPS"))
                .andExpect(jsonPath("$[0].divisions[*].discipline", contains("MAG", "WAG")));
    }

    @Test
    void testFindEvents_Filters() throws Exception {
        mockMvc.perform(get("/api/events").param("year", "2026")).andExpect(jsonPath("$", hasSize(1)));
        mockMvc.perform(get("/api/events").param("year", "2025")).andExpect(jsonPath("$", hasSize(0)));
        mockMvc.perform(get("/api/events").param("level", "WORLD_CUP")).andExpect(jsonPath("$", hasSize(0)));
        mockMvc.perform(get("/api/events").param("discipline", "WAG")).andExpect(jsonPath("$", hasSize(1)));
    }

    @Test
    void testFindEvent_SessionsGroupedByDivisionInCompetitionOrder() throws Exception {
        mockMvc.perform(get("/api/events/2026-world-championships"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.title").value("54th Artistic Gymnastics World Championships"))
                .andExpect(jsonPath("$.apparatusSuppliers").value("Spieth"))
                .andExpect(jsonPath("$.divisions[1].discipline").value("WAG"))
                .andExpect(jsonPath("$.divisions[1].sessions[*].slug",
                        contains("qualification", "team-final", "all-around-final", "uneven-bars-final",
                                "beam-final")))
                .andExpect(jsonPath("$.divisions[1].sessions[0].date").value("2026-10-18"));
    }

    @Test
    void testFindEvent_Unknown_NotFound() throws Exception {
        mockMvc.perform(get("/api/events/no-such-event")).andExpect(status().isNotFound());
    }

    @Test
    void testCreate_WithoutLogin_Unauthorized() throws Exception {
        mockMvc.perform(post("/api/events").contentType(MediaType.APPLICATION_JSON).content("{}"))
                .andExpect(status().isUnauthorized());
    }
}
