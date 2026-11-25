package doubletuck.meet.domain;

import lombok.Getter;

/**
 * What a score does for its country's team: one of the scores adding up to the
 * team's apparatus total, a team member's score left out of it, or the score of
 * an athlete competing as an individual on that apparatus (an individual entered
 * alongside a team, or a team's extra athlete competing for another title only).
 */
@Getter
public enum TeamScoreRole {

    COUNTING("Counting"),
    DROPPED("Dropped"),
    INDIVIDUAL("Individual");

    private final String longName;

    TeamScoreRole(String longName) {
        this.longName = longName;
    }

    public static TeamScoreRole find(String text) {

        if (text != null && !text.isEmpty()) {
            text = text.trim();
            for (TeamScoreRole role : TeamScoreRole.values()) {
                if (role.name().equalsIgnoreCase(text) || role.longName.equalsIgnoreCase(text)) {
                    return role;
                }
            }
        }
        return null;
    }
}
