package doubletuck.meet.importer;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Competition;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.TeamContributionRole;
import doubletuck.meet.domain.TeamResult;
import doubletuck.meet.domain.TeamResultScore;
import doubletuck.meet.domain.TeamScoreRole;
import doubletuck.meet.repository.TeamResultScoreRepository;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.Predicate;
import java.util.stream.Collectors;

/**
 * Checks the imported scores against the published totals, which are stored as
 * published rather than recomputed. Along the way it records how each score
 * figured in each team result, working it out from the team totals where the
 * results files don't state each score's team role.
 */
@Component
class ResultReconciler {

    // Scores are published to three decimals
    private static final double TOLERANCE = 0.0005;

    // Every group of a NOC's athletes is tried, so this bounds the 2^n search
    private static final int MAX_ATHLETES_PER_NOC = 12;

    private final TeamResultScoreRepository teamResultScoreRepository;

    ResultReconciler(TeamResultScoreRepository teamResultScoreRepository) {
        this.teamResultScoreRepository = teamResultScoreRepository;
    }

    void reconcile(ImportContext context) {
        Map<TeamResult, List<ImportContext.PublishedTeamTotal>> teams = context.getPublishedTeamTotals().stream()
                .collect(Collectors.groupingBy(ImportContext.PublishedTeamTotal::teamResult, LinkedHashMap::new,
                        Collectors.toList()));
        teams.forEach((team, totals) -> {
            linkTeamScores(context, team, totals);
            checkTeamTotal(context, team, totals);
        });
        context.getAllAroundResults().forEach(result -> checkAllAround(context, result));
        context.getApparatusResults().forEach(result -> checkApparatus(context, result));
    }

    /**
     * Records which of the NOC's scores counted toward the team result's apparatus
     * totals and which were left out.
     *
     * <p>A team's apparatus total is the sum of its members' best few scores (e.g.
     * 3 of 4 in qualification), but a NOC can also enter individual athletes
     * alongside its team, and the results files don't say which athletes were on
     * the team. So every group of the NOC's athletes is tried: a group is the team
     * if, on every apparatus, some number of its members' top scores adds up to
     * the published total. Groups differing only by athletes whose scores never
     * counted agree on what counted; if the groups that fit disagree, or none fits,
     * every score is linked as counting and a warning is reported. Whether a score
     * left out was a member's or an individual's isn't known from the totals, so
     * both are linked as dropped.
     *
     * <p>Where the scores file states the team roles, nothing is worked out: the
     * counting scores are only checked against the published totals, and an
     * individual's score isn't linked.
     */
    private void linkTeamScores(ImportContext context, TeamResult team, List<ImportContext.PublishedTeamTotal> totals) {
        String noc = team.getTeam().getNoc();
        Set<Competition> competitions = team.getRanking().getCompetitions();
        Set<Apparatus> apparatusWithTotals = totals.stream().map(ImportContext.PublishedTeamTotal::apparatus)
                .collect(Collectors.toSet());
        List<Score> nocScores = context.getScores().stream()
                .filter(score -> competitions.contains(score.getCompetition())
                        && score.getParticipant().getNoc().equals(noc))
                .toList();
        String location = totals.get(0).location() + ": " + noc + " team";
        // A stated role covers a member who didn't start too; worked out from the totals, only scores count
        if (nocScores.stream().anyMatch(context.getStatedTeamRoles()::containsKey)) {
            linkStatedRoles(context, team, nocScores, totals, location);
            return;
        }
        List<Score> scores = nocScores.stream().filter(score -> score.getRoutine().getScore() != null).toList();
        List<Score> onTotals = scores.stream().filter(score -> apparatusWithTotals.contains(score.getApparatus()))
                .toList();
        List<Participant> athletes = scores.stream().map(Score::getParticipant).distinct().toList();
        if (athletes.size() > MAX_ATHLETES_PER_NOC) {
            context.getReport().warn(location + " has " + athletes.size() + " athletes, too many to work out "
                    + "which scores counted; all are left as counting");
            link(context, team, onTotals, score -> true);
            return;
        }

        Set<Score> counted = null;
        for (int group = 1; group < 1 << athletes.size(); group++) {
            Set<Participant> members = new HashSet<>();
            for (int i = 0; i < athletes.size(); i++) {
                if ((group & 1 << i) != 0) {
                    members.add(athletes.get(i));
                }
            }
            Set<Score> groupCounted = countedScores(scores, members, totals);
            if (groupCounted == null) {
                continue;
            }
            if (counted == null) {
                counted = groupCounted;
            } else if (!countedValues(counted).equals(countedValues(groupCounted))) {
                context.getReport().warn(location + ": more than one group of its athletes adds up to the "
                        + "published totals, with different scores counting; all are left as counting");
                link(context, team, onTotals, score -> true);
                return;
            }
        }
        if (counted == null) {
            context.getReport().warn(location + ": no group of its athletes adds up to the published totals "
                    + totals.stream().map(total -> total.apparatus() + " " + total.total())
                            .collect(Collectors.joining(", ", "(", ")"))
                    + "; all are left as counting");
            link(context, team, onTotals, score -> true);
            return;
        }
        Set<Score> countedScores = counted;
        link(context, team, onTotals, countedScores::contains);
        onTotals.stream().filter(score -> !countedScores.contains(score))
                .forEach(score -> context.getReport().count("scores not counting toward team"));
    }

    private void link(ImportContext context, TeamResult team, List<Score> scores, Predicate<Score> counting) {
        for (Score score : scores) {
            teamResultScoreRepository.save(new TeamResultScore(team, score,
                    counting.test(score) ? TeamContributionRole.COUNTING : TeamContributionRole.DROPPED));
            context.getReport().count("team score links");
        }
    }

    /**
     * The members' scores counting toward each total -- on each apparatus, the
     * fewest top scores adding up to it -- or null when some total can't be made.
     */
    private static Set<Score> countedScores(List<Score> scores, Set<Participant> members,
            List<ImportContext.PublishedTeamTotal> totals) {
        Set<Score> counted = new HashSet<>();
        for (ImportContext.PublishedTeamTotal total : totals) {
            List<Score> ranked = scores.stream()
                    .filter(score -> score.getApparatus() == total.apparatus()
                            && members.contains(score.getParticipant()))
                    .sorted(Comparator.comparing((Score score) -> score.getRoutine().getScore()).reversed()
                            .thenComparing(Score::getId))
                    .toList();
            double sum = 0;
            int needed = 0;
            while (needed < ranked.size() && Math.abs(sum - total.total()) >= TOLERANCE) {
                sum += ranked.get(needed++).getRoutine().getScore();
            }
            if (Math.abs(sum - total.total()) >= TOLERANCE) {
                return null;
            }
            counted.addAll(ranked.subList(0, needed));
        }
        return counted;
    }

    /**
     * Links the scores as the file states their roles (a score with none stated counts),
     * leaving individuals' scores unlinked, then checks each published apparatus total is
     * the sum of the scores linked as counting.
     */
    private void linkStatedRoles(ImportContext context, TeamResult team, List<Score> scores,
            List<ImportContext.PublishedTeamTotal> totals, String location) {
        Map<Score, TeamScoreRole> stated = context.getStatedTeamRoles();
        // A DNS row may have no role stated; any other score without one is a gap in the file
        if (scores.stream().anyMatch(score -> score.getRoutine().getScore() != null && !stated.containsKey(score))) {
            context.getReport().warn(location + ": the team role is given for some of its scores but not all");
        }
        List<Score> members = scores.stream()
                .filter(score -> stated.containsKey(score) || score.getRoutine().getScore() != null)
                .filter(score -> stated.getOrDefault(score, TeamScoreRole.COUNTING) != TeamScoreRole.INDIVIDUAL)
                .toList();
        link(context, team, members,
                score -> stated.getOrDefault(score, TeamScoreRole.COUNTING) == TeamScoreRole.COUNTING);
        for (ImportContext.PublishedTeamTotal total : totals) {
            double counted = members.stream()
                    .filter(score -> score.getApparatus() == total.apparatus()
                            && stated.getOrDefault(score, TeamScoreRole.COUNTING) == TeamScoreRole.COUNTING)
                    .map(score -> score.getRoutine().getScore())
                    .filter(Objects::nonNull)
                    .mapToDouble(Double::doubleValue)
                    .sum();
            if (Math.abs(counted - total.total()) >= TOLERANCE) {
                context.getReport().warn(location + ": its counting " + total.apparatus() + " scores add up to "
                        + String.format("%.3f", counted) + ", not the published " + total.total());
            }
        }
    }

    // Tied scores make it arbitrary which athlete's counted, so groups are compared on values
    private static Map<Apparatus, List<Double>> countedValues(Set<Score> counted) {
        Map<Apparatus, List<Double>> values = new EnumMap<>(Apparatus.class);
        counted.forEach(score -> values.computeIfAbsent(score.getApparatus(), apparatus -> new ArrayList<>())
                .add(score.getRoutine().getScore()));
        values.values().forEach(Collections::sort);
        return values;
    }

    /** A team's total is its apparatus totals plus any penalty on the team as a whole. */
    private void checkTeamTotal(ImportContext context, TeamResult team, List<ImportContext.PublishedTeamTotal> totals) {
        if (team.getTotalScore() == null) {
            return;
        }
        double expected = totals.stream().mapToDouble(ImportContext.PublishedTeamTotal::total).sum()
                + penalty(team.getSjPenalty());
        if (Math.abs(team.getTotalScore() - expected) >= TOLERANCE) {
            context.getReport().warn(totals.get(0).location() + ": " + team.getTeam().getNoc() + " team total "
                    + team.getTotalScore() + " differs from its apparatus totals and penalty, "
                    + String.format("%.3f", expected));
        }
    }

    private static double penalty(Double penalty) {
        return penalty == null ? 0 : penalty;
    }

    private void checkAllAround(ImportContext context, AllAroundResult result) {
        if (result.getTotalScore() == null) {
            return;
        }
        Set<Competition> competitions = result.getRanking().getCompetitions();
        List<AllAroundResult> partResults = context.getAllAroundResults().stream()
                .filter(part -> part.getParticipant().equals(result.getParticipant())
                        && part.getRanking().getCompetitions().stream().anyMatch(partCompetition ->
                                competitions.stream().anyMatch(whole ->
                                        ImportContext.isPartOf(partCompetition, whole))))
                .toList();

        double expected;
        if (!partResults.isEmpty()) {
            expected = partResults.stream().map(AllAroundResult::getTotalScore).filter(Objects::nonNull)
                    .mapToDouble(Double::doubleValue).sum();
        } else {
            List<Score> scores = scoresOf(context, result.getParticipant(),
                    score -> competitions.contains(score.getCompetition()));
            // Some results print 0.000 for an athlete who didn't compete that day
            if (scores.isEmpty() && result.getTotalScore() == 0) {
                return;
            }
            expected = scores.stream().map(score -> score.getRoutine().getScore()).filter(Objects::nonNull)
                    .mapToDouble(Double::doubleValue).sum();
        }
        warnIfDifferent(context, "all-around total", result.getParticipant(), competitions, result.getTotalScore(),
                expected + penalty(result.getSjPenalty()));
    }

    private void checkApparatus(ImportContext context, ApparatusResult result) {
        if (result.getTotalScore() == null) {
            return;
        }
        Set<Competition> competitions = result.getRanking().getCompetitions();
        Apparatus apparatus = result.getRanking().getApparatus();
        double expected = scoresOf(context, result.getParticipant(),
                score -> score.getApparatus() == apparatus && competitions.stream()
                        .anyMatch(whole -> ImportContext.isPartOf(score.getCompetition(), whole)))
                .stream().map(Score::getTotalScore).filter(Objects::nonNull).mapToDouble(Double::doubleValue).sum();
        warnIfDifferent(context, apparatus + " combined total", result.getParticipant(), competitions,
                result.getTotalScore(), expected);
    }

    private static List<Score> scoresOf(ImportContext context, Participant participant, Predicate<Score> filter) {
        return context.getScores().stream()
                .filter(score -> score.getParticipant().equals(participant) && filter.test(score))
                .toList();
    }

    private static void warnIfDifferent(ImportContext context, String what, Participant participant,
            Set<Competition> competitions, double published, double expected) {
        if (Math.abs(published - expected) >= TOLERANCE) {
            Competition competition = competitions.iterator().next();
            context.getReport().warn("bib " + participant.getBibNumber() + " "
                    + competition.getType()
                    + (competition.getPart() != null ? " part " + competition.getPart() : "") + " " + what + " "
                    + published + " differs from the sum of its scores, " + String.format("%.3f", expected));
        }
    }
}
