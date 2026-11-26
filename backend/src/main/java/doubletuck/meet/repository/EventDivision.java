package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Discipline;

/** A discipline and age category an event has competitions for. */
public record EventDivision(Long eventId, Discipline discipline, AgeCategory ageCategory) {
}
