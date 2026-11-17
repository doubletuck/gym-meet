package doubletuck.meet.service;

import doubletuck.meet.domain.Session;

import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

/**
 * A round held in parts (e.g. a two-day all-around decided on the combined
 * total) has a session per part and a whole-round session, part blank, holding
 * the combined standings.
 */
public final class SplitRound {

    private SplitRound() {
    }

    /**
     * @param sessions the sessions of the event's discipline and age category
     * @return the parts of the round {@code session} combines, in order; empty
     *         when it is a part itself or its round isn't split
     */
    public static List<Session> parts(Session session, Collection<Session> sessions) {
        if (session.getPart() != null) {
            return List.of();
        }
        return sessions.stream()
                .filter(other -> other.getPart() != null && other.getRound() == session.getRound()
                        && other.getApparatus() == session.getApparatus()
                        && other.getDiscipline() == session.getDiscipline()
                        && other.getAgeCategory() == session.getAgeCategory()
                        && Objects.equals(other.getEvent().getId(), session.getEvent().getId()))
                .sorted(Comparator.comparing(Session::getPart))
                .toList();
    }
}
