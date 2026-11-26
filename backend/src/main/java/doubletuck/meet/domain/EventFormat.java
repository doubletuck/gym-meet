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
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

/**
 * How one discipline and age category of an event was run: where each title was decided.
 * The importer checks the competitions and rankings against it.
 */
@Getter
@Setter
@NoArgsConstructor
@ToString
@Entity
@Table(name = "event_format", uniqueConstraints = {
        @UniqueConstraint(name = "uk_event_format", columnNames = { "event_id", "discipline_code",
                "age_category_code" })
})
public class EventFormat extends BaseEntity {

    @NotNull(message = "Event is required")
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "event_id", nullable = false, foreignKey = @ForeignKey(name = "fk_event_format_event"))
    @ToString.Exclude
    private Event event;

    @NotNull(message = "Discipline is required")
    @Column(name = "discipline_code", nullable = false, length = 3)
    @Enumerated(EnumType.STRING)
    private Discipline discipline;

    @NotNull(message = "Age category is required")
    @Column(name = "age_category_code", nullable = false, length = 10)
    @Enumerated(EnumType.STRING)
    private AgeCategory ageCategory;

    @NotNull(message = "Team format is required")
    @Column(name = "team_format_code", nullable = false, length = 10)
    @Enumerated(EnumType.STRING)
    private TitleFormat teamFormat;

    @NotNull(message = "All-around format is required")
    @Column(name = "aa_format_code", nullable = false, length = 10)
    @Enumerated(EnumType.STRING)
    private TitleFormat allAroundFormat;

    @NotNull(message = "Apparatus format is required")
    @Column(name = "apparatus_format_code", nullable = false, length = 10)
    @Enumerated(EnumType.STRING)
    private TitleFormat apparatusFormat;

    /** The format of the titles a ranking of this type decides. */
    public TitleFormat formatOf(RankingType type) {
        return switch (type) {
            case TEAM -> teamFormat;
            case AA -> allAroundFormat;
            case APPARATUS -> apparatusFormat;
        };
    }

    /**
     * Whether Competition I is held per apparatus, as at an apparatus World Cup: so when no
     * team or all-around title is contested.
     */
    public boolean isApparatusOnly() {
        return teamFormat == TitleFormat.NONE && allAroundFormat == TitleFormat.NONE;
    }
}
