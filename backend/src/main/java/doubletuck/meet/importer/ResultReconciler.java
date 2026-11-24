package doubletuck.meet.importer;

import doubletuck.meet.domain.AllAroundResult;
import doubletuck.meet.domain.Apparatus;
import doubletuck.meet.domain.ApparatusResult;
import doubletuck.meet.domain.Participant;
import doubletuck.meet.domain.Score;
import doubletuck.meet.domain.Session;
import doubletuck.meet.domain.TeamScoreRole;
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
 * published rather than recomputed. Along the way it works out which scores
 * counted toward each team total, where the results files don't state each
 * score's team role.
 */
@Component
class ResultReconciler {

    // Scores are published to three decimals
    private static final double TOLERANCE = 0.0005;

    // Every group of a NOC's athletes is tried, so this bounds the 2^n search
    private static final int MAX_ATHLETES_PER_NOC = 12;

    void reconcile(ImportContext context) {
        Map<Team, List<ImportContext.PublishedTeamTotal>> teams = context.getPublishedTeamTotals().stream()
                .collect(Collectors.groupingBy(total -> new Team(total.session(), total.noc()), LinkedHashMap::new,
                        Collectors.toList()));
        teams.forEach((team, totals) -> {
            resolveTeamCount(context, team, totals);
            checkTeamTotal(context, team, totals);
        });
        context.getAllAroundResults().forEach(result -> checkAllAround(context, result));
        context.getApparatusResults().forEach(result -> checkApparatus(context, result));
    }

    private record Team(Session session, String noc) {
    }

    /**
     * Works out which of a NOC's scores counted toward its team's apparatus
     * totals and marks the rest as not counting.
     *
     * <p>A team's apparatus total is the sum of its members' best few scores (e.g.
     * 3 of 4 in qualification), but a NOC can also enter individual athletes
     * alongside its team, and the results files don't say which athletes were on
     * the team. So every group of the NOC's athletes is tried: a group is the team
     * if, on every apparatus, some number of its members' top scores adds up to
     * the published total. Groups differing only by athletes whose scores never
     * counted agree on what counted; if the groups that fit disagree, or none fits,
     * every score is left as counting and a warning is reported.
     *
     * <p>Standings ranking another session's routines are checked the same way,
     * but which scores counted is that session's own team standings to decide,
     * where it has any.
     *
     * <p>Where the scores file states the team roles, nothing is worked out: the
     * counting scores are only checked against the published totals.
     */
    private void resolveTeamCount(ImportContext context, Team team, List<ImportContext.PublishedTeamTotal> totals) {
        List<Score> scores = context.getScores().stream()
                .filter(score -> score.getSession().equals(team.session().sessionWithScores())
                        && score.getParticipant().getNoc().equals(team.noc())
                        && score.getRoutine().getScore() != null)
                .toList();
        List<Participant> athletes = scores.stream().map(Score::getParticipant).distinct().toList();
        String location = totals.get(0).location() + ": " + team.noc() + " team";
        if (scores.stream().anyMatch(context.getScoresWithTeamRole()::contains)) {
            checkStatedRoles(context, scores, totals, location);
            return;
        }
        if (athletes.size() > MAX_ATHLETES_PER_NOC) {
            context.getReport().warn(location + " has " + athletes.size() + " athletes, too many to work out "
                    + "which scores counted; all are left as counting");
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
                return;
            }
        }
        if (counted == null) {
            context.getReport().warn(location + ": no group of its athletes adds up to the published totals "
                    + totals.stream().map(total -> total.apparatus() + " " + total.total())
                            .collect(Collectors.joining(", ", "(", ")"))
                    + "; all are left as counting");
            return;
        }

        Session scoresSession = team.session().getScoresSession();
        if (scoresSession != null && context.getTeamResults().stream()
                .anyMatch(result -> result.getSession().equals(scoresSession))) {
            return;
        }
        Set<Apparatus> apparatusWithTotals = totals.stream().map(ImportContext.PublishedTeamTotal::apparatus)
                .collect(Collectors.toSet());
        for (Score score : scores) {
            if (apparatusWithTotals.contains(score.getApparatus()) && !counted.contains(score)) {
                // Whether a member's score was dropped or an individual's isn't known from the totals
                score.setTeamScoreRole(TeamScoreRole.DROPPED);
                context.getReport().count("scores not counting toward team");
            }
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

    /** Each published apparatus total must be the sum of the scores the file says counted. */
    private static void checkStatedRoles(ImportContext context, List<Score> scores,
            List<ImportContext.PublishedTeamTotal> totals, String location) {
        if (!context.getScoresWithTeamRole().containsAll(scores)) {
            context.getReport().warn(location + ": the team role is given for some of its scores but not all");
        }
        for (ImportContext.PublishedTeamTotal total : totals) {
            double counted = scores.stream()
                    .filter(score -> score.getApparatus() == total.apparatus()
                            && score.getTeamScoreRole() == TeamScoreRole.COUNTING)
                    .mapToDouble(score -> score.getRoutine().getScore())
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
    private void checkTeamTotal(ImportContext context, Team team, List<ImportContext.PublishedTeamTotal> totals) {
        context.getTeamResults().stream()
                .filter(result -> result.getSession().equals(team.session()) && result.getNoc().equals(team.noc())
                        && result.getTotalScore() != null)
                .forEach(result -> {
                    double expected = totals.stream().mapToDouble(ImportContext.PublishedTeamTotal::total).sum()
                            + penalty(result.getSjPenalty());
                    if (Math.abs(result.getTotalScore() - expected) >= TOLERANCE) {
                        context.getReport().warn(totals.get(0).location() + ": " + team.noc() + " team total "
                                + result.getTotalScore() + " differs from its apparatus totals and penalty, "
                                + String.format("%.3f", expected));
                    }
                });
    }

    private static double penalty(Double penalty) {
        return penalty == null ? 0 : penalty;
    }

    private void checkAllAround(ImportContext context, AllAroundResult result) {
        if (result.getTotalScore() == null) {
            return;
        }
        Session session = result.getSession();
        List<AllAroundResult> partResults = context.getAllAroundResults().stream()
                .filter(part -> part.getParticipant().equals(result.getParticipant())
                        && isPartOf(part.getSession(), session))
                .toList();

        double expected;
        if (!partResults.isEmpty()) {
            expected = partResults.stream().map(AllAroundResult::getTotalScore).filter(Objects::nonNull)
                    .mapToDouble(Double::doubleValue).sum();
        } else {
            List<Score> scores = scoresOf(context, result.getParticipant(),
                    score -> score.getSession().equals(session.sessionWithScores()));
            // Some results print 0.000 for an athlete who didn't compete that day
            if (scores.isEmpty() && result.getTotalScore() == 0) {
                return;
            }
            expected = scores.stream().map(score -> score.getRoutine().getScore()).filter(Objects::nonNull)
                    .mapToDouble(Double::doubleValue).sum();
        }
        warnIfDifferent(context, "all-around total", result.getParticipant(), session, result.getTotalScore(),
                expected + penalty(result.getSjPenalty()));
    }

    private void checkApparatus(ImportContext context, ApparatusResult result) {
        if (result.getTotalScore() == null) {
            return;
        }
        double expected = scoresOf(context, result.getParticipant(),
                score -> score.getApparatus() == result.getApparatus()
                        && isPartOf(score.getSession(), result.getSession()))
                .stream().map(Score::getTotalScore).filter(Objects::nonNull).mapToDouble(Double::doubleValue).sum();
        warnIfDifferent(context, result.getApparatus() + " combined total", result.getParticipant(),
                result.getSession(), result.getTotalScore(), expected);
    }

    private static boolean isPartOf(Session part, Session wholeRound) {
        return wholeRound.getPart() == null && part.getPart() != null && part.getRound() == wholeRound.getRound()
                && Objects.equals(part.getApparatus(), wholeRound.getApparatus());
    }

    private static List<Score> scoresOf(ImportContext context, Participant participant, Predicate<Score> filter) {
        return context.getScores().stream()
                .filter(score -> score.getParticipant().equals(participant) && filter.test(score))
                .toList();
    }

    private static void warnIfDifferent(ImportContext context, String what, Participant participant, Session session,
            double published, double expected) {
        if (Math.abs(published - expected) >= TOLERANCE) {
            context.getReport().warn("bib " + participant.getBibNumber() + " " + session.getRound()
                    + (session.getPart() != null ? " part " + session.getPart() : "") + " " + what + " "
                    + published + " differs from the sum of its scores, " + String.format("%.3f", expected));
        }
    }
}
