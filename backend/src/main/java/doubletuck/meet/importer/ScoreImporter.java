package doubletuck.meet.importer;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.BonusDetail;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.RankStatus;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.Routine;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.ScoreStatus;
import doubletuck.meet.domain.TeamScoreRole;
import doubletuck.meet.domain.TitleFormat;
import doubletuck.meet.repository.ApparatusResultRepository;
import doubletuck.meet.repository.ScoreRepository;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.function.Predicate;

/**
 * Imports {@code SCORES-<ROUND>-<APP>.csv} files, creating each competition the
 * first time one of its scores appears, then ranks the scores on each apparatus as
 * their rows place them.
 */
@Component
class ScoreImporter {

    // US Championships itemize the bonus FIG prints as one B value
    private static final List<Map.Entry<String, String>> BONUS_BREAKDOWN = List.of(
            Map.entry("D+", "Difficulty bonus"),
            Map.entry("E+", "Execution bonus"),
            Map.entry("S+", "Stick bonus"));

    private final ScoreRepository scoreRepository;
    private final ApparatusResultRepository apparatusResultRepository;

    ScoreImporter(ScoreRepository scoreRepository, ApparatusResultRepository apparatusResultRepository) {
        this.scoreRepository = scoreRepository;
        this.apparatusResultRepository = apparatusResultRepository;
    }

    void importFile(ImportContext context, String fileName) {
        for (CsvRow row : CsvRow.read(context.file(fileName))) {
            CompetitionType type = row.requiredCode("Competition", CompetitionType::find);
            Apparatus apparatus = row.requiredCode("Apparatus", Apparatus::find);
            Integer part = row.integer("Part");
            if (row.date("Competition Start Date") == null) {
                throw row.error("'Competition Start Date' is required");
            }
            Competition competition = context.competitionForScores(type, apparatus, part,
                    row.date("Competition Start Date"), row);

            Score score = new Score();
            score.setParticipant(context.participant(row));
            score.setCompetition(competition);
            score.setApparatus(apparatus);
            // The two-attempt vault shape suffixes each attempt's columns with 1 or 2
            if (row.hasColumn("Status1")) {
                score.setRoutine(routine(row, "1"));
                if (row.text("Status2") != null) {
                    score.setSecondRoutine(routine(row, "2"));
                }
                score.setCombinedBonus(row.decimal("Combined Bonus"));
                score.setCombinedSjPenalty(row.decimal("Combined SJ Penalty"));
                score.setTotalScore(row.decimal("Total"));
            } else {
                score.setRoutine(routine(row, ""));
                score.setTotalScore(score.getRoutine().getScore());
            }
            score = scoreRepository.save(score);
            context.getScores().add(score);
            context.getScorePlacings().add(new ImportContext.ScorePlacing(score, row.integer("Rank"),
                    row.integer("Qualification Rank"), row.code("Qualification", QualificationResult::find),
                    row.location()));
            // Optional: where the file states each score's team role, it isn't worked out from the totals
            TeamScoreRole teamRole = row.code("Team Role", TeamScoreRole::find);
            if (teamRole != null) {
                context.getStatedTeamRoles().put(score, teamRole);
            }
            context.getReport().count("scores");
        }
    }

    /**
     * Turns the placings printed with the scores into apparatus rankings, one per
     * competition, apparatus and purpose ({@link #rankPurpose}). Where Competition I
     * qualifies for apparatus finals, a non-vault apparatus has one ranking, which
     * decides the final ({@code Qualification Rank}, equal to {@code Rank}); vault has
     * two, the single-vault list ({@code Rank}, every vaulter, on the first vault) and
     * the two-vault list deciding the final ({@code Qualification Rank}, only those who
     * vaulted twice). A ranking is created only where some row places a score in it.
     */
    void rankScores(ImportContext context) {
        Map<String, List<ImportContext.ScorePlacing>> groups = new LinkedHashMap<>();
        for (ImportContext.ScorePlacing placing : context.getScorePlacings()) {
            Score score = placing.score();
            groups.computeIfAbsent(score.getCompetition().getId() + " " + score.getApparatus(),
                    key -> new ArrayList<>()).add(placing);
        }
        for (List<ImportContext.ScorePlacing> group : groups.values()) {
            Competition competition = group.getFirst().score().getCompetition();
            Apparatus apparatus = group.getFirst().score().getApparatus();
            RankingPurpose purpose = rankPurpose(context.getFormat().getApparatusFormat(), competition, apparatus);
            boolean qualifiesForFinals = competition.getType() == CompetitionType.C1 && competition.getPart() == null
                    && context.getFormat().getApparatusFormat() == TitleFormat.FINAL;
            if (!qualifiesForFinals) {
                group.stream()
                        .filter(placing -> placing.qualificationRank() != null || placing.qualification() != null)
                        .findFirst()
                        .ifPresent(placing -> {
                            throw new ImportException(placing.location() + ": 'Qualification' or "
                                    + "'Qualification Rank' is filled, but this competition qualifies no one to an "
                                    + "apparatus final (apparatus format " + context.getFormat().getApparatusFormat()
                                    + ")");
                        });
            }
            if (qualifiesForFinals && apparatus == Apparatus.VT) {
                rank(context, group, competition, apparatus, purpose, placing -> true,
                        ImportContext.ScorePlacing::rank, placing -> null,
                        placing -> placing.score().getRoutine().getScore());
                rank(context, group, competition, apparatus, RankingPurpose.QUALIFYING,
                        placing -> placing.qualificationRank() != null || placing.qualification() != null
                                || placing.score().getSecondRoutine() != null,
                        ImportContext.ScorePlacing::qualificationRank, ImportContext.ScorePlacing::qualification,
                        placing -> placing.score().getTotalScore());
            } else {
                rank(context, group, competition, apparatus, purpose, placing -> true,
                        placing -> purpose == RankingPurpose.QUALIFYING && placing.qualificationRank() != null
                                ? placing.qualificationRank() : placing.rank(),
                        ImportContext.ScorePlacing::qualification, placing -> placing.score().getTotalScore());
            }
        }
    }

    /**
     * The purpose of the ranking a score's own placing ({@code Rank}) belongs to. In an
     * unsplit Competition I it follows the apparatus format: where it qualifies for the
     * apparatus finals, the ranking deciding the final, except on vault, where it is the
     * single-vault list (the first vault, which counts for the all-around); where it
     * decides the apparatus titles itself, the final placings. An apparatus final's
     * placings are final; all others decide nothing (all-around and team finals, a split
     * competition's parts, a meet with no apparatus titles).
     */
    static RankingPurpose rankPurpose(TitleFormat apparatusFormat, Competition competition, Apparatus apparatus) {
        return switch (competition.getType()) {
            case C1 -> competition.getPart() != null ? RankingPurpose.INFORMATIONAL : switch (apparatusFormat) {
                case FINAL -> apparatus == Apparatus.VT ? RankingPurpose.INFORMATIONAL : RankingPurpose.QUALIFYING;
                case C1 -> RankingPurpose.FINAL;
                case NONE -> RankingPurpose.INFORMATIONAL;
            };
            case C3 -> RankingPurpose.FINAL;
            case C2, C4 -> RankingPurpose.INFORMATIONAL;
        };
    }

    private void rank(ImportContext context, List<ImportContext.ScorePlacing> group, Competition competition,
            Apparatus apparatus, RankingPurpose purpose, Predicate<ImportContext.ScorePlacing> member,
            Function<ImportContext.ScorePlacing, Integer> rank,
            Function<ImportContext.ScorePlacing, QualificationResult> qualification,
            Function<ImportContext.ScorePlacing, Double> total) {
        List<ImportContext.ScorePlacing> members = group.stream().filter(member).toList();
        if (members.stream().noneMatch(placing -> rank.apply(placing) != null || qualification.apply(placing) != null)) {
            return;
        }
        Ranking ranking = context.ranking(competition, RankingType.APPARATUS, apparatus, purpose);
        for (ImportContext.ScorePlacing placing : members) {
            ApparatusResult result = new ApparatusResult();
            result.setRanking(ranking);
            result.setParticipant(placing.score().getParticipant());
            result.setTotalScore(total.apply(placing));
            result.setRank(rank.apply(placing));
            result.setRankStatus(result.getRank() != null ? RankStatus.RANKED : null);
            result.setQualificationResult(purpose == RankingPurpose.QUALIFYING ? qualification.apply(placing) : null);
            apparatusResultRepository.save(result);
        }
    }

    private Routine routine(CsvRow row, String attempt) {
        Routine routine = new Routine(row.requiredCode("Status" + attempt, ScoreStatus::find));
        String difficulty = row.text("D" + attempt);
        if (difficulty != null && difficulty.startsWith("!")) {
            routine.setDifficultyInquiry(true);
            difficulty = difficulty.substring(1);
        }
        try {
            routine.setDifficulty(difficulty != null ? Double.valueOf(difficulty) : null);
        } catch (NumberFormatException e) {
            throw row.error("'D" + attempt + "' value '" + difficulty + "' is not valid");
        }
        routine.setExecution(row.decimal("E" + attempt));
        routine.setBonus(row.decimal("B" + attempt));
        routine.setPenalty(row.decimal("Penalty" + attempt));
        routine.setSjPenalty(row.decimal("SJ Penalty" + attempt));
        routine.setScore(row.decimal("Total" + attempt));
        for (Map.Entry<String, String> breakdown : BONUS_BREAKDOWN) {
            Double bonus = row.decimal(breakdown.getKey() + attempt);
            if (bonus != null) {
                routine.addBonusDetail(new BonusDetail(bonus, breakdown.getValue()));
            }
        }
        return routine;
    }
}
