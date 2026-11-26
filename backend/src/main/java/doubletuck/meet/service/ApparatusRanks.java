package doubletuck.meet.service;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.Score;

import java.util.Collection;
import java.util.HashMap;
import java.util.Map;

/**
 * A competition's apparatus rankings, looked up by score: the placing a score is published
 * with on its apparatus, and in qualification the ranking deciding the apparatus final.
 */
public final class ApparatusRanks {

    private record Key(Long participantId, Apparatus apparatus, RankingPurpose purpose) {
    }

    private final CompetitionType type;
    private final Map<Key, ApparatusResult> results = new HashMap<>();

    /**
     * @param results the results of the competition's apparatus rankings (others are ignored)
     */
    public ApparatusRanks(CompetitionType type, Collection<ApparatusResult> results) {
        this.type = type;
        for (ApparatusResult result : results) {
            Ranking ranking = result.getRanking();
            if (ranking.getType() == RankingType.APPARATUS) {
                this.results.put(new Key(result.getParticipant().getId(), ranking.getApparatus(),
                        ranking.getPurpose()), result);
            }
        }
    }

    /**
     * The placing a score is published with on its apparatus. A competition ranks an apparatus
     * once, except qualification's vault, ranked twice: the single-vault list (every vaulter, on
     * the first vault) gives the placing, and the two-vault list, which decides the final, the
     * {@link #qualificationRank}.
     */
    public Integer rank(Score score) {
        ApparatusResult result = result(score, RankingPurpose.FINAL);
        if (result == null) {
            result = result(score, RankingPurpose.INFORMATIONAL);
        }
        if (result == null) {
            result = result(score, RankingPurpose.QUALIFYING);
        }
        return result == null ? null : result.getRank();
    }

    public Integer qualificationRank(Score score) {
        ApparatusResult result = qualifying(score);
        return result == null ? null : result.getRank();
    }

    public QualificationResult qualification(Score score) {
        ApparatusResult result = qualifying(score);
        return result == null ? null : result.getQualificationResult();
    }

    private ApparatusResult qualifying(Score score) {
        return type == CompetitionType.C1 ? result(score, RankingPurpose.QUALIFYING) : null;
    }

    private ApparatusResult result(Score score, RankingPurpose purpose) {
        return results.get(new Key(score.getParticipant().getId(), score.getApparatus(), purpose));
    }
}
