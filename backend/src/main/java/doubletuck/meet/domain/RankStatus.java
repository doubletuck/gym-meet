package doubletuck.meet.domain;

import lombok.Getter;

/** Why a result has a rank, or why it has none. The rank itself is always as published. */
@Getter
public enum RankStatus {

    RANKED("Ranked"),
    INCOMPLETE("Incomplete"),
    NOC_LIMIT("NOC Limit"),
    HORS_CONCOURS("Hors Concours"),
    DID_NOT_FINISH("Did Not Finish"),
    UNPLACED("Unplaced");

    private final String longName;

    RankStatus(String longName) {
        this.longName = longName;
    }

    public static RankStatus find(String text) {
        if (text != null && !text.isEmpty()) {
            text = text.trim();
            for (RankStatus status : RankStatus.values()) {
                if (status.name().equalsIgnoreCase(text) || status.longName.equalsIgnoreCase(text)) {
                    return status;
                }
            }
        }
        return null;
    }
}
