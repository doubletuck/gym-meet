package doubletuck.meet.controller;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.importer.EventImporter;
import doubletuck.meet.repository.CompetitionRepository;

import java.net.URISyntaxException;
import java.nio.file.Path;
import java.util.Objects;

/** Loads the importer's real-data fixtures for the API tests. */
final class ApiTestFixtures {

    static final String WORLDS_WAG = "worlds/2026-WORLD-CHAMPIONSHIPS-WAG-SR-IMPORT.json";
    static final String WORLDS_MAG = "worlds/2026-WORLD-CHAMPIONSHIPS-MAG-SR-IMPORT.json";
    static final String US_MAG = "us/2026-US-CHAMPIONSHIPS-MAG-SR-IMPORT.json";
    static final String ASIAN_WAG = "asian/2026-ASIAN-CHAMPIONSHIPS-WAG-SR-IMPORT.json";
    static final String YOG_MAG = "yog/2026-YOUTH-OLYMPIC-GAMES-MAG-JR-IMPORT.json";
    static final String YOG_WAG = "yog/2026-YOUTH-OLYMPIC-GAMES-WAG-JR-IMPORT.json";
    static final String YOG_MIX = "yog/2026-YOUTH-OLYMPIC-GAMES-MIX-JR-IMPORT.json";

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

    static Long competitionId(CompetitionRepository repository, Discipline discipline, CompetitionType type,
            Apparatus apparatus, Integer part) {
        return repository.findAll().stream()
                .filter(c -> c.getDiscipline() == discipline && c.getType() == type
                        && c.getApparatus() == apparatus && Objects.equals(c.getPart(), part))
                .map(Competition::getId)
                .findFirst()
                .orElseThrow(() -> new AssertionError("no " + discipline + " " + type + " competition"));
    }
}
