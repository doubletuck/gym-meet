package doubletuck.meet.domain;

import lombok.Getter;

/**
 * Where a title (team, all-around or apparatus) was decided at an event: in Competition I,
 * in the title's own final (Competition II, III or IV), or not at all.
 */
@Getter
public enum TitleFormat {

    C1("Competition I"),
    FINAL("Final"),
    NONE("Not held");

    private final String longName;

    TitleFormat(String longName) {
        this.longName = longName;
    }

    public static TitleFormat find(String text) {
        if (text != null && !text.isEmpty()) {
            text = text.trim();
            for (TitleFormat format : TitleFormat.values()) {
                if (format.name().equalsIgnoreCase(text) || format.longName.equalsIgnoreCase(text)) {
                    return format;
                }
            }
        }
        return null;
    }
}
