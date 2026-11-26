package doubletuck.meet.repository;

import doubletuck.meet.domain.AgeCategory;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Athlete;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.EventLevel;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.domain.Routine;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.ScoreStatus;
import doubletuck.meet.domain.Team;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.List;

/** Builds and saves the rows the ranking and result repository tests share. */
@Component
class RankingTestData {

    private final EventRepository eventRepository;
    private final CompetitionRepository competitionRepository;
    private final RankingRepository rankingRepository;
    private final TeamRepository teamRepository;
    private final AthleteRepository athleteRepository;
    private final ParticipantRepository participantRepository;
    private final ScoreRepository scoreRepository;

    RankingTestData(EventRepository eventRepository, CompetitionRepository competitionRepository,
            RankingRepository rankingRepository, TeamRepository teamRepository, AthleteRepository athleteRepository,
            ParticipantRepository participantRepository, ScoreRepository scoreRepository) {
        this.eventRepository = eventRepository;
        this.competitionRepository = competitionRepository;
        this.rankingRepository = rankingRepository;
        this.teamRepository = teamRepository;
        this.athleteRepository = athleteRepository;
        this.participantRepository = participantRepository;
        this.scoreRepository = scoreRepository;
    }

    Event event(String slug) {
        Event event = new Event();
        event.setTitle(slug);
        event.setShortName("Test");
        event.setSlug(slug);
        event.setStartDate(LocalDate.of(2026, 4, 20));
        event.setEndDate(LocalDate.of(2026, 4, 26));
        event.setCity("Stuttgart");
        event.setCountryCode("GER");
        event.setLevel(EventLevel.CONTINENTAL_CHAMPIONSHIPS);
        return eventRepository.save(event);
    }

    Competition competition(Event event, CompetitionType type, Discipline discipline) {
        Competition competition = new Competition();
        competition.setEvent(event);
        competition.setDate(LocalDate.of(2026, 4, 21));
        competition.setType(type);
        competition.setDiscipline(discipline);
        competition.setAgeCategory(AgeCategory.SR);
        return competitionRepository.save(competition);
    }

    Ranking ranking(RankingType type, Apparatus apparatus, RankingPurpose purpose, Competition... competitions) {
        Ranking ranking = new Ranking();
        ranking.setEvent(competitions[0].getEvent());
        ranking.setDiscipline(competitions[0].getDiscipline());
        ranking.setAgeCategory(AgeCategory.SR);
        ranking.setType(type);
        ranking.setApparatus(apparatus);
        ranking.setPurpose(purpose);
        ranking.getCompetitions().addAll(List.of(competitions));
        return rankingRepository.save(ranking);
    }

    Team team(Event event, Discipline discipline, String noc) {
        Team team = new Team();
        team.setEvent(event);
        team.setDiscipline(discipline);
        team.setAgeCategory(AgeCategory.SR);
        team.setName(noc);
        team.setNoc(noc);
        return teamRepository.save(team);
    }

    Participant participant(Event event, Discipline discipline, String surname, String noc) {
        Athlete athlete = new Athlete();
        athlete.setDiscipline(discipline);
        athlete.setSurname(surname);
        athlete.setGivenName("Test");
        athlete = athleteRepository.save(athlete);
        Participant participant = new Participant();
        participant.setEvent(event);
        participant.setAthlete(athlete);
        participant.setNoc(noc);
        return participantRepository.save(participant);
    }

    Score score(Participant participant, Competition competition, Apparatus apparatus, double total) {
        Routine routine = new Routine(ScoreStatus.COMPLETED);
        routine.setScore(total);
        Score score = new Score();
        score.setParticipant(participant);
        score.setCompetition(competition);
        score.setApparatus(apparatus);
        score.setRoutine(routine);
        score.setTotalScore(total);
        return scoreRepository.save(score);
    }
}
