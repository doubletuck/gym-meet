package doubletuck.meet.dto;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Round;
import doubletuck.meet.domain.Session;
import doubletuck.meet.service.SessionNaming;
import doubletuck.meet.service.SplitRound;
import org.jspecify.annotations.Nullable;

import java.time.LocalDate;
import java.util.Collection;
import java.util.Comparator;

/**
 * @param slug    unique within the event, discipline and age category, e.g. {@code beam-final}
 * @param date    the day it was held; for a split round's combined session, its first part's
 * @param endDate a split round's combined session's last day, when its parts were held over
 *                several days
 */
public record SessionSummaryResponse(
        Long id,
        String slug,
        Discipline discipline,
        AgeCategory ageCategory,
        Round round,
        @Nullable Apparatus apparatus,
        @Nullable Integer part,
        LocalDate date,
        @Nullable LocalDate endDate) {

    /** @param sessions the sessions of the event's discipline and age category */
    public static SessionSummaryResponse from(Session session, Collection<Session> sessions) {
        LocalDate endDate = SplitRound.parts(session, sessions).stream()
                .map(Session::getDate)
                .filter(date -> date.isAfter(session.getDate()))
                .max(Comparator.naturalOrder())
                .orElse(null);
        return new SessionSummaryResponse(session.getId(), SessionNaming.slug(session), session.getDiscipline(),
                session.getAgeCategory(), session.getRound(), session.getApparatus(), session.getPart(),
                session.getDate(), endDate);
    }
}
