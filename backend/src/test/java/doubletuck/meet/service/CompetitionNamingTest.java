package doubletuck.meet.service;

import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.CompetitionType;
import doubletuck.meet.domain.Discipline;
import doubletuck.meet.domain.Event;
import doubletuck.meet.domain.Ranking;
import doubletuck.meet.domain.RankingPurpose;
import doubletuck.meet.domain.RankingType;
import doubletuck.meet.dto.CompetitionSummaryResponse.RankingPurposes;
import doubletuck.meet.service.CompetitionNaming.Names;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

import static doubletuck.meet.domain.RankingPurpose.FINAL;
import static doubletuck.meet.domain.RankingPurpose.INFORMATIONAL;
import static doubletuck.meet.domain.RankingPurpose.QUALIFYING;
import static org.junit.jupiter.api.Assertions.*;

class CompetitionNamingTest {

    @Test
    void testNames_Finals() {
        assertNames("Team Final", "Team Final", "team-final", competition(CompetitionType.C4, null, null));
        assertNames("All-Around Final", "AA Final", "all-around-final", competition(CompetitionType.C2, null, null));
        assertNames("Balance Beam Final", "Final", "beam-final", competition(CompetitionType.C3, Apparatus.BB, null));
        assertNames("Horizontal Bar Final", "Final", "high-bar-final",
                competition(CompetitionType.C3, Apparatus.HB, null));
        Competition round = competition(CompetitionType.C4, null, null);
        round.setRound(3);
        assertNames("Team Final, Round 3", "Team Final, Round 3", "team-final-round-3", round);
    }

    @Test
    void testNames_CompetitionIDecidingNothing_IsTheQualification() {
        // Worlds
        assertNames("Qualification", "Qualification", "qualification",
                competition(CompetitionType.C1, null, null), purposes(QUALIFYING, QUALIFYING, QUALIFYING));
        // An apparatus World Cup's
        assertNames("Vault Qualification", "Qualification", "vault-qualification",
                competition(CompetitionType.C1, Apparatus.VT, null), purposes(null, null, QUALIFYING));
        // Nothing ranked
        assertNames("Qualification", "Qualification", "qualification",
                competition(CompetitionType.C1, null, null), purposes(null, null, null));
    }

    @Test
    void testNames_CompetitionIDecidingTitlesAndQualifying_NamesBoth() {
        // SA Games, African Championships
        assertNames("Team and All-Around Final · Apparatus Qualification", "Qualification", "qualification",
                competition(CompetitionType.C1, null, null), purposes(FINAL, FINAL, QUALIFYING));
        // Asian Games
        assertNames("All-Around Final · Team and Apparatus Qualification", "Qualification", "qualification",
                competition(CompetitionType.C1, null, null), purposes(QUALIFYING, FINAL, QUALIFYING));
        // Commonwealth Games
        assertNames("Team Final · All-Around and Apparatus Qualification", "Qualification", "qualification",
                competition(CompetitionType.C1, null, null), purposes(FINAL, QUALIFYING, QUALIFYING));
    }

    @Test
    void testNames_CompetitionIDecidingEverything_IsAFinal() {
        // Oceania
        assertNames("Team and All-Around Final", "Final", "team-and-all-around-final",
                competition(CompetitionType.C1, null, null), purposes(FINAL, FINAL, null));
        // US Championships, whose single-vault lists decide nothing
        assertNames("All-Around and Apparatus Final", "Final", "all-around-and-apparatus-final",
                competition(CompetitionType.C1, null, null), purposes(null, FINAL, FINAL));
        assertNames("Team, All-Around and Apparatus Final", "Final", "team-all-around-and-apparatus-final",
                competition(CompetitionType.C1, null, null), purposes(FINAL, FINAL, FINAL));
    }

    @Test
    void testNames_Parts_NamedAfterTheirWhole() {
        // US Championships: the whole's rankings decide the titles, each day's decide nothing
        Competition whole = competition(CompetitionType.C1, null, null);
        Competition day1 = competition(CompetitionType.C1, null, 1);
        Competition day2 = competition(CompetitionType.C1, null, 2);
        List<Competition> competitions = List.of(whole, day1, day2);
        List<Ranking> rankings = List.of(ranking(RankingType.AA, FINAL, whole),
                ranking(RankingType.APPARATUS, FINAL, whole), ranking(RankingType.AA, INFORMATIONAL, day1),
                ranking(RankingType.AA, INFORMATIONAL, day2));

        Map<Competition, RankingPurposes> purposes = CompetitionNaming.purposes(competitions, rankings);
        Map<Competition, Names> names = CompetitionNaming.names(competitions, purposes);

        assertEquals(new RankingPurposes(null, INFORMATIONAL, null), purposes.get(day1));
        assertEquals(new Names("All-Around and Apparatus Final", "Final", "all-around-and-apparatus-final"),
                names.get(whole));
        assertEquals(new Names("All-Around and Apparatus Final, Part 1", "Final, Part 1",
                "all-around-and-apparatus-final-part-1"), names.get(day1));
        assertEquals("all-around-and-apparatus-final-part-2", names.get(day2).slug());
    }

    @Test
    void testPurposes_PrefersTheRankingDecidingTheMost() {
        Competition c1 = competition(CompetitionType.C1, null, null);
        Competition c3 = competition(CompetitionType.C3, Apparatus.VT, null);
        List<Ranking> rankings = List.of(ranking(RankingType.APPARATUS, INFORMATIONAL, c1),
                ranking(RankingType.APPARATUS, QUALIFYING, c1), ranking(RankingType.AA, FINAL, c1),
                ranking(RankingType.APPARATUS, FINAL, c3));

        assertEquals(new RankingPurposes(null, FINAL, QUALIFYING),
                CompetitionNaming.purposes(List.of(c1, c3), rankings).get(c1));
    }

    @Test
    void testOrder_TypesThenOlympicApparatusThenCombinedBeforeParts() {
        List<String> ordered = Stream.of(
                        competition(CompetitionType.C3, Apparatus.HB, null),
                        competition(CompetitionType.C3, Apparatus.FX, null),
                        competition(CompetitionType.C2, null, null),
                        competition(CompetitionType.C2, null, 2),
                        competition(CompetitionType.C2, null, 1),
                        competition(CompetitionType.C1, null, null))
                .sorted(CompetitionNaming.order())
                .map(competition -> CompetitionNaming.names(competition, purposes(null, null, null)).slug())
                .toList();

        assertEquals(List.of("qualification", "all-around-final", "all-around-final-part-1",
                "all-around-final-part-2", "floor-final", "high-bar-final"), ordered);
    }

    private static void assertNames(String name, String shortName, String slug, Competition competition) {
        assertNames(name, shortName, slug, competition, purposes(null, null, null));
    }

    private static void assertNames(String name, String shortName, String slug, Competition competition,
            RankingPurposes purposes) {
        assertEquals(new Names(name, shortName, slug), CompetitionNaming.names(competition, purposes));
    }

    private static RankingPurposes purposes(RankingPurpose team, RankingPurpose allAround, RankingPurpose apparatus) {
        return new RankingPurposes(team, allAround, apparatus);
    }

    private static long nextId = 1;

    private static Ranking ranking(RankingType type, RankingPurpose purpose, Competition... competitions) {
        Ranking ranking = new Ranking();
        ranking.setId(nextId++);
        ranking.setDiscipline(Discipline.MAG);
        ranking.setType(type);
        ranking.setPurpose(purpose);
        ranking.getCompetitions().addAll(new ArrayList<>(List.of(competitions)));
        return ranking;
    }

    private static final Event EVENT = new Event();

    static {
        EVENT.setId(1L);
    }

    private static Competition competition(CompetitionType type, Apparatus apparatus, Integer part) {
        Competition competition = new Competition();
        competition.setEvent(EVENT);
        competition.setDiscipline(Discipline.MAG);
        competition.setType(type);
        competition.setApparatus(apparatus);
        competition.setPart(part);
        return competition;
    }
}
