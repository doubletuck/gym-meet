# Athlete API

Base path: `/api/athletes`

Athlete search, and an athlete's career: their best results, then every meet
they entered. Public, cached and revalidated like the [Event API](api-event.md)'s
`GET` endpoints.

---

## Endpoints

### GET /api/athletes?q=

Athletes whose name, or another spelling of it a source printed, contains every
word of `q`, ignoring case and word order: `nemour`, `Kaylia NEMOUR` and
`nem kay` all find Kaylia Nemour. Accents are matched as written. At most 50,
by surname then given name.

**Query Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| q | String | Required. Words to match; a blank `q` finds no one |

**Responses**

| Status | Description |
|--------|-------------|
| 200 OK | Returns a list of [AthleteSummaryResponse](#athletesummaryresponse-object) |
| 400 Bad Request | `q` is missing |

### GET /api/athletes/{id}

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | Long | Athlete ID |

**Responses**

| Status | Description |
|--------|-------------|
| 200 OK | Returns [AthleteResponse](#athleteresponse-object) |
| 404 Not Found | No athlete with the given ID |

---

## Data Objects

Fields marked nullable may be `null`; every field is always present.

### AthleteSummaryResponse Object

| Field | Type | Description |
|-------|------|-------------|
| id | Long | Athlete ID |
| surname | String | |
| givenName | String | |
| discipline | String | `MAG` or `WAG` |
| noc | String, nullable | The country of their most recent entry (IOC code) |

### AthleteResponse Object

| Field | Type | Description |
|-------|------|-------------|
| id | Long | Athlete ID |
| surname | String | |
| givenName | String | |
| discipline | String | `MAG` or `WAG` |
| birthYear | Integer, nullable | |
| otherNames | List | Other spellings sources have printed, as `Given Surname` |
| personalBests | List | [PersonalBest](#personalbest-object) objects: their best routine score on each apparatus they have one on, in Olympic order |
| allAroundBest | Object, nullable | `{total, event, session}`: their best all-around total from a whole all-around in one session — a score on every apparatus. A split round's combined total (e.g. two days added together) and a partial total some national results print don't count. `event` and `session` as on [PersonalBest](#personalbest-object) |
| entries | List | [Entry](#entry-object) objects, one per meet entered, newest first |

### PersonalBest Object

The best routine on one apparatus. Each vault attempt is a routine of its own;
a routine that wasn't completed, or has no score, doesn't count. On a tie, the
earlier.

| Field | Type | Description |
|-------|------|-------------|
| apparatus | String | Apparatus code |
| score | Double | The routine's score |
| routine | [Routine](api-session.md#routine-object) | Its breakdown: D, E, bonus and penalties, as on the session's results |
| vault | Integer, nullable | Which of the session's two vaults it was, `1` or `2`; `null` on other apparatus, or where only one vault was expected |
| event | Object | `{slug, title, shortName, startDate, endDate}` of the meet; `shortName` is a few words for it, e.g. `Euros 2026` |
| session | [SessionSummaryResponse](api-session.md#sessionsummaryresponse-object) | Where it was scored, for a link to its results page |

### Entry Object

| Field | Type | Description |
|-------|------|-------------|
| event | Object | `{slug, title, shortName, startDate, endDate}`, as on [PersonalBest](#personalbest-object) |
| noc | String | The country they competed for (IOC code) |
| club | String, nullable | The club they entered for, where the entry list names one (national meets) |
| entryStatus | String | `COMPETITOR`, `RESERVE`, `WITHDRAWN` or `HORS_CONCOURS`, as the entry list shows them; a reserve, withdrawn or hors concours athlete usually has no sessions |
| sessions | List | The sessions they have results in, in competition order (including a team final ranking the routines of a session they competed in, where their country's team is ranked), each `{session, allAround, team, scores, apparatusStandings}`: `session` a [SessionSummaryResponse](api-session.md#sessionsummaryresponse-object); `allAround` their `{rank, total, qualification}` in it, nullable; `team` the `{noc, rank, total, qualification}` of the team they competed for, where the session ranks teams (a team being their country's entry, as teams aren't rostered), nullable; `scores` their scores in Olympic order (empty in a final ranking another session's routines: they're listed under that session), each a [ScoreRow](api-session.md#scorerow-object) without `bib`, `athlete`, `noc`, `club` and `countsTowardTeam` but with `apparatus`; `apparatusStandings` for a split round's combined session, their `{apparatus, rank, total}` on each apparatus |
