package doubletuck.meet.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.ForeignKey;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

import java.time.LocalDate;

/**
 * Routines performed on a date in front of judges: one of FIG's Competitions I-IV
 * ({@link CompetitionType}) for one discipline and age category. How the routines were
 * ranked is a {@link Ranking}'s business, not the competition's.
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@ToString
@Entity
@Table(name = "competition", uniqueConstraints = {
        // V9 declares this NULLS NOT DISTINCT, which JPA can't express, so that null apparatus, round
        // and part values count as equal and a duplicate is rejected
        @UniqueConstraint(name = "uk_competition", columnNames = { "event_id", "type_code", "discipline_code",
                "age_category_code", "apparatus_code", "round", "part" })
})
public class Competition extends BaseEntity {

    @NotNull(message = "Event is required")
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "event_id", nullable = false, foreignKey = @ForeignKey(name = "fk_competition_event"))
    private Event event;

    @NotNull(message = "Date is required")
    @Column(name = "competition_date", nullable = false)
    private LocalDate date;

    @NotNull(message = "Type is required")
    @Column(name = "type_code", nullable = false, length = 2)
    @Enumerated(EnumType.STRING)
    private CompetitionType type;

    @NotNull(message = "Discipline is required")
    @Column(name = "discipline_code", nullable = false, length = 3)
    @Enumerated(EnumType.STRING)
    private Discipline discipline;

    @NotNull(message = "Age category is required")
    @Column(name = "age_category_code", nullable = false, length = 10)
    @Enumerated(EnumType.STRING)
    private AgeCategory ageCategory;

    /** The apparatus of an apparatus final, or of an apparatus-format meet's qualification. */
    @Column(name = "apparatus_code", length = 5)
    @Enumerated(EnumType.STRING)
    private Apparatus apparatus;

    /**
     * An elimination round within the competition, with scores reset each round (the 2026
     * Youth Olympic Games' mixed team final, rounds 1-3). Null when the competition isn't
     * held in rounds.
     */
    @Column(name = "round")
    private Integer round;

    /**
     * A share of a competition held over several days and decided on the combined total (the
     * US Championships' two-day all-around: parts 1 and 2). Null for a competition held at
     * once; on a split competition, the whole-competition row (part null) holds the combined
     * standings.
     */
    @Column(name = "part")
    private Integer part;
}
