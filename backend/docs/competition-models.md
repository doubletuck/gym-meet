# Competition models (working draft)

A design palette for deciding how each way a competition is run should be stored and shown.
It lists every meet parsed so far, what its first session decided, and how the files store
it today. The rules aren't settled yet. Once they are, they move into
`instructions-results-parsing.md` §4.9 and `import-file-model.md`.

## 1. Terms

A meet's **first session** is the competition every entrant takes part in (what the books
usually call "Qualification"). For each title (team, all-around, each apparatus), it does one
of three things:

| Value | Meaning |
|---|---|
| **Qual** | It qualifies teams or athletes to a later round with its own routines, which decides the title. |
| **Final** | It decides the title itself. No later round has routines for that title. |
| **—** | The title isn't contested. |

Each title is exactly one of these, so Qual and Final are a toggle, with a third state for
titles that aren't held.

## 2. What each meet's first session decided

| Meet | Prefixes | Team | AA | Apparatus | Model |
|---|---|---|---|---|---|
| World Championships | MAG SR, WAG SR | Qual | Qual | Qual | A |
| European Championships | MAG SR | Qual | — | Qual | B |
| European Championships | WAG SR | Qual | Final | Qual | C |
| Asian Games | MAG SR, WAG SR | Qual | Final | Qual | C |
| European Championships | MAG JR | Final | Qual | Qual | D |
| Pan American Championships | MAG SR, WAG SR | Final | Qual | Qual | D |
| Mediterranean Games | MAG SR, WAG SR | Final | Qual | Qual | D |
| Commonwealth Games | MAG SR, WAG SR | Final | Qual | Qual | D |
| Central American and Caribbean Games | MAG SR, WAG SR | Final | Qual | Qual | D |
| European Championships | WAG JR | Final | Final | Qual | E |
| Pan American Championships | MAG JR, WAG JR | Final | Final | Qual | E |
| African Championships | MAG/WAG JR, SR | Final | Final | Qual | E |
| Asian Championships | MAG/WAG JR, SR | Final | Final | Qual | E |
| South American Games | MAG SR, WAG SR | Final | Final | Qual | E |
| Oceania Championships | MAG/WAG JR, SR | Final | Final | — | F |
| US Championships | MAG JR16, JR17, SR; WAG JR, SR | — | Final (two days combined) | Final (two days combined) | G |
| Apparatus World Cups (Antalya, Baku, Cairo, Cottbus, Osijek) | MAG SR, WAG SR | — | — | Qual | H |
| World Challenge Cups (Koper, Paris, Szombathely, Tashkent, Varna) | MAG SR, WAG SR | — | — | Qual | H |

Models:

- **A.** Every title is decided in a final.
- **B.** As A, but without an all-around title.
- **C.** The team title goes to a final. The all-around title is decided in the first session.
- **D.** The team title is decided in the first session. The all-around title goes to a final.
- **E.** The team and all-around titles are decided in the first session. Apparatus finals follow.
- **F.** One session decides everything. There are no apparatus titles and nothing follows it.
- **G.** The all-around is competed twice, on two days. The all-around and apparatus titles go
  to the combined totals. There is no team title.
- **H.** Apparatus titles only.

## 3. How each is stored today

Session codes are the `Round` values. "Routines" means the session holds `SCORES-*` files. A
summary "in AA (Scores Round QUAL)" means an AA session holding only standings that rank the
QUAL routines.

| Model | Meet | Routines in | Team title standings | AA title standings |
|---|---|---|---|---|
| A | Worlds | QUAL, TEAM, AA, EVENT | `SUMMARY-FINAL-TEAM` in TEAM (own routines) | `SUMMARY-FINAL-AA` in AA (own routines) |
| B | Europeans MAG SR | QUAL, TEAM, EVENT | `SUMMARY-FINAL-TEAM` in TEAM | — |
| C | Europeans WAG SR | QUAL, TEAM, EVENT | `SUMMARY-FINAL-TEAM` in TEAM | **`SUMMARY-QUAL-AA` in QUAL** |
| C | Asian Games | QUAL, TEAM, EVENT | `SUMMARY-FINAL-TEAM` in TEAM | **`SUMMARY-FINAL-AA` in AA (Scores Round QUAL)** |
| D | Europeans MAG JR | QUAL, AA, EVENT | `SUMMARY-QUAL-TEAM` in QUAL | none built (§6 item 2) |
| D | Pan Ams SR, Med Games, Commonwealth, CAC Games | QUAL, AA, EVENT | `SUMMARY-QUAL-TEAM` in QUAL | `SUMMARY-FINAL-AA` in AA (own routines) |
| E | Europeans WAG JR, Pan Ams JR, African | QUAL, EVENT | **`SUMMARY-QUAL-TEAM` in QUAL** | **`SUMMARY-QUAL-AA` in QUAL** |
| E | Asian Championships | QUAL, EVENT | **both**: `SUMMARY-QUAL-TEAM` in QUAL, and `SUMMARY-FINAL-TEAM` in TEAM (Scores Round QUAL) | **both**: `SUMMARY-QUAL-AA` in QUAL, and `SUMMARY-FINAL-AA` in AA (Scores Round QUAL) |
| E | South American Games | QUAL, EVENT | **`SUMMARY-FINAL-TEAM` in TEAM (Scores Round QUAL)** | **`SUMMARY-FINAL-AA` in AA (Scores Round QUAL)** |
| F | Oceania | AA | `SUMMARY-FINAL-TEAM` in TEAM (Scores Round AA) | `SUMMARY-FINAL-AA` in AA |
| G | US Championships | AA Part 1, AA Part 2 | — | `SUMMARY-FINAL-AA` in AA (Part 1 and 2 rows, plus combined rows with Part blank); `SUMMARY-FINAL-<APP>` for apparatus titles |
| H | World Cups | QUAL, EVENT | — | — |

The rows in bold show where the same model is stored in different ways.

## 4. How the all-around field is ranked when the first session decides the title

Rows for athletes who missed out under two-per-country, or who competed outside the
competition, appear in one of several ways.

| Meet | Model | What the summary holds | Two-per-country athletes | Q/R/NR markers |
|---|---|---|---|---|
| Europeans WAG SR | C | 91 rows, all ranked | not visible: whole field ranked as printed | none |
| Asian Games | C | MAG 23 rows / 5 unranked; WAG 38 / 14 | listed with totals, rank blank | none |
| Europeans WAG JR, Pan Ams JR, African | E | whole field, partial all-arounds unranked | not visible: whole field ranked as printed | none |
| Asian Championships | E | QUAL-AA: whole field ranked; FINAL-AA: only the 24 who counted | QUAL-AA: ranked, marked `NR`; FINAL-AA: left out | Q/R/NR on QUAL-AA, though no later AA round had routines |
| South American Games | E | MAG 23 rows / 6 unranked; WAG 26 / 10 | listed with totals, rank blank (WAG via RANK corrections) | none |
| Oceania | F | every all-arounder | none applied | none |

Other things seen:

- **Hors concours.** The Asian Championships MAG SR qualification lists two AUS guests with full
  all-around totals and no rank.
- **Partial all-arounds.** Every meet leaves them unranked, with a blank or partial total.
- **US Part 2 rows.** These are unranked because the book prints no per-day places on day 2.
  (Of 42 unranked MAG SR rows, 32 are full all-arounds.)

## 5. What the database can't tell apart

An `AllAroundResult` with a null rank can mean any of these:

1. A partial all-around (not every apparatus competed).
2. The athlete missed out under two-per-country.
3. Hors concours or a guest.
4. A day with no per-day places (US Part 2).
5. A DNF or withdrawal.

The site shows "–" for all of them and sorts them last. Nothing records which one it is.

## 6. Questions this raises

1. **Where do a first-session title's standings live?** Three answers exist today for model E:
   - in QUAL (African),
   - in both QUAL and a final-only session (Asian Championships),
   - in the final-only session only (South American Games).

   Models C and D have the same split: Europeans WAG SR AA versus Asian Games AA, and Pan Ams
   SR team versus South American Games team.
2. **Should the site show a "Team Final" / "All-Around Final" for a title decided in the first
   session?** If yes, every Final-state title gets a final-only session (`Scores Round QUAL`).
   If no, the standings stay in QUAL and the session's name has to say it decided the title.
3. **Two-per-country.** Should every Final-state all-around list the whole field? If so,
   athletes who missed out would be marked as such rather than given a blank rank, and when a
   book prints both, the whole-field rank would sit alongside the title rank.
4. **Q/R/NR on a Final-state title.** Should they be kept or dropped? So far only the Asian
   Championships print them.
5. **Models F and G** store the first session as `AA`, not `QUAL`, because nothing follows it.
   Is that still right once model E has a rule? Model F is model E without apparatus finals.

## 7. Proposed model

### 7.1 Why the current model can't say how a meet was run

`Session` stands for two things at once:

- **a competition**: where and when routines were performed (`Score` rows), and
- **a ranking**: standings over those routines (`TeamResult`, `AllAroundResult`,
  `ApparatusResult`).

When the first session decides a title, the two come apart, and each meet got its own
workaround:

- **Final-only sessions** (`scoresSession`, V7; SA Games, Asian Championships). These are
  sessions that were never competed, with dates and page addresses.
- **Qualification summaries that are really the title** (African, Europeans WAG). Nothing
  marks them as the title.
- **Single rounds stored as `AA`** (Oceania, US). The code was picked for the name the site
  shows.

As a result, the database can't say:

- where a title was decided;
- whether a title was not held or simply never parsed;
- why a rank is blank.

It also accepts Q/R/NR on standings that qualified nobody.

### 7.2 Changes

1. **Sessions are competitions only.** A session has a date, a part and routines.
   - Its `Round` says which competition it was, using FIG's numbering:

     | Code | Competition |
     |---|---|
     | `C1` (today `QUAL`) | Competition I, which every entrant competes in |
     | `AA` | Competition II, the all-around final |
     | `EVENT` | Competition III, the apparatus finals |
     | `TEAM` | Competition IV, the team final |

   - `C1` doesn't claim to be a qualification. Oceania's and the US's single round is `C1`, like
     everyone else's.
   - `scoresSession` goes away.
2. **A new `Ranking` entity holds standings.** It has:
   - a **type** (`TEAM`, `AA`, `APPARATUS` + apparatus): *what* is ranked;
   - a **purpose**: *what the standings are for*:
     - `QUALIFYING` picks who goes to a later round (Q/R/NR allowed);
     - `FINAL` gives the final placings and medals.

   It ranks the routines of one or more sessions (more than one for a mixed team, below).
   `TeamResult`, `AllAroundResult` and `ApparatusResult` belong to a ranking, not a session.
3. **The format is declared per event, discipline and age category** (`EventFormat`). These are
   your toggles, saying where each title was decided:
   - **Team:** `C1`, `FINAL` or `NONE`.
   - **All-around:** `C1`, `FINAL` or `NONE`.
   - **Apparatus:** `C1`, `FINAL` or `NONE`.

   `C1` means Competition I decided the title. `FINAL` means the title's own final decided it
   (Competition II, III or IV). `NONE` means it wasn't held. The importer checks the files
   against it:
   - a title declared with no `FINAL` ranking is an error (this catches Europeans MAG JR AA,
     never parsed);
   - a `FINAL` format with no final session is an error.
4. **A `standing` on each result explains a blank rank.** Ranks stay exactly as printed.

   | Value | Meaning |
   |---|---|
   | `RANKED` | has a rank |
   | `INCOMPLETE` | a partial all-around, or a team short of counting scores |
   | `NOC_LIMIT` | missed out under two-per-country (or a final's per-country limit) |
   | `HORS_CONCOURS` | a guest or out-of-competition entry |
   | `DID_NOT_FINISH` | withdrew partway |
   | `UNPLACED` | the source prints no places (US Part 2 rows) |
5. **Q/R/NR only on `QUALIFYING` rankings.** On a `FINAL` ranking, NR becomes the `NOC_LIMIT`
   standing.
6. **Teams become entities.** A `Team` has a name and an optional NOC, and `TeamMember` links it
   to participants.
   - Today a team is just an NOC string on `TeamResult`, with its members implied by
     `Participant.noc`. That breaks for Europeans' `WG1`/`WG2` and for **mixed teams**.
   - A mixed team has MAG and WAG members, so its ranking ranks routines from sessions of both
     disciplines. That's why a ranking can link to more than one session, and why its discipline
     can be `MIXED`.
   - Mixed teams may need more modelling: line-ups, and whether the team counts across
     disciplines. Leave them open until we look at a book, such as the Youth Olympic Games.
7. **Session names on the site come from the rankings.** For example:

   | Session | Name |
   |---|---|
   | Worlds' C1 | "Qualification" |
   | SA Games' C1 | "Team and All-Around Final · Apparatus Qualification" |
   | Oceania's C1 | "Team and All-Around Final" |

   No session is called a final it wasn't.

Apparatus standings inside a session stay on `Score` (`rank`, `qualificationRank`,
`qualificationResult`). An `APPARATUS` ranking is needed only where standings combine
sessions, as with the US two-day totals (today's `ApparatusResult`). Whether every apparatus
ranking should also become a `Ranking` row, for uniformity, is a later choice.

### 7.3 Entity diagram (proposed)

Bold relationships are new. `Event`, `Athlete`, `Club`, `Judge` and `ImportRun` are unchanged
and partly omitted.

```mermaid
erDiagram
    Event ||--o{ EventFormat : "declares"
    Event ||--o{ Session : "holds"
    Event ||--o{ Participant : "enters"
    Event ||--o{ Ranking : "publishes"
    Event ||--o{ Team : "enters"
    Athlete ||--o{ Participant : "is"
    Club |o--o{ Participant : "represents"
    Session ||--o{ Score : "contains"
    Session ||--o{ Judge : "judged by"
    Participant ||--o{ Score : "performs"
    Ranking }o--|{ Session : "ranks routines of"
    Team ||--|{ TeamMember : "has"
    Participant ||--o{ TeamMember : "is"
    Ranking ||--o{ TeamResult : "orders"
    Ranking ||--o{ AllAroundResult : "orders"
    Ranking ||--o{ ApparatusResult : "orders"
    Team ||--o{ TeamResult : "placed in"
    Participant ||--o{ AllAroundResult : "placed in"
    Participant ||--o{ ApparatusResult : "placed in"

    EventFormat {
        enum discipline "MAG or WAG"
        enum ageCategory
        enum teamDecidedIn "C1, FINAL, NONE"
        enum allAroundDecidedIn "C1, FINAL, NONE"
        enum apparatusDecidedIn "C1, FINAL, NONE"
    }
    Session {
        enum discipline
        enum ageCategory
        enum round "C1, TEAM, AA, EVENT"
        enum apparatus "EVENT only"
        int part "split rounds"
        date date
    }
    Ranking {
        enum discipline "MAG, WAG or MIXED"
        enum ageCategory
        enum type "TEAM, AA, APPARATUS"
        enum apparatus "APPARATUS only"
        enum purpose "QUALIFYING or FINAL"
    }
    Team {
        string name
        string noc "optional"
    }
    TeamMember {
        FK team
        FK participant
    }
    Score {
        enum apparatus
        decimal totalScore
        int rank
        enum qualificationResult
        enum teamScoreRole
    }
    TeamResult {
        decimal totalScore
        int rank
        enum standing
        enum qualificationResult "QUALIFYING only"
    }
    AllAroundResult {
        decimal totalScore
        int rank
        enum standing
        enum qualificationResult "QUALIFYING only"
    }
    ApparatusResult {
        enum apparatus
        decimal totalScore
        int rank
        enum standing
    }
    Participant {
        string bibNumber
        string noc
        enum entryStatus
    }
```

### 7.4 The models as sessions and rankings

| Model | Example | Sessions | Rankings |
|---|---|---|---|
| A | Worlds | C1, TEAM, AA, EVENT×n | C1: team and AA `QUALIFYING`. TEAM: team `FINAL`. AA: AA `FINAL` |
| C | Asian Games | C1, TEAM, EVENT×n | C1: team `QUALIFYING`, **AA `FINAL`**. TEAM: team `FINAL` |
| D | Commonwealth | C1, AA, EVENT×n | C1: **team `FINAL`**, AA `QUALIFYING`. AA: AA `FINAL` |
| E | SA Games, African | C1, EVENT×n | C1: **team `FINAL`, AA `FINAL`** |
| E | Asian Championships | C1, EVENT×n | C1: team and AA `FINAL`, possibly also `QUALIFYING` (§7.6, question 2) |
| F | Oceania | C1 | C1: team `FINAL`, AA `FINAL` |
| G | US | C1 part 1, C1 part 2, C1 | C1 parts: AA per day. C1 whole: AA `FINAL`, apparatus `FINAL` (combined) |
| H | World Cups | C1, EVENT×n | none beyond the scores' own ranks |

### 7.5 Files

- **`SUMMARY-QUAL-<X>` and `SUMMARY-FINAL-<X>`.** These map to `QUALIFYING` and `FINAL`
  rankings. On a FINAL summary, `Round` names the session whose routines it ranks, which
  replaces `Scores Round`.
- **A new `Standing` column.** It's blank when the row is ranked.
- **`EVENT.csv`** gains `Team Format`, `AA Format` and `Apparatus Format`.
- **A `Team` column** (team name) on summaries and scores. It's needed only where a team isn't
  simply the NOC, such as mixed teams.
- **Re-shaping existing files:**
  - title-deciding `SUMMARY-QUAL-*` become `SUMMARY-FINAL-*` with `Round` `C1` (African,
    Pan Ams, Europeans, Commonwealth, Mediterranean Games, CAC Games);
  - Oceania and US `AA` become `C1`;
  - `QUAL` becomes `C1` everywhere.

### 7.6 Open questions

1. **Format values.** Are `C1` / `FINAL` / `NONE` right, or do you want other wording?
2. **Asian Championships.** It printed two AA rankings over the same routines:
   - a qualifying one, ranking the whole field with Q/NR marking the 24 who count;
   - a final one, with only those 24 and the medals.

   Should we store both, or only the final one with `NOC_LIMIT` standings for those left out?
3. **Mixed teams.** Should we model them once we see a book?
4. **Apparatus rankings.** Should every apparatus ranking become a `Ranking` row, or only
   combined ones?
