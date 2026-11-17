# Session API

Base path: `/api/sessions`

A session's results, rebuilt as the official results print them: ranks, ties
and totals are copied as published, never recalculated. A session's id comes
from its event's [EventDetailResponse](api-event.md#eventdetailresponse-object).

Public, cached and revalidated like the [Event API](api-event.md)'s `GET`
endpoints. Responses are gzip-compressed when the client accepts it: a
championship qualification is about 280 KB of JSON, 28 KB compressed.

---

## Endpoints

### GET /api/sessions/{id}/results

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | Long | Session ID |

**Responses**

| Status | Description |
|--------|-------------|
| 200 OK | Returns [SessionResultsResponse](#sessionresultsresponse-object) |
| 404 Not Found | No session with the given ID |

---

## Data Objects

Fields marked nullable may be `null`; every field is always present.

### SessionResultsResponse Object

Which parts are filled depends on the round:

| Round | apparatus | allAround | teams | apparatusStandings |
|---|:-:|:-:|:-:|:-:|
| Championship qualification | every apparatus | ✓ | ✓ | |
| Team final | every apparatus | | ✓ | |
| All-around final | every apparatus | ✓ | | |
| Apparatus final, or apparatus-format qualification (World Cup) | one apparatus | | | |
| A split round's part (US Championships' Day 1, Day 2) | every apparatus | ✓ | | |
| A split round's combined session | | ✓ | | ✓ |

| Field | Type | Description |
|-------|------|-------------|
| event | Object | `{slug, title}` of the session's event |
| session | [SessionSummaryResponse](#sessionsummaryresponse-object) | The session itself |
| apparatus | List | `{apparatus, scores}` for each apparatus with scores, in Olympic order (MAG: FX, PH, SR, VT, PB, HB; WAG: VT, UB, BB, FX); `scores` is a list of [ScoreRow](#scorerow-object) ranked as published, unranked rows (e.g. did not start) last |
| allAround | List | [AllAroundRow](#allaroundrow-object) objects ranked as published |
| teams | List | [TeamRow](#teamrow-object) objects ranked as published |
| apparatusStandings | List | `{apparatus, rows}`: a split round's combined standings on each apparatus; each row is `{rank, bib, athlete, noc, club, total, parts}`, with `rank`, `bib`, `club` and `total` nullable, and `parts` the athlete's result on the apparatus in each part as `{part, score}` (for two vaults, their combination) |

### SessionSummaryResponse Object

| Field | Type | Description |
|-------|------|-------------|
| id | Long | Session ID |
| slug | String | Unique within the event, discipline and age category: `qualification`, `team-final`, `all-around-final`, `<apparatus>-final` (e.g. `beam-final`), `<apparatus>-qualification` at an apparatus-format meet; a split round's parts add `-part-<n>` |
| discipline | String | `MAG` or `WAG` |
| ageCategory | String | `SR`, `JR`, `JR16` or `JR17` |
| round | String | `QUAL`, `TEAM`, `AA` or `EVENT` |
| apparatus | String, nullable | The apparatus, for an apparatus final or apparatus-format qualification |
| part | Integer, nullable | The part of a split round; `null` for an ordinary session or a split round's combined session |
| date | LocalDate | The day the session was held; for a split round's combined session, its first part's |
| endDate | LocalDate, nullable | For a split round's combined session whose parts were held on different days, the last part's day; otherwise `null` |

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
| countsTowardTeam | boolean | `false` for a score dropped from its team's total |

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
| bib | String, nullable | Bib number |
| athlete | Object | `{id, surname, givenName}` |
| noc | String | IOC code |
| club | String, nullable | As on [ScoreRow](#scorerow-object) |
| total | Double, nullable | All-around total as published |
| qualification | String, nullable | Qualification to the all-around final, in qualification |
| apparatusScores | Map | Score on each apparatus in this session, keyed by apparatus code. For a split round's combined session, the sum of the parts' scores, over the parts the athlete competed the apparatus in (one part's score alone when they skipped it in the other): the combined apparatus standings can't stand in, since vault's is the two-vault title, not the all-around's one vault a day |
| parts | List | For a split round's combined session, the athlete's result in each part they took part in, as `{part, total, apparatusScores}`; otherwise empty |

### TeamRow Object

| Field | Type | Description |
|-------|------|-------------|
| rank | Integer, nullable | Placement as published |
| noc | String | IOC code |
| total | Double, nullable | Team total as published |
| qualification | String, nullable | Qualification to the team final, in qualification |
| apparatusTotals | Map | Sum of the scores counting toward the team on each apparatus, keyed by apparatus code |
