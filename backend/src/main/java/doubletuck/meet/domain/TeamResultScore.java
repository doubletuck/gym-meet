package doubletuck.meet.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.ForeignKey;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

import java.io.Serializable;

/**
 * How a team member's score figured in one team result. It's per result, not per score: the
 * same qualification score can count for a NOC's team and be dropped by its mixed team.
 */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@ToString
@Entity
@IdClass(TeamResultScore.Key.class)
@Table(name = "team_result_score", indexes = {
        @Index(name = "ix_team_result_score_score", columnList = "score_id")
})
public class TeamResultScore {

    @Id
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "team_result_id", nullable = false, foreignKey = @ForeignKey(name = "fk_team_result_score_team_result"))
    @ToString.Exclude
    private TeamResult teamResult;

    @Id
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "score_id", nullable = false, foreignKey = @ForeignKey(name = "fk_team_result_score_score"))
    @ToString.Exclude
    private Score score;

    @NotNull(message = "Role is required")
    @Column(name = "role_code", nullable = false, length = 20)
    @Enumerated(EnumType.STRING)
    private TeamContributionRole role;

    @Getter
    @Setter
    @NoArgsConstructor
    @AllArgsConstructor
    @EqualsAndHashCode
    public static class Key implements Serializable {
        private Long teamResult;
        private Long score;
    }
}
