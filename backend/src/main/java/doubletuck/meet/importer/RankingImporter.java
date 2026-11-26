package doubletuck.meet.importer;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.QualificationResult;
import doubletuck.meet.domain.RankStatus;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.repository.AllAroundResultRepository;
import doubletuck.meet.repository.ApparatusResultRepository;
import doubletuck.meet.repository.TeamResultRepository;
import org.springframework.stereotype.Component;

/**
 * Imports {@code RANKING-*.csv} files: team standings (rows keyed by NOC),
 * all-around standings (rows keyed by bib), and a split competition's combined
 * apparatus standings (rows keyed by bib and apparatus). Each row names the
 * competition whose routines it ranks ({@code Competition}, {@code Part}) and the
 * ranking's {@code Purpose}: {@code QUALIFYING} in a {@code RANKING-QUAL-*} file,
 * {@code FINAL} in a {@code RANKING-FINAL-*} one, except a split competition's part
 * rows, whose daily standings are {@code INFORMATIONAL}.
 */
@Component
class RankingImporter {

    private final TeamResultRepository teamResultRepository;
    private final AllAroundResultRepository allAroundResultRepository;
    private final ApparatusResultRepository apparatusResultRepository;

    RankingImporter(TeamResultRepository teamResultRepository, AllAroundResultRepository allAroundResultRepository,
            ApparatusResultRepository apparatusResultRepository) {
        this.teamResultRepository = teamResultRepository;
        this.allAroundResultRepository = allAroundResultRepository;
        this.apparatusResultRepository = apparatusResultRepository;
    }

    void importFile(ImportContext context, String fileName) {
        RankingPurpose filePurpose = filePurpose(fileName);
        for (CsvRow row : CsvRow.read(context.file(fileName))) {
            CompetitionType type = row.requiredCode("Competition", CompetitionType::find);
            Integer part = row.integer("Part");
            Competition competition = context.competitionForResults(type, part, row);
            RankingPurpose purpose = row.requiredCode("Purpose", RankingPurpose::find);
            RankingPurpose expected = part != null ? RankingPurpose.INFORMATIONAL : filePurpose;
            if (purpose != expected) {
                throw row.error("Purpose " + purpose + " should be " + expected + (part != null
                        ? " on a part's row" : " in a " + fileName.substring(fileName.indexOf("RANKING-"))));
            }
            if (row.hasColumn("Apparatus")) {
                Apparatus apparatus = row.requiredCode("Apparatus", Apparatus::find);
                importApparatusResult(context, row,
                        context.ranking(competition, RankingType.APPARATUS, apparatus, purpose));
            } else if (row.hasColumn("Bib")) {
                importAllAroundResult(context, row, context.ranking(competition, RankingType.AA, null, purpose));
            } else {
                importTeamResult(context, row, context.ranking(competition, RankingType.TEAM, null, purpose));
            }
        }
    }

    private void importTeamResult(ImportContext context, CsvRow row, Ranking ranking) {
        TeamResult result = new TeamResult();
        result.setRanking(ranking);
        result.setTeam(context.team(row.requiredText("NOC Code")));
        result.setTotalScore(row.decimal("Total"));
        result.setSjPenalty(row.decimal("SJ Penalty"));
        result.setRank(row.integer("Rank"));
        result.setRankStatus(rankStatus(row, result.getRank()));
        result.setQualificationResult(qualification(row, ranking));
        context.getTeamResults().add(teamResultRepository.save(result));
        context.getReport().count("team results");

        // Not stored: kept to work out which scores counted toward the team total
        for (Apparatus apparatus : Apparatus.values()) {
            Double total = row.decimal(apparatus.name() + " Total");
            if (total != null) {
                context.getPublishedTeamTotals().add(new ImportContext.PublishedTeamTotal(result, apparatus, total,
                        row.location()));
            }
        }
    }

    private void importAllAroundResult(ImportContext context, CsvRow row, Ranking ranking) {
        AllAroundResult result = new AllAroundResult();
        result.setRanking(ranking);
        result.setParticipant(context.participant(row));
        result.setTotalScore(row.decimal("Total"));
        result.setSjPenalty(row.decimal("SJ Penalty"));
        result.setRank(row.integer("Rank"));
        result.setRankStatus(rankStatus(row, result.getRank()));
        result.setQualificationResult(qualification(row, ranking));
        context.getAllAroundResults().add(allAroundResultRepository.save(result));
        context.getReport().count("all-around results");
    }

    private void importApparatusResult(ImportContext context, CsvRow row, Ranking ranking) {
        ApparatusResult result = new ApparatusResult();
        result.setRanking(ranking);
        result.setParticipant(context.participant(row));
        result.setTotalScore(row.decimal("Total"));
        result.setRank(row.integer("Rank"));
        result.setRankStatus(rankStatus(row, result.getRank()));
        result.setQualificationResult(qualification(row, ranking));
        context.getApparatusResults().add(apparatusResultRepository.save(result));
        context.getReport().count("apparatus results");
    }

    private static RankingPurpose filePurpose(String fileName) {
        if (fileName.contains("-RANKING-QUAL-")) {
            return RankingPurpose.QUALIFYING;
        }
        if (fileName.contains("-RANKING-FINAL-")) {
            return RankingPurpose.FINAL;
        }
        throw new ImportException(fileName + ": a ranking file's name has RANKING-QUAL- or RANKING-FINAL-");
    }

    /** Blank when the row is ranked; otherwise required, saying why it isn't. */
    private static RankStatus rankStatus(CsvRow row, Integer rank) {
        RankStatus status = row.code("Rank Status", RankStatus::find);
        if (rank != null) {
            if (status != null && status != RankStatus.RANKED) {
                throw row.error("Rank Status " + status + " is given with rank " + rank);
            }
            return RankStatus.RANKED;
        }
        if (status == null || status == RankStatus.RANKED) {
            throw row.error("'Rank Status' is required where 'Rank' is blank");
        }
        return status;
    }

    /** Q/R/NR markers belong only to a ranking that qualifies for a later competition. */
    private static QualificationResult qualification(CsvRow row, Ranking ranking) {
        QualificationResult qualification = row.code("Qualification", QualificationResult::find);
        if (qualification != null && ranking.getPurpose() != RankingPurpose.QUALIFYING) {
            throw row.error("Qualification " + qualification + " is on a " + ranking.getPurpose()
                    + " ranking; only a qualifying ranking can carry qualification markers");
        }
        return qualification;
    }
}
