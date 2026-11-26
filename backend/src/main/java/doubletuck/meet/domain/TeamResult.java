package doubletuck.meet.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.ForeignKey;
import jakarta.persistence.Index;
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

/** A team's line in a team ranking, as published. */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@ToString
@Entity
@Table(name = "team_result", uniqueConstraints = {
        @UniqueConstraint(name = "uk_team_result", columnNames = { "ranking_id", "team_id" })
}, indexes = {
        @Index(name = "ix_team_result_team", columnList = "team_id")
})
public class TeamResult extends BaseEntity {

    @NotNull(message = "Ranking is required")
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "ranking_id", nullable = false, foreignKey = @ForeignKey(name = "fk_team_result_ranking"))
    @ToString.Exclude
    private Ranking ranking;

    @NotNull(message = "Team is required")
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "team_id", nullable = false, foreignKey = @ForeignKey(name = "fk_team_result_team"))
    private Team team;

    @Column(name = "total_score")
    private Double totalScore;

    // A penalty on the result as a whole, as printed (negative); already deducted from totalScore
    @Column(name = "sj_penalty")
    private Double sjPenalty;

    @Column(name = "rank")
    private Integer rank;

    // Why there is or isn't a rank; null where the source doesn't say
    @Column(name = "rank_status_code", length = 20)
    @Enumerated(EnumType.STRING)
    private RankStatus rankStatus;

    // Only on a QUALIFYING ranking
    @Column(name = "qualification_result_code", length = 10)
    @Enumerated(EnumType.STRING)
    private QualificationResult qualificationResult;
}
