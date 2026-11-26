package doubletuck.meet.service;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Round;

import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/**
 * How competitions are named in addresses and ordered in lists. A competition's slug is
 * unique within its event, discipline and age category: {@code qualification},
 * {@code team-final}, {@code all-around-final}, {@code beam-final}, or
 * {@code vault-qualification} at an apparatus-format meet; an elimination round adds
 * {@code -round-1}, and a split competition's parts
 * add {@code -part-1}, {@code -part-2}.
 */
public final class CompetitionNaming {

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

    private static final List<CompetitionType> TYPE_ORDER = List.of(CompetitionType.C1, CompetitionType.C4,
            CompetitionType.C2, CompetitionType.C3);

    private CompetitionNaming() {
    }

    /**
     * The round the API names a competition by, until it's named from its rankings (rollout
     * step 5): a Competition I that is the only competition of its discipline and age category
     * (Oceania, US Championships) decided everything, so it keeps the name the files gave it
     * before Competition I was one code, the all-around final.
     *
     * @param competitions the event's competitions (those of other disciplines and age categories are ignored)
     */
    public static Round legacyRound(Competition competition, Collection<Competition> competitions) {
        if (competition.getType() == CompetitionType.C1 && competitions.stream()
                .filter(other -> other.getDiscipline() == competition.getDiscipline()
                        && other.getAgeCategory() == competition.getAgeCategory())
                .allMatch(other -> other.getType() == CompetitionType.C1)) {
            return Round.AA;
        }
        return competition.getType().getLegacyRound();
    }

    /** @param competitions the event's competitions, as for {@link #legacyRound} */
    public static String slug(Competition competition, Collection<Competition> competitions) {
        if (legacyRound(competition, competitions) == Round.AA && competition.getType() == CompetitionType.C1) {
            String name = "all-around-final";
            return competition.getPart() != null ? name + "-part-" + competition.getPart() : name;
        }
        return slug(competition);
    }

    public static String slug(Competition competition) {
        String name = switch (competition.getType()) {
            case C1 -> competition.getApparatus() != null ? apparatusSlug(competition.getApparatus()) + "-qualification"
                    : "qualification";
            case C4 -> "team-final";
            case C2 -> "all-around-final";
            case C3 -> apparatusSlug(competition.getApparatus()) + "-final";
        };
        if (competition.getRound() != null) {
            name += "-round-" + competition.getRound();
        }
        return competition.getPart() != null ? name + "-part-" + competition.getPart() : name;
    }

    public static List<Apparatus> apparatusOrder(Discipline discipline) {
        return switch (discipline) {
            case MAG -> MAG_ORDER;
            case WAG -> WAG_ORDER;
            // A mixed team's apparatus belong to both disciplines; how to list them comes with the first mixed meet
            case MIX -> List.of();
        };
    }

    /**
     * Competitions in the order they're held, apparatus in Olympic order, then
     * elimination rounds, and a split competition's combined (whole) row before
     * its parts, since it holds the result the competition is decided on.
     */
    public static Comparator<Competition> order() {
        return Comparator.comparingInt((Competition competition) -> TYPE_ORDER.indexOf(competition.getType()))
                .thenComparingInt(competition -> competition.getApparatus() == null ? -1
                        : apparatusOrder(competition.getDiscipline()).indexOf(competition.getApparatus()))
                .thenComparing(Competition::getRound, Comparator.nullsFirst(Comparator.naturalOrder()))
                .thenComparing(Competition::getPart, Comparator.nullsFirst(Comparator.naturalOrder()));
    }

    private static String apparatusSlug(Apparatus apparatus) {
        return APPARATUS_SLUGS.get(apparatus);
    }
}
