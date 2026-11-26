package doubletuck.meet.domain;

import lombok.Getter;

/**
 * The round codes the import files and the API name a competition by: QUAL, AA, EVENT and
 * TEAM. The model itself uses {@link CompetitionType}; this stays until the file standard and
 * the API move to C1-C4.
 */
@Getter
public enum Round {

    QUAL("Qualification"),
    EVENT("Apparatus Final"),
    AA("All-Around Final"),
    TEAM("Team Final");

    private final String longName;

    Round(String longName) {
        this.longName = longName;
    }

    public static Round find(String text) {

        if (text != null && !text.isEmpty()) {
            text = text.trim();
            for (Round round : Round.values()) {
                if (round.name().equalsIgnoreCase(text)
                        || round.longName.equalsIgnoreCase(text)) {
                    return round;
                }
            }
        }
        return null;
    }
}
