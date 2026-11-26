package doubletuck.meet.domain;

import lombok.Getter;

/** How a team member's score figured in one team result: added into its apparatus total, or left out. */
@Getter
public enum TeamContributionRole {

    COUNTING("Counting"),
    DROPPED("Dropped");

    private final String longName;

    TeamContributionRole(String longName) {
        this.longName = longName;
    }

    public static TeamContributionRole find(String text) {
        if (text != null && !text.isEmpty()) {
            text = text.trim();
            for (TeamContributionRole role : TeamContributionRole.values()) {
                if (role.name().equalsIgnoreCase(text) || role.longName.equalsIgnoreCase(text)) {
                    return role;
                }
            }
        }
        return null;
    }
}
