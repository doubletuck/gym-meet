package doubletuck.meet.service;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

class CompetitionNamingTest {

    @Test
    void testSlug() {
        assertEquals("qualification", CompetitionNaming.slug(competition(CompetitionType.C1, null, null)));
        assertEquals("vault-qualification", CompetitionNaming.slug(competition(CompetitionType.C1, Apparatus.VT, null)));
        assertEquals("team-final", CompetitionNaming.slug(competition(CompetitionType.C4, null, null)));
        assertEquals("all-around-final", CompetitionNaming.slug(competition(CompetitionType.C2, null, null)));
        assertEquals("all-around-final-part-2", CompetitionNaming.slug(competition(CompetitionType.C2, null, 2)));
        assertEquals("beam-final", CompetitionNaming.slug(competition(CompetitionType.C3, Apparatus.BB, null)));
        assertEquals("high-bar-final", CompetitionNaming.slug(competition(CompetitionType.C3, Apparatus.HB, null)));
        Competition round = competition(CompetitionType.C4, null, null);
        round.setRound(3);
        assertEquals("team-final-round-3", CompetitionNaming.slug(round));
    }

    @Test
    void testOrder_RoundsThenOlympicApparatusThenCombinedBeforeParts() {
        List<String> ordered = Stream.of(
                        competition(CompetitionType.C3, Apparatus.HB, null),
                        competition(CompetitionType.C3, Apparatus.FX, null),
                        competition(CompetitionType.C2, null, null),
                        competition(CompetitionType.C2, null, 2),
                        competition(CompetitionType.C2, null, 1),
                        competition(CompetitionType.C1, null, null))
                .sorted(CompetitionNaming.order())
                .map(CompetitionNaming::slug)
                .toList();

        assertEquals(List.of("qualification", "all-around-final", "all-around-final-part-1",
                "all-around-final-part-2", "floor-final", "high-bar-final"), ordered);
    }

    private static Competition competition(CompetitionType type, Apparatus apparatus, Integer part) {
        Competition competition = new Competition();
        competition.setDiscipline(Discipline.MAG);
        competition.setType(type);
        competition.setApparatus(apparatus);
        competition.setPart(part);
        return competition;
    }
}
