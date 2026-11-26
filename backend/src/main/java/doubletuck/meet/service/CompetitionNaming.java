package doubletuck.meet.service;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.dto.CompetitionSummaryResponse.RankingPurposes;
import org.jspecify.annotations.Nullable;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Stream;

/**
 * How competitions are named on the site, addressed and ordered. A competition is named from
 * its rankings: a final for the titles it decided, then what it qualified for. A Competition I
 * that decided nothing is "Qualification"; the SA Games' is "Team and All-Around Final ·
 * Apparatus Qualification"; Oceania's "Team and All-Around Final".
 *
 * <p>A slug is unique within the event, discipline and age category: {@code qualification}
 * (or {@code vault-qualification} at an apparatus-format meet) for a Competition I that
 * qualified anyone, otherwise one from its name ({@code team-and-all-around-final});
 * {@code team-final}, {@code all-around-final}, {@code beam-final}. An elimination round adds
 * {@code -round-1}, and a split competition's parts add {@code -part-1}, {@code -part-2}.
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

    // Where a competition's routines are ranked more than once for one title, the ranking deciding the most
    private static final List<RankingPurpose> PREFERENCE = List.of(RankingPurpose.FINAL, RankingPurpose.QUALIFYING,
            RankingPurpose.INFORMATIONAL);

    private CompetitionNaming() {
    }

    /** A competition's name, its short name (under an apparatus already shown) and its slug. */
    public record Names(String name, String shortName, String slug) {
    }

    /**
     * Names the competitions of one event.
     *
     * @param competitions the event's competitions (a part is named after its whole, among them)
     * @param purposes     what each one's rankings are for, from {@link #purposes}
     */
    public static Map<Competition, Names> names(Collection<Competition> competitions,
            Map<Competition, RankingPurposes> purposes) {
        Map<Competition, Names> names = new HashMap<>();
        for (Competition competition : competitions) {
            Competition whole = competition.getPart() == null ? competition
                    : SplitRound.whole(competition, competitions).orElse(competition);
            names.put(competition, names(competition, purposes.get(whole)));
        }
        return names;
    }

    /** What the rankings of a competition's routines are for. */
    public static RankingPurposes purposes(Collection<Ranking> rankings) {
        return new RankingPurposes(purpose(rankings, RankingType.TEAM), purpose(rankings, RankingType.AA),
                purpose(rankings, RankingType.APPARATUS));
    }

    private static @Nullable RankingPurpose purpose(Collection<Ranking> rankings, RankingType type) {
        return rankings.stream()
                .filter(ranking -> ranking.getType() == type)
                .map(Ranking::getPurpose)
                .min(Comparator.comparingInt(PREFERENCE::indexOf))
                .orElse(null);
    }

    private static boolean any(RankingPurposes purposes, RankingPurpose purpose) {
        return Stream.of(purposes.team(), purposes.allAround(), purposes.apparatus()).anyMatch(p -> p == purpose);
    }

    /** What each competition's rankings are for. */
    public static Map<Competition, RankingPurposes> purposes(Collection<Competition> competitions,
            Collection<Ranking> rankings) {
        Map<Competition, RankingPurposes> purposes = new HashMap<>();
        for (Competition competition : competitions) {
            purposes.put(competition, purposes(rankings.stream()
                    .filter(ranking -> ranking.getCompetitions().contains(competition))
                    .toList()));
        }
        return purposes;
    }

    /**
     * @param purposes what the rankings of the competition's routines are for; for a part, those of
     *                 the whole competition, which it's named after
     */
    static Names names(Competition competition, RankingPurposes purposes) {
        String name;
        String shortName;
        String slug;
        switch (competition.getType()) {
            case C1 -> {
                if (any(purposes, RankingPurpose.QUALIFYING) || !any(purposes, RankingPurpose.FINAL)) {
                    List<String> decided = titles(competition, purposes, RankingPurpose.FINAL);
                    List<String> qualified = titles(competition, purposes, RankingPurpose.QUALIFYING);
                    String qualification = competition.getApparatus() != null
                            ? competition.getApparatus().getLongName() + " Qualification" : "Qualification";
                    name = decided.isEmpty() ? qualification
                            : list(decided) + " Final · " + list(qualified) + " Qualification";
                    shortName = "Qualification";
                    slug = competition.getApparatus() != null
                            ? APPARATUS_SLUGS.get(competition.getApparatus()) + "-qualification" : "qualification";
                } else {
                    name = list(titles(competition, purposes, RankingPurpose.FINAL)) + " Final";
                    shortName = "Final";
                    slug = slugOf(name);
                }
            }
            case C2 -> {
                name = "All-Around Final";
                shortName = "AA Final";
                slug = "all-around-final";
            }
            case C3 -> {
                name = competition.getApparatus().getLongName() + " Final";
                shortName = "Final";
                slug = APPARATUS_SLUGS.get(competition.getApparatus()) + "-final";
            }
            case C4 -> {
                name = "Team Final";
                shortName = "Team Final";
                slug = "team-final";
            }
            default -> throw new IllegalStateException("No name for " + competition.getType());
        }
        if (competition.getRound() != null) {
            name += ", Round " + competition.getRound();
            shortName += ", Round " + competition.getRound();
            slug += "-round-" + competition.getRound();
        }
        if (competition.getPart() != null) {
            name += ", Part " + competition.getPart();
            shortName += ", Part " + competition.getPart();
            slug += "-part-" + competition.getPart();
        }
        return new Names(name, shortName, slug);
    }

    /** The titles the competition's rankings are for, with this purpose: "Team", "All-Around", "Apparatus". */
    private static List<String> titles(Competition competition, RankingPurposes purposes, RankingPurpose purpose) {
        List<String> titles = new ArrayList<>();
        if (purposes.team() == purpose) {
            titles.add("Team");
        }
        if (purposes.allAround() == purpose) {
            titles.add("All-Around");
        }
        if (purposes.apparatus() == purpose) {
            titles.add(competition.getApparatus() != null ? competition.getApparatus().getLongName() : "Apparatus");
        }
        return titles;
    }

    /** "Team", "Team and All-Around", "Team, All-Around and Apparatus". */
    private static String list(List<String> titles) {
        if (titles.size() <= 1) {
            return String.join("", titles);
        }
        return String.join(", ", titles.subList(0, titles.size() - 1)) + " and " + titles.getLast();
    }

    private static String slugOf(String name) {
        return name.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]+", "-").replaceAll("^-|-$", "");
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

    /** Of a competition's rankings of one type, the one deciding the most. */
    public static Optional<Ranking> preferred(Collection<Ranking> rankings, RankingType type) {
        return rankings.stream()
                .filter(ranking -> ranking.getType() == type)
                .min(Comparator.comparingInt((Ranking ranking) -> PREFERENCE.indexOf(ranking.getPurpose()))
                        .thenComparing(Ranking::getId));
    }

    /** As {@link #preferred}, for ordering: 0 for the ranking deciding the most. */
    public static int preference(Ranking ranking) {
        return PREFERENCE.indexOf(ranking.getPurpose());
    }
}
