package doubletuck.meet.importer;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Judge;
import doubletuck.meet.domain.JudgeFunction;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.repository.JudgeRepository;
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
            List<Competition> competitions = context.competitionsForJudge(type, apparatus);
            if (competitions.isEmpty()) {
                competitionsWithoutScores.add(type + (apparatus != null ? " " + apparatus : ""));
                continue;
            }

            JudgeFunction function = row.requiredCode("Function", JudgeFunction::find);
            String surname = row.requiredText("Surname");
            String givenName = row.requiredText("Given Name");
            for (Competition competition : competitions) {
                Judge judge = new Judge();
                judge.setCompetition(competition);
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
}
