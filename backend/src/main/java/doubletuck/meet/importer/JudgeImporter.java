package doubletuck.meet.importer;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Judge;
import doubletuck.meet.domain.JudgeFunction;
import doubletuck.meet.repository.JudgeRepository;
import doubletuck.meet.service.CompetitionNaming;
import org.springframework.stereotype.Component;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/** Imports {@code JUDGES.csv}, attaching each judge to the competition(s) their round and apparatus identify. */
@Component
class JudgeImporter {

    private final JudgeRepository judgeRepository;

    JudgeImporter(JudgeRepository judgeRepository) {
        this.judgeRepository = judgeRepository;
    }

    void importFile(ImportContext context, String fileName) {
        Set<String> competitionsWithoutScores = new LinkedHashSet<>();
        for (CsvRow row : CsvRow.read(context.file(fileName))) {
            CompetitionType type = row.requiredCode("Competition", CompetitionType::find);
            Apparatus apparatus = row.code("Apparatus", Apparatus::find);
            Integer round = row.integer("Round");
            Discipline panel = panel(context, row, apparatus);
            List<Competition> competitions = context.competitionsForJudge(type, apparatus, round);
            if (competitions.isEmpty()) {
                competitionsWithoutScores.add(type + (apparatus != null ? " " + apparatus : "")
                        + (round != null ? " round " + round : ""));
                continue;
            }

            JudgeFunction function = row.requiredCode("Function", JudgeFunction::find);
            String surname = row.requiredText("Surname");
            String givenName = row.requiredText("Given Name");
            for (Competition competition : competitions) {
                Judge judge = new Judge();
                judge.setCompetition(competition);
                judge.setDiscipline(panel);
                judge.setApparatus(apparatus);
                judge.setFunction(function);
                judge.setSurname(surname);
                judge.setGivenName(givenName);
                judge.setNocCode(row.text("NOC Code"));
                judgeRepository.save(judge);
                context.getReport().count("judges");
            }
        }
        competitionsWithoutScores.forEach(competition -> context.getReport().warn(fileName + ": judges for "
                + competition + " were skipped because no scores were imported for that competition"));
    }

    /**
     * The discipline of the judge's panel ({@code Panel}): required in a mixed competition, whose men's
     * and women's panels both judge floor, and the apparatus must be one of that discipline's; not
     * given elsewhere.
     */
    private static Discipline panel(ImportContext context, CsvRow row, Apparatus apparatus) {
        if (!context.isMixed()) {
            if (row.text("Panel") != null) {
                throw row.error("'Panel' is given only in a mixed team's judges file");
            }
            return null;
        }
        Discipline panel = row.requiredCode("Panel", Discipline::find);
        if (panel == Discipline.MIX) {
            throw row.error("'Panel' is MAG or WAG");
        }
        if (apparatus != null && !CompetitionNaming.apparatusOrder(panel).contains(apparatus)) {
            throw row.error(apparatus + " isn't a " + panel + " apparatus");
        }
        return panel;
    }
}
