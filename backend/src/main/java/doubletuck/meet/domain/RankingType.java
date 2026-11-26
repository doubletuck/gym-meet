package doubletuck.meet.domain;

import lombok.Getter;

/** What a ranking orders: teams, all-arounders, or gymnasts on one apparatus. */
@Getter
public enum RankingType {

    TEAM("Team"),
    AA("All-Around"),
    APPARATUS("Apparatus");

    private final String longName;

    RankingType(String longName) {
        this.longName = longName;
    }

    public static RankingType find(String text) {
        if (text != null && !text.isEmpty()) {
            text = text.trim();
            for (RankingType type : RankingType.values()) {
                if (type.name().equalsIgnoreCase(text) || type.longName.equalsIgnoreCase(text)) {
                    return type;
                }
            }
        }
        return null;
    }
}
