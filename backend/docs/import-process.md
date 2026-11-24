# Importing Results

How the parsed results files under `data/` (at the repository root) get into the database. The
files themselves are described in [import-file-model.md](import-file-model.md);
how they are produced from results PDFs is in
[instructions-results-parsing.md](instructions-results-parsing.md).

## Running an import

The importer runs from the command line under the `import` profile, alongside
the profile that supplies the database (`local` for a workstation):

```shell
mvn spring-boot:run -Dspring-boot.run.profiles=local,import \
  -Dspring-boot.run.arguments="--import.path=../data/2026/2026-WORLD-CHAMPIONSHIPS"
```

| Argument | Description |
|---|---|
| `--import.path` | A manifest (`*-IMPORT.json`), or a directory searched recursively for them — a single meet's folder, or a whole year. Can be given more than once. |
| `--import.replace` | Reimport a discipline and age category that is already in the database (see [Importing again](#importing-again)). Without it, that is an error. |
| `--import.status` | Import nothing; report each manifest as up to date, changed since it was imported, or not imported (see [What has been imported](#what-has-been-imported)). |

The app imports and then exits; it doesn't start the web server. For each
manifest it logs a report: how many of each record it created, how many
athletes it created rather than matched, and any warnings. Each manifest is
imported on its own, so one failing doesn't stop the others; the run exits with
an error if any failed.

## What has been imported

Each manifest imported is recorded as an `ImportRun` in the same transaction:
its event, discipline and age category, whether it replaced an earlier import,
its warning count and report, and a SHA-256 hash of the manifest and every file
it lists. A failed import leaves no record, as it leaves no results.

`--import.status` compares each manifest's files with its latest import's hash:

```shell
mvn spring-boot:run -Dspring-boot.run.profiles=local,import \
  -Dspring-boot.run.arguments="--import.path=../data/2026 --import.status"
```

```text
2026-WORLD-CHAMPIONSHIPS-MAG-SR-IMPORT.json: up to date, imported 2026-11-17T01:56:53Z
2026-US-CHAMPIONSHIPS-WAG-SR-IMPORT.json: changed since it was imported 2026-11-17T01:56:51Z
```

A changed manifest is brought up to date by importing it again with
`--import.replace`. Changing a file's line endings counts as a change.

## What a manifest import does

A manifest covers one discipline and age category of a competition (e.g. the
2026 Worlds WAG seniors). It's imported in a single transaction: a problem
anywhere in its files rolls back everything from that manifest, and the error
names the file and line.

1. **Event.** Found by FIG event number, or when there is none, by title and
   overlapping dates; created if not found. Two manifests sharing an event (the
   2026 Worlds' MAG and WAG) therefore import into one `Event`. A meet's
   disciplines can run on different days under one title (the 2026 US
   Championships: MAG 6–8 August, WAG 7–9 August), so a manifest that matches
   on title and overlapping dates widens the event's dates to cover its own.
   Every manifest needs a `shortName`; an existing event takes the
   manifest's when it differs ("event short names updated"). Databases from
   before short names start with each event's title cut to 40 characters,
   until its manifests are imported again.
   More than one event matching is an error. A new event's slug is
   the manifest's `slug`, when it has one: the 2026 European Championships are
   four events (one per discipline and age category, each with its own FIG
   number) in one folder, so each manifest names its own, e.g.
   `2026-european-championships-wag-sr`. A slug another event already has is an
   error. Without one, the slug is the manifest's prefix without the discipline
   and age category, lowercased: `2026-WORLD-CHAMPIONSHIPS-WAG-SR-IMPORT.json`
   gives `2026-world-championships`. When another event already has that slug,
   the discipline is added (`2026-world-championships-wag`).
2. **Participants.** Each entry-list row is matched to an `Athlete` (below) and
   entered into the event. A club is found or created by name within the
   participant's NOC. Some entry lists print a country's NOC only on its first
   row; it carries down to the rows below.
3. **Scores.** Each row creates a `Score`, and the first score of a session
   creates the `Session` (see [Sessions](#sessions)). A `!` before a D score is
   stripped and sets `difficultyInquiry`. The itemized US bonus columns (`D+`,
   `E+`, `S+`) become `bonusDetail` entries.
4. **Summaries.** Team, all-around and combined apparatus standings, attached
   to the session their round and part identify.
5. **Judges.** Attached to the session their round and apparatus identify.
6. **Reconciling.** The imported scores are checked against the published
   totals (see [Checks](#checks)).

### Sessions

A score's session is its round and part, plus its apparatus when the round is
held as one session per apparatus:

- **Apparatus finals** (`EVENT`) — always one session per apparatus.
- **Qualification at an apparatus-format meet** (a World Cup) — one session per
  apparatus. A meet is treated as apparatus-format when its manifest has no
  qualification summary, since such meets have no team or all-around ranking.
- **Everything else** (championship qualification, team and all-around finals)
  — one session covering every apparatus.

The session's date is the `Session Start Date` of its scores. A split round's
whole-round session (part blank), which holds only combined standings, is
created from the summaries and dated on its first part. A summary with a
`Scores Round` (2026 Asian Championships: the team and all-around finals,
`QUAL`) creates its session too, linked to that round's session
(`Session.scoresSession`) and dated on it; that round's scores must already be
imported, and the session can have no scores of its own.

A judge with no apparatus (Superior Jury) in a round held as one session per
apparatus is attached to each of those sessions: the finals' Superior Jury
presides over every apparatus final.

### Matching athletes

1. A **FIG license** identifies an athlete outright. If the license is already
   recorded under a different spelling of the name, that spelling is kept as an
   `AthleteNameVariant`.
2. Otherwise an athlete with the same **name and discipline**, ignoring case, or
   a known name variant of one, is the same person.
3. Otherwise a new athlete is created and listed in the report.

A name match whose FIG license, birth date or birth year contradicts the row
fails the import rather than merging two people. Since the athlete unique key
is name and discipline, two different athletes with the same name can't both
be stored. A matched athlete gains any license, birth date or birth year the
row adds; existing values are never overwritten.

Names (athletes, name variants and judges) are stored in written form whatever
capitalisation the source printed: each run of two or more capitals becomes a
capital followed by lowercase, so FIG's "BLAKELY" and "McDONALD" are stored as
"Blakely" and "McDonald", and "van POL" as "van Pol". The entities' name setters
apply this (`PersonName`), so it holds for every write, not only imports.

## Checks

Totals are stored as published, never recomputed
([data-model.md](data-model.md) §5), so the importer checks them against the
scores and reports any that don't agree as a warning:

- **Team totals.** Where a scores file states each score's team role (the
  optional `Team Role` column: `COUNTING`, `DROPPED`, `INDIVIDUAL`), it's
  stored as given, and each published team apparatus total is checked against
  the sum of the NOC's `COUNTING` scores; a NOC with roles stated for only some
  of its scores is reported too. Otherwise the results files don't say which
  scores were dropped from a team total, or which of a NOC's athletes were on
  the team — a NOC can enter individual athletes alongside its team (the 2026
  Europeans let teams add a sixth). So the importer works it out from the
  published team apparatus totals: it tries every group of the NOC's athletes,
  and a group is the team if, on every apparatus, some number of its members'
  top scores adds up to the published total. Those top scores counted; every
  other score of the NOC on that apparatus gets `teamScoreRole = DROPPED`,
  including the individuals' (the totals can't tell them apart). Groups that
  differ only by athletes whose scores never counted agree on what counted. If
  no group fits, or groups that fit disagree, every score is left as counting
  and a warning is reported. This assumes an athlete is on the team for every
  apparatus or none; where the team's line-up changes by apparatus (the 2026
  Oceania Championships' fifth athlete), only stated roles get it right. The
  team total is then checked against the sum of its published apparatus totals
  plus any team penalty (`SJ Penalty`). Team standings ranking another
  session's routines are checked against that session's scores the same way,
  and leave which scores counted to that session's own team standings where it
  has any.
- **All-around totals** against the sum of the athlete's scores in that
  session (or the session it ranks), plus any penalty on the result
  (`SJ Penalty`); for a split round's
  whole-round session, against the sum of the parts' totals. A published
  `0.000` for an athlete with no scores that day is not reported.
- **Combined apparatus totals** (split rounds) against the sum of the parts'
  `Score.totalScore`.

A score's NOC differing from its participant's, a session's scores having
different dates, and judges for a session with no scores are also reported.

## Importing again

With `--import.replace`, a discipline and age category already in the event is
deleted and imported again: its sessions with their scores, results and judges,
then the event's participants of that discipline left with no results at all.
Athletes and clubs are kept, so the reimport matches them again. Other
disciplines and age categories sharing the event aren't touched.
