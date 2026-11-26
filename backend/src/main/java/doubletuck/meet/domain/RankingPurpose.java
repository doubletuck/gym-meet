package doubletuck.meet.domain;

import lombok.Getter;

/**
 * What a ranking is for: picking who goes on to a later competition (where Q/R/NR markers
 * belong), giving a title's final placings and medals, or ordering results without deciding
 * anything (qualification's single-vault list, a split competition's daily standings).
 */
@Getter
public enum RankingPurpose {

    QUALIFYING("Qualifying"),
    FINAL("Final"),
    INFORMATIONAL("Informational");

    private final String longName;

    RankingPurpose(String longName) {
        this.longName = longName;
    }

    public static RankingPurpose find(String text) {
        if (text != null && !text.isEmpty()) {
            text = text.trim();
            for (RankingPurpose purpose : RankingPurpose.values()) {
                if (purpose.name().equalsIgnoreCase(text) || purpose.longName.equalsIgnoreCase(text)) {
                    return purpose;
                }
            }
        }
        return null;
    }
}
