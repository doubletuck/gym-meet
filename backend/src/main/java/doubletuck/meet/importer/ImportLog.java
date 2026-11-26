package doubletuck.meet.importer;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.ImportRun;
import doubletuck.meet.repository.ImportRunRepository;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.stream.Stream;

/**
 * Records each manifest imported, and tells whether a manifest's files have
 * changed since it was last imported.
 */
@Component
public class ImportLog {

    /** {@code REMOVED}: imported, then deleted with a slice it depends on (a mixed team with the MAG slice). */
    public enum State {
        NOT_IMPORTED, UP_TO_DATE, CHANGED, REMOVED
    }

    /** @param lastRun null when never imported */
    public record Status(State state, ImportRun lastRun) {
    }

    // A run's content hash when the slice was deleted with another; never a SHA-256
    private static final String REMOVED = "removed";

    private final ImportRunRepository importRunRepository;

    ImportLog(ImportRunRepository importRunRepository) {
        this.importRunRepository = importRunRepository;
    }

    void record(Path manifestFile, ImportManifest manifest, Event event, Discipline discipline,
            AgeCategory ageCategory, boolean replaced, ImportReport report) {
        ImportRun run = new ImportRun();
        run.setManifest(manifestFile.getFileName().toString());
        run.setEvent(event);
        run.setDiscipline(discipline);
        run.setAgeCategory(ageCategory);
        run.setContentHash(contentHash(manifestFile, manifest));
        run.setReplaced(replaced);
        run.setWarningCount(report.getWarnings().size());
        run.setReport(report.summary());
        importRunRepository.save(run);
    }

    /**
     * Records that a slice imported earlier was deleted along with another, so its manifest shows as
     * needing to be imported again.
     */
    void removed(Event event, Discipline discipline, AgeCategory ageCategory, String reason) {
        importRunRepository.findFirstByEventAndDisciplineAndAgeCategoryOrderByIdDesc(event, discipline, ageCategory)
                .ifPresent(last -> {
                    ImportRun run = new ImportRun();
                    run.setManifest(last.getManifest());
                    run.setEvent(event);
                    run.setDiscipline(discipline);
                    run.setAgeCategory(ageCategory);
                    run.setContentHash(REMOVED);
                    run.setReplaced(true);
                    run.setReport(reason);
                    importRunRepository.save(run);
                });
    }

    public Status status(Path manifestFile) {
        return importRunRepository.findFirstByManifestOrderByIdDesc(manifestFile.getFileName().toString())
                .map(run -> run.getContentHash().equals(REMOVED) ? new Status(State.REMOVED, run)
                        : new Status(run.getContentHash().equals(
                        contentHash(manifestFile, ImportManifest.read(manifestFile))) ? State.UP_TO_DATE
                        : State.CHANGED, run))
                .orElse(new Status(State.NOT_IMPORTED, null));
    }

    /** SHA-256 of the manifest and every file it lists, in the order it lists them. */
    static String contentHash(Path manifestFile, ImportManifest manifest) {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
        List<Path> files = new ArrayList<>();
        files.add(manifestFile);
        Stream.of(manifest.participants(), manifest.scores(), manifest.rankings(), manifest.judges())
                .flatMap(List::stream)
                .map(manifestFile.getParent()::resolve)
                .forEach(files::add);
        files.forEach(file -> {
            try {
                digest.update(Files.readAllBytes(file));
            } catch (IOException e) {
                throw new UncheckedIOException("Unable to read " + file, e);
            }
        });
        return HexFormat.of().formatHex(digest.digest());
    }
}
