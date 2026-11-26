# Parsing Results PDFs into CSV

How to turn an official results PDF into the import files under
`data/<year>/<event>/` (at the repository root). This is the *how*: tools, techniques, checks, and what
each kind of source document does. The *what* — every file, column and its
database mapping — is [`import-file-model.md`](import-file-model.md); the
entities are in [`data-model.md`](data-model.md).

- Where the PDFs, the FIG records and the draft `EVENT.csv` in a meet folder come from, and
  how meets are tracked, is [`results-sourcing.md`](results-sourcing.md).
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
full-page image, or, for a page laid out in CorelDRAW with its text converted to
outlines, only the logos: the 2026 African Championships). No OCR package is
installed; read the pages as images instead:

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
- **When OCR drops whole columns** of numbers (the African Championships'
  outlined text: Vision's accurate recognizer skipped most D scores on a page),
  run `ocr_pages.swift --fast` too, into a second folder: the fast recognizer
  reads the numbers but drops lone characters (ranks, `Q`). `ocr_draft.py
  <fast> merge <accurate> <out>` keeps every fast word plus the accurate words
  that overlap none, and the drafting modes read the merged folder. A dense
  multi-apparatus table reads better still cropped into one strip per
  apparatus (`sips -c <h> <w> --cropOffset <y> <x>`) and OCR'd strip by strip.
- **A layout no drafting mode covers** (the African Championships junior book): a throwaway drafter
  that places each word in the column whose left edge (measured once per page layout) is nearest
  works well. Two traps: OCR drops lone ranks, and filling them in sequence hides a shared rank, so
  check every rank by eye; and a row whose bib OCR missed gets taken for the line below the previous
  athlete (vault 2), so look for stray continuation lines on non-vault pages. Telling bold scores
  from regular by ink density was unreliable; check them by eye (the team totals then confirm them).
  A sideways page (a finals start list) OCRs after `sips -r 90`.

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
   truncated to 3 decimals (rounded in some books, §5.22) + any combined bonus; multi-part totals = the sum of
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
- **An entry list can print other bibs than the results** (2026 South American Games: every
  results table and start list one numbering, the Entry List by NOC another). The results' bibs are
  written, each entry matched to the one bib the results print its name and NOC with (agreed with
  the user); the entry list's numbers aren't kept.
- **Entry list annotations** go in PARTICIPANTS' `Entry Status`: a
  `(reserve)` suffix on the name is dropped and the entry is `RESERVE`; an
  entry struck through on the list is `WITHDRAWN` (Senior Pan Americans WAG
  bib 127; the "Number of Entries" counts include it). An entry marked
  `(Hors Concours)` is `HORS_CONCOURS` (Varna: five BUL athletes, counted
  `6 + 4 (HC)` on the entries by NOC page), and so is an invited country that
  "does not enter any ranking" (Asian Championships MAG: Australia, whose rows
  print `*` for a rank and are kept with `Rank` blank).
- **An entry list can cut a name short too**: the 2026 Central American and Caribbean Games print
  `FERNANDEZ RODRIGUEZ Melissa Del Car` (WAG bib 131); the start lists and results have `Melissa
  Del Carmen`, written in `PARTICIPANTS` as a `NAME` correction.
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
  ZAVORY share 5th on equal E and D), and so does Koper's, which prints no
  shared rank at all. Szombathely's too (WAG beam qualification: MAYER and
  ANDRADE share 1st on equal E and D; vault on the higher vault). Tashkent breaks every tie (E, then
  D; vault the highest vault, then E, then D). Paris breaks every tie, vault
  on the higher vault, then the higher E of either vault, then D. The African Championships break
  every tie in qualification, even at `0.000`, on E (vault: the higher vault), and the finals on
  E then D (WAG floor: DARIES 4th over MOALLIC, 12.100 and E 7.400 both). Their junior book shares
  the rank in qualification only on equal E and D (MAG pommel horse 4th), and in the finals on any
  equal total (MAG rings 2nd, WAG bars 3rd, E differing) except vault (higher vault) (§5.15).
  The Asian Championships print a Tie Break Report per table (E, then D; vault: the higher vault,
  then E, then D; all-around: the best five, four, … apparatus scores, then E, then D) whose ranks
  match the tables, except where it shares a rank the table splits on equal E and D (MAG floor
  DE LEON and TRINH `=45`, the table 45 and 46; parallel bars TIAN and ERGASHEV `=14`): the shared
  rank is written, as the report's rule ("will share the same classification") says, and logged
  as a `TIE_BREAK` correction.
  The Central American and Caribbean Games break every tie the same way, and their Tie Break
  Reports' ranks match the tables (all-around: the best three, two, one apparatus scores, then E,
  then D); equal on E and D, the rank is shared (MAG floor final: NUÑEZ FARFAN and VELEZ BELENDEZ 4th).
  The Asian Games book (§5.21) breaks ties the same way and shares a rank on equal E and D (MAG floor
  qualification: OKA and KARIMI `=6`). Its all-around Tie Break Report ranks the whole field, counting
  the athletes the final leaves unranked (MAG TRAN 14th, the final's 13th, behind an unranked third
  Japanese); the final's ranks are written. Its all-around report's vault `Rk` shares a rank on an
  equal first vault (MAG HASHIMOTO and IDRISSOV `13`) that the Results Vault 1 list breaks on E (13
  and 14); the list's is written.
  The South American Games book (§5.22) breaks ties on E, then D, and shares the rank on equal E and
  D (MAG floor qualification: SAMPAIO and BRAJAO 13th; WAG floor RODRIGUES Gabriela and ESTOCO 9th;
  WAG First Vault list RODRIGUES Gabriela and FERNANDEZ 17th); vault on the higher vault (MAG
  qualification VILLAFAÑE 2nd over ARMIJO at 13.275). Its Tie-Break Output pages match the tables.
  Where a better source publishes the tie-break the book leaves out
  (sporttech.io's export ranks equal totals by E score, while the Junior Pan
  Americans book prints them tied), take that rank and log it as a
  `TIE_BREAK` correction.
- Strip tie markers: `1T`, `45=`, `2*` → the number (`common.rank_number`).
- Leave `Rank` blank where the source publishes none (a DNS row, US Day 2,
  a Team Final with no per-apparatus ranks).
- The two-per-country rule never changes a rank; it shows as `NR`.

- **Rank Status: why a ranking row has no rank** (`RANKING-*` only; import-file-model.md).
  `out.ranking` sets it by rule, in order: an hors concours entry (`HORS_CONCOURS`; a team all of
  whose entries are); marked `NR` (`NOC_LIMIT`); a partial all-around, an entry who started no
  apparatus included, or a team short of an apparatus total (`INCOMPLETE`); a split competition's
  part row (`UNPLACED`: US day-2 rows); and in a final ranking that prints a top (two per country),
  `NOC_LIMIT` when two compatriots are ranked and the total beats the lowest ranked total, otherwise
  `UNPLACED`. A row no rule covers stops the parser: bring it to the user.

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
- **A blank cell for an athlete on the apparatus's start list** (Oceania WAG SR BAYLES's beam, between
  bars and floor printed `Final DNS`; WAG JR ATKINSON's bars): a `DNS` row, logged as a `ROW`
  correction (agreed with the user).
- **`DNS` after placeholder zeros** (Asian Games: `0.0 0.000 DNS` in a table, `D 0.000 DNS` over
  `E 0.000` in a team report) is `DNS`; the zeros aren't scores, and the parsers check they are zero.
  A vaulter who did neither vault prints `DNS DNS` (`Status1` and `Status2` `DNS`, no result).
- **A bare zero on another apparatus** (Junior Pan Americans MAG CERNA's rings:
  `0`, no D or E, counted in Ecuador's team total): `COMPLETED`, blank D/E,
  `Total` `0`, its printed rank.
- **sporttech.io distinguishes `—` from `DNS`**: `—` is no routine (a team's
  non-competing member, an apparatus a team didn't use them on) and gets no row;
  `… … DNS` is an entered routine not performed and gets a `DNS` row.
- **Vault DNF** (vault 1 done, vault 2 not): `Status2=DNS`, blank `Total`.
- **A blank vault 2 line with a result of half vault 1** (2026 South American Games MAG vault final
  ROSTAGNO: vault 1 12.075, vault 2 printed empty, result `6.037`, ranked 8th): the book counted
  vault 2 as zero, so it is `INVALID_VAULT` with `Total2` `0.000`, as `STATUS` and `ROW`
  corrections, and the printed result and rank stand (agreed with the user).
- **A `DNS` only the team report prints** (2026 South American Games MAG: AGÜERO and CHIAPPONI on
  rings, absent from the rings table; LEON's vault, which the two-vault table wouldn't list): a
  `DNS` row, rank blank.
- **All-around/team DNF** rows are kept with blank `Rank`/`Total`; a team
  missing a whole apparatus prints a blank column and `DNF` total.
- **A team penalty** printed beside the apparatus totals (Senior Pan Americans
  MAG CUB: `-1.000`, team score 190.728 against apparatus totals of 191.728)
  goes in the team ranking's `SJ Penalty`; `Total` stays the printed score.
  The Central American and Caribbean Games print `* Penalty -1.0` under the team (MAG VEN, WAG GUA:
  a wrong start order on one apparatus), deducted from the team score but not from the apparatus
  total; written as `SJ Penalty` `-1.0`.
  The Mediterranean Games print it unsigned in the team report's `SJ Pen`
  column (POR WAG: `0.3`); it is written negative (`-0.3`), as deducted.
  The Asian Championships star the totals a penalty was taken from and note
  `* Penalty -0.6` under the team (WAG juniors LBN: −0.3 off the beam total for
  overrunning the warm-up, −0.3 off the team total for its flag). The whole
  `-0.6` is written as `SJ Penalty` and the starred apparatus total as its best
  three scores (a `SCORE` correction), so the counting scores can be worked out
  and the apparatus totals plus the penalty make the team total.
- **An SJ penalty on a two-vault result** (Baku WAG vault qualification,
  MAKOVICKOVA: `0.3` printed unsigned under `SJ Pen.` between vault 1's score
  and the vault score, which is the average + 0.2 − 0.3; neither vault's own
  score includes it) goes in `Combined SJ Penalty`, written negative (§6).
- **A score never goes below zero.** Where D + E + bonus − penalty is negative,
  the printed total is `0.000` and the components are kept as printed (African
  Championships MAG pommel horse MGBAKOBO: 1.000 + 4.300 − 6.000; WAG bars
  TENEKU, CISSE): `COMPLETED`, not `DNS`, and the arithmetic check allows it.
- US all-around totals for partial all-arounders are printed and kept, and so are the Oceania
  Championships' (no `DNF` printed), with the printed rank or none: that book ranks WAG GODWIN, with
  no floor, 6th, and leaves the athletes with fewer apparatus unranked.

### 4.4 Competition dates

- **From the Competition Schedule pages, never from a report footer's
  timestamp.** Footers are print times: Europeans WAG qualification was
  stamped 13 Aug but competed 12 Aug.
- **Read the schedule's time blocks, not just its labels.** A line naming
  "Junior Team Final" with the same time block as the qualification
  subdivisions is a relabel, not a separate competition; a competition only gets files
  if the PDF has its own results report.
- **A competition over several days** (Worlds qualification) uses its first day.
- **Exception — splitting known days:** when the schedule gives two days for
  a set of finals but not which apparatus is on which, the per-apparatus print
  timestamps (tightly clustered within one of the known days) decide it
  (Europeans MAG SR finals: FX/PH/SR one day, VT/PB/HB the next).
- **No schedule at all** (Cottbus): infer from print timestamps, say so in the
  parser, and confirm with the user.

### 4.5 Vault

- **A single-vault list published apart from the book** (Asian Games MAG "Results Vault 1", §5.21)
  is read like one: it gives every first vault and its `Rank`, and the book's reports are checked
  against it.
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
- **A two-vault table only, whose all-around report ranks the two-vault athletes** (2026 South
  American Games MAG): the other first vaults come from the team report (team members) and the
  all-around report (individuals), with `Rank` blank, as at the Junior Pan Americans. The reports'
  vault `(Rk)` is the two-vault table's rank, printed for the two-vault athletes only, so it isn't a
  ranking of first vaults. WAG prints a First Vault list, read as a single-vault list.
- **One vault table, with an all-around report that ranks vault 1** (African
  Championships): the table ranks the two-vault athletes (`Qualification Rank`,
  Q/R) and lists the one-vault athletes after them, unranked; the all-around
  report's vault `RK` column ranks the whole field on vault 1 (shared on equal
  scores), and that is `Rank`, as a single-vault list's would be.
- **A two-vault table only, with an all-around report that ranks vault 1**
  (Commonwealth Games, Central American and Caribbean Games, Asian Games WAG): the one-vault athletes' first vaults come from the team
  and all-around reports; the all-around report's vault `Rk` ranks each
  all-arounder's first vault against the whole field and is their `Rank`; the
  others' `Rank` is blank (§5.19).
- **Per-attempt vs combined bonus**: MAG prints a per-vault bonus inside each
  vault score (`B1`/`B2`). WAG's +0.2 applies to the combined result
  (`Combined Bonus`) — printed as a `*` on the total (Europeans), its own
  `Vault Bonus` column (Worlds), on the second vault's line but excluded from
  that vault's score (Cottbus), or as `Bns` (US).
- **Which shape a file uses** depends on the competition and source — check the page:
  Team and AA finals are single-attempt at FIG events; US AA vault is
  double-attempt where a vault event is held; at a World Cup every vaulter
  does two vaults in qualification — Cottbus, Antalya, Cairo, Osijek, Varna, Koper, Szombathely, Paris and Tashkent publish a single ranking,
  Baku a vault 1 list and a two-vault list over the same vaulters (§5.7).
- **An invalid second vault** (Baku WAG vault final, HERON) prints `0.0` under
  `D` and `0.000`, with E blank: `Status2` `INVALID_VAULT`, and the vault
  score is half of vault 1.

### 4.6 Qualification markers

- `Q`, `R1`–`R4`, `NR` as printed (Worlds' AA qualification has four
  reserves).
- `Qualification Rank` on every `C1` row (where Competition I qualifies for apparatus finals): the double-vault rank for vault,
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
- **Unnumbered reserves** (Cairo, Szombathely: a plain `R` on the two athletes after the eight `Q`)
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
- **A qualifier missing from the final** (Koper WAG floor: PEDRO, `Q` and on
  the finals start list, didn't compete; SZILAGYI, `R1`, took the place and is
  ranked 8th): both keep their printed markers. The book gives no reason.
  Szombathely has three (§5.13), one qualifier missing two finals.
- **Two per country, reopened**: when a qualifier withdraws, a compatriot
  marked `NR` can take the place ahead of the reserves (Mediterranean Games WAG
  floor: GAVA for TONELLI, both ITA). Their `Qualification` stays `NR`.
  So in an all-around final (Commonwealth Games WAG: DARIES Zelme for
  ROOSKRANTZ, both RSA). The
  African Championships print no `NR`, so the compatriot's stays blank: nine
  finals there changed after qualification, by a reserve or a compatriot
  (§5.15). Asian Championships WAG bars: KE Qinqin (`Q`, on the start list) out for
  QIU Qiyuan (`NR`), both CHN. The South American Games print no `NR` either: MAG parallel bars
  ZABALA (`Q`, 1st) out for BARAJAS (3rd, COL's third), who won; WAG floor LIDE (`Q`) out for
  GUTIERREZ (12th, PAN's third). Both finals' start lists already name the replacement.
- **A start list printed after a reserve came in renumbers the reserves left** (Central American
  and Caribbean Games WAG floor: SWABY RANGER `Q` out, HERRERA POLANCO `R1` in; the start list's
  reserves are the qualification's `R2` and `R3`, printed `R1` and `R2`). The table's markers are
  written; the start list is checked against them renumbered. Its notes name each replacement.
  The Asian Games' start lists likewise take one off each remaining reserve's number for every
  reserve already in the final (MAG floor: KIM Jaeho, `R1`, in), and keep tied reserves' numbers
  (MAG pommel horse `R1`, `R1`, `R3`).
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
| `AS` / `SA` (Pan American, Cairo, African, Asian and Oceania Championships, Central American and Caribbean Games panel supervisor) | `SV`, with the panel's apparatus |
| `Superior Jury: <name>  UPAG  Technical Delegate` / `President` (Central American and Caribbean Games, one per discipline on every judges page) | `TD` / `President`, apparatus blank, NOC from other meets (§4.7 below) |
| The Oceania Championships' single Superior Jury (`SJ Gareth Brettell (OGU)` in the MAG sheet's title, `SUPERIOR JURY Allana Slater OGU (AUS)` on WAG's) | `TD`, apparatus blank (agreed with the user) |
| `Reserve` printed in each panel (Oceania WAG: the same judge in all four) | `R`, with that panel's apparatus |
| `MAG AGU President` / `WAG AGU President:` heading the Asian Championships sheets | `President`, NOC blank |
| `Superior Jury: <name>  AGU  President`, then `<name>  AGU  <Apparatus> Supervisor` per apparatus (Asian Games) | `President`, NOC blank; `SV` with that apparatus |
| `S` (Osijek panel supervisor, printed after `E5`) | `SV`, with the panel's apparatus |
| Spanish: `Línea`, `Línea1`, `Tiempo`, `Tiempo1`, `Presidenta`, `Miembro` | `L`, `L1`, `T`, `T1`, `President`, `Member` |
| Superior Jury name with no function printed (Pan Americans MAG) | `Member` |
| `DS1` (World Cup panel) | `DS1` — Difficulty Supervisor |
| `pen5` (Cottbus beam panel) | `T2` — beam has two time judges |
| `President`, `Vice-President`, `Member` | as printed, apparatus blank |
| `TD` (Technical Delegate, the Superior Jury at Baku) | `TD`, apparatus blank |
| A World Cup's single Superior Jury / Competition Jury name, no function printed (Antalya, Koper MAG; Tashkent's `<name> WG` / `<name> Wgym`, NOC blank), or `SJ: <name> FIG` (Szombathely); the African Championships MAG `Competition Jury` (credited `UAG`: blank, like `UPAG`) | `TD`, apparatus blank |
| `Technical Delegate`, `Technical Delegate Assistant` (Paris Superior Jury) | `TD`, `TDA`, apparatus blank |
| `Supervisor`; `Time`, `Line` printed once or twice on a panel (Antalya WAG) | `SV`; `T`/`L`, or `T1 T2`/`L1 L2` |
| `Time Judge` (printed twice on Varna's beam panels), `Line Judge`, `Line Judge 1` | `T` or `T1 T2`, `L`, `L1` |
| Reserves `R1`… / one unnumbered reserve | `R1`… / `R`, apparatus blank unless the source assigns one (Commonwealth Games finals: a day's reserves, one row for each of that day's finals) |
| `<Apparatus> & <Apparatus> Supervisor` (Commonwealth Games Superior Jury) | `SV`, one row per apparatus |
| `RES` / `RES 1`… printed inside a panel's column (Mediterranean Games, Baku) | `R` / `R1`…, with that panel's apparatus |
| `PR` (South American Games Superior Jury, legend "President") | `President`, apparatus blank |
| `Superior Jury - Vault & Uneven Bars`, `- Balance Beam & Floor Exercise`, each with its own `PR` (South American Games WAG finals) | `President`, one row per apparatus it names |
| `L` beside an `L2` on one panel (South American Games WAG floor final) | `L1`, `L2` |

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
federation: `UPAG-ECU` is written `ECU`, a plain `UPAG` is blank where nothing better is known (the
Central American and Caribbean Games credit their Superior Juries and every apparatus supervisor to
`UPAG`; each is written with the federation the same book or other 2026 meets give them, as `NOC`
corrections: MACERONI Mauricio, an `ARG` E judge in the same book's finals, `ARG`; CABRERA DÁVILA
Yazaira `PUR`, CAMACHO Esteban `CRC`, and so on), and so is the Asian
Gymnastics Union's `AGU` and the Oceania Gymnastics Union's `OGU` where nothing better is known (the Asian Championships' Presidents;
its apparatus supervisors' federations were looked up, §5.16; the Asian Games' supervisors are the same
judges, given the same federations; its one `AGU` panel judge, D1 AMER Rima, is written `JOR`, as
given by the user). A federation printed with a suffix (South American Games WAG qualification,
LOPEZ Silvina `ARG-B`; `ARG` on the finals sheet) is written as the federation, a `NOC` correction.
A federation printed with the union
(`AUS / OGU`, `OGU (AUS)`) is written as the federation; the Oceania MAG Superior Jury's plain `OGU`
is written `NZL`, his federation at the 2026 World Championships (a `NOC` correction). Men's
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
- **An ISO code where the IOC code differs** is corrected and logged (`NOC`):
  the African Championships print Zimbabwe `ZWE` on the entry list and results,
  `ZIM` on the entries by NOC page; written `ZIM`. Their junior book prints DR Congo as `RDC` (the
  French abbreviation, neither IOC nor ISO); written `COD`, agreed with the user. The Asian Games credit two Singaporean judges to
  `SIN` on the WAG qualification and team final sheets and to `SGP` on the finals sheets; written `SGP`.
- The US Championships prints no NOC; participants are written as `USA`.
- **Commonwealth Games Associations** are written as printed (agreed with the user): at the
  Commonwealth Games England, Scotland, Wales, Northern Ireland, the Isle of Man and Jersey compete
  apart (`ENG`, `SCO`, `WAL`, `NIR`, `IOM`, `JEY`), each with its own team, so they can't be folded
  into `GBR` or `IRL`. Their athletes link to their GBR/IRL entries by FIG licence. The front end
  names and flags them (`frontend/app/lib/countries.ts`).

### 4.9 Competition structures

Map the meet onto competitions and rankings (`data-model.md`; the design and every meet so far:
`competition-models.md`) before parsing, and settle its **format** with the user: for the team,
all-around and apparatus titles, `C1` (Competition I decided it), `FINAL` (its own final did) or
`NONE` (not held), written in `EVENT.csv` (`Team Format`, `AA Format`, `Apparatus Format`).

**Which competition holds the routines.** `C1` is Competition I, every entrant's, whatever the book
calls it ("Qualification", "Final", "Team Final and Individual Qualification"); `C2`, `C3` and `C4` are
the all-around, apparatus and team finals, each only where it has routines of its own. A meet's only
competition is `C1` (Oceania, US Championships). Write `common.COMPETITION[<the book's report name>]`,
or `C1` for such a meet.

**Which ranking decides a title.** A title Competition I decided has a `FINAL` ranking of `C1`, however
the book labels it: a qualification report (African Championships), finals that re-rank the same
routines (Asian Championships, South American Games), or the one competition's finals (Oceania).
A title its own final decided has a `QUALIFYING` ranking of `C1` (where printed, with Q/R/NR) and a
`FINAL` ranking of that final. `out.ranking` names the file (`RANKING-QUAL-` or `RANKING-FINAL-`) and
sets the purpose from the format; a parser only says which competition a row ranks. One ranking per
title and purpose: where a book prints a qualifying and a final ranking of the same routines for a
title Competition I decided (Asian Championships), pass the qualifying rows as `left_out_from`, so the
final ranking keeps the whole field. Qualification to another event (the 2026 Oceania Championships'
fifth athletes competing for World Championships places) is no part of the format; nothing in the
meet records it.

| Structure | Format (team, AA, apparatus) | Competitions, and the title rankings | Example |
|---|---|---|---|
| Championship | `FINAL`, `FINAL`, `FINAL` | `C1`, `C4`, `C2`, `C3` per apparatus | Worlds |
| Team and apparatus finals, no all-around title | `FINAL`, `NONE`, `FINAL` | `C1`, `C4`, `C3` | Europeans MAG seniors (but see competition-models.md: the title exists, only its medallists printed) |
| All-around decided in Competition I | `FINAL`, `C1`, `FINAL` | `C1`, `C4`, `C3`; `RANKING-FINAL-AA` of `C1` (Asian Games: 24 ranked, two per country, the others unranked) | Europeans WAG seniors, Asian Games |
| Team decided in Competition I, all-around final | `C1`, `FINAL`, `FINAL` | `C1`, `C2`, `C3`; `RANKING-FINAL-TEAM` of `C1` | Europeans MAG juniors, Senior Pan Americans, Mediterranean Games, Commonwealth Games, Central American and Caribbean Games |
| Team and all-around decided in Competition I | `C1`, `C1`, `FINAL` | `C1`, `C3`; both final rankings of `C1` | African Championships, Junior Pan Americans, Europeans WAG juniors, Asian Championships (also printed as finals of the same routines), South American Games (printed only as those finals) |
| One competition deciding the team and all-around titles, nothing to qualify for | `C1`, `C1`, `NONE` | `C1` (single-attempt vault, as at any all-around final); both final rankings of `C1` | Oceania Championships |
| Competition split into parts, decided on the combined total | `NONE`, `C1`, `C1` | `C1` per part, and the whole `C1` (part blank) holding the combined standings: `RANKING-FINAL-AA` (part rows `INFORMATIONAL`) and `RANKING-FINAL-<APP>` | US Championships |
| Apparatus competition | `NONE`, `NONE`, `FINAL` | `C1` and `C3` per apparatus | Apparatus World Cups, World Challenge Cups |

If a meet doesn't fit any of these, stop and discuss the model change first.

**Team roles.** Where a source says who was up for each team on each apparatus, write every
score's `Team Role` (`COUNTING`, `DROPPED`, `INDIVIDUAL`; import-file-model.md) and the team
ranking's apparatus totals as the sums of the `COUNTING` scores, checked against the printed team
total. A team's line-up can change by apparatus (2026 Oceania Championships: five a team, four up on
each apparatus, the fifth an individual competing for World Championships qualification), which the
importer can't work out from totals alone. Without such a source, leave the column out and give
the apparatus totals the source prints.

## 5. Source formats

### 5.1 FIG / Swiss Timing results books (Europeans, Worlds)

A concatenation of reports, each stamped with a footer like
`GARM1APFX-------------QUAL--------_73I 1.0  <timestamp>  Page 1/5`.
Parsers: [`parse_2026_world_championships.py`](../tools/results-parsing/parse_2026_world_championships.py)
(the 2026 Europeans files predate the parsers and were built by hand, except the juniors' men's
all-around final ranking, which
[`parse_2026_european_championships.py`](../tools/results-parsing/parse_2026_european_championships.py)
writes from its "All-Around Results" report, in the current standard). The senior men's book prints
no all-around ranking: only the medallists, dated on qualification day (see
competition-models.md, open items).

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
  columns (not captured — join to the `C1` file).
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
  report**; `SCORES-C4-<APP>`/`SCORES-C2-<APP>` are built from these blocks
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
Combined standings go on the whole competition (`C1`, part blank): `RANKING-FINAL-AA` rows with
`Part` blank, and `RANKING-FINAL-<APP>`. Day 2 has no per-day places, so
`Rank` is blank on `Part 2` rows (`UNPLACED`). Day-1-only athletes have no combined rows.

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
  event each day, so their `SCORES-C1-VT` is double-attempt: vault 1 is the AA
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
apparatus, no team or all-around title, so no `RANKING-*` files. Each
apparatus's qualification is its own competition (its own day and panel). Vault
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
| All-Around Results | the rankings; every routine's D, E, penalty, bonus, score and rank (cross-checked) |
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
finals on 7–8 March, each apparatus its own competition. The schedule splits them
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

### 5.12 Organizer media book, Imagine results print (Koper World Challenge Cup)

The Slovenian Federation's media book (`18293-ResultsbookMedia.pdf`): every page has text and no
report codes. A Competition Schedule (p. 2), entry counts by NOC (p. 3), the entry list (pp. 4-7),
medallists (p. 8), Elevien qualification start lists (pp. 9-22), the qualification judges (WAG
p. 23, MAG p. 24), the results tables printed by Imagine (`Final results`, footer `Imagine(c)`),
a tie-break report, the Elevien finals draw (pp. 48-49), the finals start lists (pp. 50-51), the
finals judges (pp. 52-53), the finals, a finals tie-break (p. 64) and medallists with scores
(p. 65). Parser:
[`parse_2026_world_challenge_cup_koper.py`](../tools/results-parsing/parse_2026_world_challenge_cup_koper.py),
which finds each table by its `Final results` heading, round line and apparatus name, and its
discipline by its bibs (MAG below 100).

**Structure.** An apparatus competition (§4.9) on the Baku pattern: qualification on 28-29 May,
finals on 30-31 May, MAG FX/PH/SR and WAG VT/UB first, MAG VT/PB/HB and WAG BB/FX second (schedule;
the table footers stamp every qualification table 29 May). Top eight per apparatus, two per
country (no `NR` printed), `R1`-`R2` (MAG vault: nine vaulters, one reserve).

| Report | Gives |
|---|---|
| List of competitors with BIB numbers | bib, NOC, FIG licence, `SURNAME`, `Given`, function, `(Hors Concours)`: the participants. No birth year |
| Number of Entries by NOC (p. 3) | men and women per country, blank for none; hors concours not counted (cross-checked) |
| Qualification tables (pp. 25-34) | every `C1` row, whole field, no markers |
| The same tables cut to the finalists (pp. 38-47) | the `Q`/`R1`-`R2` markers; their rows must repeat the whole-field tables |
| Tie Break Report (pp. 35-37, 64) | every group of equal totals: rank, total, E, D (cross-checked) |
| Qualification start lists (Elevien) | per day and part, groups in one column per apparatus under icons (MAG FX/PH, VT/PB in two columns; others one) (cross-checked as sets) |
| Finals start list (pp. 50-51) | each final's eight starters and `R1`-`R2` (cross-checked) |
| Medallists (pp. 8, 65) | a cross-check only |

**Gotchas**

- **Decimal commas**; D and the bonus/penalty print two decimals (`5,00`, `0,30`), E and scores
  three; written as printed with a point. Columns `D E S.b. Pen. Score Comp. <blank> Total`: `S.b.`
  is the bonus (MAG), `Pen.` unsigned (written negative); `Comp.` and the unlabelled column are
  `0,00` on every row, and the parser fails otherwise.
- **Vault**: the athlete's line holds vault 1 and the vault score, vault 2 the line below, each
  `D E S.b. Pen. Score`. MAG's bonus is inside the attempt's score; WAG's +0.2 is in the unlabelled
  column, headed `Bon.` on WAG vault (`Combined Bonus`).
- Results and start lists print bibs with leading zeros (`0012`), written as the entry list
  (`12`). Results print `PAES DIOGO` for `PAES Diogo`; the entry list's name is used.
- **Ties are always broken** (E, then D): no shared ranks. The tie-break report misspells some
  names (`IDRISOV`, `Almong`) and prints IORDACHE's floor E as `7,399` for the table's 7,366 (which
  adds up); it is reported, not used.
- **Replacement**: WAG floor PEDRO (`Q`) is on the finals start list but didn't compete; SZILAGYI
  (`R1`) did (§4.6).
- **Athletes without a result**: on a qualification start list but with no row and no DNS: MAG
  SALIMOV (FX, VT, HB), TANG Chia-Hung (FX, PH, SR, PB), LEE Yu-Chen (VT), MAMENOV and
  GARNCZAREK (PB), YOLSHIN-CASH (HB); WAG KORPELA (VT, FX), FENTON (VT), CZIFRA and PRIJANOVIC
  (UB), OLIVEIRA and PRPIC (FX). The vault tables rank only two-vault athletes, so a vaulter here
  may have done one vault. Hors concours (MAG 81, 82; WAG 159) are on the start lists with no
  results.
- **The p. 65 medallists print LEE Yu-Chen's floor bronze as 13,600**; the final has 13.000.
- Judges: MAG pages (`JUDGES ASSIGNMENT`, `QUALIFICATION` / `FINALES`) print `Competition Jury
  Julio Marcos FIG` (`TD`, written `MARCOS FELIPE Julio` as at Worlds), then panels under icons in
  the grid FX/PH, SR/VT, PB/HB: `function number SURNAME Given NOC`, `D1 D2 E1-E5` plus `T L1 L2`
  (FX) and `L` (VT). The right panel's labels start a few columns left of its `Number` heading.
  `MINNAR RUAN` is written `MINNAR Ruan`. WAG pages print `Superior Jury: LARIO Helena Beatriz
  Wgym President` (written `President`, NOC blank), panels VT/UB, BB/FX with `Function # Name NOC`
  and a category letter, `Time Judge 1`/`2` and `Line Judge 1`/`2` (`T1 T2`, `L1 L2`), and reserves
  `R1`-`R4` each beside an apparatus. A long name pushes its NOC onto the next line.

### 5.13 Organizer media book, typed in Excel (Szombathely World Challenge Cup)

The Hungarian Federation's media book (`18241-ResultsbookMedia.pdf`, printed from Excel): every page
has text and no report codes. A Competition Schedule (p. 2), entry counts by NOC (p. 3), medallists
and medal standings (pp. 4-5), then per discipline the Entry List by Bib Number, a qualification
start list per apparatus, the qualification judges, the qualification tables, a Tie Break Report for
each table with equal totals, the List of Qualifiers, the finals Start List, the finals judges, the
finals, a finals tie-break and a Medalists page per final. Parser:
[`parse_2026_world_challenge_cup_szombathely.py`](../tools/results-parsing/parse_2026_world_challenge_cup_szombathely.py).

**Structure.** An apparatus competition (§4.9): every qualification on 18 September; finals on
19 September (MAG FX/PH/SR, WAG VT/UB) and 20 September (MAG VT/PB/HB, WAG BB/FX), read from the
schedule, whose dates the tables' date lines repeat. Top eight per apparatus, two per country (no
`NR` printed), then a plain `R` on two reserves (§4.6).

| Report | Gives |
|---|---|
| Entry List by Bib Number (`Men` / `Women`) | bib, FIG licence, `SURNAME Given`, NOC, birth year: the participants |
| Number of Entries by NOC (p. 3) | men and women per country, `-` for none (cross-checked) |
| Results tables (`MAG - Qualification`, `WAG - Final`) | every SCORES file |
| Tie Break Report | the tied athletes' rank, total, E (vault: the highest vault) and, where E is equal, D (cross-checked) |
| List of Qualifiers, finals Start List | Q (numbered 1-8 in order), R1-R2 per apparatus, with the qualifying scores; the finals' starters (cross-checked) |
| Qualification start lists | per apparatus, `Bib Name NOC` (cross-checked as sets) |
| Medallists (p. 4, each final's page) | a cross-check only; their dates are wrong (`SAT 20 SEPT`, `FRI 20 SEPT`) |

**Gotchas**

- **The tables don't name the apparatus.** Each table runs over its `k/M` pages (footer), and
  they come in the schedule's order: MAG FX PH SR VT PB HB, WAG VT UB BB FX. The vault layout, the
  List of Qualifiers, the start lists and the tie-break titles prove the order.
- **Penalties in three columns**: `T` (time), `L` (line) and `O` (other), unsigned, written as one
  negative `Penalty`; `SB` is MAG's bonus. Which columns a table prints varies, so a value is placed
  under the nearest heading and the arithmetic proves bonus against penalty. MAG rings final SOUZA
  Caio: D 1.0, E 9.100, `O` 7.3, 2.800.
- **Vault** prints vault 1 above the athlete's line and vault 2 below, each `D E [SB] [L] [O]
  score`; the athlete's line holds `[VB]` and the vault score. MAG's `SB` is inside the attempt's
  score; WAG's `VB` (+0.2) is outside it (`Combined Bonus`). A DNF prints `DNF` with a vault 2 `DNS`
  and no rank (MAG BRANDENBURGER).
- **Wrapped names**: a long name prints above and below the athlete's line, which leaves it blank
  there (`DE SOUZA` / `BITENCOURT Lucas`); the List of Qualifiers and start lists push the NOC and
  score onto the next line instead.
- **The MAG vault qualification table's second page is missing** (printed `1/2`). MARKO Levente
  (135) is on the vault start list with no row, and thegymter.net's results have none either; he
  gets no vault row.
- **Replacements** (§4.6): MAG SOUZA Caio (`Q`) missed the parallel bars and high bar finals, the
  day after his rings final, for BUTRIMAS and BRANDENBURGER (`R1`); WAG VIEUXTEMPS (`Q`) missed the
  floor final for MAYER (`R1`). All keep their printed markers.
- **Athletes without a result**: on a qualification start list but with no row: MAG MARKO (VT),
  VERNIAIEV and BUTRIMAS (HB); WAG ANANJEVA (UB). MAG MENTOVAI (131) is entered but on no start list.
- **Misprints**, reported only: the tie-break reports print KORBIEL's pommel horse E `6.66` (6.066)
  and DAVIDSSON's rings final E `7.9666` (7.966); the List of Qualifiers numbers MAG pommel horse's
  6th qualifier `5`; the WAG vault finals start list prints ROPER Emily at 1 and 4 and leaves out
  DRUSCH, who vaulted.
- Judges: `SJ: <name> FIG` above the panels is the Technical Delegate (`TD`, NOC blank): MAG `Zunich
  Butch` (finals `Zunicz Butch`), written `ZUNICH Butch` as at Worlds (`JUDGE_NAME`); WAG `Donatella
  Sacchi`, kept as printed. Panels two to a row, `Function SURNAME Given NOC`, `D1 D2 E1-E5` plus
  `Time`, `Time 1`/`2`, `Line`, `Line 1`/`2`; no supervisor or reserves. The grid is MAG FX/PH,
  SR/VT, PB/HB and WAG VT/UB, BB/FX, from the time and line judges (MAG FX `T L1 L2`, VT `L`; WAG VT
  `L`, UB `T`, BB `T1 T2`, FX `L1 L2 T`). The MAG qualification panels for apparatus competed at the
  same time print the same judges. A long name pushes its NOC onto the next line, or joins it with
  one space; `LEEWORTHY Robin` prints `GBR` twice.

### 5.14 Media book in the FIG layout, Swiss Timing print (Paris World Challenge Cup)

The media book (`18305-ResultsbookMedia.pdf`), printed by Swiss Timing in the layout of the FIG
books (§5.1): every page has text and a `GAR…` footer code; page 1 is a cover image. A Competition
Schedule (p. 2), entries by NOC (p. 3), medallists (pp. 4-5), then per discipline the Entry List by
NOC (`_32A`) and by bib (`_32D`, full date of birth), the qualification judges (`_57A` MAG, `_57B`
WAG), per apparatus a start list (`_51I`), the results (`_73I`; vault `_73J`) and a Tie Break Report
(`_77A`; vault `_77B`), the List of Qualifiers (`_53B` MAG, `_53C` WAG), the finals start lists, the
finals judges, and per final a Medallists page (`_92A`), the results and any tie-break report.
Parser: [`parse_2026_world_challenge_cup_paris.py`](../tools/results-parsing/parse_2026_world_challenge_cup_paris.py).

**Structure.** An apparatus competition (§4.9): every qualification on 26 September, every final on
27 September (schedule; each report's date line agrees). Top eight per apparatus, two per country
(no `NR` printed), then `R1`-`R3`.

| Report | Gives |
|---|---|
| Entry List by Bib Number (`_32D`) | bib, FIG licence, `SURNAME Given`, NOC, date of birth: the participants |
| Entry List by NOC (`_32A`), Number of Entries by NOC (p. 3) | the same entries; counts per country, a blank for none, placed by column edge (cross-checked) |
| Results (`_73I`, vault `_73J`) | every SCORES file; finals add Qualification Rank and Start Order (cross-checked, not written) |
| Tie Break Report (`_77A`, vault `_77B`) | the tied athletes' rank, total and E (vault: the higher vault and which, `12.900 (VT1)`) (cross-checked) |
| List of Qualifiers | per apparatus `order bib Name NOC score`, 1-8 then R1-R3 (cross-checked) |
| Finals Start List Part 1 / Part 2 (`GARG1AP…FNL-PART<n>_51G`) | each final's starters and reserves (cross-checked) |
| Qualification start lists (`_51I`) | per apparatus, `Bib Name NOC`, `*` on every vaulter (cross-checked as sets) |
| Medallists (p. 4, `_92A`) | a cross-check only |

**Gotchas**

- **Six late French entries without results.** Bibs 77-80 (MAG BELLIL, BURBAIL, MANSARD,
  TRAORE-MALATRE) and 259-260 (WAG CHARPY, LETRANGE) come after the rest of the entry list and
  are counted in the entries by NOC. Each is first on the start list of one or two apparatus, and
  their results rows print bib, name and NOC only: no rank, no score, no `DNS` (real non-starters
  print `DNS` on the same pages). The book gives no reason. They are written as entries with no
  SCORES rows (`NO_RESULT` in the parser), confirmed with the user. See §6 item 8.
- **Bibs of one to three digits** (MAG 1-80), printed one space after the rank (`1 34`). The
  WAG List of Qualifiers prints the order and the bib run together (`1255` is order 1, bib 255).
- **Vault** prints `1` and vault 1 on the athlete's line, `2` and vault 2 on the next line, each
  `D E [Pen.] [Bonus] score`. The two-vault result follows vault 1's score, with WAG's `Vault Bonus`
  (+0.2, `Combined Bonus`) in between; MAG's bonus is inside the attempt (`0.1 14.666`). `DNS DNS`
  is no vault at all (both statuses `DNS`); `DNF` is vault 1 done and vault 2 `DNS` (MAG
  BRANDENBURGER).
- **Pen. and Bonus** share the space between E and the score; the sign tells them apart (§2.5).
  WAG beam qualification SUAREZ Alessia: D 1.1, E 7.700, `-6.0`, 2.800.
- **The finals start lists are printed twice**, the same pages in each discipline's section
  (pp. 29-32 and 69-72); the first copy is read, and the two are checked to be identical. Men are
  on the left and women on the right, in blocks headed `Start Time: hh:mm`; the apparatus is the
  schedule's for that discipline and time. Reserves print `R1`-`R3` with no bib.
- **Icons instead of apparatus names** on the judges pages and the List of Qualifiers (§2.7). The
  grid is MAG FX/PH, SR/VT, PB/HB and WAG VT/UB, BB/FX, confirmed from rendered pages.
- Judges: the Superior Jury is `Name  Technical Delegate` and `Name  Technical Delegate
  Assistant`, written `TD` and `TDA` with apparatus and NOC blank. Panels are `D1 D2 E1-E5` (WAG
  qualification `E1-E4`) plus `Time Judge`, `Time Judge 1`/`2`, `Line Judge`, `Line Judge 1`/`2`;
  MAG lists round reserves `R1`… below the panels (apparatus blank). Judge names are kept as
  printed, as a World Gymnastics book: `EECKHOUTTE Sebastien` (the Europeans' `Sébastien`).

### 5.15 Organizer media book, CorelDRAW outlines (African Championships)

The Union Africaine de Gymnastique's senior media book (`18377-ResultsbookMedia.pdf`, 60 pages, made
in CorelDRAW). Pages 1-6 have text: the cover, the Competition Schedule (pp. 2-3), the Number of
Entries by NOC (p. 4) and the Entries List by NOC (p. 5: `# NOC SURNAME Given Discipline FIG-ID BIB
date of birth`). Every results page is text converted to outlines (no text layer, §2.3) and the
judges' pages are photographs. Per discipline: qualification start lists, judges, the team report,
the all-around report, a table per apparatus, Tie Break pages, the Apparatus Finals Start List, the
finals judges and a table per final. Parser:
[`parse_2026_african_championships.py`](../tools/results-parsing/parse_2026_african_championships.py),
reading [`transcriptions/2026-AFRICAN-CHAMPIONSHIPS/`](../tools/results-parsing/transcriptions/2026-AFRICAN-CHAMPIONSHIPS/).

**Structure.** Qualification on 23 April decides the team and all-around titles (no team or
all-around final, §4.9); the top eight per apparatus (two per country, no `NR` printed) and two
reserves (a plain `R`, written `R1`, `R2`, §4.6) go to the finals: 25 April MAG FX/PH/SR, WAG VT/UB;
26 April MAG VT/PB/HB, WAG BB/FX (schedule; the footers agree). The book is the seniors' only; the
juniors' book is a separate scan (below).

| Report | Gives |
|---|---|
| Entries List by NOC (p. 5, text) | bib, FIG licence, `SURNAME Given`, NOC, full date of birth (`dd/mm/yyyy`, Egypt `yyyy/mm/dd`): the participants |
| Number of Entries by NOC (p. 4, text) | MAG and WAG per country, blank for none (cross-checked; WAG slips below) |
| Team report (`<n> Country  total`) | each member's scores, the counting ones in bold, and the team total; no apparatus totals |
| All-Around Results | every routine `D E P Total RK` (no bonus, `0.000` for no penalty) and the all-around total; incomplete all-arounds print `<partial> DNF` |
| Apparatus tables (qualification and finals) | every SCORES file |
| Tie Break pages | the tied athletes' rank and total and the deciding E (vault: the higher vault) (cross-checked) |
| Apparatus Finals Start List | 1-8, `R1`, `R2` per final (cross-checked) |

**Gotchas**

- **No team apparatus totals.** The team ranking's `<APP> Total` is the sum of the member scores
  printed in bold, which are checked to be each apparatus's best three and to add up to the printed
  team total (agreed with the user). Namibia's fifth WAG entry, HANDURA (born 2010), is not on its
  team page and competed as an individual.
- **Vault** prints vault 1 on the athlete's line and vault 2 below, each `D E [PEN] Score`; the
  athlete's line ends with the two-vault `Total`, and WAG's +0.2 sits in a `Bonus` column on the
  vault 2 line (`Combined Bonus`). MAG's vault bonus column is always empty. Athletes with one vault
  follow the ranking, unranked; `Rank` comes from the all-around report (§4.5). WAG ABDALLA: vault 2
  `DNS`, total `DNF`.
- **PEN is unsigned** (written negative), up to `10.000` (MAG high bar SAMB: D 0.000, E 6.500,
  total 0.000). Scores floor at zero (§4.3). Pommel horse and every WAG table have no BONUS column.
- **Finals that changed** (each printed marker kept; the parser reports them): MAG pommel horse
  MOHAMED and HOSSAINI (`Q`) out for NGORBO (`R`) and AFIFY (EGY, unmarked); rings MCLEAN out for
  SODEA (`R`); vault CHESTER out for NGORBO (`R`), after the start list was printed; high bar CHESTER
  out for SODEA (`R`) on the start list, and AFIFY, on it, replaced by AHMED (EGY) at the final. WAG
  bars and beam ABDALLA out, for SOLIMAN (EGY) and MUCHATUTA (`R`); floor ROOSKRANTZ and N. DARIES out
  for Z. DARIES and NHLEKO (all RSA). The start list's reserves move up in turn. No reasons given.
- **The WAG uneven bars final prints `Q`** beside all eight finalists, a leftover; ignored.
- **Names as printed differ**: ALHAMIDI Yacer Nadir prints `ALHAMIDI Nadir` (tables) and `Nadir
  HAMIDI` (team, start list); HANDURA Nagaititue prints `Ngaititue` everywhere after the entry
  list. Results files take the entry list's name.
- **Entries by NOC page slips** (WAG): it counts one Namibian (five entered and competed) and three
  Senegalese (two), 26 in all (29), and prints Zimbabwe `ZIM` where everything else prints `ZWE`
  (written `ZIM`, §4.8). The MAG counts agree.
- Judges: MAG (photographed sheets) heads the page with `Competition Jury  ZAYED Yasser UAG`
  (`TD`, §4.7); panels `SV D1 D2 E1-E5`, floor `T L1 L2`, vault `L`, laid out FX/PH, SR/VT, PB/HB
  under icons; `R1`, `R2` printed empty. WAG prints `SUPERIOR JURY 1  2058  Debbie  RSA` and
  `SUPERIOR JURY 2  4646  Rawan  EGY` with no surnames, written `Member`: Rawan as ABOUSHOUSHA
  Rawan (EGY), a judge at the Cairo World Cup, logged as a `JUDGE_NAME` correction noting the book
  gives no full name (agreed with the user); Debbie is not written (§6). WAG panels `AS D1 D2
  E1-E5` (`AS` written `SV`) plus vault `L`, bars `T`, beam `T1 T2`, floor `L1 L2 T`, each row with
  a seat number and a judge number (not written). The finals sheet cuts `DELGADO MIRANDA` to
  `DELGADO MIRAND` on two panels (`JUDGE_NAME`).
- A stale footer: the WAG bars tie-break page also prints `26 May 2023`.

**Junior book.** `18378-ResultsbookMedia.pdf` (78 pages, printed through "Microsoft: Print To PDF")
is a scan with no text layer anywhere, the schedule (the same pages as the seniors') and entry list
included, so everything is transcribed, into
[`transcriptions/2026-AFRICAN-CHAMPIONSHIPS/JR/`](../tools/results-parsing/transcriptions/2026-AFRICAN-CHAMPIONSHIPS/JR/).
The same parser reads it, choosing the book by the FIG event number the file name starts with. The
same structure and reports as the seniors, laid out by a scoring program rather than CorelDRAW, plus
an **Individual Judges Scores** page per table (D, E1–E5, the E total, the penalty parts and total,
the bonus, the score). The data model has no place for the judges' marks (§6), so those pages are a
cross-check only, agreed with the user: E must be the mean of the middle three marks, truncated; the
parts add up to the penalty total; the score adds up; and each value and rank agrees with the table.
The E check caught OCR slips arithmetic alone would not (a 6 read as 8 in a judge's mark).
Qualification on 24 April; the finals on the seniors' two days, after them.

- **Vault bonus**: a bonus is printed on the line of the vault it belongs to and included in that
  vault's score (MAG ABOUWARD, vault 2: 3.600 + 9.266 − 0.100 + 0.100 = 12.866); the two-vault
  total is the plain average. Written as that vault's `B`; no combined bonus (no WAG +0.2).
- **DNS in finals**: MAG floor DAVIES VANEETVELDE and high bar MKANDAWIRE print `DNS` and no values,
  unranked (§4.3).
- **Shared ranks in finals** (§4.2): equal totals share the rank (MAG rings SHAARAWY and MKANDAWIRE
  2nd; WAG bars FEKI and DU PLESSIS 3rd), though E differs; vault finals rank KIMITI 5th and EDINE
  MEZIANE 6th on 10.849, on the higher vault. Qualification breaks ties on E as the seniors' does,
  and shares the rank when D is equal too (MAG pommel horse DAVIES VANEETVELDE and LECHHEB 4th, the
  tie-break page printing both E and D).
- **Entries by NOC page slips**: it counts five South African men (the list has three, all of whom
  competed) and three Senegalese women (two), leaves out DR Congo's one woman, and prints Mali's code
  in the Country cell with no Total. Zimbabwe is `ZIM` there and `ZWE` elsewhere (written `ZIM`).
- **Countries**: YAELLE (bib 166) prints `RDC`, the French abbreviation; written `COD` (§4.8).
  NOGUER MUNOZ prints `MLI` (Mali) throughout.
- **Judges' scores page slips**: five WAG vault 2 lines print an ND that disagrees with the penalty
  total beside it (ELGARHI, SAFADI: ND 0.000, total 0.100; FEKI, STRAUSS: 0.000 and 0.300;
  BADENHORST: 0.300 and 0.100). The total agrees with the score and the vault table; the parser
  lists the five.
- **Finals that changed**: MAG pommel horse MKANDAWIRE (`Q`) out for KIMITI (`R`) on the start list;
  vault AMOURA (`Q`, on the start list) out for YIMGA, the start list's second reserve (LAKEHAL, the
  first, did not compete). No reasons given.
- Judges: no `SV`/`AS` on any panel; the qualification sheet cuts `DELGADO MIRANDA` to `DELGADO
  MIRAND` on the vault and beam panels (`JUDGE_NAME`). The WAG Superior Jury prints `Debbie` and
  `Rawan` only, handled as for the seniors.
- Names: MEZIANE Zine Edine (entry list) prints `EDINE MEZIANE Zine` in results; the identity check
  accepts it, and files take the entry list's name.

### 5.16 Media book in the FIG layout, Starting Future print (Asian Championships)

The Asian Gymnastics Union's media books, one per discipline and age category
(`18565-ResultsbookMedia.pdf` MAG seniors, 73 pages; `18566-…` MAG juniors, 49; `18567-…` WAG
seniors, 66; `18568-…` WAG juniors, 59), every results page with text; each book is recognised by
its title band (`19th JUNIOR MEN'S ARTISTIC GYMNASTICS ASIAN CHAMPIONSHIPS`). The
layout and report suffixes are the FIG books' (§5.1); the footer code is `GA` + `M`/`W` + a unit
(`x01` team, `x02` all-around, `x03`… apparatus in Olympic order, where `x` is 1 for seniors, 3 for
MAG juniors and 2 for WAG juniors; `000` the whole meet) + a phase
(`900` qualification, `100` finals, `000` the medal pages) + the suffix: `GAM103900_73I` is MAG floor
qualification. The Team Final and Team Qualification pages share a code (`_73C`/`_73D`), as do the
two all-around reports (`_73G`/`_73H`); the printed title tells them apart. Parser:
[`parse_2026_asian_championships.py`](../tools/results-parsing/parse_2026_asian_championships.py)
(all four books in one run).

**Structure.** One competition (MAG 18 June, WAG 25 June, in subdivisions) is the qualification
and the team and all-around finals (§4.9): the book prints the Team and All-Around Qualification
rankings (every team and athlete, `Q`/`R1-R4`/`NR`) and, from the same routines, a Team Final (the
top eight, same ranks and totals) and an All-Around Final (the 24 `Q`s, two per country, ranked 1-24:
MAG HUNG 8th in qualification, 7th in the final). Seniors: MAG qualification 18 June, finals
20 June FX/PH/SR and 21 June VT/PB/HB; WAG qualification 25 June, finals 27 June VT/UB and 28 June
BB/FX. Juniors a day later: MAG qualification 19 June, finals 20 June PH/SR/FX and 21 June
PB/HB/VT; WAG qualification 26 June, finals 27 June UB/VT and 28 June FX/BB (schedules; the MAG
junior book's title band says 25-28 June, a leftover from the WAG book). The entry list is one
report across the books: juniors on its pages 1-2 of 5, seniors on 3-5.

| Report | Gives |
|---|---|
| Entry List by NOC (`_32A`) | NOC heading, `SURNAME Given`, licence, bib, date of birth: the participants |
| Judges Assignments (`_57A`/`_57B`, qualification and finals) | President, panels in the icon grid (MAG FX/PH, SR/VT, PB/HB; WAG VT/UB, BB/FX), reserves |
| Apparatus tables (`_73I`; vault `_73I` "Vault 1" and the two-vault `_73J`) | every SCORES file; finals add `Qualification Rank` and `Start Order` (not written) |
| Team Qualification / Team Final (`_73C`/`_73D`) | `RANKING-FINAL-TEAM` (the final's places, the other teams added from the qualification, unranked); each member's D and E lines (cross-checked) |
| All-Around Qualification / Final (`_73G`/`_73H`) | `RANKING-FINAL-AA` (the final's places, the other athletes added from the qualification, unranked: NR as `NOC_LIMIT`); every routine (cross-checked) |
| Tie Break Reports (`_77A`-`_77C`) | the tied athletes' ranks (cross-checked, §4.2) |
| List of Qualifiers (`_53B`/`_53C`), finals Start List (`_51G`) | Q/R/NR per final (cross-checked) |
| Medallists by Event (`_93`) | the top three of every final (cross-checked) |

**Gotchas**

- **Apparatus tables print D to one decimal** (`6.0`), the team and all-around reports to three
  (`6.000`); the files copy the tables, the cross-checks compare values. A bonus prints `+0.1`
  (written `0.1`), a penalty `-0.3`, between E and the score. WAG vault's +0.2 sits between vault 1's
  score and the result (`Combined Bonus`); MAG's per-vault bonus sits before each vault's score.
- **Team report columns drift.** On a page, the team's header line (apparatus totals and ranks) can
  sit a column away from its members' lines, so the apparatus columns are taken from where the
  team's all-arounders' routines end (`DNS` is right-aligned under the score). The E line carries
  each routine's E with its penalty and bonus after it, in column order. No BP line.
- **Long names wrap** onto the E line in the all-around reports (`KAMILJANOV` / `Ravshan`);
  names come from the entry list.
- **Invited Australia** (MAG): `*` for a rank in every qualification table and report, including
  the team row (apparatus totals without ranks); unranked, entered `HORS_CONCOURS` (§4.1).
- **Finals that changed**: MAG high bar LI Hongyan (`Q`) prints `DNS` with his qualification rank
  and start order; WAG bars KE Qinqin out for QIU Qiyuan (`NR`, §4.6).
- **WAG KRASNOPEROVA** (KGZ): "withdrawn on Uneven Bars" on the start lists; no bars row.
- **The MAG junior book** has no qualification judges sheet, no qualification start lists, no
  tie-break pages and no team or all-around medal pages; its `JUDGES` holds the finals only.
- **Team penalty** (WAG juniors LBN): a starred beam total and team total with `* Penalty -0.6`
  (§4.3).
- **Junior athletes with every apparatus `DNS`** (MAG BAK Junwoo) print an empty E line.
- **Swapped birth dates**: the MAG senior entry list prints NAGHOUJ (JOR, licence 31183) born
  10 NOV 2006 and AL-KHALIDI (54342) 24 DEC 2000; World Gymnastics has NAGHOUJ born 2000 and
  AL-KHALIDI 2006, as the 2026 Tashkent book prints. The whole dates are written swapped
  (`BIRTH_DATE`, agreed with the user). Found when Tashkent's import met the years already recorded.
- **Names**: MAG AZIZOV prints `Llyas` (Ilyas elsewhere, same licence: a `NAME` correction). Judges
  `CHENG Feng-Yi` and `CHEN Ming-Yao` are written as World Gymnastics' books print them (`JUDGE_NAME`).
  MAG apparatus supervisors `LIPING Huang`, printed given name first, is written `HUANG Liping`,
  and `KIM Alexander`, KAZ's `KIM Alexandr` at the World Championships, is written `KIM Alexandr`
  (both confirmed by the user). The MAG apparatus supervisors are all credited to `AGU`; each is
  written with their federation from World Gymnastics, given by the user (`NOC` corrections). The
  WAG finals sheet credits its supervisors and reserves R2-R4 to `AGU` too; the qualification sheet
  gives their federations, which are used. The two Presidents stay blank, as a Superior Jury does.
  The junior books print the same officials and spellings, corrected the same way (the WAG junior
  sheets credit the four supervisors to `AGU` on both rounds; the senior qualification sheet gives
  their federations).
  The WAG qualification judges sheet is marked REVISED (floor E5 renamed TSAI I-Hsien); the
  revised sheet is the one printed.

### 5.17 Organizer media book, scanned Elevien print (Oceania Championships)

The Oceania Gymnastics Union's media books, one per age category and laid out the same: seniors
`18530-ResultsbookMedia.pdf`, juniors `18531-ResultsbookMedia.pdf` (each 20 pages: MAG pp. 1-10,
WAG pp. 11-20, each numbered "Media Book – Page 1-9"). The parser reads both in one run. Per discipline: a cover, then pages with text
(Competition Schedule, Entries by NOC, Medallists by Event and Medal Standings on one page; the Entry
List by NF and by Bib Number), then scans (Elevien start lists, the judges' sheet, Team Results, All
Around), and a Medallists page with text. The scans are rotated a quarter turn. Parser:
[`parse_2026_oceania_championships.py`](../tools/results-parsing/parse_2026_oceania_championships.py),
reading [`transcriptions/2026-OCEANIA-CHAMPIONSHIPS/`](../tools/results-parsing/transcriptions/2026-OCEANIA-CHAMPIONSHIPS/)
for the scans (typed by eye: two short tables a discipline).

**Structure.** One competition on 9 May (8 May is podium training) decides the team and all-around
titles, which the medallists pages call the "All around Final" and "Team Final"; no apparatus finals,
nothing qualifies, so by §4.9 it is Competition I (`C1`), holding every routine, with final team and all-around rankings of it (agreed with the user). The
juniors compete the same day in the same format (the MAG juniors' judges' sheet calls it the "Junior
Invitational"). Seniors: two teams of five per discipline. Juniors: MAG an Australian team of four
and two New Zealand individuals (New Zealand entered no team, so their scores are `INDIVIDUAL`);
WAG Australia five, New Zealand three.

| Report | Gives |
|---|---|
| Entry List (by NF, text) | country heading, `Given SURNAME`: the participants, in this order. No licence or birth year |
| Entry List by Bib Number (text) | bib, country, name (cross-checked) |
| Entries by NOC (text) | teams and athletes per country (cross-checked) |
| All Around (scan) | every routine, `Final <score>` / `D <d> P <pen>` / `E <e> S <bonus>` under apparatus icons (MAG FX PH SR VT PB HB, WAG VT UB BB FX), and the total; no apparatus ranks |
| Team Results 3 + 2 (scan) | rank, country, total; nothing else |
| Elevien results site's team pages (not in the books; screenshots kept in the event folder) | each team's line-up per apparatus, its counting and dropped scores: every score's `Team Role` |
| Start Lists (scan, Elevien) | per rotation, the athletes on each apparatus (cross-checked as sets) |
| Judges' Assignments (scan) | MAG a grid of `Given Surname (NOC)`; WAG four panels of `SURNAME Given NOC` |
| Medallists by Event, Medallists (text) | the top three all-arounders and both teams (cross-checked) |

**Gotchas**

- **`P` is unsigned** (written negative), `S` is the bonus; both print `0.0` for none (written blank).
  Pommel horse and every WAG cell print no `S`. Penalties include 3.0 and 6.0 short-routine
  deductions (MAG FU-ALLEN, STODDART).
- **Team totals** don't name the members, and the line-up changed by apparatus (the competition
  rules, from Gymnaverse's event page: five a team, up to four up on an apparatus, the best three
  counting; the fifth competes only for World Championships all-around qualification). So MAG AUS's
  234.294 is below the best three of its athletes: MALIK's floor (13.000) was an individual's. The
  line-ups come from the Elevien results site's team pages (screenshots from the user, transcribed as
  `<DISC>-TEAM-SCORES.txt`): MAG AUS individuals MALIK (FX), FOSTER (VT), HARDY (HB), NZL GREENE (HB),
  a team member on floor; WAG AUS STEWART (VT) and BAYLES (BB, her `DNS` row), NZL none. Every score's
  `Team Role` is written from them, and the counting scores add up to every printed total. A team
  member who didn't start is `DROPPED`. WAG AUS bars lists five team members, BAYLES's `DNS` among
  them, against the rule of four up; four performed, which is what the parser checks. Juniors: MAG
  AUS, a team of four, has no individual; WAG AUS ATKINSON is the individual on bars and beam (both her
  `DNS` rows). The site ranks the MAG juniors' New Zealand 2nd (115.063, every score of its two
  athletes), but the book enters no New Zealand team and ranks Australia alone: the book is followed,
  and DAVIES and VILJOEN are `INDIVIDUAL`.
- **Ranks**: partial all-arounders print a total and no rank, except WAG GODWIN (no floor), ranked
  6th (§4.3).
- **Start lists vs results**: MAG SR HARDY has a high bar score but is on no high bar rotation; WAG
  SR BAYLES is on the beam start list with a blank beam cell, and WAG JR ATKINSON likewise on bars
  (both written `DNS`, §4.3). The MAG JR start list prints DAVIES (113) twice in five groups; the
  sets still match the results.
- **Names**: results print `Given Surname` in mixed case (`Jun McDonald`); the files take the entry
  list's `Given SURNAME`. MAG FOSTER prints `Ben`, `Benjamin` (licence 45150) at Worlds: the licence
  is added (`LICENCE`) so the import links him.
- **Judges** (competition `C1`): MAG prints `AS` (`SV`), `Line 1`/`Line 2`/`Time` on floor and `Line 1` on
  vault; Puay Sng is `(SGP)` on floor and `(SIN)` on rings and parallel bars (written `SGP`, a `NOC`
  correction); surnames are written in capitals. WAG prints `Supervisor`, vault `Line`, bars
  `Time 1`, beam `Time 1`/`Time 2`, floor `Time`/`Line 1`/`Line 2`, and the same `Reserve` in every
  panel. The panels are VT/UB over BB/FX by the icons and the time and line judges. Five WAG judges
  are written with the full names World Gymnastics prints (`JUDGE_NAME`). The WAG sheet is headed
  "7 - 10 May 2026".

### 5.18 Organizer media book, own layout (Tashkent World Challenge Cup)

The Uzbek Federation's media book (`18291-ResultsbookMedia.pdf`, 74 pages, made with PDF Candy):
every page has text except the cover, with no report codes; pages are found by their heading lines.
A schedule (pp. 2-4), Number of Entries by NOC (p. 5), Medallists By Event (p. 6), Medals Standing
(p. 7), the entry list (`Number of Athletes`, pp. 8-10), then per discipline the qualification start
lists, the qualification judges, per apparatus the results (`Apparatus Results` / `MAG
Qualification` / apparatus) and any `Tie-Break Report` on the next page, the finals start lists (one
page a day), the finals judges and the finals. Parser:
[`parse_2026_world_challenge_cup_tashkent.py`](../tools/results-parsing/parse_2026_world_challenge_cup_tashkent.py).

**Structure.** An apparatus competition (§4.9) on the Baku pattern: qualification on 21-22 May,
finals on 23-24 May, MAG FX/PH/SR and WAG VT/UB first, MAG VT/PB/HB and WAG BB/FX second (schedule
rotations; the start lists' dates agree). Top eight per apparatus, two per country (no `NR` printed),
`R1`-`R3`.

| Report | Gives |
|---|---|
| Number of Athletes (pp. 8-10) | under `NOC – Country`, `SURNAME Given  Bib  Licence  Year`: the participants. MAG bibs 1xx, WAG 2xx |
| Number of Entries by NOC (p. 5) | men and women per country (cross-checked; see below) |
| Apparatus Results | every SCORES file; `Q`/`R1`-`R3` after the total |
| Tie-Break Report | the tied athletes' rank, total and E (vault: the highest vault) (cross-checked) |
| Qualification start lists | MAG a page per apparatus and subdivision, WAG a page per apparatus in group columns; `(HC)` marks hors concours (cross-checked as sets) |
| Finals start lists | each final's eight starters and `R1`-`R3`, vaulters `2VT` (cross-checked) |
| Medallists By Event (p. 6) | a cross-check only |
| Elevien app screenshot (in the event folder) | the MAG rings final's D, E and bonus |

**Gotchas**

- **The entry list's names drift**: a long name wraps, sometimes onto another athlete's line
  (`GOBADZE Ani MOTTEN` / `Dorien`; `Arda DEMIR` / `Sercan KARTIN Emirhan` for HAMARAT Volkan Arda,
  DEMIR Sercan, KARTIN Emirhan), and numbers sit a line from their names. Each country's names are
  read in order, split where an upper-case word follows a given name, and paired with its numbers
  in order; every results table then confirms the names. `AZAMOVAsadbek` prints without a space (a
  `NAME` correction).
- **Columns** `D score E score [B] Pen Total`: `B` (MAG, not pommel horse) prints `0.0` for none,
  `Pen` unsigned with two decimals and `0.00` for none (written negative, or blank).
- **The MAG rings final prints totals only** (no D or E) and ranks TEMIRKHONOV over NGUYEN Van Khanh
  Phong on equal 13.850, with no tie-break page. D, E and bonus come from a screenshot of the Elevien
  app the user supplied (`18291-2026-WCC-TASHKENT-MAG-SR-STILLRINGS-FINALS.png`), logged as `ROW`
  corrections; they add up to every total and break the tie on E (8.950 / 8.550).
- **Vault** prints `1` and vault 1, its score and the vault total on the athlete's line, then `2`
  and vault 2; MAG's `B` is inside the attempt. WAG's +0.2 prints as `(+0.2)` after vault 2's score
  and is in the total (`Combined Bonus` 0.2). The WAG qualification table prints each vaulter's birth
  year under the name: NAYAK and SAMANTA print 1995 and 2003 against the entry list's 1997 and 1995,
  and the table's are written (`BIRTH_DATE`, agreed with the user). AL-KHALIDI 2006 and NAGHOUJ 2000
  are right (World Gymnastics); the Asian Championships' book had them swapped (§5.16). TELLO prints
  `DNF` with vault 2
  `DNS`.
- **Ties are always broken** (E, then D; vault the highest vault, then E, then D). The MAG rings and
  WAG vault finals have ties and no tie-break page.
- **Hors concours**: MAG 135-138 and WAG 225-227, all UZB, print `(HC)` on the qualification start
  lists only; they are not on the entry list and have no results, so are not written (§6 item 8).
- **A start-list athlete left out of the table**: MAG SITCHINAVA is on the vault start list with no
  row, not even `DNS`. Elevien has him `DNS`, so the parser adds a blank row and `ROW` corrections
  set both vaults `DNS` (from the user). MAG floor subdivision IV prints its bibs against the wrong names
  (`104 VU Tien Anh`; VU is 145).
- **Number of Entries by NOC** swaps men and women for HUN, IND and ISL and counts 3 men for GEO and
  VIE (4 each); its totals (42, 28, 70) agree with the entry list.
- Judges: MAG `SUPERIOR JURY : Mr. HAN Yoon Soo WG` (`TD`, NOC blank), then panels `D1 D2 E1-E4` in
  the grid FX/VT, PH/PB, SR/HB (icons; `T L1 L2` on floor, `L` on vault): the left column is day
  one's apparatus, the right day two's. `R1` printed under each column (`R2` blank) is left out
  (agreed with the user). WAG `Superior Jury: GRATT Johanna Wgym` (`TD`, NOC blank), panels VT/UB,
  BB/FX (legend) with `Function Name NOC` and a category letter, `Time Judge 1`/`2` on beam, `Line
  Judge 1`/`2` on floor, and reserves `R1`-`R4` (apparatus blank). Wrapped labels put their number
  on the next line, beside the next judge's name; each judge is read at their NOC and category
  letter.

### 5.19 Games results book, ORIS-style print (Commonwealth Games)

The Glasgow 2026 Games' media book (`18222-ResultsbookMedia.pdf`, 134 pages, Longines timing): every
page has text and a footer code (`GARM1APFX-------------QUAL--------_73I`, the schedule `_08`, entry
lists `_32A`, officials `_35`, start lists `_51x`, judges `_57x`, results `_73x`, tie-breaks `_77x`,
medallists `_93`, medal standings `_95`); the parser finds pages by code, with the dashes removed.
Parser: [`parse_2026_commonwealth_games.py`](../tools/results-parsing/parse_2026_commonwealth_games.py).

**Structure.** "Team Final and Individual Qualification" (MAG 24 July, WAG 25 July) decides the team
title, so it is `C1` with a `RANKING-FINAL-TEAM` of it (§4.9, as at the Mediterranean Games); the
all-around finals (26 July) and apparatus finals (27-28 July, by the schedule) follow. Teams of up
to five, three scores counting. Athletes compete for Commonwealth Games Associations (§4.8).

| Report | Gives |
|---|---|
| Entry List by CGA (`_32A`) | under `AUS - Australia`, `SURNAME Given  Licence  Bib  Date of birth`: the participants, in printed order |
| Apparatus results (`_73I`, vault `_73J`) | every qualification and final SCORES file but the all-around final's; vault: the two-vault athletes only (below). Finals add the qualification rank and start order (cross-checked) |
| Team results (`_73C`/`_73D`) | the team ranking; each member's routines (cross-checked), and the first vaults of team members |
| All-around results (`_73G`/`_73H`) | the all-around rankings; the all-around final's routines (it has no apparatus tables); the first vaults and their whole-field rank (below); qualification routines cross-checked |
| Judges Assignments (`_57x`) | JUDGES. The Competition Officials list (`_35`) is a cross-check of each judge's CGA |
| Start lists (`_51x`), Tie Break (`_77x`), Medallists by Event (`_93`) | cross-checks only |

**Gotchas**

- **Vault qualification lists only the two-vault athletes.** The other first vaults come from the
  team report (team members) and the all-around qualification report (all-arounders, individuals
  included); they agree wherever both print one, and every vaulter is in one of the three. There is
  no single-vault list: `Rank` is the all-around report's vault `Rk`, which ranks an all-arounder's
  first vault against the whole field (checked against every first vault), and blank for everyone
  else (agreed with the user). MAG NG Chun Chen (bib 132) vaulted `0.000` (D and E `0.000`), then
  `DNF` with vault 2 `DNS`: `INVALID_VAULT`; CHAKMA's vault 2 `0.000` halves his average.
- **The team and all-around reports have icon headings**, in the legend's order (MAG FX PH SR VT
  PB HB, WAG VT UB BB FX), proven by matching every value with the apparatus tables. The team report
  prints a member's `D score` per apparatus, then an `E` line and a `BP` line (WAG one `EP` line);
  values are placed by position, a column starting at the team line's `(rank)` for that apparatus.
  A signed 1-decimal value is a penalty, unsigned a bonus. The all-around report prints `D score (Rk)`
  per apparatus in order, `DNS` for one not done.
- `DNS` is printed for an entered routine not done (team report, tables). A team member with no
  routine at all prints blank lines (WAG RSA NHLEKO Buhle). A team that didn't finish prints `DNF`
  with blank apparatus totals (MAG MAS: no rings, no high bar), written unranked; the all-around
  `DNF`/`DNS` rows likewise.
- **The apparatus finals start lists and judges pages are printed twice**, in each discipline's
  section (pp. 69-74 = 124-129); the parser reads the first copy and checks the second is identical.
  Each lists the men's finals down the left and the women's down the right, in the schedule's order.
- Markers: `Q`, `R1`-`R4` (all-around), `NR` on the tables. Replacements: MAG all-around SINGH
  (`Q`) out for EYRES (`R1`); WAG all-around ROOSKRANTZ (`Q`) for her compatriot DARIES Zelme (`NR`),
  ranked above the first reserve as the note allows; WAG bars EVANS (`Q`) for TAYLOR (`NR`), both
  WAL. The all-around start list renumbers its reserves after the replacement, so it is only
  checked for its finalists.
- **Ties are broken** (apparatus: E, then D; vault: the higher vault, E, D; all-around: the best
  five, four, … apparatus scores, then E, then D), and the Tie Break reports' ranks match the tables.
- Finals E scores have three decimals (`8.466`, an average of three judges' marks).
- Judges: per round a Superior Jury (`President`, and `Floor Exercise & Vault Supervisor` written as
  an `SV` for each apparatus, NOC blank as printed), then panels `D1 D2 E1-E4` (finals `E1-E5`) with
  `Time Judge [1|2]` and `Line Judge [1|2]`; the qualification and all-around final grids are the
  legend's (MAG FX/PH, SR/VT, PB/HB; WAG VT/UB, BB/FX), confirmed by floor's time and line judges,
  vault's line judge and beam's two time judges. Reserves `R1`-`R3`: a round's serve every panel
  (apparatus blank); the finals' are listed per day, so each is written once for each of that day's
  finals. The assignments spell some names otherwise than the officials list (`HANLEY Nicola` /
  `Nikki`, `JANSE van VUUREN Jan Hendrik` / `Jannie`): the assignments are written. `ZUNICH Andreja`
  is written `ZUNICH Butch`, as the officials list and the Worlds files have him (`JUDGE_NAME`).
  PADDOCK Samantha is credited to ENG on every assignments page and to WAL on the officials list;
  ENG is written.
- The entry list's licences and birth dates agree with every earlier 2026 entry for the same
  licence; NIR's athletes compete for IRL elsewhere and link by licence.

### 5.20 Games results book, ORIS-style Bornan print (Central American and Caribbean Games)

The Santo Domingo 2026 Games' media book (`18666-ResultsbookMedia.pdf`, 193 pages, Bornan timing):
artistic is pp. 1-109, every page with text and a footer code (`GARM1APFX-------------QUAL--------_73I`;
the judges pages have no `Report Created` stamp); the rhythmic (pp. 110-161) and trampoline
(pp. 162-193) books follow without codes and are skipped. The layout and codes are the Commonwealth
Games' (§5.19), so the parser
([`parse_2026_central_american_caribbean_games.py`](../tools/results-parsing/parse_2026_central_american_caribbean_games.py))
started from that one.

**Structure.** "Individual Qualification & Team Final" (MAG 2 August, WAG 3 August) decides the team
title: `C1` with a `RANKING-FINAL-TEAM` of it, as at the Commonwealth Games (§4.9); the all-around finals
(4 August) and apparatus finals (5-6 August, by the schedule) follow. Teams of five, four up per
apparatus, three counting; individuals from countries without a team.

| Report | Gives |
|---|---|
| Entry List by NOC (`_32A`, men and women under one code, told apart by the page heading) | `SURNAME Given  Licence  Bib  Date of birth` under `COL - Colombia`: the participants. Number of Entries by NOC (`_30`) counts them (cross-checked) |
| Apparatus results (`_73I`, vault `_73J`) | every qualification and final SCORES file but the all-around final's; vault qualification lists only the two-vault athletes (below). Finals add the qualification rank and start order (cross-checked) |
| Team results (`GARMTEAM…FNL_73C`/`_73D`, titled Final, printed on qualification day) | the team ranking and penalty; each member's routines (cross-checked), and the first vaults of team members |
| All-around results (`_73G`/`_73H`) | the all-around rankings; the all-around final's routines; the first vaults and their whole-field rank; qualification routines cross-checked |
| Qualification results by team (`GARMQUAL_73A`/`GARWQUAL_73B`) | scores only, every team member and individual, vault `V1 V2 [Bonus] FS`, all-around total and rank (cross-checked) |
| Judges Assignments (`_57A`/`_57B`, qualification, all-around final, apparatus finals) | JUDGES |
| Lists of Qualifiers (`_53A` all-around, `_53B`/`_53C` apparatus), start lists (`_51x`), Tie Break (`_77x`), Medallists by Event (`_93`) | cross-checks only |

**Gotchas**

- **D has one decimal in the apparatus tables (`5.5`) and three in the reports (`5.500`)**; each is
  written as printed (the single vaults, from the reports, keep three) and compared as numbers.
- **The reports' E lines drift against their D lines**, so values can't be placed by position: a
  bonus can print nearer the next routine's E (`8.800 +0.1 9.100 -0.3`, MAG NUÑEZ FARFAN: the
  `+0.1` is rings', the `-0.3` vault's). The E line lists the E scores of the routines done, in
  order, each followed by its penalty or bonus; the arithmetic proves it. A routine's apparatus on
  the team report's D line is the team column its score starts in.
- **Long names wrap** in the all-around reports and the vault tables: the rest of the name prints
  on the next line, alone or before the `E` or the vault 2 line. Team reports and start lists print
  initials (`TAPERIO JAYES MRJ`, `SOTO J` for SOTO RODRIGUEZ Jensuel Jose), matched against the
  entry list by surname and initials.
- **Vault qualification lists only the two-vault athletes**, as at the Commonwealth Games: the
  other first vaults come from the team and all-around reports, and `Rank` is the all-around
  report's vault `Rk` (whole field), blank for the rest. WAG's `+0.2` prints between vault 1's
  score and the result (`Combined Bonus`). The by-team report leaves one individual's bonus out
  (WAG MANCIA POLANCO: `12.750 12.500 12.825`). MAG vault final NIN REYES: vault 1 `0.0 0.000 0.000`,
  `DNF`, vault 2 `DNS`: `INVALID_VAULT` then `DNS`, unranked.
- **The WAG judges pages' legend names the men's apparatus**; the icons (rendered) and the time and
  line judges (vault's line judge, beam's two time judges, floor's time and line judges) give the
  grid VT/UB, BB/FX. MAG is FX/PH, SR/VT, PB/HB. Panels are `AS D1 D2 E1-E4` in every competition,
  finals included; one judge can sit on several panels of a competition. No reserves are listed.
- **Apparatus finals start lists** (`GAR-1AP…FNL-PART<day>_51G`, revised) print men left and women
  right in blocks headed `Start Time: hh:mm`, the first block of a day men only; a name can end one
  space before its NOC. Replacements (MAG rings NUÑEZ FARFAN for PORRAS ESCATEL, parallel bars LOPEZ
  MARTINEZ for SOTO RODRIGUEZ, both `NR` compatriots; WAG floor, §4.6) are noted at the foot.
- MAG all-around: 15 `Q` (GUA's third, `NR`, is the only reserve); BELL Clayton (JAM) didn't start
  the final, so 14 are ranked.
- Judges credited to `UPAG` (both Superior Juries, every apparatus supervisor) are written with the
  federation other 2026 meets give them, each a `NOC` correction keyed by the judge's name; every
  one had a single federation across the Worlds, World Cup and Senior Pan American files.
- Entry-list birth dates for ALVAREZ Jorman (MAG 202) and HERRERA POLANCO Brithany (WAG 110) differ
  from the 2026 Worlds entry list by ten days; Worlds' are written (`BIRTH_DATE` corrections).

### 5.21 Games results book, ORIS-style Bornan print (Asian Games)

The Aichi-Nagoya 2026 Games' OCA results book (`18608-AG2026_GAR_RB_v1.pdf`, 136 pages, Bornan
timing), and the MAG "Results Vault 1" report (`18608-AG2026-MAG-SR-VAULT-QUAL-C73I_Results.pdf`, one
page, the same print and code `GARM1APVTQUAL_73I`), published apart from the book: artistic only, every page with text and a footer code but the cover, the copyright page and
the back cover (p. 136, an image). The codes and layout are the Central American and Caribbean
Games' (§5.20), so the parser
([`parse_2026_asian_games.py`](../tools/results-parsing/parse_2026_asian_games.py)) started from that
one. Headers are bilingual (English, then Japanese).

**Structure.** "Qualification and All-Around Final" (MAG 21, WAG 22 September) ranks the all-around
title (the best 24, two per NOC; the others print their totals unranked) and qualifies eight teams to
the team final (23 September, three up, three counting, its own routines) and eight athletes to each
apparatus final (24-25 September). So it is `C1`; the all-around title is a `RANKING-FINAL-AA` of `C1`
and the team final a normal `C4` competition (§4.9). Qualification teams are five
up to four, three counting; individuals from other NOCs.

| Report | Gives |
|---|---|
| Entry List by NOC (`_32A`, men and women under one code) | the participants; Number of Entries by NOC (`_30`) counts them |
| Apparatus results (`_73I`, vault `_73J`) | every qualification and apparatus final SCORES file; vault qualification lists only the two-vault athletes. Finals add the qualification rank and start order (cross-checked) |
| Team results, qualification (`GARMTEAMQUAL_73C`/`GARWTEAMQUAL_73D`) | the team ranking, markers (`Q`, WAG KAZ `R1`) and penalty; each member's routines (cross-checked) and the first vaults of team members |
| Team results, final (`…TEAMFNL_73C`/`_73D`) | the team final's routines (SCORES-C4) and standings |
| All-around results (`GARM1AAFNL_73G`/`GARW1AAFNL_73H`, titled Final, the qualification's routines) | RANKING-FINAL-AA; the first vaults of all-arounders and their whole-field rank; every routine cross-checked against the tables |
| Qualification results by team (`_73A`/`_73B`) | scores only, every athlete, all-around rank (cross-checked) |
| MAG Results Vault 1 (the separate file) | every first vault, with D, E and its whole-field `Rank`; the only source for KAMILJANOV's (below). The two-vault table and the team and all-around reports are checked against it |
| Judges Assignments (qualification `_57A`/`_57B`, team final `…TEAMFNL_57x`, apparatus finals `GAR-FNL-000<day>00_57D`) | JUDGES |
| Lists of Qualifiers (`_53B`/`_53C` apparatus, `_53D` team), start lists (`_51x`), Tie Break (`_77x`), Medallists by Event (`_93`) | cross-checks only |

**Gotchas**

- **A vault in no report of the book but the results by team.** MAG KAMILJANOV Ravshan (UZB, 154),
  an individual who did pommel horse and one vault, is in neither the team nor the all-around report
  nor the two-vault table; the results by team print only his score (`12.433`). The Results Vault 1
  report gives his D and E, and every vaulter's rank. WAG has no such list: its first vaults' `Rank`
  is the all-around report's (all-arounders only), as at the CAC Games.
- **Tied first vaults**: the Results Vault 1 list breaks them on E (MAG ZHANG and LAN 7 and 8 at
  14.133; HASHIMOTO 14 behind IDRISSOV, PUA 26 behind RYU), where the all-around report's `Rk` shares
  the rank (13, 25). The list's ranks are written.
- **A two-vault result printed above the truncated average**: MAG qualification TRINH Hai Khang,
  13.366 and 14.033, printed `13.700` (13.6995; the unrounded E scores average to 13.700, but other
  results are truncated, KIM Jaeho's `14.149`). Written as printed; the parser allows this one.
- **Placeholder zeros before `DNS`** (§4.3): MAG KANETA's floor (`0.0 0.000 DNS`, and `D 0.000 DNS`
  over `E 0.000` in the team report). MIRVALIEV (UZB) prints `DNS DNS` in the two-vault table.
- **The finals start lists and judges pages are printed twice** (pp. 52-55 = 113-116); the first copy
  is read, the second checked identical. Each lists the men's finals down the left and the women's
  down the right; a start list's block heading can share a line with the other side's last reserve.
- **Names.** The entry list prints MAS `Muhammad Sharul Aimy` and MYA `PAN EI PHYU` with no
  SURNAME Given split; their other 2026 entries (same licences) split them AIMY / Muhammad Sharul and
  PHYU / Pan Ei, and so does the parser (agreed with the user). The results by team print initials
  (`TAN A`, `CHEN HYJ`, `MSA`); the all-around report cuts long names, wrapping the rest under them.
  Taiwanese given names print with lower-case second syllables (`TANG Chia-hung`), other 2026 books
  `Chia-Hung`; they link by licence.
- **Judges**: the Superior Jury (`President` and one `<Apparatus> Supervisor` per apparatus, all
  `AGU`) heads each sheet; panels `D1 D2 E1-E5` with time and line judges, in the grid MAG FX/PH,
  SR/VT, PB/HB and WAG VT/UB, BB/FX (floor's and vault's line judges, beam's two time judges). Reserves:
  MAG `R1 R2` per round; WAG none in qualification, `R1` in the team final; the finals' per day and
  discipline, written once for each of that day's finals. The supervisors' federations come from the
  Asian Championships and D1 AMER Rima's (`JOR`) from the user (`NOC` corrections); `AL-BUAINAIN Abeer` and `ORTEGA Jasmin Amanda` are kept as
  printed (the Asian Championships print `AL BOUAINAIN Abeer`, `ORTEGA Jasmin`).
- **WAG KAZ**, ninth and first reserve team, has `* Penalty -1.0` (a wrong start order) under its total
  (`130.796*`): `SJ Penalty` `-1.0`.
- **Finals replacements**: MAG floor ZHANG (`Q`) out for KIM Jaeho (`R1`), OKA (`Q`) for HASHIMOTO
  (`NR`); rings OKA for LEE Junghyo (`R1`); parallel bars ZHANG for LAN (`NR`); high bar ZHANG for
  HAMIDI (`R1`). WAG bars KE for QIU (`NR`); floor ZHANG Qingying for ZHANG Yihan and AN Chang Ok for
  HAN Yon Mi (both `NR`).
- Birth dates for GHADIMI Mehrdad (QAT, 137: 16 Jun 2003) and ANDREW Chiara Dawn (PHI, 537: 30 May
  2006) differ from the 2026 Asian Championships entry list (5 Oct 2003, 20 May 2006). This book's are
  right (checked by the user; World Gymnastics for ANDREW): the Asian Championships files carry
  `BIRTH_DATE` corrections, and the two athletes' stored birth dates were corrected by hand, since a
  reimport keeps athlete records. KANETA Kiichi (JPN, 116) prints licence 49174; his licence is 49574,
  as the Baku Apparatus World Cup has it (a `LICENCE` correction).

### 5.22 Games media book, bilingual Bornan print (South American Games)

The Santa Fe 2026 Games' media book (`18708-ResultsbookMedia.pdf`, 250 pages): rhythmic (pp. 2-77)
and trampoline (pp. 79-133) first, then artistic (pp. 136-249), the only part read, every page with
text. Headers are Spanish over English (`Suelo Masculino` / `Men's Floor Exercise`), and the footer
code puts the report family first: `C73A.GARM1APFX-------------QUAL--------.ENG` (the CAC and Asian
Games' `_73I` reports). Families: schedule `C08`, entries by NOC `C30`, entry list `C32A`, start lists
`C51x`, lists of qualifiers `C53x`, judges `C57x`, results `C73x`, tie-breaks `C77x`, medallists
`C92x`/`C93`, medal standings `C95`. The results letter varies (`C73A`/`C73B` qualification, `C73I`
finals, `C73J` vault finals, but `C73A` for the MAG high bar final), so the parser
([`parse_2026_south_american_games.py`](../tools/results-parsing/parse_2026_south_american_games.py))
matches on the event part.

**Structure.** "Competition I: Qualification" (MAG 13, WAG 14 September, two subdivisions) is
followed by apparatus finals (15-16 September): `C1`. "Competition II: Final" (team and
all-around) shares subdivision 2's time block; its reports, titled Final, rank the qualification's
routines, so Competition I decided both titles: `RANKING-FINAL-TEAM`/`-AA` of `C1` (§4.9).
Teams of up to six, five up per apparatus, four counting (MAG BRA, COL, ARG, CHI, PER; WAG ARG, BRA,
PAN, PER, BOL; BOL's four all count). The all-around final ranks two per NOC and prints the others
unranked.

| Report | Gives |
|---|---|
| Entry List by NOC (`C32A`, printed twice: front matter and section) | under `ARG - Argentina (6)`, `SURNAME Given  Licence  Bib  Year`: the participants, with the results' bibs (below). Entries by NOC (`C30`) counts them |
| Apparatus results (`C73x`) | every qualification and final routine but the first vaults of one-vault athletes. Vault qualification: the two-vault athletes only; WAG adds a First Vault list (every first vault, ranked) on the report's second page |
| Team results (`C73C`/`C73D`, Final) | RANKING-FINAL-TEAM; MAG team members' first vaults; every other routine cross-checked |
| All-around results (`C73G`/`C73H`, Final) | RANKING-FINAL-AA; MAG individuals' first vaults; every other routine cross-checked |
| Judges Assignments (`C57x`, qualification and finals) | JUDGES |
| Lists of Qualifiers (`C53x`), start lists (`C51x`), Tie-Break Output (`C77x`), Medallists by Event (`C93`) | cross-checks only |

**Gotchas**

- **The results' bibs aren't the entry list's** (MAG 40-78 against 1-74, WAG 1-35 against 6-75):
  every results table and start list uses one numbering. It is written; each entry is matched to it
  by name and NOC (§4.1).
- **Columns are placed by position** (§2.6): `D E B Pen. Total` right-aligned under their labels, the
  total not under its label (a row's last three-decimal value). `Pen.` is unsigned and `0.0` for none
  (written negative, or blank). A D or E can be blank: WAG ORTIZ's bars (`0.000` E, no D, ranked
  31st; `COMPLETED`, §4.3) and CARVAJAL's first vault (no D, E `0.000`, `0.3` penalty, `0.000`:
  `INVALID_VAULT`). The two-vault table prints CARVAJAL's vault 1 as its penalty alone; the First
  Vault list gives the rest.
- **Vault**: line 1 `D E [Pen.] Score Total [Q|R]`, line 2 `D E Pen. Score [B]`. MAG's `B` is that
  vault's bonus (inside its score: final ROMERO 4.8 + 9.15 + 0.1 = 14.05); WAG's is the combined
  bonus. **Two-vault results are rounded, not truncated**: CHICA's 13.375 and 13.350 print `13.363`,
  ACOSTA's 13.367 and 12.934 `13.351` (with the bonus), but AGÜERO's 13.675 and 13.400 `13.537`. The
  parser allows 0.0005 either way. MAG has no First Vault list (§4.5). ROSTAGNO's blank vault 2 in
  the final: §4.3.
- **The team and all-around reports** print per athlete a line of `D Score` pairs (icon columns in
  the legend's order: MAG FX PH SR VT PB HB, WAG VT UB BB FX), an E line (each routine's E, then its
  penalty, three decimals) and a rank line (each routine's bonus, printed under the next column's D,
  then its `(rank)`). The team report's line A is placed by the header's `Score` columns (members
  skip apparatus). The all-around report's long names push the values right and wrap the rest of
  the name, and the `NOC - Country`, onto the lines below, so its values are read in order. Both
  are checked against the tables, and the vault `(rank)` against the two-vault table. The team
  report prints a bare `0` in BRAJAO's bonus line (no bonus), and no E for ORTIZ's 0.000 bars.
- **The WAG all-around final's ranks**: SAUCEDO (ARG), RODRIGUES Gabriela (BRA) and LIDE (PAN),
  each her NOC's third, print their whole-field rank (6, 7, 9; 6 and 9 also held by the final's
  GUTIERREZ and WORRING), where the other non-counting athletes print none. Written blank, as `RANK`
  corrections (agreed with the user); the MAG final is consistent.
- **No `NR`**: the third athlete of a NOC gets no marker; reserves are `R1`, `R2`. Replacements:
  §4.6. The floor finals' start lists add the two reserves after the eight.
- **Judges**: the Superior Jury is one `PR` (President) per sheet, but the WAG finals have two, one
  per pair of apparatus. Panels `D1 D2 E1-E4` (MAG) or `E1-E3` (WAG) in qualification, `E1-E6` (MAG)
  or `E1-E5` (WAG) in the finals, with line and time judges; the MAG parallel bars panels have a
  `T` (checked on the rendered page). Judges whose World Gymnastics books (Worlds, Osijek World Cup)
  give a fuller name are written so (`LI LIN WAY Jim Anthony`, `ALVARADO CLEMENTE Lisseth Amelia`,
  `STAMATTI Fabian Audite`; `JUDGE_NAME` corrections). Those known only from the Pan American and CAC
  books (`ABAD Juan José`, `ANTEQUERA ECHEVERRIA Walter`, `PEREZ CABALLERO Raul Antonio`) keep this
  book's spelling.
- **Names** are printed short (`MEJIA Thomas`, other 2026 books `MEJIA Thomas Eden`;
  Brazilians by another surname: `BRAJAO Diogo` is the Worlds' `SOARES Diogo`, `ANDRADE Bernardo`
  `MIRANDA Bernardo`). They link by licence. Two licences carry another given name elsewhere:
  GARVIZU Jose (BOL, 66689; `Mateo` at the Pan Americans) and RODRIGUES Chloe (PER, 59772; `Soleil`
  at Paris).
- **MAG TORRES Sebastian (VEN, 77)** is on the vault start list (rotation 3) and in no vault report;
  his vault isn't written (§6).

## 6. Open items

1. **Invalid vault appearance.** FIG books print a plain `0.000` with D and E
   and no marker; sporttech.io a bare `0` with no D or E; Baku's Microplus
   print a D (`0.0`) and `0.000` with E blank; Antalya's EVAL print `0,000` in
   every column. Watch for a source that marks it differently.
2. **Europeans MAG senior all-around.** The title was decided in Competition I (medallists dated on
   qualification day), but the senior book prints no all-around ranking, only the medallists; the
   format says `NONE` for now (competition-models.md, open). The juniors' all-around final ranking is
   parsed (`parse_2026_european_championships.py`).
3. **Europeans files were built by hand** before the parsers existed and lack
   the newer `Birth Date` column; there is no parser to regenerate them.
4. **`SV` vs `DS1`** may be the same role (an apparatus supervisor) seen in
   different contexts; kept separate for now. Both are World Cups: Cottbus
   heads each panel with `DS1`, Baku with `SV`.
5. **Penalties attributed to an apparatus.** sporttech.io's export records CUB's
   team penalty against one routine (bib 338's parallel bars) and has fields
   for per-apparatus team penalties and individual all-around penalties; only
   the team-level total is modelled (`TeamResult.sjPenalty`). The 2026 Asian
   Championships WAG juniors print one against LBN's beam total (§4.3); it is
   folded into the team's `SJ Penalty`. Revisit if the site should show where a
   team penalty was taken.
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
8. **Hors concours results.** Varna's and Koper's books leave the hors concours athletes' scores out,
   so they are entries with no results. Szombathely's leaves its one (WAG KOVACS Regina, bib 224,
   on the beam start list only) off the entry list too, so she isn't written at all. Paris's six
   late French entries (§5.14) aren't marked hors concours, but their rows print no result either.
   Tashkent's seven (§5.18) are on the start lists only, like Szombathely's, so aren't written.
   Their scores would need another source (the FIG results system) and a way to keep them out of the ranks.
10. **Judges printed without a surname.** The 2026 African Championships WAG Superior Jury (senior
   and junior books) prints `Debbie` (RSA, judge number 2058) and `Rawan` (EGY, 4646) only. Rawan is written as ABOUSHOUSHA
   Rawan (EGY), the Cairo World Cup judge (a correction; the book gives no full name). Debbie isn't
   written, a judge needing a surname; add her if her surname is found.
9. **Plain `AIN`.** Cairo and Osijek print one `AIN` for both neutral groups, kept as printed
   (Osijek's entry list and entry counts keep the two groups apart, under two `AIN` headings).
   Those athletes link by FIG licence, but their Cairo entries form a third neutral
   group beside `AIN1`/`AIN2`. Revisit if the site groups results by country.
11. **World Gymnastics judge IDs.** Every judge has an ID in the World Gymnastics database
   (the African Championships WAG sheets print some as judge numbers). Backfill them, which would
   link a judge across meets despite spelling and federation differences (item 7), and replace the
   hand-checked federations of judges credited to a continental union (the 2026 Central American
   and Caribbean Games' nine, filled from other 2026 meets).
12. **Individual judges' marks.** The 2026 African Championships junior book prints every routine's
   E1–E5 marks and its penalty parts (ND, line, time, …) (§5.15). Nothing in the model holds them, so
   they are transcribed and checked but not written. Storing them would need columns on `SCORES`
   (or a file of their own) and fields on `Score`, joined to the panel's judges by function.
13. **A routine on a start list that no report prints.** 2026 South American Games MAG TORRES
   Sebastian (VEN, 77) is on the qualification vault start list and in no vault report (the book has
   no first-vault list for MAG, and he is in neither the team nor the all-around report). No row is
   written. The FIG results system may have his vault (or a DNS).
