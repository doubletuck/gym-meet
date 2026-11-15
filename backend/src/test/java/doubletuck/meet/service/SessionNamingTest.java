package doubletuck.meet.service;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Round;
import doubletuck.meet.domain.Session;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.stream.Stream;

import static org.junit.jupiter.api.Assertions.*;

class SessionNamingTest {

    @Test
    void testSlug() {
        assertEquals("qualification", SessionNaming.slug(session(Round.QUAL, null, null)));
        assertEquals("vault-qualification", SessionNaming.slug(session(Round.QUAL, Apparatus.VT, null)));
        assertEquals("team-final", SessionNaming.slug(session(Round.TEAM, null, null)));
        assertEquals("all-around-final", SessionNaming.slug(session(Round.AA, null, null)));
        assertEquals("all-around-final-part-2", SessionNaming.slug(session(Round.AA, null, 2)));
        assertEquals("beam-final", SessionNaming.slug(session(Round.EVENT, Apparatus.BB, null)));
        assertEquals("high-bar-final", SessionNaming.slug(session(Round.EVENT, Apparatus.HB, null)));
    }

    @Test
    void testOrder_RoundsThenOlympicApparatusThenParts() {
        List<String> ordered = Stream.of(
                        session(Round.EVENT, Apparatus.HB, null),
                        session(Round.EVENT, Apparatus.FX, null),
                        session(Round.AA, null, null),
                        session(Round.AA, null, 2),
                        session(Round.AA, null, 1),
                        session(Round.QUAL, null, null))
                .sorted(SessionNaming.order())
                .map(SessionNaming::slug)
                .toList();

        assertEquals(List.of("qualification", "all-around-final-part-1", "all-around-final-part-2",
                "all-around-final", "floor-final", "high-bar-final"), ordered);
    }

    private static Session session(Round round, Apparatus apparatus, Integer part) {
        Session session = new Session();
        session.setDiscipline(Discipline.MAG);
        session.setRound(round);
        session.setApparatus(apparatus);
        session.setPart(part);
        return session;
    }
}
