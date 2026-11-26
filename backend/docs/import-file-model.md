# Import File Model

Reference for the CSV files produced by parsing an official artistic gymnastics results PDF into a shape ready for import into this
application's database.

Every table below has three columns: **Column** (the CSV header), **Description**
(what it represents), and **Entity Mapping** (the domain attribute it maps
to). Entity Mapping is left blank where no attribute exists yet — that's a
gap to close before that column can be imported as more than a
cross-check/reference value, not an oversight in this document.

## File families

| File | Scope | One file per |
|---|---|---|
| `EVENT.csv` | The competition(s) itself | One row per discipline+age sub-event |
| `<PREFIX>-PARTICIPANTS.csv` | Entry list | Discipline + Age Category |
| `<PREFIX>-JUDGES.csv` | Judging panels, all rounds | Discipline + Age Category |
| `<PREFIX>-SCORES-<COMPETITION>-<APP>.csv` | Individual results, one apparatus | Discipline + Age Category + Competition + Apparatus |
| `<PREFIX>-RANKING-{QUAL,FINAL}-{TEAM,AA}.csv` | Team/all-around standings: a qualifying or a final ranking | Discipline + Age Category + Purpose + Type |
| `<PREFIX>-RANKING-FINAL-<APP>.csv` | Combined standings on one apparatus for a competition split into parts (US Championships' two-day apparatus titles) | Discipline + Age Category + Apparatus |
| `<PREFIX>-IMPORT.json` | Manifest: the event's metadata plus every file above that belongs to this discipline+age | Discipline + Age Category |
| `<EVENT>-CORRECTIONS.csv` | Log of values written differently from the results book (not imported) | Event folder |

`<PREFIX>` is exactly the `Prefix` column of the event's `EVENT.csv`:
`<EVENT-SLUG>-<DISCIPLINE>-<AGE-CATEGORY>`, e.g.
`2026-EUROPEAN-CHAMPIONSHIPS-MAG-SR`. `<COMPETITION>` is one of `C1` / `C2` /
`C3` / `C4`, matching the `CompetitionType` enum in `data-model.md` exactly
(Competition I, which every entrant takes part in; the all-around final; the
apparatus finals; the team final), and `<APP>` is the two-letter `Apparatus` code.

Naming notes:

- `SCORES` files are per-athlete routine detail; `RANKING` files are the
  published standings (team or all-around, or multi-part combined standings),
  captured as published rather than computed.
- A ranking file's segment after `RANKING` is its purpose: `QUAL` for a
  ranking that qualifies for a later competition, `FINAL` for the one that
  decides the title. Its `Competition` column names the competition whose
  routines it ranks, which isn't always a final: the 2026 South American
  Games' `RANKING-FINAL-TEAM` is `C1`, since Competition I decided the team
  title, while the World Championships' is `C4`.
- `SR` is both the Senior age code and the Still Rings apparatus code;
  position disambiguates (`…-MAG-SR-SCORES-C1-SR.csv` is Senior Rings).
- Older files used other names (in git history; converted to these in 2026, rollout steps 2–3 in
  competition-models.md):
  - before the competition codes, `SCORES-QUAL-`, `SCORES-AA-`,
    `SCORES-EVENT-` and `SCORES-TEAM-` for `C1`, `C2`, `C3` and `C4` (a meet
    whose only competition was Competition I called it `AA`); `SUMMARY-` for
    `RANKING-`; a `Round` column for `Competition`, with a `Scores Round`
    column naming the competition ranked where it wasn't the row's own;
    `Session Start Date` for `Competition Start Date`;
  - earlier still, `QUALS-<APP>`, `FINALS-<APP>`, `TEAM-<APP>`, `AA-<APP>`,
    `QUALS-TEAM` and `FINALS-TEAM`.

Not every competition/file combination exists for every meet — a competition
only gets a `SCORES` file, and a ranking a `RANKING` file, if the source PDF
has an actual results report for it, independent of what a schedule page might
list (`instructions-results-parsing.md` §4.4, §4.9). The event's format
(`EVENT.csv`) says which rankings and finals there must be.

## General conventions

These apply to every file below.

- **Empty means empty.** An empty cell for "not applicable / not printed" —
  never `N/A`, `-` or a placeholder `0`. A penalty that wasn't applied is
  blank, not `0`.
- **`Status` is always written** (`COMPLETED`, `DNS`, `INVALID_VAULT`), never
  blank to mean completed, because `Routine.status` is required. The one
  exception is `Status2` on vault, where blank means "no second attempt was
  expected".
- **Values are copied as printed**: `0.0` stays `0.0`, `5.70` stays `5.70`,
  `-0.10` keeps its sign, and a leading `!` on a D score (under inquiry) stays
  part of the value (on import it's stripped and sets
  `Routine.difficultyInquiry`). The exceptions are documented per column (a `+` sign on a
  bonus and tie markers on ranks are dropped; a vault bonus asterisk becomes
  `Combined Bonus`).
- **Ties**: duplicate `Rank` values are copied as printed; ranks are never
  recomputed.
- **Every file states its own context** through the metadata prefix below,
  including a `Competition` column that is constant within most files.

## Self-describing metadata prefix

Every file below opens with a fixed run of metadata columns before its own
content, so the file is meaningful on its own without its filename intact.

| Column | Description | Entity Mapping |
|---|---|---|
| Event Name | The literal `Event.title` for this specific discipline+age sub-event (e.g. `37th Senior European Championships`) — not a coarser shared label. A single "European Championships" can produce several distinct `Event` rows (one per discipline+age), each with its own title, FIG event number, and date range; this column always matches the specific one this file belongs to. | `Event.title` |
| Discipline | `MAG` / `WAG`. Present in every file mainly to resolve which `Competition` (or, for `PARTICIPANTS`, which `Athlete`) the row belongs to. | `Competition.discipline` (also sets `Athlete.discipline` when importing `PARTICIPANTS`) |
| Competition | `C1` / `C2` / `C3` / `C4`: [CompetitionType](../src/main/java/doubletuck/meet/domain/CompetitionType.java). The competition a `SCORES` row was performed in, or a `JUDGES` row judged; on a `RANKING` row, the competition whose routines are ranked. Present on `SCORES`, `JUDGES` and `RANKING`. | `Competition.type` |
| Age Category | `SR` / `JR` / `JR16` / `JR17`. `Event` itself has no age category field — a single `Event` row in this data set happens to be scoped to one age category, but that's convention, not a schema guarantee. | `Competition.ageCategory` |
| Event Start Date | `Event.startDate`. Exists to disambiguate one year's edition from another, since `Event Name` alone doesn't carry a year. Present on `PARTICIPANTS`, `JUDGES`, `RANKING`. | `Event.startDate` |
| Competition Start Date | The calendar date this specific competition (and, for `C3`, this specific apparatus; for a competition split into parts, this part) was actually competed — sourced from the PDF's Competition Schedule pages, **never** from a page footer's report-generation timestamp (the two can disagree by a day or more). Present on `SCORES` only, in place of `Event Start Date`. Named "Start" because a large-field competition can in principle span more than one calendar day. | `Competition.date` |
| Part | Which part of a competition split across several days this row belongs to (`1`, `2`, … — US Championships' Day 1 and Day 2). Blank for an ordinary competition, and on `RANKING` rows holding the combined standings of a split competition (the whole competition). Present on `SCORES` and `RANKING`, right after `Competition`. | `Competition.part` |

## `EVENT.csv`

One row per discipline+age sub-event making up the competition.

| Column | Description | Entity Mapping |
|---|---|---|
| Prefix | The `<PREFIX>` used to name every other file for this sub-event | |
| Slug | Optional. The event's address on the site, lowercase words separated by hyphens (`2026-european-championships-wag-sr`). Needed when one folder holds several events, as the 2026 European Championships do; without it, the slug comes from the prefix (see [import-process.md](import-process.md)) | `Event.slug` |
| Title | The sub-event's official title | `Event.title` |
| Short Name | The name readers use, then the year, at most 40 characters; the same for every event in the folder: `Euros 2026`, `Worlds 2026`, `Pan Ams 2026`, `African Champs 2026`, `Oceania Champs 2026`, `US Champs 2026`, `Baku WC 2026` (Apparatus World Cup), `Paris WCC 2026` (World Challenge Cup) | `Event.shortName` |
| Discipline | The discipline of this sub-event covers | `Event.discipline` |
| Age Category | Age category of this sub-event: [AgeCategory](../src/main/java/doubletuck/meet/domain/AgeCategory.java) | |
| Level | The competition's tier: [EventLevel](../src/main/java/doubletuck/meet/domain/EventLevel.java) | `Event.level` |
| Start Date | The first day of competition of the event | `Event.startDate` |
| End Date | The final day of competition of the event | `Event.endDate` |
| City | The city where the event is hosted | `Event.city` |
| Country | The IOC code of the country hosting the event (`GER`, `NED` — not ISO `DEU`, `NLD`) | `Event.countryCode` |
| Venue | The name of the venue where the event is hosted | `Event.venue` |
| FIG Event Number | The FIG number that identifies the event if a FIG associated competition | `Event.figEventNumber` |
| Apparatus Suppliers | The equipment manufacturer for this competition | `Event.apparatusSuppliers` |
| Team Format | Where the team title was decided: `C1` (in Competition I), `FINAL` (in the team final, `C4`) or `NONE` (not contested): [TitleFormat](../src/main/java/doubletuck/meet/domain/TitleFormat.java). Required | `EventFormat.teamFormat` |
| AA Format | Likewise the all-around title (`FINAL`: the all-around final, `C2`). Required | `EventFormat.allAroundFormat` |
| Apparatus Format | Likewise the apparatus titles (`FINAL`: the apparatus finals, `C3`; `C1`: Competition I's placings, or for a split competition its combined standings, decide them). Required | `EventFormat.apparatusFormat` |

The format is copied into each manifest (`teamFormat`, `aaFormat`,
`apparatusFormat`), and the importer checks the files against it
([import-process.md](import-process.md#checks)): each title held has a
`FINAL` ranking of the competition the format names, qualifying rankings exist
only for a title decided in a later final, and no final is held for a title not
decided in one. Competition I is held per apparatus (an apparatus World Cup)
when the team and all-around formats are both `NONE`.

## `PARTICIPANTS.csv`

One row per athlete entry.

| Column | Description | Entity Mapping |
|---|---|---|
| Order | Entry-list position, as printed | |
| NOC Code | Country code the participant is competing under, as printed — 3 characters, or 4 for FIG's numbered neutral-athlete codes (`AIN1`, `AIN2`). Some entry lists print it only on each country's first row; it applies to the rows below until the next one | `Participant.noc` |
| Bib Number | Assigned bib number to uniquely identify the participant in the competition: the one the results print, where an entry list prints other numbers (2026 South American Games) | `Participant.bibNumber` |
| FIG License | FIG license number assigned to the gymnast | `Athlete.licenseNumber` |
| Name | Combined name exactly as printed — `SURNAME Given Name` in FIG sources, `Given Surname` in US Championships | |
| Surname | Participant's surname | `Athlete.surname` |
| Given Name | Participant's given name | `Athlete.givenName` |
| Birth Year | Participant's birth year. Blank where the source prints none (US Championships) | `Athlete.birthYear` |
| Birth Date | Participant's full birth date (`YYYY-MM-DD`), when the entry list publishes one (FIG World Championships does; European Championships prints only a year). Blank otherwise | `Athlete.birthDate` |
| Club | **US Championships only.** The athlete's gym/club as printed | `Participant.club` → `Club.name` (the club's country is the participant's NOC) |
| Entry Status | **Optional.** How the entry list shows the athlete: `COMPETITOR`, `RESERVE` (marked as a reserve), `WITHDRAWN` (struck through) or `HORS_CONCOURS` (marked `(Hors Concours)`: competes out of competition). A missing column or blank cell means `COMPETITOR`. Written where the entry list shows reserves or withdrawals (2026 Senior Pan Americans) or hors concours entries (2026 Varna World Challenge Cup) | `Participant.entryStatus` |

## `JUDGES.csv`

One row per judge per apparatus panel per round — every round bundled into
one file per discipline+age.

| Column | Description | Entity Mapping |
|---|---|---|
| Competition | The competition the judge is evaluating: see the metadata prefix | `Judge.competition` (with `Apparatus`, identifies the competition) |
| Apparatus | The apparatus the judge is evaluating: [Apparatus](../src/main/java/doubletuck/meet/domain/Apparatus.java) | `Judge.apparatus` |
| Function | The function the judge is in when evaluating: [JudgeFunction](../src/main/java/doubletuck/meet/domain/JudgeFunction.java). Superior Jury roles are written as printed (`President`, `Vice-President`, `Member`, `TD` — the Technical Delegate at a World Cup, `TDA` — the Technical Delegate Assistant) and resolve through `JudgeFunction.find`; reserve judges are `R` (single, unnumbered) or `R1`…`R6` (printed `RES`/`RES 1`… at the Mediterranean Games); World Cup panels print `DS1` (Difficulty Supervisor) and, on beam, `pen5` — written as `T2` (mapping table: `instructions-results-parsing.md` §4.7) | `Judge.function` |
| Name | Combined name of judge as printed | |
| Surname | Judge's surname | `Judge.surname` |
| Given Name | Judge's given name | `Judge.givenName` |
| NOC Code | Federation the judge is credited to, as printed. Blank when none is printed (e.g. a Superior Jury member) | `Judge.nocCode` |

## `SCORES-<COMPETITION>-<APP>.csv`

One row per athlete's result on one apparatus per competition. Column shape
depends on two independent things: whether the apparatus is Vault (a
double-attempt structure everywhere except Team/AA finals) and which
competition it is (Competition I carries extra qualification-tracking columns
that finals don't need). The `C1`/`C3`/`C4`/`C2` columns below mark which
competition(s) a column actually appears in.

The placings printed with the scores are stored as apparatus rankings
(data-model.md §5.1), whose purpose follows the competition and the event's
apparatus format: in a `C1` that qualifies for apparatus finals (apparatus
format `FINAL`), `Rank` is the qualifying ranking (on vault, the single-vault
list, which decides nothing, and `Qualification Rank` the qualifying two-vault
list); in a `C1` that decides the apparatus titles itself (`C1`), `Rank` is the
final ranking; a `C3`'s `Rank` is final; every other `Rank` (a `C2` or `C4`, a
split competition's parts, a meet with no apparatus titles) decides nothing.
`Qualification` and `Qualification Rank` may be filled only in a `C1` that
qualifies for apparatus finals.

### Non-vault apparatus (`FX`, `PH`, `SR`, `PB`, `HB` for MAG; `FX`, `BB`, `UB` for WAG)

| Column | C1 | C3 | C4 | C2 | Description | Entity Mapping |
|---|:-:|:-:|:-:|:-:|---|---|
| Competition | ✓ | ✓ | ✓ | ✓ | Which competition this result is from | `Competition.type` |
| Apparatus | ✓ | ✓ | ✓ | ✓ | Two-letter code | `Score.apparatus` (also `Competition.apparatus` for `C3`, and for `C1` at an apparatus World Cup) |
| Rank | ✓ | ✓ | ✓ | ✓ | Published apparatus placement. Duplicate values for ties are legitimate, copied as printed. Blank where the source prints no per-apparatus rank (e.g. the 2026 Worlds Team Final) | `ApparatusResult.rank` in the competition's apparatus ranking (data-model.md §5.1) |
| Bib | ✓ | ✓ | ✓ | ✓ | Identifies the athlete, joins to `PARTICIPANTS.csv` | *(join key to `Participant.bibNumber` — not re-stored on `Score`)* |
| Name | ✓ | ✓ | ✓ | ✓ | As printed on this report — cross-check against `PARTICIPANTS.csv` by Bib rather than trusting a possibly-truncated column here | *(not stored — verification only)* |
| NOC Code | ✓ | ✓ | ✓ | ✓ | | *(not stored — already on `Participant.noc`)* |
| Status | ✓ | ✓ | ✓ | ✓ | `COMPLETED`, `DNS`, or `INVALID_VAULT` — always written explicitly, never blank. Mirrors `Routine.status` being required | `Score.routine.status` |
| D | ✓ | ✓ | ✓ | ✓ | Difficulty score. A leading `!` marks it under inquiry | `Score.routine.difficulty`, `Score.routine.difficultyInquiry` |
| E | ✓ | ✓ | ✓ | ✓ | Execution score. Some sources print `E` before `D` (MAG PH and every WAG apparatus at the 2026 Europeans); the CSV always writes to these fixed column names regardless of source order | `Score.routine.execution` |
| B | ✓ | ✓ | ✓ | ✓ | Bonus. Populated for MAG (blank on every MAG PH row specifically — PH has no bonus). Present but always blank for WAG — kept for column alignment between disciplines rather than omitted | `Score.routine.bonus` |
| Penalty | ✓ | ✓ | ✓ | ✓ | Blank when no penalty applied — never `0`. Where a source splits penalties into several columns (2026 Szombathely World Challenge Cup: time, line, other), their sum | `Score.routine.penalty` |
| SJ Penalty | ✓ | ✓ | ✓ | ✓ | Superior Jury Penalty, distinct from `Penalty`. Not observed with a non-blank value on any non-vault apparatus so far | `Score.routine.sjPenalty` |
| Total | ✓ | ✓ | ✓ | ✓ | Blank when `Status` is `DNS` | `Score.routine.score` (and `Score.totalScore`, which equals it for a single routine) |
| Qualification | ✓ | | | | `Q`/`R1`–`R4`/`NR`/blank, matching `QualificationResult` exactly. Only where the apparatus format is `FINAL` (there's a further competition to qualify into); anywhere else the import fails. Sources that number the qualifiers (`Q1`…`Q8`, sporttech.io) are written as `Q`. Where the qualification table prints no markers but the final's start list names the finalists and ordered reserves (2026 Cottbus World Cup), they're taken from the start list | `ApparatusResult.qualificationResult` in the double-vault (`QUALIFYING`) ranking |
| Qualification Rank | ✓ | | | | Placement in the ranking that decides the apparatus final. On every non-vault apparatus that's the same ranking as `Rank`, so the value is always equal to `Rank` — written out anyway so every `C1` file pairs `Qualification` with its own rank, vault included. Like `Qualification`, only where the apparatus format is `FINAL` | `ApparatusResult.rank` in the qualification's `QUALIFYING` apparatus ranking |
| Team Role | ✓ | | ✓ | ✓ | **Optional**, last column, on any `SCORES` file (vault's too). What the score did for its country's team: `COUNTING` (one of the scores making up the team's apparatus total), `DROPPED` (a team member's score left out of it) or `INDIVIDUAL` (an athlete competing as an individual on this apparatus, e.g. a team's fifth athlete up for World Championships qualification only). Written where a source says who was up for the team on each apparatus (2026 Oceania Championships, from the Elevien results site). A missing column, or a NOC whose cells are all blank, means the importer works the roles out from the team summary's apparatus totals. Blank on a `DNS` row with no team role known | `TeamResultScore.role` (`INDIVIDUAL`: no link) |

### Vault, double-attempt shape (`C1` and `C3` only)

Built by joining a single-vault listing (everyone, one row per bib) and a
double-vault listing (only those attempting a second vault) — see
`instructions-results-parsing.md` §4.5 for the join logic. In `C1`, the two
listings are two different rankings over the same attempts: `Rank` ranks the
whole field on the first vault (the one that counts for all-around and team);
`Qualification Rank` ranks only the two-vault entrants on their combined
result, which decides the Vault final.

| Column | C1 | C3 | Description | Entity Mapping |
|---|:-:|:-:|---|---|
| Competition | ✓ | ✓ | | `Competition.type` |
| Apparatus | ✓ | ✓ | | `Score.apparatus` |
| Rank | ✓ | ✓ | `C1`: from the single-vault list (whole field, ranked on vault 1), or the all-around report's vault rank column where that is the only such ranking (2026 African Championships; at the 2026 Commonwealth Games it ranks only the all-arounders' first vaults against the field, and the other rows are blank); blank where the source has neither (2026 Junior Pan Americans, whose first vaults come from the all-around report; 2026 South American Games MAG, from the team and all-around reports). `C3`: the final's placement | `ApparatusResult.rank` in the competition's apparatus ranking (data-model.md §5.1) |
| Bib | ✓ | ✓ | | *(join key)* |
| Name | ✓ | ✓ | | *(not stored — verification only)* |
| NOC Code | ✓ | ✓ | | *(not stored)* |
| Status1 | ✓ | ✓ | Status of attempt 1: `COMPLETED`, `DNS`, or `INVALID_VAULT`. Always populated | `Score.routine.status` |
| D1 | ✓ | ✓ | | `Score.routine.difficulty`, `Score.routine.difficultyInquiry` |
| E1 | ✓ | ✓ | | `Score.routine.execution` |
| B1 | ✓ | ✓ | Bonus applied to attempt 1 itself. Populated for MAG, always blank for WAG so far | `Score.routine.bonus` |
| Penalty1 | ✓ | ✓ | | `Score.routine.penalty` |
| SJ Penalty1 | ✓ | ✓ | Superior Jury Penalty, attempt 1 — distinct from the ordinary `Penalty1`. Seen for WAG at the 2026 Europeans | `Score.routine.sjPenalty` |
| Total1 | ✓ | ✓ | | `Score.routine.score` |
| Status2 | ✓ | ✓ | Status of attempt 2, **four-state**: blank = no second attempt was expected at all (`Score.secondRoutine` is null); `COMPLETED`; `DNS` = a second attempt was expected (on the double-vault list) but not completed; `INVALID_VAULT` | `Score.secondRoutine.status` |
| D2 | ✓ | ✓ | | `Score.secondRoutine.difficulty`, `Score.secondRoutine.difficultyInquiry` |
| E2 | ✓ | ✓ | | `Score.secondRoutine.execution` |
| B2 | ✓ | ✓ | Bonus applied to attempt 2 itself. Same MAG/WAG split as `B1` | `Score.secondRoutine.bonus` |
| Penalty2 | ✓ | ✓ | | `Score.secondRoutine.penalty` |
| SJ Penalty2 | ✓ | ✓ | Superior Jury Penalty, attempt 2 | `Score.secondRoutine.sjPenalty` |
| Total2 | ✓ | ✓ | Blank whenever `Status2` is blank or `DNS` | `Score.secondRoutine.score` |
| Combined Bonus | ✓ | ✓ | A bonus applied to the *combined* two-vault result, not either attempt — distinct from `B1`/`B2`. Some sources print it as a `*` on the combined `Total` (WAG's +0.2), others as its own `Vault Bonus` column; either way it lands here as a number or blank, with `Total` holding the clean number. Present for MAG too (always blank so far) for column alignment | `Score.combinedBonus` |
| Combined SJ Penalty | ✓ | ✓ | **Optional.** A Superior Jury penalty on the *combined* two-vault result, not either attempt — distinct from `SJ Penalty1`/`SJ Penalty2`. Written negative, as deducted, though the source prints it unsigned in its `SJ Pen.` column beside the vault score (2026 Baku World Cup WAG qualification: `-0.3`); already deducted from `Total`. A missing column or blank cell means none. Written on every vault file of the 2026 Baku World Cup | `Score.combinedSjPenalty` |
| Total | ✓ | ✓ | The result the Vault final is decided on — `Total1` alone for a single-vault athlete, the published average plus `Combined Bonus` (and `Combined SJ Penalty`) for a completed two-vault athlete, blank when there's no valid combined result | `Score.totalScore` |
| Qualification | ✓ | | Only ever set from the double-vault list; blank for single-vault-only athletes | `ApparatusResult.qualificationResult` in the double-vault (`QUALIFYING`) ranking |
| Qualification Rank | ✓ | | Rank **within the double-vault list** — distinct from `Rank`. Blank for single-vault-only athletes | `ApparatusResult.rank` in the qualification's `QUALIFYING` apparatus ranking |

### Vault, single-attempt shape (`C4` and `C2`)

Team Final and All-Around Final vault routines are performed once, not
twice — same columns and same Entity Mapping as the non-vault apparatus
table above (`Status`→`Score.routine.status`, `D`→`Score.routine.difficulty`,
etc.), **not** the `1`/`2` split. Don't assume "Vault" always means the
double-attempt shape — check the actual page: US Championships' `C1` vault
uses the **double-attempt** shape (without `Qualification` columns) for the
levels that hold a two-vault vault event, since the same competition decides the
vault title.

### Bonus breakdown columns (US Championships)

USA Gymnastics MAG scoring itemizes bonuses that FIG folds into one `B`.
Those files carry the standard columns (`B` is the sum of the parts) plus
the itemized parts as trailing columns, so nothing printed is lost. Absent
from FIG files.

| Column | Description | Entity Mapping |
|---|---|---|
| D+ | Difficulty bonus | `Score.routine.bonusDetail` entry, description "Difficulty bonus" |
| E+ | Execution bonus (printed `0.0` on every routine in 2026) | `Score.routine.bonusDetail` entry, description "Execution bonus" |
| S+ | Stick bonus | `Score.routine.bonusDetail` entry, description "Stick bonus" |

On the double-attempt vault shape they're `D+1`/`E+1`/`S+1` and
`D+2`/`E+2`/`S+2`, mapping to `routine` and `secondRoutine` respectively.
`E+2` is always blank: the second-vault listings don't print it. US `ND`
(neutral deduction) is written to the standard `Penalty` column. WAG files
carry the breakdown columns too, always blank.

## `RANKING-{QUAL,FINAL}-{TEAM,AA}.csv`

Team or all-around standings only — one row per NOC (Team) or per athlete
(All-Around) — not the detailed per-athlete/per-apparatus scores feeding
into it (those live in `SCORES-<COMPETITION>-<APP>.csv` instead). A ranking
file exists only where the source PDF prints the standings (see "File
families" above).

- `RANKING-QUAL-*` is a **qualifying** ranking: it picks who goes on to the
  title's final, so it exists only where the event's format for the title is
  `FINAL`, and it ranks `C1`.
- `RANKING-FINAL-*` is the **final** ranking, deciding the title. It ranks the
  competition the format names: `C1` where Competition I decided the title
  (2026 South American Games, African Championships, Oceania Championships),
  otherwise the title's own final (`C4` team, `C2` all-around). Where a book
  prints both a qualifying and a final ranking over the same `C1` routines for
  a title Competition I decided (2026 Asian Championships), only the final one
  is written.

For a competition split into parts (US Championships), `RANKING-FINAL-AA`
holds a row per athlete per part (`Part` = 1, 2; `Purpose` `INFORMATIONAL`)
plus a row per athlete with `Part` blank for the combined standings — the
result the title is decided on. The combined rows leave the `<APP> Total`
columns blank (the source prints only the combined grand total).

| Column | Description | Entity Mapping |
|---|---|---|
| Competition | The competition whose routines are ranked (metadata prefix) | `Ranking.competitions` |
| Part | See the metadata prefix. Blank on combined rows of a split competition | `Competition.part` (blank → the whole competition) |
| Purpose | `QUALIFYING` in a `RANKING-QUAL-*` file, `FINAL` in a `RANKING-FINAL-*` file, `INFORMATIONAL` on a split competition's part rows (daily standings that decide nothing): [RankingPurpose](../src/main/java/doubletuck/meet/domain/RankingPurpose.java). Required, and must agree with the file name and part | `Ranking.purpose` |
| Rank | Placement in the standings | `TeamResult.rank` / `AllAroundResult.rank` |
| Rank Status | Blank when `Rank` is printed. Otherwise required, saying why there's no rank: `INCOMPLETE` (a partial all-around, including an entry who started no apparatus at all, or a team short of counting scores), `NOC_LIMIT` (left out under two-per-country, or a final ranking's per-country limit; what a qualifying ranking marks `NR`), `HORS_CONCOURS`, `DID_NOT_FINISH`, `UNPLACED` (the source prints no place, as on US Part 2 rows or below the places a final ranking prints): [RankStatus](../src/main/java/doubletuck/meet/domain/RankStatus.java) | `TeamResult.rankStatus` / `AllAroundResult.rankStatus` (`RANKED` where ranked) |
| Bib | Identifies the athlete. **All-Around ranking only** | |
| Name | Athlete name as printed. **All-Around ranking only** | |
| NOC Code | Country/federation the row represents | `Team.noc` (and `Team.name`) of the `TeamResult` |
| `<APP> Total` (one column per apparatus) | Already the sum/drop-lowest total printed by the source, not recomputed. Apparatus set and column order is discipline-specific: `FX, PH, SR, VT, PB, HB` for MAG, `FX, BB, UB, VT` for WAG. The exceptions, where the source prints no apparatus totals: the 2026 African Championships' are the sums of the member scores its team report prints in bold (the counting ones); the 2026 Oceania Championships' are the sums of the `COUNTING` scores, from the team line-ups. Either way checked against the printed team total | *(not stored — on a team ranking, used to check or work out `TeamResultScore.role` (`INDIVIDUAL`: no link))* |
| SJ Penalty | Penalty on the row as a whole, distinct from an individual routine's `Penalty`, as printed (negative) and already deducted from `Total` — e.g. a team penalty (2026 Senior Pan Americans MAG CUB, `-1.000`). Where a book takes part of a team penalty off an apparatus total (2026 Asian Championships WAG juniors LBN, beam), the whole penalty is written here and the apparatus total as the sum of its counting scores | `TeamResult.sjPenalty` / `AllAroundResult.sjPenalty` |
| Total | Grand total | `TeamResult.totalScore` / `AllAroundResult.totalScore` |
| Qualification | [QualificationResult](../src/main/java/doubletuck/meet/domain/QualificationResult.java). `RANKING-QUAL-*` only: a final ranking qualifies no one, and a marker on one fails the import. The 2026 Worlds All-Around qualification also uses `R4` | `TeamResult.qualificationResult` / `AllAroundResult.qualificationResult` |

## `RANKING-FINAL-<APP>.csv`

Combined standings on one apparatus for a competition split into parts — US
Championships' two-day apparatus titles. One row per athlete in the source's
two-day apparatus report, which lists only athletes who competed on that
apparatus on both days; for vault, only the two-vault entrants who contested
the vault title. All rows belong to the whole competition, so `Part` is
always blank, and `Purpose` is `FINAL` (the apparatus format is `C1`).

| Column | Description | Entity Mapping |
|---|---|---|
| Event Name, Discipline, Age Category, Event Start Date, Competition, Part | Metadata prefix | the whole `Competition` (`part` null) the ranking belongs to |
| Purpose | `FINAL` | `Ranking.purpose` |
| Apparatus | Two-letter code | `Ranking.apparatus` |
| Rank | Combined placement, as published | `ApparatusResult.rank` |
| Rank Status | As on the team and all-around rankings | `ApparatusResult.rankStatus` |
| Bib | Joins to `PARTICIPANTS.csv` | *(join key)* |
| Name | As printed | *(not stored — verification only)* |
| NOC Code | | *(not stored)* |
| Part 1 Total, Part 2 Total | Each part's result as printed in the combined report — for vault, the two-vault result. Cross-check against that part's `SCORES` row `Total` | *(not stored — already `Score.totalScore` on each part)* |
| Total | Combined total | `ApparatusResult.totalScore` |

## `CORRECTIONS.csv`

`<EVENT>-CORRECTIONS.csv` (the event folder's name, without a discipline or
age category) logs every value in the files above that differs from what the
results book prints, and why: a tie-break the book doesn't show, a status or
score taken from a better source, a misspelled judge. The files hold the
corrected value; this log keeps the printed one. It is written by hand,
applied by the parsers as they write each file (`common.Corrections`), and
not imported. A correction whose `Printed` value isn't the row's, or that
matches no file written, fails the parser, so the log can't drift from the
files.

| Column | Description |
|---|---|
| File | The corrected file's name without the event prefix and `.csv`, e.g. `MAG-JR-SCORES-C1-FX` or `WAG-JR-RANKING-FINAL-TEAM` |
| Key | The row: its `Bib` as printed (`Bib Number` in `PARTICIPANTS`), a team ranking's `NOC Code`, or a judge's `Competition Apparatus Function` (`-` for a blank apparatus), e.g. `C1 FX E1`. In `JUDGES`, the judge's `Name` as printed instead corrects every row with that name. Keys match the rows as printed, before any correction |
| Field | The corrected column, by its header |
| Printed | The value as the book prints it (blank when the book prints nothing) |
| Corrected | The value written |
| Category | `TIE_BREAK`, `RANK`, `SCORE`, `STATUS`, `NAME`, `JUDGE_NAME`, `LICENCE`, `BIRTH_DATE`, `NOC` (an entry printed under the wrong country), `ROW` (a row or value the book leaves out), `BIB` (a result printed with another athlete's bib) |
| Source | Where the corrected value comes from: `sporttech export`, `FIG athlete database`, `other panels`, … |
| Note | Free text |

