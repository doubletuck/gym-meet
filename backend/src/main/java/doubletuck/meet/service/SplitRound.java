package doubletuck.meet.service;

import doubletuck.meet.domain.Competition;

import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

/**
 * A competition held in parts (e.g. a two-day all-around decided on the combined
 * total) has a row per part and a whole-competition row, part blank, holding
 * the combined standings.
 */
public final class SplitRound {

    private SplitRound() {
    }

    /**
     * @param competitions the competitions of the event's discipline and age category
     * @return the parts of the competition {@code competition} combines, in order; empty
     *         when it is a part itself or isn't split
     */
    public static List<Competition> parts(Competition competition, Collection<Competition> competitions) {
        if (competition.getPart() != null) {
            return List.of();
        }
        return competitions.stream()
                .filter(other -> isPartOf(other, competition))
                .sorted(Comparator.comparing(Competition::getPart))
                .toList();
    }

    public static boolean isPartOf(Competition part, Competition whole) {
        return whole.getPart() == null && part.getPart() != null && part.getType() == whole.getType()
                && part.getApparatus() == whole.getApparatus()
                && Objects.equals(part.getRound(), whole.getRound())
                && part.getDiscipline() == whole.getDiscipline()
                && part.getAgeCategory() == whole.getAgeCategory()
                && Objects.equals(part.getEvent().getId(), whole.getEvent().getId());
    }
}
