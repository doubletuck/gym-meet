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
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

/**
 * Gymnasts ranked together at an event, usually one NOC's team. Its members aren't stored:
 * they are the gymnasts whose scores are linked to its results ({@link TeamResultScore}).
 */
@Getter
@Setter
@NoArgsConstructor
@ToString
@Entity
@Table(name = "team", uniqueConstraints = {
        @UniqueConstraint(name = "uk_team", columnNames = { "event_id", "discipline_code", "age_category_code", "name" })
})
public class Team extends BaseEntity {

    @NotNull(message = "Event is required")
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "event_id", nullable = false, foreignKey = @ForeignKey(name = "fk_team_event"))
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

    @NotBlank(message = "Name is required")
    @Size(max = 100, message = "Name must have 100 or fewer characters")
    @Column(name = "name", nullable = false, length = 100)
    private String name;

    // The NOC it represents, where it represents one
    @Size(min = 3, max = 4, message = "NOC must be a 3- or 4-character code")
    @Column(name = "noc", length = 4)
    private String noc;
}
