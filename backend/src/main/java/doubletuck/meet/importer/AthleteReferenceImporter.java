package doubletuck.meet.importer;

import doubletuck.meet.domain.Athlete;
import doubletuck.meet.domain.AthleteNameVariant;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.repository.AthleteNameVariantRepository;
import doubletuck.meet.repository.AthleteRepository;
import doubletuck.meet.repository.ParticipantRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.file.Files;
import java.nio.file.Path;
import java.text.Normalizer;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * Fills in athletes' FIG licenses and birth dates from the athlete reference
 * files: the hand-curated {@code ATHLETES.csv}, then {@code FIG-LICENSES.csv},
 * FIG's licenses as {@code fig_athletes.py} keeps them.
 *
 * <p>It runs after the results are imported, and only adds to athletes they
 * created: it never creates an athlete or changes a value already recorded. A
 * row finds its athlete by license, or else by name and discipline (or a known
 * name variant) where exactly one such athlete has competed for the row's
 * country. A row that disagrees with what is recorded is reported, not applied.
 */
@Service
public class AthleteReferenceImporter {

    static final String ATHLETES = "ATHLETES.csv";
    static final String FIG_LICENSES = "FIG-LICENSES.csv";

    // Entry-list codes for athletes whom FIG lists under another federation's: home nations and
    // Crown dependencies, and neutral athletes (AIN; WG1/WG2 and AIN1/AIN2 at some meets), from any.
    private static final Map<String, Set<String>> FEDERATIONS = Map.of(
            "ENG", Set.of("GBR"), "SCO", Set.of("GBR"), "WAL", Set.of("GBR"), "NIR", Set.of("GBR", "IRL"),
            "IOM", Set.of("GBR"), "JEY", Set.of("GBR"), "GUE", Set.of("GBR"));
    private static final Set<String> NEUTRAL = Set.of("AIN", "AIN1", "AIN2", "WG1", "WG2");

    private final AthleteRepository athleteRepository;
    private final AthleteNameVariantRepository nameVariantRepository;
    private final ParticipantRepository participantRepository;

    AthleteReferenceImporter(AthleteRepository athleteRepository,
            AthleteNameVariantRepository nameVariantRepository, ParticipantRepository participantRepository) {
        this.athleteRepository = athleteRepository;
        this.nameVariantRepository = nameVariantRepository;
        this.participantRepository = participantRepository;
    }

    /**
     * Applies {@code ATHLETES.csv} and {@code FIG-LICENSES.csv} from a directory, whichever it has.
     */
    @Transactional
    public ImportReport importDirectory(Path directory) {
        List<Path> files = List.of(directory.resolve(ATHLETES), directory.resolve(FIG_LICENSES)).stream()
                .filter(Files::isRegularFile)
                .toList();
        if (files.isEmpty()) {
            throw new ImportException("No " + ATHLETES + " or " + FIG_LICENSES + " in " + directory);
        }
        ImportReport report = new ImportReport(directory.getFileName() + " (athlete reference)");
        Athletes athletes = new Athletes();
        for (Path file : files) {
            for (CsvRow row : CsvRow.read(file)) {
                apply(row, athletes, report);
            }
        }
        return report;
    }

    private void apply(CsvRow row, Athletes athletes, ImportReport report) {
        Discipline discipline = row.requiredCode("Discipline", Discipline::find);
        String noc = row.requiredText("NOC Code");
        String surname = row.requiredText("Surname");
        String givenName = row.requiredText("Given Name");
        String license = row.text("FIG License");
        LocalDate birthDate = row.date("Birth Date");
        String who = surname + " " + givenName + " (" + noc + ")";

        Athlete athlete = license != null ? athletes.byLicense.get(license) : null;
        if (athlete != null && athlete.getDiscipline() != discipline) {
            report.warn(row.location() + ": FIG license " + license + " is " + discipline + " here, but "
                    + athlete.getDiscipline() + " athlete " + name(athlete) + " in the database");
            return;
        }
        if (athlete == null) {
            Set<Athlete> named = athletes.named(discipline, surname, givenName, noc);
            if (named.size() > 1) {
                report.warn(row.location() + ": " + who + " matches " + named.size() + " athletes; not applied");
                return;
            }
            athlete = named.isEmpty() ? null : named.iterator().next();
            if (athlete != null && license != null && athlete.getLicenseNumber() != null) {
                report.warn(row.location() + ": " + name(athlete) + " is recorded with FIG license "
                        + athlete.getLicenseNumber() + ", not " + license + "; not applied");
                return;
            }
        }
        if (athlete == null) {
            report.count("rows with no athlete");
            return;
        }
        report.count("athletes found");

        if (license != null && athlete.getLicenseNumber() == null) {
            athlete.setLicenseNumber(license);
            athletes.byLicense.put(license, athlete);
            report.count("licenses added");
        }
        if (birthDate == null) {
            return;
        }
        if (athlete.getBirthDate() != null) {
            if (!athlete.getBirthDate().equals(birthDate)) {
                report.warn(row.location() + ": " + name(athlete) + " is recorded as born " + athlete.getBirthDate()
                        + ", not " + birthDate);
            }
        } else if (athlete.getBirthYear() != null && athlete.getBirthYear() != birthDate.getYear()) {
            report.warn(row.location() + ": " + name(athlete) + " is recorded as born in " + athlete.getBirthYear()
                    + ", not " + birthDate);
        } else {
            athlete.setBirthDate(birthDate);
            report.count("birth dates added");
            if (athlete.getBirthYear() == null) {
                athlete.setBirthYear((short) birthDate.getYear());
                report.count("birth years added");
            }
        }
    }

    /** Every athlete, by license and by name, with the countries each has competed for. */
    private class Athletes {

        private final Map<String, Athlete> byLicense = new HashMap<>();
        private final Map<String, Set<Athlete>> byName = new HashMap<>();
        private final Map<Long, Set<String>> nocs = new HashMap<>();

        Athletes() {
            for (Athlete athlete : athleteRepository.findAll()) {
                if (athlete.getLicenseNumber() != null) {
                    byLicense.put(athlete.getLicenseNumber(), athlete);
                }
                byName.computeIfAbsent(key(athlete.getDiscipline(), athlete.getSurname(), athlete.getGivenName()),
                        k -> new LinkedHashSet<>()).add(athlete);
            }
            for (AthleteNameVariant variant : nameVariantRepository.findAll()) {
                Athlete athlete = variant.getAthlete();
                byName.computeIfAbsent(key(athlete.getDiscipline(), variant.getSurname(), variant.getGivenName()),
                        k -> new LinkedHashSet<>()).add(athlete);
            }
            for (Participant participant : participantRepository.findAll()) {
                nocs.computeIfAbsent(participant.getAthlete().getId(), k -> new HashSet<>()).add(participant.getNoc());
            }
        }

        Set<Athlete> named(Discipline discipline, String surname, String givenName, String noc) {
            Set<Athlete> found = new LinkedHashSet<>();
            for (Athlete athlete : byName.getOrDefault(key(discipline, surname, givenName), Set.of())) {
                if (nocs.getOrDefault(athlete.getId(), Set.of()).stream().anyMatch(entered -> sameCountry(entered, noc))) {
                    found.add(athlete);
                }
            }
            return found;
        }
    }

    static boolean sameCountry(String entered, String federation) {
        return entered.equals(federation) || NEUTRAL.contains(entered)
                || FEDERATIONS.getOrDefault(entered, Set.of()).contains(federation);
    }

    // A name compared without case or accents
    private static String key(Discipline discipline, String surname, String givenName) {
        String name = (surname + "|" + givenName).toLowerCase(Locale.ROOT);
        return discipline + "|" + Normalizer.normalize(name, Normalizer.Form.NFKD).replaceAll("\\p{M}", "");
    }

    private static String name(Athlete athlete) {
        return athlete.getSurname() + " " + athlete.getGivenName() + " (id " + Objects.toString(athlete.getId()) + ")";
    }
}
