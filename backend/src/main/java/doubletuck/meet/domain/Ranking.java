package doubletuck.meet.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.ForeignKey;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinTable;
import jakarta.persistence.ManyToMany;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

import java.util.LinkedHashSet;
import java.util.Set;

/**
 * Standings over the routines of one or more competitions, published for a purpose: who goes
 * on to a later competition, a title's final placings, or an order that decides nothing. One
 * competition usually has several (a qualification ranks teams, all-arounders and each
 * apparatus); a ranking spans several competitions where it combines them (a two-day
 * all-around, a mixed team's qualification across the men's and women's competitions).
 */
@Getter
@Setter
@NoArgsConstructor
@ToString
@Entity
@Table(name = "ranking", indexes = {
        @Index(name = "ix_ranking_event", columnList = "event_id")
})
public class Ranking extends BaseEntity {

    @NotNull(message = "Event is required")
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "event_id", nullable = false, foreignKey = @ForeignKey(name = "fk_ranking_event"))
    private Event event;

    @NotNull(message = "Discipline is required")
    @Column(name = "discipline_code", nullable = false, length = 3)
    @Enumerated(EnumType.STRING)
    private Discipline discipline;

    @NotNull(message = "Age category is required")
    @Column(name = "age_category_code", nullable = false, length = 10)
    @Enumerated(EnumType.STRING)
    private AgeCategory ageCategory;

    @NotNull(message = "Type is required")
    @Column(name = "type_code", nullable = false, length = 10)
    @Enumerated(EnumType.STRING)
    private RankingType type;

    // Only on an APPARATUS ranking
    @Column(name = "apparatus_code", length = 5)
    @Enumerated(EnumType.STRING)
    private Apparatus apparatus;

    @NotNull(message = "Purpose is required")
    @Column(name = "purpose_code", nullable = false, length = 20)
    @Enumerated(EnumType.STRING)
    private RankingPurpose purpose;

    @ManyToMany(fetch = FetchType.EAGER)
    @JoinTable(name = "ranking_competition",
            joinColumns = @JoinColumn(name = "ranking_id", foreignKey = @ForeignKey(name = "fk_ranking_competition_ranking")),
            inverseJoinColumns = @JoinColumn(name = "competition_id", foreignKey = @ForeignKey(name = "fk_ranking_competition_competition")))
    @ToString.Exclude
    private Set<Competition> competitions = new LinkedHashSet<>();
}
