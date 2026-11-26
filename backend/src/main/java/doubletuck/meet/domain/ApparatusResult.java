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

/** A gymnast's line in an apparatus ranking, as published. The apparatus is the ranking's. */
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@ToString
@Entity
@Table(name = "apparatus_result", uniqueConstraints = {
        @UniqueConstraint(name = "uk_apparatus_result", columnNames = { "ranking_id", "participant_id" })
}, indexes = {
        @Index(name = "ix_apparatus_result_participant", columnList = "participant_id")
})
public class ApparatusResult extends BaseEntity {

    @NotNull(message = "Ranking is required")
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "ranking_id", nullable = false, foreignKey = @ForeignKey(name = "fk_apparatus_result_ranking"))
    @ToString.Exclude
    private Ranking ranking;

    @NotNull(message = "Participant is required")
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "participant_id", nullable = false, foreignKey = @ForeignKey(name = "fk_apparatus_result_participant"))
    private Participant participant;

    // What the apparatus is decided on: the routine's score, or for two vaults their combination
    @Column(name = "total_score")
    private Double totalScore;

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
