# Competition API

Base path: `/api/competitions`

A competition's results, rebuilt as the official results print them: ranks, ties
and totals are copied as published, never recalculated. A competition's id comes
from its event's [EventDetailResponse](api-event.md#eventdetailresponse-object).

A competition is routines performed on a date ([data-model.md](../data-model.md) §3):
Competition I, which every entrant takes part in, the team final, the all-around final
or an apparatus final. Its standings are the rankings of its routines (§5). A title
decided in another competition's routines is shown with that competition, not as a
page of its own: the 2026 Asian Championships' and South American Games' team and
all-around titles, and the 2026 Asian Games' all-around title, are on Competition I.

Public, cached and revalidated like the [Event API](api-event.md)'s `GET`
endpoints. Responses are gzip-compressed when the client accepts it: a
championship qualification is about 280 KB of JSON, 28 KB compressed.

---

## Endpoints

### GET /api/competitions/{id}/results

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | Long | Competition ID |

**Responses**

| Status | Description |
|--------|-------------|
| 200 OK | Returns [CompetitionResultsResponse](#competitionresultsresponse-object) |
| 404 Not Found | No competition with the given ID |

---

## Data Objects

Fields marked nullable may be `null`; every field is always present.

### CompetitionResultsResponse Object

Which parts are filled depends on the competition:

| Competition | apparatus | allAround | teams | apparatusStandings |
|---|:-:|:-:|:-:|:-:|
| Competition I at a championship | every apparatus | ✓ | ✓ | |
| Team final | every apparatus | | ✓ | |
| All-Around final | every apparatus | ✓ | | |
| Apparatus final, or apparatus-format Competition I (World Cup) | one apparatus | | | |
| A split competition's part (US Championships' Day 1, Day 2) | every apparatus | ✓ | | |
| A split competition's combined row | | ✓ | | ✓ |

Where a competition's routines are ranked more than once for one title, `allAround` and
`teams` show the ranking that decided the most: the final placings over the
qualifying standings, the qualifying standings over a ranking that decides nothing.
The competition's `purposes` say which it is.

| Field | Type | Description |
|-------|------|-------------|
| event | Object | `{slug, title}` of the competition's event |
| competition | [CompetitionSummaryResponse](#competitionsummaryresponse-object) | The competition itself |
| apparatus | List | `{apparatus, scores}` for each apparatus with scores, in Olympic order (MAG: FX, PH, SR, VT, PB, HB; WAG: VT, UB, BB, FX); `scores` is a list of [ScoreRow](#scorerow-object) ranked as published, unranked rows (e.g. did not start) last |
| allAround | List | [AllAroundRow](#allaroundrow-object) objects ranked as published |
| teams | List | [TeamRow](#teamrow-object) objects ranked as published |
| apparatusStandings | List | `{apparatus, rows}`: a split competition's combined standings on each apparatus; each row is `{rank, bib, athlete, noc, club, total, parts}`, with `rank`, `bib`, `club` and `total` nullable, and `parts` the athlete's result on the apparatus in each part as `{part, score}` (for two vaults, their combination) |

### CompetitionSummaryResponse Object

| Field | Type | Description |
|-------|------|-------------|
| id | Long | Competition ID |
| slug | String | Unique within the event, discipline and age category (see [Names](#names-and-slugs)): `qualification`, `team-final`, `all-around-final`, `<apparatus>-final` (e.g. `beam-final`), `<apparatus>-qualification` at an apparatus-format meet, or from the name for a Competition I that qualified no one (`team-and-all-around-final`); an elimination round adds `-round-<n>`, a split competition's parts `-part-<n>` |
| name | String | The competition's name, from its rankings (see [Names](#names-and-slugs)), e.g. "Qualification", "Balance Beam Final", "Team and All-Around Final · Apparatus Qualification" |
| shortName | String | As briefly as a tile under an apparatus can put it: "Qualification" (a Competition I that qualified anyone), "Final", "AA Final", "Team Final"; with ", Part <n>" for a part |
| discipline | String | `MAG`, `WAG` or `MIX` |
| ageCategory | String | `SR`, `JR`, `JR16` or `JR17` |
| type | String | `C1` (Competition I, which every entrant takes part in), `C2` (all-around final), `C3` (an apparatus final) or `C4` (team final) |
| apparatus | String, nullable | The apparatus, for an apparatus final or apparatus-format Competition I |
| round | Integer, nullable | An elimination round within the competition, scores reset each round (Youth Olympic Games' mixed team final); `null` otherwise |
| part | Integer, nullable | The part of a split competition; `null` for an ordinary competition or a split competition's combined row |
| purposes | Object | `{team, allAround, apparatus}`: what the competition's rankings of each type are for, `QUALIFYING` (picks who goes to a later competition; Q/R/NR marks), `FINAL` (the title's final placings and medals) or `INFORMATIONAL` (decides nothing, e.g. qualification's single-vault list, a part's daily standings); each nullable, `null` where the competition has no ranking of that type. Where its routines are ranked more than once for a title, the purpose deciding the most |
| date | LocalDate | The day the competition was held; for a split competition's combined row, its first part's |
| endDate | LocalDate, nullable | For a split competition's combined row whose parts were held on different days, the last part's day; otherwise `null` |

#### Names and slugs

A competition is named from its rankings, so no competition is called a final it
wasn't, or a qualification it wasn't:

| Competition | Name | Slug |
|---|---|---|
| Team, all-around or apparatus final | "Team Final", "All-Around Final", "Balance Beam Final" | `team-final`, `all-around-final`, `beam-final` |
| Competition I with no final ranking (Worlds) | "Qualification"; at an apparatus-format meet "Vault Qualification" | `qualification`, `vault-qualification` |
| Competition I with final and qualifying rankings | The titles it decided, then what it qualified for: "Team and All-Around Final · Apparatus Qualification" (South American Games), "All-Around Final · Team and Apparatus Qualification" (Asian Games), "Team Final · All-Around and Apparatus Qualification" (Commonwealth Games) | `qualification` |
| Competition I with final rankings only | "Team and All-Around Final" (Oceania), "All-Around and Apparatus Final" (US Championships) | from the name: `team-and-all-around-final` |
| A part | Its whole competition's name, then ", Part <n>" | the whole's, then `-part-<n>` |

### ScoreRow Object

One athlete's result on one apparatus.

| Field | Type | Description |
|-------|------|-------------|
| rank | Integer, nullable | Placement as published. In a championship qualification, vault is ranked on the first vault |
| bib | String, nullable | Bib number |
| athlete | Object | `{id, surname, givenName}`; names in written form ("Blakely", "McDonald") |
| noc | String | The country the athlete competed for (IOC code) |
| club | String, nullable | The club the athlete entered for, where the entry list names one (national meets); `null` otherwise |
| routine | [Routine](#routine-object) | The routine; for vault, the first attempt |
| secondRoutine | [Routine](#routine-object), nullable | Vault's second attempt, when one was expected |
| combinedBonus | Double, nullable | A bonus on the combined two-vault result |
| total | Double, nullable | The result the apparatus is decided on: for two vaults, their published combination |
| qualificationRank | Integer, nullable | Placement in the ranking that decides the apparatus final |
| qualification | String, nullable | `Q`, `R1`–`R4` or `NR` |
| teamRole | String | What the score does for its team in the competition's team rankings: `COUNTING`, `DROPPED` (a team member's score left out of the team total) or `INDIVIDUAL` (no part of a ranked team: an athlete competing as an individual, a country with no team result, or a did-not-start with no role known). `COUNTING` where no team is ranked |

### Routine Object

| Field | Type | Description |
|-------|------|-------------|
| status | String | `COMPLETED`, `DNS`, `INVALID_VAULT` or `UNKNOWN` |
| difficulty | Double, nullable | D score |
| difficultyInquiry | boolean | The D score was under inquiry (printed with a leading `!`) |
| execution | Double, nullable | E score |
| bonus | Double, nullable | Bonus |
| bonusDetail | List, nullable | Itemized bonus, `[{bonus, description}]` (US Championships) |
| penalty | Double, nullable | Neutral deductions |
| sjPenalty | Double, nullable | Superior Jury penalty |
| score | Double, nullable | The routine's score |

### AllAroundRow Object

| Field | Type | Description |
|-------|------|-------------|
| rank | Integer, nullable | Placement as published |
| rankStatus | String | Why the result has a rank, or why it has none: `RANKED`, `INCOMPLETE` (a partial all-around, or a team short of an apparatus total), `NOC_LIMIT` (left out under the limit per country), `HORS_CONCOURS`, `DID_NOT_FINISH` or `UNPLACED` (no place published) |
| bib | String, nullable | Bib number |
| athlete | Object | `{id, surname, givenName}` |
| noc | String | IOC code |
| club | String, nullable | As on [ScoreRow](#scorerow-object) |
| total | Double, nullable | All-around total as published |
| sjPenalty | Double, nullable | Penalty on the result as a whole (negative), already deducted from `total` |
| qualification | String, nullable | Qualification to the all-around final, where the ranking qualifies to one |
| apparatusScores | Map | Score on each apparatus in this competition, keyed by apparatus code. For a split competition's combined row, the sum of the parts' scores, over the parts the athlete competed the apparatus in (one part's score alone when they skipped it in the other): the combined apparatus standings can't stand in, since vault's is the two-vault title, not the all-around's one vault a day |
| parts | List | For a split competition's combined row, the athlete's result in each part they took part in, as `{part, total, apparatusScores}`; otherwise empty |

### TeamRow Object

| Field | Type | Description |
|-------|------|-------------|
| rank | Integer, nullable | Placement as published |
| rankStatus | String | As on [AllAroundRow](#allaroundrow-object) |
| noc | String | IOC code |
| total | Double, nullable | Team total as published |
| sjPenalty | Double, nullable | Penalty on the team as a whole (negative), already deducted from `total`; the apparatus totals don't include it |
| qualification | String, nullable | Qualification to the team final, where the ranking qualifies to one |
| apparatusTotals | Map | Sum of the scores counting toward the team on each apparatus, keyed by apparatus code |
