# Ranking API

Base path: `/api/rankings`

The results of a ranking with no competition of its own in its division, shown as a page of its
own. So far the only kind is a mixed team's qualification (the 2026 Youth Olympic Games): it has no
routines of its own, and ranks each NOC's best men's and women's Competition I scores. A ranking's id
comes from its event's [EventDetailResponse](api-event.md#eventdetailresponse-object) (a division's
`rankings`). A competition's own rankings are read with its results
([Competition API](api-competition.md)).

Public, cached and revalidated like the [Event API](api-event.md)'s `GET` endpoints.

---

## Endpoints

### GET /api/rankings/{id}/results

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | Long | Ranking ID |

**Responses**

| Status | Description |
|--------|-------------|
| 200 OK | Returns [RankingResultsResponse](#rankingresultsresponse-object) |
| 404 Not Found | No such ranking, or one that is a competition's own (read it with the competition's results) |

---

## Data Objects

Fields marked nullable may be `null`; every field is always present.

### RankingResultsResponse Object

| Field | Type | Description |
|-------|------|-------------|
| event | Object | `{slug, title}` of the ranking's event |
| ranking | [RankingSummaryResponse](#rankingsummaryresponse-object) | The ranking itself |
| teams | List | [TeamRow](api-competition.md#teamrow-object) objects ranked as published; a mixed team's apparatus totals are its best score on each discipline's apparatus |
| apparatus | List | `{discipline, apparatus, scores}`, as on a competition's results: the scores counting toward the teams, from the competitions ranked, each discipline's apparatus in Olympic order (the men's, then the women's). Each [ScoreRow](api-competition.md#scorerow-object) has no `rank` (its placing belongs to its own competition) and `teamRole` `COUNTING` |

### RankingSummaryResponse Object

| Field | Type | Description |
|-------|------|-------------|
| id | Long | Ranking ID |
| slug | String | `qualification` for a qualifying ranking, `final` otherwise; unique within the event, discipline and age category, with its competitions' slugs |
| name | String | "Qualification" or "Final" |
| discipline | String | `MIX` so far |
| ageCategory | String | `SR`, `JR`, `JR16` or `JR17` |
| type | String | `TEAM` so far |
| purpose | String | `QUALIFYING`, `FINAL` or `INFORMATIONAL` |
| date | LocalDate | The first day of the competitions it ranks (the men's Competition I, 7 November) |
| endDate | LocalDate, nullable | Their last day, when later (the women's, 8 November); otherwise `null` |
