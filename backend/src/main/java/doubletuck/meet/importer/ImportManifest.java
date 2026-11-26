package doubletuck.meet.importer;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.json.JsonMapper;

import java.nio.file.Path;
import java.time.LocalDate;
import java.util.List;

/**
 * An {@code <PREFIX>-IMPORT.json} manifest: the event's metadata plus the files
 * holding one discipline and age category's results.
 */
public record ImportManifest(
        ManifestEvent event,
        List<String> participants,
        List<String> judges,
        List<String> scores,
        List<String> rankings) {

    /**
     * @param slug            the event's address; optional, see EventImporter for the default
     * @param teamFormat      where the team title was decided: {@code C1}, {@code FINAL} or {@code NONE}
     * @param aaFormat        likewise the all-around title
     * @param apparatusFormat likewise the apparatus titles
     */
    public record ManifestEvent(
            String slug,
            String title,
            String shortName,
            String disciplines,
            String ageCategory,
            String level,
            LocalDate startDate,
            LocalDate endDate,
            String city,
            String country,
            String figEventNumber,
            String venue,
            String apparatusSuppliers,
            String teamFormat,
            String aaFormat,
            String apparatusFormat) {
    }

    private static final JsonMapper MAPPER = JsonMapper.builder().build();

    public static ImportManifest read(Path file) {
        try {
            ImportManifest manifest = MAPPER.readValue(file.toFile(), ImportManifest.class);
            if (manifest.event() == null) {
                throw new ImportException(file + ": manifest has no event");
            }
            return manifest;
        } catch (JacksonException e) {
            throw new ImportException("Unable to read " + file + ": " + e.getOriginalMessage(), e);
        }
    }

    public List<String> participants() {
        return participants == null ? List.of() : participants;
    }

    public List<String> judges() {
        return judges == null ? List.of() : judges;
    }

    public List<String> scores() {
        return scores == null ? List.of() : scores;
    }

    public List<String> rankings() {
        return rankings == null ? List.of() : rankings;
    }
}
