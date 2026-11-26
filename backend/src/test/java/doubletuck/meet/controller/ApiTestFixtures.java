package doubletuck.meet.controller;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.Round;
import doubletuck.meet.importer.EventImporter;
import doubletuck.meet.repository.CompetitionRepository;
import doubletuck.meet.service.CompetitionNaming;

import java.net.URISyntaxException;
import java.nio.file.Path;
import java.util.List;
import java.util.Objects;

/** Loads the importer's real-data fixtures for the API tests. */
final class ApiTestFixtures {

    static final String WORLDS_WAG = "worlds/2026-WORLD-CHAMPIONSHIPS-WAG-SR-IMPORT.json";
    static final String WORLDS_MAG = "worlds/2026-WORLD-CHAMPIONSHIPS-MAG-SR-IMPORT.json";
    static final String US_MAG = "us/2026-US-CHAMPIONSHIPS-MAG-SR-IMPORT.json";
    static final String ASIAN_WAG = "asian/2026-ASIAN-CHAMPIONSHIPS-WAG-SR-IMPORT.json";

    private ApiTestFixtures() {
    }

    static void load(EventImporter importer, String... manifests) {
        for (String manifest : manifests) {
            try {
                importer.importManifest(Path.of(ApiTestFixtures.class.getResource("/import/" + manifest).toURI()),
                        false);
            } catch (URISyntaxException e) {
                throw new IllegalStateException(e);
            }
        }
    }

    /** By the round the API names the session by. */
    static Long sessionId(CompetitionRepository repository, Discipline discipline, Round round, Apparatus apparatus,
            Integer part) {
        List<Competition> all = repository.findAll();
        return all.stream()
                .filter(s -> s.getDiscipline() == discipline && CompetitionNaming.legacyRound(s, all) == round
                        && s.getApparatus() == apparatus && Objects.equals(s.getPart(), part))
                .map(Competition::getId)
                .findFirst()
                .orElseThrow(() -> new AssertionError("no " + discipline + " " + round + " session"));
    }
}
