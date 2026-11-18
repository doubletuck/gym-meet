package doubletuck.meet.domain;

import lombok.Getter;

/** How an athlete is entered in an event, as the entry list shows it. */
@Getter
public enum EntryStatus {

    COMPETITOR("Competitor"),
    RESERVE("Reserve"),
    WITHDRAWN("Withdrawn");

    private final String longName;

    EntryStatus(String longName) {
        this.longName = longName;
    }

    public static EntryStatus find(String text) {

        if (text != null && !text.isEmpty()) {
            text = text.trim();
            for (EntryStatus entryStatus : EntryStatus.values()) {
                if (entryStatus.name().equalsIgnoreCase(text)
                        || entryStatus.longName.equalsIgnoreCase(text)) {
                    return entryStatus;
                }
            }
        }
        return null;
    }
}
