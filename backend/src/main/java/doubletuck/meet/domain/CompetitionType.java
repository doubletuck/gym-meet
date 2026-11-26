package doubletuck.meet.domain;

import lombok.Getter;

/**
 * FIG's numbering of a meet's competitions (Technical Regulations): Competition I, which every
 * entrant takes part in, then the all-around final, the apparatus finals and the team final.
 * The code says which competition it was, not what it decided: a Competition I may qualify to
 * the finals, decide titles itself, or both.
 */
@Getter
public enum CompetitionType {

    C1("Competition I", Round.QUAL),
    C2("Competition II", Round.AA),
    C3("Competition III", Round.EVENT),
    C4("Competition IV", Round.TEAM);

    private final String longName;

    /** The round the API still names it by (until the step 5 change). */
    private final Round legacyRound;

    CompetitionType(String longName, Round legacyRound) {
        this.longName = longName;
        this.legacyRound = legacyRound;
    }

    public static CompetitionType find(String text) {
        if (text != null && !text.isEmpty()) {
            text = text.trim();
            for (CompetitionType type : CompetitionType.values()) {
                if (type.name().equalsIgnoreCase(text) || type.longName.equalsIgnoreCase(text)) {
                    return type;
                }
            }
        }
        return null;
    }

    public static CompetitionType of(Round round) {
        for (CompetitionType type : CompetitionType.values()) {
            if (type.legacyRound == round) {
                return type;
            }
        }
        throw new IllegalArgumentException("No competition type for round " + round);
    }
}
