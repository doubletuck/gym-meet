# Parsing Results PDFs into CSV

How to turn an official results PDF into the import files under
`data/<year>/<event>/`. This is the *how*: tools, techniques, checks, and what
each kind of source document does. The *what* — every file, column and its
database mapping — is [`import-file-model.md`](import-file-model.md); the
entities are in [`data-model.md`](data-model.md).

- The step-by-step procedure is the `parse-results` skill
  (`.claude/skills/parse-results/SKILL.md`), which refers back here.
- Parsers live in [`tools/results-parsing/`](../tools/results-parsing/): one
  `parse_<year>_<event>.py` per meet, sharing
  [`common.py`](../tools/results-parsing/common.py).
- When a new PDF breaks an assumption, add what you learned to the right
  section below (§4 conventions, §5 the source format) rather than appending a
  history.

## 1. Workflow

1. **Survey the PDF** — page count, which pages have text, which report types
   it contains, and that it is the competition, discipline and level you
   expect (§2.1–§2.3).
2. **Identify the source format** (§5) and the **competition structure**
   (§4.9); stop and discuss anything the data model can't represent yet.
3. **Write the meet's parser** on top of `common.py`; transcribe any scanned
   pages (§2.3).
4. **Run every check in §3**, on a scratch copy first; plant a wrong value to
   prove the checks catch it.
5. **Write the files in place**, including `<PREFIX>-IMPORT.json`, and compare
   against any files that already existed.
6. **Report oddities** and update these docs.

## 2. Tools and techniques

### 2.1 Text extraction

- **poppler-utils** (`brew install poppler`): `pdftotext`, `pdftoppm`,
  `pdfinfo`, `pdfimages`.
- **Always `pdftotext -layout`** — column alignment survives as whitespace,
  which every technique below relies on. Split the output on form feed
  (`\f`) to get physical pages; `pdftoppm -f/-l` wants physical page numbers,
  not the "Page X / Y" printed in footers.
- Parsers run with `python3 -I` (isolated mode; it also keeps the script's
  folder off `sys.path`, so they add it explicitly to import `common`).

### 2.2 Surveying a long PDF

Results books are concatenations of many small reports. Before parsing,
list every physical page with its report identity (footer code and title for
FIG books, header lines for others) and collapse runs of the same report.
Check what the book actually is: one "Cottbus" PDF turned out to be a rhythmic
gymnastics book from another competition.

### 2.3 Scanned pages

A page with no text layer gives `pdftotext` nothing (`pdfimages -list` shows a
full-page image). No OCR package is installed; read the pages as images instead:

- **Map the book** with
  [`contact_sheet.py`](../tools/results-parsing/contact_sheet.py): it stacks
  each page's title band, labelled with the page number, into one image.
- **Read pages at ~110 dpi** (`pdftoppm -r 110 -png`, cropped to the table)
  and transcribe them into pipe-separated files under
  `tools/results-parsing/transcriptions/<EVENT>/` (format: the README there).
  The parser reads those files like any other source.
- **Look for a text copy** of the same results first (a federation or FIG
  website often has one) and use transcription only for what's missing; where
  both exist, compare them (§3). sporttech.io results can be exported as a CSV
  of every frame (Senior Pan Americans, §5.5).
- **A whole book of tables** (Senior Pan Americans, ~150 pages) is too much to
  read by eye; draft it with OCR (macOS only). Render the pages
  (`pdftoppm -r 220 -png <pdf> <scratch>/pages/p`), OCR them with
  [`ocr_pages.swift`](../tools/results-parsing/ocr_pages.swift) (the Vision
  framework, one word per line with its box), then draft transcriptions with
  [`ocr_draft.py`](../tools/results-parsing/ocr_draft.py): `layout` rebuilds a
  page as text for surveying; `table`, `vault-list`, `team` and `entries` draft
  sporttech.io tables and an organizer entry list, placing words in columns by
  position and marking every row that doesn't parse or add up with `!`.
  Correct those against the image (the parsers reject `!` lines), and check
  markers by eye. OCR drops lone characters (`0`, `—`, a leading `I`/`J`),
  misreads struck-through numbers and swaps Latin letters for Cyrillic
  look-alikes in names; arithmetic alone misses a dropped bare `0`, so compare
  with a text copy when there is one. Other layouts need a new `ocr_draft.py`
  mode.

### 2.4 Read the header row first, every time

Column presence and order differ between sources, disciplines and even
apparatus in the same book (`E` before `D` on some tables, an extra `Bonus`
column on others, Q/R columns on only some pages). Print the literal header
line before writing a parser for a table. Values always go to the fixed CSV
column names regardless of source order.

### 2.5 Tokenizing a fixed-width row

- **Split on two or more spaces** (`re.split(r'\s{2,}', …)`); single spaces
  occur only inside names.
- **Strip a trailing one-character marker first.** A right-aligned `Q` gets
  more leading spaces than `R1`/`NR`, so `13.833 R1` fuses on a naive split:
  match `\s+(Q|R\d|NR)\s*$` before tokenizing.
- **Never slice by fixed character offsets** taken from a header: columns
  drift by a character or two between rows.
- **Short rows are DNS/DNF rows** — detect them by token count, not by forcing
  the normal mapping. A placeholder `0.000` on a DNS row is not a score.
- **Penalty and bonus can share columns** and either may be empty; the sign
  separates them (bonus positive, sometimes printed `+0.1`; penalty negative).
  3-decimal tokens are scores, 1-decimal tokens are penalty/bonus.
- **pdftotext occasionally moves a value to the next line** (a NOC and total
  pushed below the name) or joins a NOC to the name with one space; identity
  regexes must tolerate both.

### 2.6 Positional parsing

When a line omits values for skipped apparatus, order alone can't tell which
value belongs where — match by column position:

- Places printed under a Final line: assign each to the Final value whose
  right edge it sits under, and fail if none is within a few columns.
- Values right-aligned under a total (team-report `DNS`): match on right edge,
  not start position.
- Lines that print either every apparatus (with placeholders) or only the
  performed ones: if the count equals the apparatus count, assign in order;
  if it equals the performed count, assign to those; otherwise fail.

### 2.7 Icons instead of text

Some column or panel labels are icons (FIG Judges Assignments, team and
all-around result columns). Render the page and confirm the order from the
picture; a printed legend can list the apparatus in a *different* order than
the columns. Then verify the mapping with data — e.g. an athlete's score in an
icon-headed column matches the same score in a text-labelled table.

## 3. Checks

Every parser runs these and exits non-zero on any failure (`common.Checks`).
A parser that silently drops or misplaces values is worse than one that stops.

1. **Arithmetic** — D + E + bonus + penalty (+ any itemized bonuses) = the
   printed score, for every routine.
2. **Aggregates** — all-around totals = sum of apparatus scores; team
   apparatus totals = best counting scores; a two-vault result = the average
   truncated to 3 decimals + any combined bonus; multi-part totals = the sum of
   the parts.
3. **Ranks** — never decrease down a table, totals never increase, tied ranks
   have equal totals.
4. **Counts** — rows parsed = rows counted by an independent regex (ranked
   rows + DNS markers); entries = the source's own totals ("Number of Entries",
   "34 Participants" on a start list).
5. **Cross-source agreement** — wherever two reports show the same thing,
   compare them: single vs double vault lists, team/all-around reports vs
   per-apparatus tables, a two-day report's Day 1 block vs Day 1's results,
   transcriptions vs a text copy, each final's athletes vs the qualifiers.
6. **Identity** — every bib's name, NOC (and birth year where printed) matches
   the entry list; results tables truncate long names (§4.2).
7. **Prove the checks** — plant one wrong digit in a source and one in a
   transcription, and confirm both are caught.
8. **Corrections are logged** — every value written differently from the
   book is a row in the event's `CORRECTIONS.csv` (import-file-model.md), and
   the parser fails on an unlogged difference from a text copy it compares
   with, or a logged correction that no longer applies.
9. **Summary pages are a cross-check, not a source** — medal lists and
   standings can disagree with the results tables (Cottbus WAG vault bronze,
   §5.3). When they do, the results table wins; flag it.

Run on a scratch copy of the event folder first, diff against any existing
files, and only then write in place. A rerun should reproduce identical files.

## 4. Conventions when producing the files

The column-level standard (empty cells, explicit `Status`, preserving printed
formats, the metadata prefix) is in `import-file-model.md`. These are the
decisions that come up while parsing.

### 4.1 Names

- **`PARTICIPANTS` is the master name record.** Surname/Given Name are derived
  there once; results files carry `Bib` + `Name` only, and every results row's
  name is replaced by the participant's full name by bib.
- **Entry list annotations** go in PARTICIPANTS' `Entry Status`: a
  `(reserve)` suffix on the name is dropped and the entry is `RESERVE`; an
  entry struck through on the list is `WITHDRAWN` (Senior Pan Americans WAG
  bib 127; the "Number of Entries" counts include it). An entry marked
  `(Hors Concours)` is `HORS_CONCOURS` (Varna: five BUL athletes, counted
  `6 + 4 (HC)` on the entries by NOC page).
- **Truncation happens anywhere a name is long** — narrow vault columns, but
  also normal tables (`BORDELAIS-MAISONNABLE` without his given name, initials
  like `KUBON CV` in all-around tables). Always diff against `PARTICIPANTS`.
- **Splitting** (`common.split_surname_first` / `split_given_first`):
  - FIG books print `SURNAME Given`: the surname is the leading run of
    upper-case words, keeping lowercase particles (`van POL`, `LIDE de LEON`)
    and `Mc` prefixes (`McDONALD`, `Mc CLENAGHAN`). Don't use "up to the last
    upper-case word" — a trailing initial (`SOTO RODRIGUEZ Jensuel J`) breaks it.
  - Organizer books may print `Given SURNAME` (Cottbus): the surname is the
    trailing upper-case run (`Kilan VAN DER AA`).
  - Judges lists may print `Given, SURNAME` (Cottbus): split on the comma
    (`Melanie, Jenkins` has a mixed-case surname).
  - US Championships prints `Given Surname` in mixed case; its Surname/Given
    split was curated by hand and is read from the existing `PARTICIPANTS`.
- **Strip decoration**: a leading `*` on US names.
- **Linking a different spelling.** The importer matches athletes by FIG
  licence, else by exact name (import-process.md, Matching athletes). A source
  that prints no licences and another form of a name (US Championships' "Fred
  Richard" for Worlds' "Frederick Richard") would create a second athlete. Put
  the athlete's licence, from an international entry list, in that row's
  `FIG License`: the import then links them and keeps the printed name as a
  variant. The US parser keeps the column when it rewrites `PARTICIPANTS`.
- **Judges have no master file**, so `JUDGES` derives the split itself.

### 4.2 Ranks and markers

- Copy ranks as published, including duplicate ranks for ties and tie-breaks
  that order equal totals — never recompute (tie-break rules change by quad).
  Elevien's World Cup books break a tie on E, then D (Osijek WAG floor
  qualification: SHAMAY over ZLOBEC, E 7.500 both); equal on both, the rank
  is shared. Varna's book does the same (MAG floor qualification: BOURDET and
  ZAVORY share 5th on equal E and D).
  Where a better source publishes the tie-break the book leaves out
  (sporttech.io's export ranks equal totals by E score, while the Junior Pan
  Americans book prints them tied), take that rank and log it as a
  `TIE_BREAK` correction.
- Strip tie markers: `1T`, `45=`, `2*` → the number (`common.rank_number`).
- Leave `Rank` blank where the source publishes none (a DNS row, US Day 2,
  a Team Final with no per-apparatus ranks).
- The two-per-country rule never changes a rank; it shows as `NR`.

### 4.3 Status

- `COMPLETED`, `DNS` or `INVALID_VAULT`, always written.
- **Not entered on an apparatus** (a specialist's other apparatus, printed as
  underscores or simply absent): no row at all.
- **Entered but didn't perform**: `DNS`, blank scores and rank — including a
  US routine printed `0.00 / 0.000` (scratched).
- **Invalid vault**: an attempt the judges scored `0.000` (an aborted run, the
  table not touched): `INVALID_VAULT` with its printed D, E and `0.000` total,
  and its rank. The zero counts (all-around, team, the two-vault average), and
  the site shows it with the status. Europeans WAG SR bib 111 and WAG JR bib
  301 on vault 1; Worlds MAG ZAPATA's vault 2, whose average was halved. Not
  `DNS` or `UNKNOWN`, even where the source prints no status. sporttech.io
  prints a bare `0` with no D or E (§5.4): D and E stay blank, `Total` is `0`.
- **A bare zero on another apparatus** (Junior Pan Americans MAG CERNA's rings:
  `0`, no D or E, counted in Ecuador's team total): `COMPLETED`, blank D/E,
  `Total` `0`, its printed rank.
- **sporttech.io distinguishes `—` from `DNS`**: `—` is no routine (a team's
  non-competing member, an apparatus a team didn't use them on) and gets no row;
  `… … DNS` is an entered routine not performed and gets a `DNS` row.
- **Vault DNF** (vault 1 done, vault 2 not): `Status2=DNS`, blank `Total`.
- **All-around/team DNF** rows are kept with blank `Rank`/`Total`; a team
  missing a whole apparatus prints a blank column and `DNF` total.
- **A team penalty** printed beside the apparatus totals (Senior Pan Americans
  MAG CUB: `-1.000`, team score 190.728 against apparatus totals of 191.728)
  goes in the team summary's `SJ Penalty`; `Total` stays the printed score.
  The Mediterranean Games print it unsigned in the team report's `SJ Pen`
  column (POR WAG: `0.3`); it is written negative (`-0.3`), as deducted.
- **An SJ penalty on a two-vault result** (Baku WAG vault qualification,
  MAKOVICKOVA: `0.3` printed unsigned under `SJ Pen.` between vault 1's score
  and the vault score, which is the average + 0.2 − 0.3; neither vault's own
  score includes it) goes in `Combined SJ Penalty`, written negative (§6).
- US all-around totals for partial all-arounders are printed and kept.

### 4.4 Session dates

- **From the Competition Schedule pages, never from a report footer's
  timestamp.** Footers are print times: Europeans WAG qualification was
  stamped 13 Aug but competed 12 Aug.
- **Read the schedule's time blocks, not just its labels.** A line naming
  "Junior Team Final" with the same time block as the qualification
  subdivisions is a relabel, not a separate session; a round only gets files
  if the PDF has its own results report.
- **A round over several days** (Worlds qualification) uses its first day.
- **Exception — splitting known days:** when the schedule gives two days for
  a set of finals but not which apparatus is on which, the per-apparatus print
  timestamps (tightly clustered within one of the known days) decide it
  (Europeans MAG SR finals: FX/PH/SR one day, VT/PB/HB the next).
- **No schedule at all** (Cottbus): infer from print timestamps, say so in the
  parser, and confirm with the user.

### 4.5 Vault

- **Two FIG listings in qualification**: a single-vault list (everyone, first
  vault, whole-field rank — the vault that counts for all-around and team) and
  a double-vault list (vault-final hopefuls: both vaults, average, its own
  rank, Q/R). Join them by bib; a double-list bib missing from the single list
  is an error. Take names from the single list (the double list's column
  truncates). Vault 1 must be identical in both.
- **No single-vault list** (Junior Pan Americans): every vaulter's first vault
  comes from the all-around report, with `Rank` blank (no vault ranking of the
  field is published); the double list adds vault 2, `Total`, Q/R and
  `Qualification Rank`, and its vault 1 must match the all-around report's.
- **Per-attempt vs combined bonus**: MAG prints a per-vault bonus inside each
  vault score (`B1`/`B2`). WAG's +0.2 applies to the combined result
  (`Combined Bonus`) — printed as a `*` on the total (Europeans), its own
  `Vault Bonus` column (Worlds), on the second vault's line but excluded from
  that vault's score (Cottbus), or as `Bns` (US).
- **Which shape a file uses** depends on the round and source — check the page:
  Team and AA finals are single-attempt at FIG events; US AA vault is
  double-attempt where a vault event is held; at a World Cup every vaulter
  does two vaults in qualification — Cottbus, Antalya, Cairo, Osijek and Varna publish a single ranking,
  Baku a vault 1 list and a two-vault list over the same vaulters (§5.7).
- **An invalid second vault** (Baku WAG vault final, HERON) prints `0.0` under
  `D` and `0.000`, with E blank: `Status2` `INVALID_VAULT`, and the vault
  score is half of vault 1.

### 4.6 Qualification markers

- `Q`, `R1`–`R4`, `NR` as printed (Worlds' AA qualification has four
  reserves).
- `Qualification Rank` on every `QUAL` row: the double-vault rank for vault,
  equal to `Rank` elsewhere. sporttech.io ranks every vaulter (a single vault
  counts half) but lists only the two-vault athletes, so its ranks skip the
  one-vault athletes between them (Senior Pan Americans MAG: 13, then 17);
  copy them as printed.
- **Numbered qualifiers** (`Q1`…`Q8`, sporttech.io) are written as `Q`; the
  number is the qualifier's order (it skips athletes left out by the
  two-per-country rule) — check it runs 1…8 in rank order. Those left-out
  athletes print no marker, so their `Qualification` stays blank rather than
  `NR`.
- **A marker on an all-around ranking with no all-around final** (Junior Pan
  Americans: `Q` beside the top eight, two per country) isn't recorded — it
  qualifies to nothing in the meet.
- **A tie among the reserves** shares a number, and the reserves run past three
  to take in the whole tie: Osijek MAG pommel horse prints R1 and three R2s at
  =10 (equal E and D), Baku MAG floor two R3s.
- **Unnumbered reserves** (Cairo: a plain `R` on the two athletes after the eight `Q`)
  are written `R1`, `R2` in rank order; the final's start list numbers them the same way,
  unless a qualifier withdrew before it was printed (§5.9).
- **Markers not printed on the results table** but named on the final's start
  list (8 finalists + ordered reserves): take them from the start list, record
  it as a source file, and check the Q set equals the final's athletes.
- **A tie at the last qualifying place** puts both athletes through, so the
  final has nine (Mediterranean Games WAG beam: two at =11, after three `NR`s).
  The List Of Qualifiers numbers them 11 and 12; the table's tied ranks stand.
- **A reserve added to a full final** (Varna WAG beam: STOIMENOVA, R1, starts
  first ahead of the eight qualifiers; nine are ranked): her `Qualification`
  stays `R1`, and the start list's reserves are the R2 and R3. The book gives
  no reason.
- **Two per country, reopened**: when a qualifier withdraws, a compatriot
  marked `NR` can take the place ahead of the reserves (Mediterranean Games WAG
  floor: GAVA for TONELLI, both ITA). Their `Qualification` stays `NR`.
- **Replacements without reserve markers** (Senior Pan Americans all-around:
  `Q` on 24, no `R`): a finalist who wasn't a qualifier keeps a blank
  `Qualification`; the parser reports absent qualifiers and their replacements
  rather than failing.

### 4.7 Judges

| Printed | Written |
|---|---|
| `D1`, `D2`, `E1`–`E7` | as printed |
| `Time Judge`, `Time Judge 1`, `Time 1` | `T`, `T1`, `T1` |
| `Line Judge`, `Line Judge 1`, `Line 1` | `L`, `L1`, `L1` |
| `<Apparatus> Supervisor` (Superior Jury) | `SV`, with that apparatus |
| `AS` / `SA` (Pan American and Cairo WAG panel supervisor) | `SV`, with the panel's apparatus |
| `S` (Osijek panel supervisor, printed after `E5`) | `SV`, with the panel's apparatus |
| Spanish: `Línea`, `Línea1`, `Tiempo`, `Tiempo1`, `Presidenta`, `Miembro` | `L`, `L1`, `T`, `T1`, `President`, `Member` |
| Superior Jury name with no function printed (Pan Americans MAG) | `Member` |
| `DS1` (World Cup panel) | `DS1` — Difficulty Supervisor |
| `pen5` (Cottbus beam panel) | `T2` — beam has two time judges |
| `President`, `Vice-President`, `Member` | as printed, apparatus blank |
| `TD` (Technical Delegate, the Superior Jury at Baku) | `TD`, apparatus blank |
| A World Cup's single Superior Jury / Competition Jury name, no function printed (Antalya) | `TD`, apparatus blank |
| `Supervisor`; `Time`, `Line` printed once or twice on a panel (Antalya WAG) | `SV`; `T`/`L`, or `T1 T2`/`L1 L2` |
| `Time Judge` (printed twice on Varna's beam panels), `Line Judge`, `Line Judge 1` | `T` or `T1 T2`, `L`, `L1` |
| Reserves `R1`… / one unnumbered reserve | `R1`… / `R`, apparatus blank unless the source assigns one |
| `RES` / `RES 1`… printed inside a panel's column (Mediterranean Games, Baku) | `R` / `R1`…, with that panel's apparatus |

**One spelling per judge.** The same judge is printed differently between
meets (`GOULET` / `GOULET JR`, `LIN WAY, Jim` / `LI LIN WAY, Jim Anthony`)
and sometimes within one (`CORDEIRO` / `CORDEIRO ANDRADE`). Write the name as
World Gymnastics prints it in its own books (Worlds, World Cups), else the
meet's most common spelling, and log the change as a `JUDGE_NAME`
correction. Two judges sharing a surname and country are only merged with
evidence (GUA's VALENZUELA Marco judged at Worlds; VALENZUELA Ricardo is
someone else).

Every value must resolve through `JudgeFunction.find`. The `Apparatus` column
is the two-letter code, never the spelled-out name. Superior Jury rows may
have no NOC (blank); a Superior Jury credited to `FIG` is written blank too. Judges credited to a continental union print it as their
federation: `UPAG-ECU` is written `ECU`, a plain `UPAG` is blank. Men's
finals line judges lent by the women's panel print `WAG` as their federation
(Senior Pan Americans); that is blank too.

### 4.8 Countries

- IOC codes, as World Gymnastics uses them (`GER`, `NED`), for NOCs and the
  host country — not ISO.
- Neutral athletes keep the code printed: `AIN1`/`AIN2` (Cottbus, "Individual
  Neutral Athletes"), `WG1`/`WG2` (Europeans, "World Gymnastics 1"/"2"); the
  same athletes appear as `RUS`/`BLR` at Worlds. Cairo and Osijek print a plain
  `AIN` for both groups, and it is written `AIN` (§6). Judges keep their printed codes too
  (`AIN 1` is written `AIN1`), even where one page prints `RUS`/`BLR` and another
  `AIN2`/`AIN1` for the same judge. Each code is its own group,
  entering its own team (Europeans' `WG1` and `WG2` teams), so never merge them.
- Some entry lists print the NOC only on each country's first row.
- The US Championships prints no NOC; participants are written as `USA`.

### 4.9 Competition structures

Map the meet onto `Session`s (`data-model.md` §3) before parsing:

| Structure | Sessions | Example |
|---|---|---|
| Championship | `QUAL`, `TEAM`, `AA`, `EVENT` per apparatus | Worlds, Europeans |
| Juniors without a team final | no `TEAM`; team summary has no Q markers | Europeans juniors, Junior Pan Americans |
| All-around decided in qualification | no `AA` session; `SUMMARY-QUAL-AA` only | Europeans WAG, Junior Pan Americans |
| Team decided in qualification, all-around final | `QUAL`, `AA`, `EVENT` per apparatus; no `TEAM` | Senior Pan Americans, Mediterranean Games |
| Round split into parts, decided on the combined total | one session per part + a whole-round session (part blank) holding the combined standings | US Championships |
| Apparatus competition | `QUAL` and `EVENT` per apparatus; no team or AA | Apparatus World Cups |

If a meet doesn't fit any of these, stop and discuss the model change first.

## 5. Source formats

### 5.1 FIG / Swiss Timing results books (Europeans, Worlds)

A concatenation of reports, each stamped with a footer like
`GARM1APFX-------------QUAL--------_73I 1.0  <timestamp>  Page 1/5`.
Parsers: [`parse_2026_world_championships.py`](../tools/results-parsing/parse_2026_world_championships.py)
(the 2026 Europeans files predate the parsers and were built by hand).

**Finding reports**

- The footer code identifies a report template, `GAR` + `M`/`W` + report
  (`1APFX` apparatus, `1AA` all-around, `TEAM`, `GEN`) + round (`QUAL`, `FNL`)
  + suffix (`_73I` apparatus results, `_73J` vault double list, `_73C`/`_73D`
  team results, `_73G`/`_73H` all-around results, `_57A`/`_57B` judges, `_32D`
  entry list by bib, `_51x` start lists, `_77x` tie-break reports, `_92x`
  medallists).
- A page's footer describes the content above it.
- **Codes are reused for different reports** — e.g. Junior Men's apparatus
  final and all-around final pages share codes, and Worlds' "Men's
  Qualifications" (every athlete) and "Men's All-Around Qualification" share
  `_73G`. Always confirm by the printed title (and timestamp), never by the
  code alone.
- Entry list titles vary in case ("Entry List By BIB" for WAG Europeans).

**Apparatus tables**

- Europeans: `D, E, B` columns; MAG PH and every WAG apparatus print `E`
  before `D`; PH has no bonus. A `!` before a D score marks an inquiry — kept
  as part of the value.
- Worlds: `D` before `E` everywhere; separate `Pen.` and `Bonus` columns; no
  `SJ Pen.` column; finals add trailing `Qualification Rank` and `Start Order`
  columns (not captured — join to the `QUAL` file).
- Vault: `_73I` "Qualifications - Vault 1" is the single list, `_73J` the
  double list; a DNF shows as `DNF` in the total with `DNS` for vault 2.

**Team and all-around reports**

- Team results: a team summary line (`(rank) total` per apparatus) followed
  by each athlete's `D` line and `E` line (and `BP` bonus/penalty line for
  MAG, `EP`/`E P` for WAG), apparatus identified by column position (§2.6).
- All-around results: an identity line with `D Score (Rk)` per apparatus,
  then E and BP lines; the overall total can sit on its own line. A regex over
  those lines must allow `-` (a penalty) — a digits-and-dots class silently
  failed on penalized rows.
- At Worlds the Team Final and All-Around Final have **no per-apparatus
  report**; `SCORES-TEAM-<APP>`/`SCORES-AA-<APP>` are built from these blocks
  (no per-apparatus rank in the Team Final; the AA report's `(Rk)` is used).
- Column order follows the icons, e.g. MAG FX PH SR VT PB HB, WAG VT UB BB FX
  at Worlds; the WAG legend text lists them differently.

**Judges Assignments**

- Superior Jury block (President, Vice-President, Members, apparatus
  supervisors), then panels in an icon grid — MAG FX/PH, SR/VT, PB/HB; WAG
  VT/UB, BB/FX — split into left/right halves at the second `Function`
  heading, then reserves.
- The last reserve can share its text line with `Legend:` (a first pass
  dropped Worlds' R6).
- Europeans assign reserves to panels and use one unnumbered reserve on WAG
  finals (`R`); Worlds list reserves for the whole round.

**Other**

- Entry lists: Europeans print birth year; Worlds print full date of birth
  (`Birth Date`).
- Junior events may have no Team Final and no AA Final (Europeans).
- Europeans WAG JR vault qualification: the first ranking (`_C73J`, printed
  14 Aug, pages 206–209) leaves out Lucia Piliarova (bib 430), so every rank
  below her =22 is one short. The organizers' later tie-break ranking
  (`_C77B`, printed 16 Aug, pages 210–213) lists her at =22 and has the
  corrected ranks, which are used. Her vault (D 4.2, E 8.600, 12.800) is
  taken from the team and all-around pages. The tie-break pages list only
  tied gymnasts; the all-around and team pages print every all-arounder's
  vault rank, and the rest follow from their tied neighbours.
- Checks run at Worlds: all of §3; team/AA blocks against the per-apparatus
  qualification tables proved the icon column order.

### 5.2 USA Gymnastics ProScore (US Championships)

A ProScore printout: no footer codes, no NOCs or FIG licences, names
`Given Surname`, values printed with underscores when empty (`_._`, `_.__`,
`__.___`). Parser:
[`parse_2026_us_championships.py`](../tools/results-parsing/parse_2026_us_championships.py)
(reads names, clubs and the Surname/Given split from the existing
`PARTICIPANTS` files).

**Structure.** Each level competes the all-around on two days (Day 1 =
`Part 1`, Day 2 = `Part 2`); titles are decided on two-day combined totals —
AA on the combined total, each apparatus on the combined apparatus total.
Combined standings go on the whole-round session: `SUMMARY-FINAL-AA` rows with
`Part` blank, and `SUMMARY-FINAL-<APP>`. Day 2 has no per-day places, so
`Rank` is blank on `Part 2` rows. Day-1-only athletes have no combined rows.

| Report | Gives |
|---|---|
| Day 1 "Meet Results" | Day 1 routines (D/E, D+/E+, S+/ND, Final), apparatus places, AA total and place |
| Day 1 "Event Results - Vault" (MAG SR, WAG SR, WAG JR) | the Day 1 two-vault list: both vaults, day result, rank |
| Day 2 "Meet Results - Multi" | Day 2 routines ("Finals" block), combined AA total and rank; its "Prelims" block repeats Day 1 (cross-checked) |
| Day 2 "Event Results - Multi - <apparatus>" | combined apparatus standings; for vault, both days' attempts |
| "USAG 10-Point Results" | national-team selection points — not parsed |

**Gotchas**

- **The two-day reports number the days backwards**: `#1` is Day 2, `#2` is
  Day 1 (printed first). Map by heading.
- Two-day Meet Results omit D/E pairs for skipped apparatus but print
  placeholder D+/E+ and S+/ND pairs (§2.6).
- Day 1 apparatus places are positional; the vault place is blank for levels
  with a vault event.
- **Bonuses**: MAG prints D+ (difficulty bonus), E+ (execution bonus, `0.0`
  on every 2026 routine), S+ (stick bonus) and ND (neutral deduction). `B` =
  D+ + E+ + S+, `Penalty` = ND, and D+/E+/S+ are kept as breakdown columns. WAG
  prints only ND (and the vault `Bns`).
- **Vault**: MAG juniors vault once each day (the two-day report prints an
  empty `x/0.000` second slot). MAG SR, WAG SR and WAG JR hold a two-vault
  event each day, so their `SCORES-AA-VT` is double-attempt: vault 1 is the AA
  vault, vault 2 and the day's result come from the vault lists. Day 1 second
  vaults come from Day 1's list — the two-day report omits anyone who didn't
  contest the vault title on both days. Single vaulters aren't in the vault
  title reports. The Day 1 vault rank is the two-vault list's rank.
- The two-day apparatus reports list only athletes who competed on that
  apparatus on both days.

### 5.3 Organizer results book, mostly scanned (Cottbus Apparatus World Cup)

The organizer's (CABI-Berlin) media book: entry lists and finals judges lists
have text; every results page, start list, medal list and qualification
judges list is a scanned image. The book also omits MAG vault qualification's
second results page. Parser:
[`parse_2026_apparatus_world_cup_cottbus.py`](../tools/results-parsing/parse_2026_apparatus_world_cup_cottbus.py),
which uses, in order: the book's text pages; a text PDF of the qualification
results from USA Gymnastics (`...-MAG-QUAL.pdf`: all MAG apparatus, WAG FX/BB);
transcriptions of everything else. The 227 transcribed rows that the text PDF
also covers matched it on every field.

**Structure.** An apparatus competition: qualification and finals per
apparatus, no team or all-around round, so no `SUMMARY-*` files. Each
apparatus's qualification is its own session (its own day and panel). Vault
qualification has a single ranking — every vaulter does two vaults, ranked on
the average.

**Gotchas**

- Names: `Given SURNAME` on entry lists and results, `Given, SURNAME` on
  judges lists; the entry list prints the NOC only on each country's first row.
- `AIN1`/`AIN2` neutral codes for athletes and judges.
- Q/R markers are missing from five qualification tables (MAG FX, PH, SR; WAG
  VT, UB — the first day's prints); they come from the finals start lists
  (`FINALS-START-LISTS.txt`).
- MAG prints bonuses as `+0.1`; WAG vault's +0.2 sits on the second vault's
  line but is a combined bonus.
- No Competition Schedule page: qualification MAG FX/PH/SR and WAG VT/UB on
  19 Feb, the rest on 20 Feb; finals in the same split on 21/22 Feb — inferred
  from print timestamps and confirmed with the user.
- Judges: `DS1` heads every panel; WAG beam has `pen5` (→ `T2`).
- **The book's medal list is wrong** for the WAG vault bronze: it names
  USHIOKU, but the results page — confirmed by other published results — has
  BELAK 3rd (13.516 with the combined bonus). The CSV follows the results page.

### 5.4 Organizer book with sporttech.io results (Junior Pan American Championships)

The organizer's media book: schedule, entry lists, start lists, judges, finalists
and medal pages from the organizer (English and Spanish), and every results
table printed by sporttech.io (footer "Generated by sporttech.io official
scoring system at …"). No report codes — the parser
([`parse_2026_pan_american_championships.py`](../tools/results-parsing/parse_2026_pan_american_championships.py))
names each report's pages and checks them against the printed title ("Event
Final (vault)") or the legend's apparatus. Every per-apparatus qualification
table is titled "All-Around", whatever the apparatus.

**Structure.** Juniors: qualification decides the team and all-around titles
(medals on qualification day), then apparatus finals. Teams of four, three
counting; a fifth member is entered and listed but competes on nothing.

| Report | Gives |
|---|---|
| Entry List by NOC | full legal name, `Given SURNAME` short form (used as `Name`), FIG licence (`En tramite` = pending, written blank; one found since in the FIG athlete database is a `LICENCE` correction), bib, birth year |
| All-Around (multi-apparatus) | every routine (D, E, Total; Pen and B on the line below, by position), AA total and rank |
| Team competitions – qualification | team apparatus totals, team score, each member's scores (cross-checked) |
| All-Around (one apparatus) | that apparatus's qualification table, with `Q1`…`Q8`/`R1`…`R3` |
| Two-vault list | both vaults inline (`D B E Pen Total`, then the average; WAG adds a `VB` column) |
| Finalistas / finals start list | finalists and ordered reserves per apparatus (cross-checked against Q/R) |
| Event Final (…) | the finals |

**Gotchas**

- Values: `—` no routine, `… … DNS` did not start, a bare `0` a zero score
  (§4.3); AA totals `DNF`/`DNS`/`—`.
- The `Pen`/`B` line sits under each routine's D/E columns: assign by position
  and sign; arithmetic proves the assignment.
- Q/R markers print beside the rank, after it (`7. Q #256` on the AA ranking),
  or on the line below (vault list) — all handled; the AA ranking's `Q`s aren't
  recorded (§4.6).
- Team member rows leave a skipped apparatus blank and are left-aligned under
  the team totals; values are placed by nearest start position.
- PB and HB tables also list non-competing team members (`—`) whom the
  all-around report leaves out.
- Results print `SURNAME Given` with spellings that differ from the entry list
  (`GARCIA` / `GARCÍA`, `IBANEZ` / `IBAÑEZ SANCHEZ`, `VALENTINA` for the
  athlete entered as Marcela Valentina Nolasco Muñóz); identity is checked as
  every results surname word appearing in the entry's full legal name.
  Given names can differ too: bib 435 is printed "GONZALEZ Abraham" on the
  PB/HB tables but entered as Marat GONZALEZ, which is the name on his FIG
  licence (66647); the entry list's name is used.
- The WAG uneven bars qualification table stops at rank 50 (p. 99): RIVEROS
  (207, rank 51) and VAN DINTER (205, rank 52) are missing. Their routines
  come from the all-around report, their ranks are `ROW` corrections
  (`TRUNCATED` in the parser).
- **Text copy:** sporttech.io's export (`18529-sporttech-export.csv`) is
  compared with every routine, rank and standing, as for the seniors (§5.5).
  It matches every score; it breaks the ties the book prints (48 apparatus
  ranks, 2 all-around ranks, all `TIE_BREAK` corrections) and has MAG bib
  425's second vault as DNS.
- The uneven bars final prints no overall `Total` column.
- Judges: MAG prints `SURNAME, Given` and names its Superior Jury with no
  function; WAG prints `SURNAME Given` with Spanish functions (§4.7) and stray
  `#`/digits before names (stripped). Panels are icons — MAG FX/PH, SR/VT,
  PB/HB; WAG VT/UB, BB/FX.
- The book's entry-count page is headed "SENIOR" but holds the junior counts
  (46 men, 58 women), which match the entry lists.

### 5.5 Scanned organizer book with sporttech.io results (Senior Pan American Championships)

The same organizer media book as §5.4, for the seniors, but every page except
the Competition Schedule is a scanned image (the PDF went through a
compressor). The tables are the same sporttech.io layouts, so §5.4's notes on
values, markers and the `Pen`/`B` line apply. The parser
([`parse_2026_pan_american_championships_sr.py`](../tools/results-parsing/parse_2026_pan_american_championships_sr.py))
reads only the transcriptions
([`transcriptions/2026-PAN-AMERICAN-CHAMPIONSHIPS-SR/`](../tools/results-parsing/transcriptions/2026-PAN-AMERICAN-CHAMPIONSHIPS-SR/README.md)),
made with OCR (§2.3) and corrected by eye.

**Text copy.** sporttech.io's CSV export of the competition
(`18533-sporttech-export.csv`, next to the PDF; downloaded from sporttech.io
as `CAMPEONATO PANAMERICANO ADULTOS DE GIMNASIA ARTÍSTICA – 2026.csv`) has one row per frame (routine) of every stage. It names no stage:
rows come stage by stage (the `Group #` starting again at 1) and athlete by
athlete, and a performance's round comes from the days its frames started
(`LastStartTime`; a frame that never started is dated `0001-01-01`). `FAILED`
is DNS; a frame `FINISHED` but never published (MAG bib 344's second vault)
isn't a result. The export is trusted over the book for routines, statuses,
ranks and totals: where they differ, the export's value is written and logged
in `CORRECTIONS.csv` (MAG bib 312's second vault, `DNS`, which the two-vault
list leaves out). **Not its Q/R markers**: they contradict who competed in the
finals (senior MAG vault: 347 marked Q and 367 R1, but 367 vaulted in the final
and 347 didn't) and put athletes the two-per-country rule excludes on the
reserve lists, so they look recomputed after the meet; the book's markers
agree with the finals and are kept. The comparison is
[`sporttech.py`](../tools/results-parsing/sporttech.py), shared by both Pan
American parsers. `NPenalty` is positive, `VaultBonus` sits on the `Vault2`
frame, and each frame also carries its performance's all-around and team
totals and ranks (`Rank_G` is filled even for unranked athletes). The parser
compares every routine, status, rank and total with it, both ways; this caught
a bare `0` on vault that OCR had dropped and the arithmetic couldn't see.

**Structure.** Qualification decides the team title ("Team Final Ranking" on
qualification day); the top 24 all-arounders (two per country) go to an
all-around final, the top eight per apparatus to the finals (§4.9).

| Report | Pages (MAG / WAG) |
|---|---|
| Number of Entries by NOC | 3 |
| Entry list | 8–10 / 111–114 |
| Judges (qualification, all-around final, finals) | 29, 88, 94 / 127, 172, 178 |
| All-around (qualification, every routine) | 30–33 / 128–132 |
| Team competitions – qualification | 35–39 / 134–138 |
| Per-apparatus qualification, two-vault list | 41–76 / 140–163 |
| All-around final | 89–90 / 174–175 |
| Event finals | 95–100 / 179–182 |

**Gotchas**

- The all-around ranking prints `Q` under the rank for its 24 qualifiers and
  no reserve markers; four MAG and one WAG qualifier didn't compete in the
  final and were replaced by lower-ranked athletes (§4.6).
- The two-vault list's ranks skip the one-vault athletes (§4.6).
- Team members' struck-through scores are the ones not counting; the strike
  confuses OCR (`9.300` read as `2.300`), which the team cross-check catches.
- MAG CUB's team score carries a `-1.000` team penalty (§4.3).
- Bare zeros: MAG bib 309's qualification vault and WAG bib 143's all-around
  final vault (`INVALID_VAULT`; bib 143 then didn't start bars or beam, `DNF`);
  MAG bib 301's second vault on the two-vault list.
- WAG bib 127 is struck through on the entry list (§4.1); WAG bib 153 is
  entered and on the start lists but has no results at all.
- Judges: MAG prints `SURNAME, Given` with the Superior Jury unlabelled
  (`Member`); WAG prints `SURNAME Given` with Spanish functions and seven E
  judges. Panel icons: MAG FX/PH, SR/VT, PB/HB; WAG VT/UB, BB/FX. A few names
  are spelled differently between pages (`CORDEIRO` / `CORDEIRO ANDRADE`,
  `MENESES` / `MENESSES`); they are copied as printed.

### 5.6 Organizer book in FIG layout, Microplus print (Mediterranean Games)

The organizers' results book (Taranto 2026, Microplus timing): every report has
text, a FIG-style footer code (`GARM1APFX-------------QUAL--------_C73I`, the
schedule `_C08`, entries `_C30`/`_C32A`) or an internal one
(`MAG_SEN_000271` entry list, `_000273` team composition, `_000293` List Of
Qualifiers), but the column layouts are its own. The book also holds the
rhythmic results (pp. 179–224), which are skipped. Parser:
[`parse_2026_mediterranean_games.py`](../tools/results-parsing/parse_2026_mediterranean_games.py).
It finds pages by discipline, round line (`Qualification`, `All-Around Final`,
`Apparatus Final`) and report title, with the apparatus from the footer code —
codes are reused (the all-around final's per-apparatus pages and judges page
carry apparatus-final codes).

**Structure.** Qualification decides the team title (the schedule's "Team
Final" is the qualification block); an all-around final and apparatus finals
follow (§4.9). Three scores count per team apparatus; some entered team members
never compete (in PARTICIPANTS, with no results).

| Report | Gives |
|---|---|
| Entry List By BIB | bib, NOC, FIG licence, `SURNAME Given`, full birth date — the participants |
| Number of Entries by NOC (per discipline), Team Composition | the same entries (cross-checked) |
| Number of Entries by NOC (general, p. 6) | competitors per country — those with a routine (cross-checked) |
| Results By Apparatus | every SCORES file, including the all-around final's (single vault) |
| Vault qualification | a vault 1 list for the whole field (`_C73J`, no `Vault` column) and a two-vault list (`_C73J` with `Vault` and `Vault Score` columns) |
| All-Around Results | the summaries; every routine's D, E, penalty, bonus, score and rank (cross-checked) |
| Team Results | team apparatus totals and score; each member's D, score and rank (cross-checked) |
| Tie Break, All-Around Tie Break | the ranks of tied athletes (cross-checked) |
| List Of Qualifiers | Q (numbered), R1–R3, NR per apparatus (cross-checked) |

**Gotchas**

- Column order differs by table: MAG `D E B` except pommel horse (`E D`, no
  bonus); WAG `E D` everywhere; two-vault lists `E D [B] Pen Vault Score`.
  Penalties print with two decimals (`-0.10`), kept as printed.
- Inquiries: `!5.1` on the apparatus tables, `! 5.1` on the reports.
- DNS rows print a placeholder `0.000` in the E column; a two-vault DNF prints
  `DNF` and `2 … DNS` (MAG with a `0.0` bonus). Bare-zero vault: WAG bib 139,
  `E 0.000 D 0.0 0.000`, ranked — `INVALID_VAULT`.
- WAG `*` on a two-vault result means the +0.2 bonus is included: `Combined
  Bonus` `0.2`, `Total` as printed.
- The all-around and team reports have icon headings; their legend lists the
  apparatus in reverse. The columns are MAG FX PH SR VT PB HB and WAG VT UB BB
  FX, proven by matching every value with the apparatus tables. Values sit
  under each column's `D` heading, a `DNS` under `Total`, and a lone `0.00`
  (an invalid vault's blank E) under `Total` too; a zero penalty prints `0.00`.
- The team report's E and penalty lines and member totals print out of line,
  so only each member's `D Total Rk` line is read.
- **The WAG vault 1 table (pp. 128–129) leaves out KURTULUS Zeynep (bib 152)**,
  and every rank below her is one short. Her vault comes from the all-around
  report (`OMITTED` in the parser); her rank and the shifted ranks are
  corrections from the all-around report and the vault tie-break (p. 130),
  and bib 136, who isn't an all-arounder, is placed by her neighbours.
- Entry-list errors, written as World Gymnastics records them and logged as
  corrections: LECHAUD Luis (MAG bib 47) is printed born 6 Sep 2004, not 9 Jul
  2004; BUSUTTIL Philippa (WAG bib 140) with licence 81723, not 52109; COSTA
  Mafalda (141) and PARENTE Mariana (143) born a day early, likely a time-zone
  conversion. The importer refused each against the athlete Worlds had already
  created, so check a new book's entries against the existing PARTICIPANTS
  files before importing.
- MAG all-around qualification marks 18 `Q` and no reserves; three qualifiers
  (35, 45, 60) didn't compete in the 15-athlete final.
- Judges: the Superior Jury is a `President` credited to `FIG` (written blank);
  panels are `D1 D2 E1–E4` plus `T`/`T1 T2`/`L`/`L1 L2`, and reserves print as
  `RES`/`RES 1–3` inside a panel's column (§4.7). The grid is MAG FX/PH, SR/VT,
  PB/HB; WAG VT/UB, BB/FX, matching the legend — the time and line judges
  confirm it (MAG floor, WAG beam's two time judges).

### 5.7 Organizer book in FIG layout, Microplus print (Baku Apparatus World Cup)

The same Microplus print as §5.6, every page with text: Competition Schedule
(`_C08`), entry counts (`_C30`), medallists (`_C93`/`_C95`), and per discipline
the entries by NOC (`_C32A`), the Entry List By BIB (`MAG_SEN_000269`,
`WAG_SEN_000233`), qualification start lists (`_C51A`/`_C51B`), Judges
Assignment (`_C57A`/`_C57B`, finals `_C57G`), Results By Apparatus (`_C73I`,
vault `_C73J`), Tie Break (`_C77A`/`_C77B`), List Of Qualifiers (`_000291`,
`_000252`), the finals start list (`_C51G`) and per-final medallists
(`_C92A`). Parser:
[`parse_2026_apparatus_world_cup_baku.py`](../tools/results-parsing/parse_2026_apparatus_world_cup_baku.py),
which shares §5.6's page lookup and table reading.

**Structure.** An apparatus competition (§4.9): qualification on 5–6 March,
finals on 7–8 March, each apparatus its own session. The schedule splits them
the same way both weekends: MAG FX/PB/SR and WAG VT/UB first, MAG VT/PH/HB and
WAG BB/FX second (it also lists a "WAG: PH" rotation, a misprint for MAG). Top
eight per apparatus to the final, two per country, three reserves; every
qualifier competed.

| Report | Gives |
|---|---|
| Entry List By BIB | bib, NOC, FIG licence, `SURNAME Given`, birth year — the participants |
| Entries by NOC (per discipline) | the same entries (cross-checked) |
| Number of Entries by NOC (general) | gymnasts with a routine per country (76 men, 46 women; cross-checked) |
| Results By Apparatus | every SCORES file |
| Vault qualification | a vault 1 list (whole field, no `Vault` column) and a two-vault list (`Vault` column, `Vault Score` split over two header lines) over the same vaulters |
| List Of Qualifiers, finals Start List | Q (numbered 1–8), R1–R3 per apparatus; the finals' starters (cross-checked) |
| Qualification Start List | the same set of athletes as the results (an athlete appears in more rotations than they have routines, so only the sets compare) |
| Tie Break | the ranks of tied athletes (cross-checked) |

**Gotchas**

- Column order as §5.6: MAG `D E B` except pommel horse (`E D`, no bonus);
  WAG `E D`; two-vault lists `Vault E D [B] Pen [SJ Pen.] Total, Vault Score`.
  Vault tables truncate long names (`TANIGAWA`, `YULO Karl Jahrel`).
- WAG `*` on a two-vault result: the +0.2 bonus is included. MAKOVICKOVA's
  `0.3` under `SJ Pen.` is a penalty on the vault score (§4.3).
- A tie for the last reserve place lists two `R3`s (MAG floor: =11 MONTGOMERY
  and ISLOMOV) on the table, the List Of Qualifiers and the start list.
- WAG vault qualification DNF: BUSUTTIL vaulted once (`DNF`, `2 … DNS`); she
  is ranked 17th on the vault 1 list.
- Judges: the Superior Jury is one `TD` credited to `FIG` (written blank),
  printed `Given Surname` in mixed case (`Steve Butcher`, `Lyudmila Li`); the
  parser takes the last word as the surname, upper-cased. Every panel is `SV`,
  `D1 D2 E1–E5` plus time and line judges; reserves print in a panel's column.
  The grid is MAG FX/PH, SR/VT, PB/HB; WAG VT/UB, BB/FX, proven by the time and
  line judges (MAG FX `T L1 L2`, VT `L`; WAG VT `L`, UB `T`, BB `T1 T2`, FX
  `T L1 L2`). The MAG line judge ZELAYA (ARG) also sits on the WAG floor panel.
- The organizers' medallists and medal standings pages aren't parsed.

### 5.8 Organizer media book, EVAL scoring print (Antalya Apparatus World Cup)

The Turkish Federation's media book (`17936-ResultsbookMedia.pdf`): its own layouts, no
report codes, results printed by EVAL scoring with Turkish/English headings (`Soyadı
Surname`). Every page has text except MAG rings qualification (p. 21, transcribed in
[`transcriptions/2026-APPARATUS-WORLD-CUP-ANTALYA/`](../tools/results-parsing/transcriptions/2026-APPARATUS-WORLD-CUP-ANTALYA/README.md)).
Parser:
[`parse_2026_apparatus_world_cup_antalya.py`](../tools/results-parsing/parse_2026_apparatus_world_cup_antalya.py),
which names each report's pages and checks them against the printed title.

**Structure.** An apparatus competition (§4.9) on the Baku pattern: qualification on 12–13
March, finals on 14–15 March, MAG FX/PH/SR and WAG VT/UB first, MAG VT/PB/HB and WAG BB/FX
second (General Programme, p. 2). Top eight per apparatus, R1–R3, no `NR` printed.

| Report | Gives |
|---|---|
| BIB NUMBERS (pp. 5–6) | bib, NOC, `SURNAME`, `Given` in two columns — the participants. No licence or birth year |
| Results tables | every SCORES file; a TIE BREAK REPORTS page after most repeats the tied rows (cross-checked) |
| Qualification start lists (pp. 7–14) | per day, groups with one column per apparatus still rotating; an apparatus drops out after its number of groups (p. 3) |
| Finals start lists (pp. 37–38) | each final's eight starters (cross-checked) |
| Judges Assignment (pp. 15–16, 39–40) | panels under apparatus icons; judges numbered consistently per discipline |

**Gotchas**

- **Decimal commas**: D, E, bonus and penalty print `5,700`; totals print `13.966` (tie-break
  pages `13,966`). Written with a point, three decimals as printed. Penalties print
  unsigned in their own column (`0,300`) and are written negative; `0,000` is blank. MAG
  prints a `Bonus` column (`0,000` kept); WAG non-vault tables have none.
- **Garbled names**: some names and headings sit in a font whose text layer is shifted
  (`ù(1(5` = ŞENER, `%ø1(5` = BİNER, `6R\DGÕ` = Soyadı): ASCII 29 code points low, `ù`/`ø`/`Õ`
  for Ş/İ/ı. Names come from the entry list anyway; the identity check unscrambles.
  Results print Turkish letters (`ASİL`, `KILIÇER`) the entry list leaves out.
- **Neutral athletes** are `AIN2` on the entry list, `AIN` everywhere else; written `AIN2`.
- **Vault**: every vaulter does two vaults, ranked on the vault score (Cottbus shape, §4.5).
  Each row prints vault 1 above the name and vault 2 below. MAG's bonus is per vault; WAG's
  +0.2 is on vault 2's line but excluded from its score (`Combined Bonus`).
- **Misprints**, logged as corrections: MAG vault final NIN REYES's vault 2 prints E `-1,700`
  (the deductions; E 8.300); WAG vault qualification PEÑA ABREU's vault score prints 12.533
  for 12.583. An invalid vault prints `0,000` in every column (`INVALID_VAULT`, D/E `0.000`).
- **Athletes without a result**: a DNS row is printed only twice (MAG HB HAMADOUCHE, WAG BB
  DROBNIAK, a name with no values). Others on the qualification start lists have no row at all
  (MAG TANIDA on FX/PH/SR; five MAG vaulters; …): they get none, and the parser lists them.
- The page 3 entry counts are "as per nominative registration" (MAG 89 for 80 bibs) and
  aren't a usable check.
- Judges: one unlabelled Superior Jury name per discipline (MAG "Competition Jury" `SURNAME
  Given`, WAG "SUPERIOR JURY" `Given Surname`) is written `TD`. MAG panels `SV D1 D2 E1–E5`
  plus `T L1 L2` / `L`, with `R1 R2` for the whole round under the last panel; WAG `Supervisor`,
  `Time`, `Line` (numbered when a panel has two) and a `Reserve` per panel. The grid is MAG
  FX/PH, SR/VT, PB/HB; WAG VT/UB, BB/FX (icons, time and line judges). One MAG qualification
  label is missing (rings E2, between E1 and E3) and one finals surname (vault line judge,
  number 19 = KOGA).

### 5.9 Organizer media book, Elevien start lists (Cairo Apparatus World Cup)

The Egyptian Federation's media book (`17939-ResultsbookMedia.pdf`): every page has text
except the cover. The reports carry no codes: a Competition Schedule (pp. 2–3), entry
counts by country (p. 4), medallists (p. 5), then per discipline an entry list, Elevien
qualification start lists, Judges Assignment, results and tie-break pages, a finals start
list and the finals judges. Parser:
[`parse_2026_apparatus_world_cup_cairo.py`](../tools/results-parsing/parse_2026_apparatus_world_cup_cairo.py),
which names each report's pages and checks them against the printed titles and dates.

**Structure.** An apparatus competition (§4.9) on the Baku pattern: qualification on 3–4
April, finals on 5–6 April, MAG FX/PH/SR and WAG VT/UB first, MAG VT/PB/HB and WAG BB/FX
second. The page footers give the same dates. Top eight per apparatus, then two reserves
printed `R` (§4.6). No `NR` is printed.

| Report | Gives |
|---|---|
| Number of Entries by NOC (per discipline) | NOC, `SURNAME Given`, bib, FIG licence, birth year: the participants |
| Number of Entries by NOC (p. 4) | men and women per country (cross-checked, after the NOC corrections) |
| Results tables | every SCORES file; results print `Given SURNAME` |
| Tie Break | every group of equal totals, with the E score (vault: the higher vault) and the D score where E is equal (cross-checked) |
| Qualification start lists (Elevien) | per day, groups with one column per apparatus still rotating, placed as on the day's first page |
| Apparatus Finals Start List | per final, eight starters and R1–R2, in blocks under icons (WAG VT UB / BB FX, MAG FX PH SR / VT PB HB) |
| Medalists By Event (p. 5) | a cross-check only: it dates every final 5 April and prints `Qiyuan QUI` |

**Gotchas**

- **Entry-list NOC errors**: CASTANEDA (WAG 194) is printed `HKG`, CHEN Hoi Yuen Joanne (210)
  `SLO` and TRTNIK (227) `UKR`. The start lists, the results and p. 4 show CRC, HKG and SLO,
  so these are `NOC` corrections.
- **Optional columns**: penalties print unsigned in a `PEN` column (written negative);
  MAG non-vault tables add `BONUS`, except pommel horse. Both columns are optional, so a
  non-vault value is placed under its heading by position. Vault prints
  `D E [PEN] Score [Bonus]` per attempt, with the vault score at the end of vault 1's line.
  MAG's bonus is inside the attempt's score (`B1`/`B2`). WAG's +0.2 is printed on vault 2's
  line but isn't included in it (`Combined Bonus`).
- **A vault row split by a page break**: vault 2 is the first line of the next page, which
  has no column heading (WAG HAMIDI, MAG RENAUD).
- **Vault DNS**: an athlete who did neither vault prints `DNS DNS` over `DNS DNF`, or one
  `DNS DNF` line (WAG ZOIDAKI), with no rank and the bib at the margin. Both attempts are
  written `DNS`. An invalid vault prints `0.000` for D, E and the score (WAG qualification
  KOVALOVA, vault 1: `INVALID_VAULT`; her vault score is half of vault 2).
- The vault tie-break pages print no `Tie Break` heading. E and D print a leading zero
  (`08.633`).
- Long names wrap their surname onto the next line (`Ahmet Burak` / `EKICI`). Names
  sometimes end in a three-letter surname (`Qiyuan QIU CHN`), so the NOC is the code
  just before the values.
- **Replacements**: MAG VERA (COL) qualified on floor and high bar but did no vault and
  missed both finals. The next reserve came in, and the finals start list numbers its
  reserves after that (floor R1 LETELIER, R2 AZIZOV, who had no marker).
- **Athletes without a result**: on a qualification start list but with no row: MAG RENAUD
  (HB); WAG PONIZILOVA (VT, BB, FX), GUEVARA CORNEJO (UB), KINIUK (FX).
- Judges: the Technical Delegate is one name above the panels (MAG `Andrew TOMBS FIG`, WAG
  `TD Helena Lario WGYM`), written `TD` with a blank NOC. MAG panels are `SV D1 D2 E1–E5`
  plus `T L1 L2` (FX) and `L` (VT), with round reserves `R1 R2` below the last panel. These
  are blank in qualification. The page's text layer also holds stray judge numbers.
  WAG panels print `AS` (written `SV`), each judge's number and brevet, `T`/`T1 T2`/`L`/
  `L1 L2`, and a per-panel `Reserve`. BB qualification prints the label on the line below
  the name. `E4`/`E5` are sometimes printed with a Cyrillic `Е`, and a long surname pushes
  the given name and NOC onto the next line. The grid is MAG FX/PH, SR/VT, PB/HB and WAG
  VT/UB, BB/FX, from the icons and the time and line judges. On the finals page, the WAG
  time judge MOSTAFA Shadi prints WOOLF's brevet (4094 for 5384).
- Judge spellings: the WAG TD prints `Helena Lario`, written `LARIO Helena Beatriz` as at
  Worlds (`JUDGE_NAME`). The Pan American books print `VELASQUEZ, Juan Carlos` (COL),
  which is `VELASQUEZ ALVARADO Juan Carlos` here; Cairo's spelling is kept.

### 5.10 Organizer media book, Elevien print (Osijek Apparatus World Cup)

The Croatian Federation's media book (`17937-ResultsbookMedia.pdf`), printed whole by Elevien
(Cairo used it only for its start lists, §5.9): every page has text and no report codes. A
Competition Schedule (p. 3), entry counts by country (p. 4), medallists and medal standings
(pp. 5–6), then per discipline, after a cover page `(MAG)` / `(WAG)`: Entry List by NOC, Entry
List by BIB, qualification start lists per day, Judges Assignment, Qualification Results, List
of Qualifiers to Finals, Finals Starting Lists, finals judges, Finals Results and Medalists by
Apparatus. Parser:
[`parse_2026_apparatus_world_cup_osijek.py`](../tools/results-parsing/parse_2026_apparatus_world_cup_osijek.py),
which finds each report by its printed title (a page without one continues the report before).

**Structure.** An apparatus competition (§4.9) on the Baku pattern: qualification on 9–10
April, finals on 11–12 April, MAG FX/PH/SR and WAG VT/UB first, MAG VT/PB/HB and WAG BB/FX
second (schedule and finals start lists). Top eight per apparatus, two per country (no `NR`
printed), R1–R3; every qualifier competed.

| Report | Gives |
|---|---|
| Entry List by NOC | NOC heading, then `Given SURNAME`, bib, FIG licence: the participants. No birth year |
| Entry List by BIB | bib, name, NOC (cross-checked) |
| Number of Entries by NOC (p. 4) | men and women per country, `-` for none; one row per neutral group, both `AIN` (cross-checked) |
| Results tables | every SCORES file; `Q`/`R1`–`R3` beside the total |
| Tie-break (after some qualification tables and finals) | the tied athletes' rank, total and E (vault: the highest vault) (cross-checked) |
| List of Qualifiers, Finals Starting Lists | the Q and R markers; each final's eight starters, then its reserves unnumbered, dated (cross-checked) |
| Qualification start lists | per day, groups with one column per apparatus still rotating (cross-checked as sets) |
| Medallists (p. 5, each final, Medalists by Apparatus) | a cross-check only |

**Gotchas**

- Columns `D E ND [Bonus] Total` (WAG and pommel horse have no bonus); D prints one decimal,
  `ND` (neutral deductions) is unsigned and written negative. Non-vault values are placed under
  their heading by position.
- **Vault** prints `V1` above the athlete's line and `V2` below, each `D E [ND] [bonus] Score`;
  the athlete's line holds the vault score (`Average`). MAG's `SB` is inside the attempt's score
  (`B1`/`B2`); WAG's `VB` (+0.2) sits on vault 2's line outside its score (`Combined Bonus`).
  The ND and bonus columns drift against their headings by up to three characters, and a
  continued page prints no heading, so a lone value is placed by its sign: ND is deducted from
  D + E, SB added, VB in neither. An invalid vault prints `0.0 0.000 0.000` (WAG KUBON,
  vault 2); a vault DNF prints `DNF` with `V2 … DNS` and no rank; a DNS one line, no attempts.
  WAG AJALLA's vault 2 has a 2.0 ND.
- **Tie-break sections** follow day 1's qualification tables and some finals, carrying onto the
  next page without a heading. WAG uneven bars qualification's prints ranks 12–38 for the
  table's 17–44 and leaves out two tied pairs; its totals and E scores agree, and the table is
  taken.
- **DNS rows for athletes not on that apparatus's start list**: MAG LINDPOINTNER (VT), FEDERICI
  (PB), THORPE (HB); WAG ANTILA (BB, FX), SOULELE (BB). Written `DNS` as printed.
- Judges: `Technical Delegate: SURNAME Given (NOC)` above the panels, written `TD` with that NOC
  (MAG ZUNICH, written `ZUNICH Butch` as at Worlds; WAG ZAYED). Panels two to a row under the
  apparatus names: `D1 D2 E1–E5 S` then time and line judges, `Given SURNAME NOC`. `S` is the
  supervisor (`SV`). MAG's `R1`–`R3` under parallel bars are the round's reserves (apparatus
  blank). The grid is MAG FX/PH, SR/VT, PB/HB and WAG VT/UB, BB/FX, by name. `Tanguy LE ROCH`
  is written `le ROCH` as at Worlds.

### 5.11 Organizer media book, typed in Word (Varna World Challenge Cup)

The Bulgarian Federation's media book (`18226-ResultsbookMedia.pdf`), typed in Word: a
Competition Schedule (pp. 2-3), entry counts by NOC (p. 4), medallists and medal standings
(pp. 5-6), the Entry List by NF (pp. 7-10), then per discipline the qualification start lists,
judging assignments, one results table per page (`Qualification FX - MAG`), a tie-break page
after some, the finals start lists and the finals, each followed by a `MEDALISTS` page. The start
lists and judging assignments are images, transcribed in
[`transcriptions/2026-WORLD-CHALLENGE-CUP-VARNA/`](../tools/results-parsing/transcriptions/2026-WORLD-CHALLENGE-CUP-VARNA/README.md).
Parser:
[`parse_2026_world_challenge_cup_varna.py`](../tools/results-parsing/parse_2026_world_challenge_cup_varna.py),
which finds each table by its title (`-` or `–`) and takes the page after it as its tie-break page.

**Structure.** An apparatus competition (§4.9) on the Baku pattern: qualification on 7-8 May,
finals on 9-10 May, MAG FX/PH/SR and WAG VT/UB first, MAG VT/PB/HB and WAG BB/FX second
(schedule and finals start lists). Top eight per apparatus, two per country (no `NR` printed),
R1-R3. The WAG beam final has nine (§4.6).

| Report | Gives |
|---|---|
| Entry List by NF | bib, NOC, FIG licence, `SURNAME`, `Given`, function (`MAG Gymnast`, `(Hors Concours)`): the participants. No birth year |
| Number of Entries by NOC (p. 4) | men and women per country, hors concours added (`6 + 4 (HC)`) (cross-checked) |
| Results tables | every SCORES file; `Given SURNAME`, `Q`/`R1`-`R3` under `Status` |
| Tie-Break pages | the tied athletes' rank, total, E and, where E is equal, D (cross-checked) |
| Qualification start lists (images) | per apparatus, groups of `NOC BIB Surname Given`, `(HC)` marked (cross-checked as sets) |
| Finals start lists (images) | each final's starters and R1-R3 (cross-checked) |
| Judging assignments (images) | MAG qualification and WAG qualification and finals panels |
| Medallists (p. 5, each final's page) | a cross-check only |

**Gotchas**

- **Decimal commas** (rings qualification prints points), D and E with three decimals. Columns
  `D E ND B Final`: ND (neutral deductions) printed unsigned and `0,000` when none, written
  negative or blank; `B` only for MAG, blank on most rows.
- **Vault**: MAG qualification prints `D E ND [B] Score Avg Final` on the athlete's line and vault
  2 below; finals add `Max` (the higher vault) before `Final`. MAG's bonus is in the attempt's
  score. WAG qualification puts vault 1 on the athlete's line, `Avg Max Final` centred on a line
  of its own, and vault 2 below with its +0.2 after the score; `Avg` leaves the bonus out and
  `Final` adds it. WAG finals print as MAG's, the bonus before vault 2's score and inside `Avg.`.
  The bonus is never in the attempt's score (`Combined Bonus`).
- **A missing vault**: WAG qualification AKTURK prints vault 1 and a vault score of 10.850, but no
  vault 2. It came from thegymter.net (D 3.6, E 7.300, ND 0.3: 10.600) and is logged as `ROW`
  corrections.
- **Misprinted bibs**: the WAG uneven bars final prints LOBOK as 216 and SULEKIC as 206; the finals
  start list has 251 and 214. Logged as `BIB` corrections; the parser identifies the row by the
  corrected bib. Misspelt names (`DYSHYK`, `WESSENHOFFER`, `Dabiz`) are reported and take the
  entry list's spelling.
- **Hors concours** athletes are on the qualification start lists (MAG 110-113, one apparatus
  each; WAG 206 on vault and beam) but the results tables leave them out: no score rows.
- **Athletes without a result**: on a qualification start list but with no row: MAG YILMAZ (FX),
  WAG DEMERS (BB). The start lists list some athletes in more groups than they have routines.
- The tie-break page after the MAG high bar final is titled `PB`. Not every table with equal
  totals has a tie-break page (MAG pommel horse, WAG beam qualification).
- p. 4 prints Mongolia as `MNG`; everywhere else it is `MGL`.
- Judges: one MAG page (qualification; no finals page is printed) and two WAG pages, panels under
  apparatus icons in the grid MAG FX/PH, SR/VT, PB/HB and WAG VT/UB, BB/FX (time and line judges
  agree). MAG: `LI Jing` as Technical Delegate (written `TD`, no NOC); panels `D1 D2 E1-E5`, no
  supervisor, plus `T L1 L2` (FX) and `L` (VT); a few judges sit on four panels. The floor panel
  truncates `GYULAI Gergely Laszl` (`JUDGE_NAME`). WAG: judge numbers, `Function` labels (`Time
  Judge`, `Line Judge 1`), reserves `R1`-`R3` below the panels. The WAG pages name no Technical
  Delegate; the cover's `Ms. Lyudmila LI` is written as `TD`.

## 6. Open items

1. **Invalid vault appearance.** FIG books print a plain `0.000` with D and E
   and no marker; sporttech.io a bare `0` with no D or E; Baku's Microplus
   print a D (`0.0`) and `0.000` with E blank; Antalya's EVAL print `0,000` in
   every column. Watch for a source that marks it differently.
2. **Europeans MAG all-around summaries** (`SUMMARY-QUAL-AA`,
   `SUMMARY-FINAL-AA`) were never built; the reports exist in that PDF.
3. **Europeans files were built by hand** before the parsers existed and lack
   the newer `Birth Date` column; there is no parser to regenerate them.
4. **`SV` vs `DS1`** may be the same role (an apparatus supervisor) seen in
   different contexts; kept separate for now. Both are World Cups: Cottbus
   heads each panel with `DS1`, Baku with `SV`.
5. **Penalties attributed to an apparatus.** sporttech.io's export records CUB's
   team penalty against one routine (bib 338's parallel bars) and has fields
   for per-apparatus team penalties and individual all-around penalties; only
   the team-level total is modelled (`TeamResult.sjPenalty`). Revisit if a book
   prints a penalty against a team's apparatus total.
6. **SJ penalties on vault.** Baku printed an SJ penalty on a combined
   two-vault result (§4.3), stored as `Score.combinedSjPenalty` beside the
   per-attempt `SJ Penalty1`/`SJ Penalty2`. Check the Code of Points: an SJ
   penalty may always apply to the apparatus score — one value per `Score`,
   which for vault is the combined result — in which case the per-attempt
   columns and this one should become a single SJ penalty on the score.
7. **Judge name variants.** The Baku TD prints as `Steve Butcher`; the Pan
   American books print `BUTCHER, Steven`. Cairo prints `VELASQUEZ ALVARADO Juan
   Carlos` for the Pan Americans' `VELASQUEZ, Juan Carlos`. Not merged (judges have
   no master record); settle on one spelling if judges are ever linked across meets.
8. **Hors concours results.** Varna's book leaves the hors concours athletes' scores out,
   so they are entries with no results. Their scores would need another source (the FIG
   results system) and a way to keep them out of the ranks.
9. **Plain `AIN`.** Cairo and Osijek print one `AIN` for both neutral groups, kept as printed
   (Osijek's entry list and entry counts keep the two groups apart, under two `AIN` headings).
   Those athletes link by FIG licence, but their Cairo entries form a third neutral
   group beside `AIN1`/`AIN2`. Revisit if the site groups results by country.
