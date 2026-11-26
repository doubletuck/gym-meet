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

    C1("Competition I"),
    C2("Competition II"),
    C3("Competition III"),
    C4("Competition IV");

    private final String longName;

    CompetitionType(String longName) {
        this.longName = longName;
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
}
