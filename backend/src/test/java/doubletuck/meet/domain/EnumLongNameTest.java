package doubletuck.meet.domain;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * {@code find} lookups by long name for the enums without a dedicated test class.
 */
class EnumLongNameTest {

    @Test
    void testApparatus() {
        assertEquals(Apparatus.SR, Apparatus.find("SR"));
        assertEquals(Apparatus.SR, Apparatus.find("still rings"));
        assertEquals("Horizontal Bar", Apparatus.HB.getLongName());
        assertNull(Apparatus.find("Rings"));
    }

    @Test
    void testRound() {
        assertEquals(Round.EVENT, Round.find("EVENT"));
        assertEquals(Round.EVENT, Round.find("Apparatus Final"));
        assertEquals(Round.AA, Round.find("all-around final"));
        assertEquals("Qualification", Round.QUAL.getLongName());
    }

    @Test
    void testCompetitionType_AcceptsTheFilesRoundCodes() {
        assertEquals(CompetitionType.C1, CompetitionType.find("C1"));
        assertEquals(CompetitionType.C4, CompetitionType.find("Competition IV"));
        assertEquals(CompetitionType.C1, CompetitionType.find("QUAL"));
        assertEquals(CompetitionType.C3, CompetitionType.find("Apparatus Final"));
        assertEquals(Round.TEAM, CompetitionType.C4.getLegacyRound());
        assertEquals(CompetitionType.C2, CompetitionType.of(Round.AA));
        assertNull(CompetitionType.find("C5"));
    }

    @Test
    void testRankingEnums() {
        assertEquals(RankingType.AA, RankingType.find("All-Around"));
        assertEquals(RankingPurpose.INFORMATIONAL, RankingPurpose.find("informational"));
        assertEquals(RankStatus.NOC_LIMIT, RankStatus.find("NOC Limit"));
        assertEquals(RankStatus.HORS_CONCOURS, RankStatus.find("HORS_CONCOURS"));
        assertEquals(TeamContributionRole.DROPPED, TeamContributionRole.find("Dropped"));
        assertNull(TeamContributionRole.find("INDIVIDUAL"));
        assertEquals(Discipline.MIX, Discipline.find("mix"));
    }

    @Test
    void testEventLevel() {
        assertEquals(EventLevel.WORLD_CHAMPIONSHIPS, EventLevel.find("WORLD_CHAMPIONSHIPS"));
        assertEquals(EventLevel.WORLD_CHAMPIONSHIPS, EventLevel.find("World Championships"));
        assertEquals("International Tournament", EventLevel.INTERNATIONAL_TOURNAMENTS.getLongName());
        assertEquals(EventLevel.REGIONAL_GAMES, EventLevel.find("Regional Games"));
        assertEquals(EventLevel.REGIONAL_COMPETITION, EventLevel.find("REGIONAL_COMPETITION"));
    }

    @Test
    void testScoreStatus() {
        assertEquals(ScoreStatus.DNS, ScoreStatus.find("DNS"));
        assertEquals(ScoreStatus.DNS, ScoreStatus.find("Did Not Start"));
        assertEquals("Invalid Vault", ScoreStatus.INVALID_VAULT.getLongName());
        assertNull(ScoreStatus.find("DNF"));
    }

    @Test
    void testEntryStatus() {
        assertEquals(EntryStatus.RESERVE, EntryStatus.find("RESERVE"));
        assertEquals(EntryStatus.WITHDRAWN, EntryStatus.find("Withdrawn"));
        assertEquals(EntryStatus.HORS_CONCOURS, EntryStatus.find("Hors Concours"));
        assertEquals("Competitor", EntryStatus.COMPETITOR.getLongName());
        assertNull(EntryStatus.find("SPARE"));
    }
}
