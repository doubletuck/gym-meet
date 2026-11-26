package doubletuck.meet.service;

import doubletuck.meet.domain.Competition;
import doubletuck.meet.exception.ConflictException;
import doubletuck.meet.repository.CompetitionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CompetitionService {

    private final CompetitionRepository competitionRepository;

    public CompetitionService(CompetitionRepository competitionRepository) {
        this.competitionRepository = competitionRepository;
    }

    /**
     * Creates a competition, rejecting a duplicate (same event, type, discipline,
     * age category, apparatus, round and part) with a {@link ConflictException}.
     * The database's {@code uk_competition} constraint rejects one too; this check
     * reports it as a conflict naming the competition rather than a SQL error.
     */
    @Transactional
    public Competition createCompetition(Competition competition) {
        // A null apparatus, round or part matches only a competition where it is also null
        if (competitionRepository.findByEventAndTypeAndDisciplineAndAgeCategoryAndApparatusAndRoundAndPart(
                competition.getEvent(), competition.getType(), competition.getDiscipline(),
                competition.getAgeCategory(), competition.getApparatus(), competition.getRound(),
                competition.getPart()).isPresent()) {
            throw new ConflictException("A " + competition.getType() + " competition for event "
                    + competition.getEvent().getId() + " (" + competition.getDiscipline() + " "
                    + competition.getAgeCategory()
                    + (competition.getApparatus() != null ? " " + competition.getApparatus() : "")
                    + (competition.getRound() != null ? " round " + competition.getRound() : "")
                    + (competition.getPart() != null ? " part " + competition.getPart() : "") + ") already exists");
        }
        return competitionRepository.save(competition);
    }
}
