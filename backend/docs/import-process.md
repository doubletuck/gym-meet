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

1. **Event and format.** Found by FIG event number, or when there is none, by title and
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
   the discipline is added (`2026-world-championships-wag`). The manifest's
   `teamFormat`, `aaFormat` and `apparatusFormat` (each `C1`, `FINAL` or
   `NONE`; required) are stored as the slice's `EventFormat`: where each title
   was decided. The files are checked against it (see [Checks](#checks)).
2. **Participants.** Each entry-list row is matched to an `Athlete` (below) and
   entered into the event. A club is found or created by name within the
   participant's NOC. Some entry lists print a country's NOC only on its first
   row; it carries down to the rows below.
3. **Scores.** Each row creates a `Score`, and the first score of a competition
   creates the `Competition` (see [Competitions](#competitions)). A `!` before a D
   score is stripped and sets `difficultyInquiry`. The itemized US bonus columns
   (`D+`, `E+`, `S+`) become `bonusDetail` entries. Once every scores file is read,
   the placings printed with the scores become apparatus rankings (see
   [Rankings](#rankings)).
4. **Rankings.** Team, all-around and combined apparatus standings
   (`RANKING-*` files) become rankings of the competition their `Competition`
   and `Part` identify (see [Rankings](#rankings)). Then the competitions and
   rankings are checked against the format.
5. **Judges.** Attached to the competition their `Competition` and apparatus identify.
6. **Reconciling.** The imported scores are checked against the published
   totals (see [Checks](#checks)).

### Competitions

The files name a competition by its type, `C1`–`C4` ([data-model.md](data-model.md)
§2). A score's competition is its `Competition` and `Part`, plus its apparatus when
the competition is held one per apparatus:

- **Apparatus finals** (`C3`) — always one competition per apparatus.
- **Competition I at an apparatus World Cup** — one competition per apparatus. A
  meet is one when its format holds no team or all-around title (both `NONE`).
- **Everything else** (championship Competition I, team and all-around finals)
  — one competition covering every apparatus.

The competition's date is the `Competition Start Date` of its scores. A split
competition's whole row (part blank), which holds only combined standings, is
created from the rankings and dated on its first part. Any other ranking row ranks
a competition whose scores must already be imported: a final ranking of `C1`
(2026 Asian Championships and South American Games: the team and all-around titles;
2026 Asian Games: the all-around title; 2026 Oceania Championships: both) creates
no competition of its own.

A judge with no apparatus (Superior Jury) in a competition held one per apparatus
is attached to each of those competitions: the finals' Superior Jury presides over
every apparatus final.

### Rankings

Each ranking is one competition's routines ranked for one purpose
([data-model.md](data-model.md) §5), created the first time a row needs it:

| File content | Ranking |
|---|---|
| File content | Ranking |
|---|---|
| `RANKING-QUAL-<X>` rows | `QUALIFYING` team or all-around ranking (Q/R/NR kept) |
| `RANKING-FINAL-<X>` rows | `FINAL` ranking; Q/R/NR on one fails the import |
| A split competition's part rows (`Part` set) | `INFORMATIONAL`: the day's standings decide nothing |
| `RANKING-FINAL-<APP>` rows (US) | `FINAL` apparatus ranking of the whole row |
| Score `Rank`/`Qualification Rank`/`Qualification`, `C1` with apparatus format `FINAL`, not vault | one `QUALIFYING` apparatus ranking (the two columns always agree) |
| Same, vault | `Rank`: an `INFORMATIONAL` single-vault list of every vaulter on the first vault; `Qualification Rank` + `Qualification`: a `QUALIFYING` double-vault list of those who vaulted twice |
| Score `Rank`, `C1` (not a part) with apparatus format `C1` | `FINAL` apparatus ranking |
| Score `Rank`, apparatus final (`C3`) | `FINAL` apparatus ranking |
| Score `Rank`, all-around or team final, a part, or apparatus format `NONE` | `INFORMATIONAL` apparatus ranking |

A ranking row's `Purpose` must agree with its file name (`QUALIFYING` in
`RANKING-QUAL-*`, `FINAL` in `RANKING-FINAL-*`) or, on a part's row, be
`INFORMATIONAL`. `Qualification` or `Qualification Rank` on a score where
Competition I qualifies no one to apparatus finals fails the import.

An apparatus ranking is created only where some row places a score in it. Team rows
find or create the slice's `Team` for the NOC. A ranking row with a printed rank
gets the rank status `RANKED`, and must leave `Rank Status` blank; one without a
rank must state its `Rank Status`. Results worked out from scores are `RANKED`
where ranked and otherwise unstated (the score's own status explains a DNS).

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

**Format.** These fail the import:

- a qualifying ranking of a title whose format isn't `FINAL`, or that doesn't
  rank `C1` (a title Competition I decided has a `FINAL` ranking of `C1`, not a
  qualifying one);
- a final ranking that doesn't rank the competition the format names (`C1`
  for `C1`; `C4`, `C2` or `C3` for a team, all-around or apparatus `FINAL`);
- a qualifying or final ranking of a title whose format is `NONE`;
- a title whose format isn't `NONE` with no `FINAL` ranking (a book never
  parsed, such as the 2026 Junior Europeans MAG all-around final);
- a `C4`, `C2` or `C3` competition whose title's format isn't `FINAL`.

**Totals.** Totals are stored as published, never recomputed
([data-model.md](data-model.md) §5), so the importer checks them against the
scores and reports any that don't agree as a warning:

- **Team totals.** How each score figured in each team result is recorded as a
  `TeamResultScore` link (`COUNTING` or `DROPPED`), per team result, so a score
  can count for one ranking and be dropped by another. Where a scores file states
  each score's team role (the optional `Team Role` column: `COUNTING`, `DROPPED`,
  `INDIVIDUAL`), the links follow it — an `INDIVIDUAL` score gets none, a `DNS`
  with a stated role is linked too — and each published team apparatus total is
  checked against the sum of the NOC's `COUNTING` scores; a NOC with roles stated
  for only some of its scored routines is reported too. Otherwise the results files don't say which
  scores were dropped from a team total, or which of a NOC's athletes were on
  the team — a NOC can enter individual athletes alongside its team (the 2026
  Europeans let teams add a sixth). So the importer works it out from the
  published team apparatus totals: it tries every group of the NOC's athletes,
  and a group is the team if, on every apparatus, some number of its members'
  top scores adds up to the published total. Those top scores counted; every
  other score of the NOC on that apparatus is linked as `DROPPED`, including the
  individuals' (the totals can't tell them apart). Groups that
  differ only by athletes whose scores never counted agree on what counted. If
  no group fits, or groups that fit disagree, every score is linked as counting
  and a warning is reported. This assumes an athlete is on the team for every
  apparatus or none; where the team's line-up changes by apparatus (the 2026
  Oceania Championships' fifth athlete), only stated roles get it right. The
  team total is then checked against the sum of its published apparatus totals
  plus any team penalty (`SJ Penalty`). Each team ranking is worked out on its
  own, including a final ranking of the qualification's routines.
- **All-around totals** against the sum of the athlete's scores in the ranked
  competition, plus any penalty on the result (`SJ Penalty`); for a split
  competition's whole row, against the sum of the parts' totals. A published
  `0.000` for an athlete with no scores that day is not reported.
- **Combined apparatus totals** (split competitions) against the sum of the parts'
  `Score.totalScore`.

A score's NOC differing from its participant's, a competition's scores having
different dates, and judges for a competition with no scores are also reported.

## Importing again

With `--import.replace`, a discipline and age category already in the event is
deleted and imported again: its format, its rankings with their results and team score links,
its teams, and its competitions with their scores and judges, then the event's participants of that discipline left with no results at all.
Athletes and clubs are kept, so the reimport matches them again. Other
disciplines and age categories sharing the event aren't touched.
