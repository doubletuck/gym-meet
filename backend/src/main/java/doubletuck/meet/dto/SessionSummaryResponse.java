package doubletuck.meet.dto;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Round;
import doubletuck.meet.domain.Session;
import doubletuck.meet.service.SessionNaming;
import org.jspecify.annotations.Nullable;

import java.time.LocalDate;

/**
 * @param slug unique within the event, discipline and age category, e.g. {@code beam-final}
 */
public record SessionSummaryResponse(
        Long id,
        String slug,
        Discipline discipline,
        AgeCategory ageCategory,
        Round round,
        @Nullable Apparatus apparatus,
        @Nullable Integer part,
        LocalDate date) {

    public static SessionSummaryResponse from(Session session) {
        return new SessionSummaryResponse(session.getId(), SessionNaming.slug(session), session.getDiscipline(),
                session.getAgeCategory(), session.getRound(), session.getApparatus(), session.getPart(),
                session.getDate());
    }
}
