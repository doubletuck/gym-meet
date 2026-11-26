package doubletuck.meet.service;

import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.dto.CompetitionSummaryResponse;
import doubletuck.meet.dto.CompetitionSummaryResponse.RankingPurposes;
import doubletuck.meet.service.CompetitionNaming.Names;

import java.time.LocalDate;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

/** The competitions of one event as the API lists them, named from the event's rankings. */
public final class CompetitionSummaries {

    private final List<Competition> competitions;
    private final Map<Competition, RankingPurposes> purposes;
    private final Map<Competition, Names> names;

    /**
     * @param competitions the event's competitions
     * @param rankings     the event's rankings
     */
    public CompetitionSummaries(Collection<Competition> competitions, Collection<Ranking> rankings) {
        this.competitions = List.copyOf(competitions);
        this.purposes = CompetitionNaming.purposes(competitions, rankings);
        this.names = CompetitionNaming.names(competitions, purposes);
    }

    public CompetitionSummaryResponse of(Competition competition) {
        LocalDate endDate = SplitRound.parts(competition, competitions).stream()
                .map(Competition::getDate)
                .filter(date -> date.isAfter(competition.getDate()))
                .max(Comparator.naturalOrder())
                .orElse(null);
        Names name = names.get(competition);
        return new CompetitionSummaryResponse(competition.getId(), name.slug(), name.name(), name.shortName(),
                competition.getDiscipline(), competition.getAgeCategory(), competition.getType(),
                competition.getApparatus(), competition.getRound(), competition.getPart(),
                purposes.get(competition), competition.getDate(), endDate);
    }
}
