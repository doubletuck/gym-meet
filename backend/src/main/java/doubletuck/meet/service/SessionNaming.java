package doubletuck.meet.service;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Round;
import doubletuck.meet.domain.Session;

import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * How sessions are named in addresses and ordered in lists. A session's slug is
 * unique within its event, discipline and age category: {@code qualification},
 * {@code team-final}, {@code all-around-final}, {@code beam-final}, or
 * {@code vault-qualification} at an apparatus-format meet; a split round's parts
 * add {@code -part-1}, {@code -part-2}.
 */
public final class SessionNaming {

    private static final Map<Apparatus, String> APPARATUS_SLUGS = Map.of(
            Apparatus.VT, "vault",
            Apparatus.UB, "uneven-bars",
            Apparatus.BB, "beam",
            Apparatus.FX, "floor",
            Apparatus.PH, "pommel-horse",
            Apparatus.SR, "rings",
            Apparatus.PB, "parallel-bars",
            Apparatus.HB, "high-bar");

    // Olympic order, the order results books list the apparatus in
    private static final List<Apparatus> MAG_ORDER = List.of(Apparatus.FX, Apparatus.PH, Apparatus.SR, Apparatus.VT,
            Apparatus.PB, Apparatus.HB);
    private static final List<Apparatus> WAG_ORDER = List.of(Apparatus.VT, Apparatus.UB, Apparatus.BB, Apparatus.FX);

    private static final List<Round> ROUND_ORDER = List.of(Round.QUAL, Round.TEAM, Round.AA, Round.EVENT);

    private SessionNaming() {
    }

    public static String slug(Session session) {
        String round = switch (session.getRound()) {
            case QUAL -> session.getApparatus() != null ? apparatusSlug(session.getApparatus()) + "-qualification"
                    : "qualification";
            case TEAM -> "team-final";
            case AA -> "all-around-final";
            case EVENT -> apparatusSlug(session.getApparatus()) + "-final";
        };
        return session.getPart() != null ? round + "-part-" + session.getPart() : round;
    }

    public static List<Apparatus> apparatusOrder(Discipline discipline) {
        return discipline == Discipline.MAG ? MAG_ORDER : WAG_ORDER;
    }

    /**
     * Rounds in competition order, apparatus in Olympic order, and a split
     * round's parts before its combined (whole-round) session.
     */
    public static Comparator<Session> order() {
        return Comparator.comparingInt((Session session) -> ROUND_ORDER.indexOf(session.getRound()))
                .thenComparingInt(session -> session.getApparatus() == null ? -1
                        : apparatusOrder(session.getDiscipline()).indexOf(session.getApparatus()))
                .thenComparing(Session::getPart, Comparator.nullsLast(Comparator.naturalOrder()));
    }

    private static String apparatusSlug(Apparatus apparatus) {
        return APPARATUS_SLUGS.get(apparatus);
    }
}
