package doubletuck.meet.importer;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

/**
 * Imports results from the command line under the {@code import} profile:
 * {@code --import.path=<manifest, or a directory searched for *-IMPORT.json>}
 * (repeatable) and optionally {@code --import.replace}. Each manifest is
 * imported on its own, so one failing doesn't stop the rest; the run fails if
 * any did. With {@code --import.status}, nothing is imported: each manifest is
 * reported as imported and up to date, changed since, or not imported.
 */
@Component
@Profile("import")
class ImportRunner implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(ImportRunner.class);

    private final EventImporter eventImporter;
    private final ImportLog importLog;

    ImportRunner(EventImporter eventImporter, ImportLog importLog) {
        this.eventImporter = eventImporter;
        this.importLog = importLog;
    }

    @Override
    public void run(ApplicationArguments args) {
        List<String> paths = args.getOptionValues("import.path");
        if (paths == null || paths.isEmpty()) {
            throw new IllegalArgumentException("--import.path is required");
        }
        boolean replace = args.containsOption("import.replace");

        List<Path> manifests = paths.stream().flatMap(path -> manifests(Path.of(path))).toList();
        if (manifests.isEmpty()) {
            throw new IllegalArgumentException("No *-IMPORT.json manifests found under " + paths);
        }
        if (args.containsOption("import.status")) {
            manifests.forEach(manifest -> log.info(status(manifest)));
            return;
        }

        List<String> failures = new ArrayList<>();
        for (Path manifest : manifests) {
            try {
                log.info("Imported {}", eventImporter.importManifest(manifest, replace).summary());
            } catch (RuntimeException e) {
                log.error("Failed to import {}: {}", manifest.getFileName(), e.getMessage());
                failures.add(manifest.getFileName().toString());
            }
        }
        log.info("Imported {} of {} manifests", manifests.size() - failures.size(), manifests.size());
        if (!failures.isEmpty()) {
            throw new IllegalStateException("Failed to import " + failures);
        }
    }

    private String status(Path manifest) {
        ImportLog.Status status = importLog.status(manifest);
        String name = manifest.getFileName().toString();
        return switch (status.state()) {
            case NOT_IMPORTED -> name + ": not imported";
            case UP_TO_DATE -> name + ": up to date, imported " + status.lastRun().getCreationTimestamp();
            case CHANGED -> name + ": changed since it was imported " + status.lastRun().getCreationTimestamp();
            case REMOVED -> name + ": " + status.lastRun().getReport();
        };
    }

    private static Stream<Path> manifests(Path path) {
        if (Files.isRegularFile(path)) {
            return Stream.of(path);
        }
        try (Stream<Path> files = Files.walk(path)) {
            // A mixed team's manifest after the rest: it uses the MAG and WAG slices' entries and Competition I
            return files.filter(file -> file.getFileName().toString().endsWith("-IMPORT.json"))
                    .sorted(Comparator.comparing((Path file) -> file.getFileName().toString().contains("-MIX-"))
                            .thenComparing(Comparator.naturalOrder()))
                    .toList()
                    .stream();
        } catch (IOException e) {
            throw new UncheckedIOException("Unable to search " + path, e);
        }
    }
}
