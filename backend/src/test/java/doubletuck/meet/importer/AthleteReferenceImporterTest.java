package doubletuck.meet.importer;

import doubletuck.meet.domain.Athlete;
import doubletuck.meet.domain.AthleteNameVariant;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.EntryStatus;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.repository.AthleteNameVariantRepository;
import doubletuck.meet.repository.AthleteRepository;
import doubletuck.meet.repository.EventRepository;
import doubletuck.meet.repository.ParticipantRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
@Import(AthleteReferenceImporter.class)
class AthleteReferenceImporterTest {

    private static final String FIG_HEADER = "FIG License,Gymnast ID,Discipline,Surname,Given Name,NOC Code,"
            + "Birth Date,Licensed On,Valid To,First Seen,Last Seen\n";
    private static final String ATHLETES_HEADER = "Discipline,NOC Code,FIG License,Surname,Given Name,Birth Date,"
            + "Source,Note\n";

    @TempDir
    private Path dir;

    @Autowired
    private AthleteReferenceImporter importer;

    @Autowired
    private AthleteRepository athleteRepository;

    @Autowired
    private AthleteNameVariantRepository nameVariantRepository;

    @Autowired
    private EventRepository eventRepository;

    @Autowired
    private ParticipantRepository participantRepository;

    private Event event;

    @BeforeEach
    void setUp() {
        event = new Event();
        event.setTitle("Asian Games");
        event.setShortName("Asian Games");
        event.setSlug("asian-games");
        event.setStartDate(LocalDate.of(2026, 9, 21));
        event.setEndDate(LocalDate.of(2026, 10, 4));
        event.setCity("Nagoya");
        event.setCountryCode("JPN");
        event.setLevel(EventLevel.CONTINENTAL_CHAMPIONSHIPS);
        event = eventRepository.save(event);
    }

    @Test
    void testImport_ByLicense_FillsInBirthDate() throws IOException {
        Athlete ghadimi = entered("GHADIMI", "Mehrdad", "70193", (short) 2003, "QAT");
        fig("70193,111770,MAG,GHADIMI,Mehrdad,QAT,2003-06-16,2026-06-08,2028-06-08,2026-11-27,2026-11-27");

        ImportReport report = importer.importDirectory(dir);

        assertEquals(LocalDate.of(2003, 6, 16), ghadimi.getBirthDate());
        assertEquals(1, report.getCount("birth dates added"));
        assertEquals(0, report.getWarnings().size());
    }

    @Test
    void testImport_ByNameAndCountry_AddsLicenseAndBirthDate() throws IOException {
        Athlete ghadimi = entered("Ghadimi", "Mehrdad", null, null, "QAT");
        fig("70193,111770,MAG,GHADIMI,Mehrdad,QAT,2003-06-16,2026-06-08,2028-06-08,2026-11-27,2026-11-27");

        ImportReport report = importer.importDirectory(dir);

        assertEquals("70193", ghadimi.getLicenseNumber());
        assertEquals(LocalDate.of(2003, 6, 16), ghadimi.getBirthDate());
        assertEquals(Short.valueOf((short) 2003), ghadimi.getBirthYear());
        assertEquals(1, report.getCount("licenses added"));
    }

    @Test
    void testImport_ByNameVariantUnderHomeNation_IsFound() throws IOException {
        Athlete jarman = entered("Jarman", "Jake", null, null, "ENG");
        AthleteNameVariant variant = new AthleteNameVariant();
        variant.setAthlete(jarman);
        variant.setSurname("Jarmann");
        variant.setGivenName("Jake");
        nameVariantRepository.save(variant);
        fig("40001,1,MAG,JARMANN,Jake,GBR,2001-12-03,2026-01-01,2028-01-01,2026-11-27,2026-11-27");

        importer.importDirectory(dir);

        assertEquals(LocalDate.of(2001, 12, 3), jarman.getBirthDate());
    }

    @Test
    void testImport_SameNameOtherCountry_IsNotApplied() throws IOException {
        Athlete ali = entered("Ahmed", "Ali", null, null, "EGY");
        fig("40002,2,MAG,AHMED,Ali,QAT,2001-01-01,2026-01-01,2028-01-01,2026-11-27,2026-11-27");

        ImportReport report = importer.importDirectory(dir);

        assertNull(ali.getBirthDate());
        assertNull(ali.getLicenseNumber());
        assertEquals(1, report.getCount("rows with no athlete"));
    }

    @Test
    void testImport_Conflicts_AreReportedAndNothingIsOverwritten() throws IOException {
        Athlete marques = entered("Marques", "Marcelo", "40989", (short) 2001, "POR");
        marques.setBirthDate(LocalDate.of(2001, 11, 15));
        Athlete ghadimi = entered("Ghadimi", "Mehrdad", "70193", (short) 2004, "QAT");
        Athlete other = entered("Reis", "Joana", "1", null, "POR");
        fig("40989,3,MAG,MARQUES,Marcelo,POR,2001-11-16,2026-01-01,2028-01-01,2026-11-27,2026-11-27\n"
                + "70193,111770,MAG,GHADIMI,Mehrdad,QAT,2003-06-16,2026-06-08,2028-06-08,2026-11-27,2026-11-27\n"
                + "57980,4,MAG,REIS,Joana,POR,2009-02-24,2026-01-01,2028-01-01,2026-11-27,2026-11-27");

        ImportReport report = importer.importDirectory(dir);

        assertEquals(LocalDate.of(2001, 11, 15), marques.getBirthDate());
        assertNull(ghadimi.getBirthDate());
        assertEquals("1", other.getLicenseNumber());
        assertEquals(3, report.getWarnings().size(), report.summary());
        assertTrue(report.getWarnings().get(0).contains("born 2001-11-15, not 2001-11-16"), report.summary());
        assertTrue(report.getWarnings().get(1).contains("born in 2004, not 2003-06-16"), report.summary());
        assertTrue(report.getWarnings().get(2).contains("FIG license 1, not 57980"), report.summary());
    }

    @Test
    void testImport_HandCuratedFileComesFirst() throws IOException {
        Athlete ali = entered("Ahmed", "Ali", null, (short) 2001, "QAT");
        Files.writeString(dir.resolve(AthleteReferenceImporter.ATHLETES),
                ATHLETES_HEADER + "MAG,QAT,,Ahmed,Ali,2001-05-05,Qatar federation,\n");
        fig("40002,2,MAG,AHMED,Ali,QAT,2001-05-06,2026-01-01,2028-01-01,2026-11-27,2026-11-27");

        ImportReport report = importer.importDirectory(dir);

        assertEquals(LocalDate.of(2001, 5, 5), ali.getBirthDate());
        assertEquals("40002", ali.getLicenseNumber());
        assertEquals(1, report.getWarnings().size(), report.summary());
    }

    @Test
    void testImport_NoReferenceFiles_Fails() {
        assertThrows(ImportException.class, () -> importer.importDirectory(dir));
    }

    @Test
    void testSameCountry() {
        assertTrue(AthleteReferenceImporter.sameCountry("QAT", "QAT"));
        assertTrue(AthleteReferenceImporter.sameCountry("NIR", "IRL"));
        assertTrue(AthleteReferenceImporter.sameCountry("AIN", "BLR"));
        assertFalse(AthleteReferenceImporter.sameCountry("QAT", "BRN"));
    }

    private void fig(String rows) throws IOException {
        Files.writeString(dir.resolve(AthleteReferenceImporter.FIG_LICENSES), FIG_HEADER + rows + "\n");
    }

    private Athlete entered(String surname, String givenName, String license, Short birthYear, String noc) {
        Athlete athlete = new Athlete();
        athlete.setDiscipline(Discipline.MAG);
        athlete.setSurname(surname);
        athlete.setGivenName(givenName);
        athlete.setLicenseNumber(license);
        athlete.setBirthYear(birthYear);
        athlete = athleteRepository.save(athlete);
        Participant participant = new Participant();
        participant.setEvent(event);
        participant.setAthlete(athlete);
        participant.setBibNumber(String.valueOf(athlete.getId()));
        participant.setNoc(noc);
        participant.setEntryStatus(EntryStatus.COMPETITOR);
        participantRepository.save(participant);
        return athlete;
    }
}
