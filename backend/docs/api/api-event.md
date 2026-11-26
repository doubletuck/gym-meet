# Event API

Base path: `/api/events`

Gymnastics competitions, where `Event` is the named competition (e.g.
"54th Artistic Gymnastics World Championships"). An `Event` is the primary
record to which `Participant`s and `Competition`s are related. Its results are
read through the [Competition API](api-competition.md).

The `GET` endpoints are public. Their responses may be cached for 5 minutes
(`Cache-Control: max-age=300, public`) and carry an `ETag`, so a client
revalidating a cached response gets `304 Not Modified` when nothing has
changed. The `POST`, `PUT` and `DELETE` endpoints require a login; without one
they return `401 Unauthorized`.

The live OpenAPI description is served at `/v3/api-docs` (browsable at
`/swagger-ui.html`).

---

## Endpoints

### GET /api/events

Lists events, newest first, each with the disciplines and age categories it has
results for.

**Query Parameters**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| year | int | No | Only events starting or ending in this year |
| level | String | No | Only events of this `EventLevel` code (e.g. `WORLD_CHAMPIONSHIPS`) |
| discipline | String | No | Only events with results in this discipline (`MAG` or `WAG`) |

**Responses**

| Status | Description |
|--------|-------------|
| 200 OK | A list of [EventSummaryResponse](#eventsummaryresponse-object) objects |

---

### GET /api/events/{slug}

Returns an event and its competitions, grouped by discipline and age category.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| slug | String | The event's slug, e.g. `2026-world-championships` |

**Responses**

| Status | Description |
|--------|-------------|
| 200 OK | Event found; returns [EventDetailResponse](#eventdetailresponse-object) |
| 404 Not Found | No event with the given slug |

---

### POST /api/events

Creates a new event. Requires a login.

**Request Body** — [EventRequest](#eventrequest-object) (JSON)

**Validation**

- The `slug` must be unique across events.
- When present, the `figEventNumber` must be unique across events.
- The pair `title` + `startDate` must be unique.

**Responses**

| Status | Description |
|--------|-------------|
| 201 Created | Event created; returns the new [EventResponse](#eventresponse-object) |
| 401 Unauthorized | Not logged in |
| 409 Conflict | An event with the same `slug`, `figEventNumber`, or `title` + `startDate` already exists |

---

### PUT /api/events/{id}

Updates an existing event. Requires a login. Replaces `figEventNumber`,
`slug`, `title`, `shortName`, `startDate`, `endDate`, `city`, `countryCode`, `venue`,
`apparatusSuppliers`, and `level`.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | Long | Event ID |

**Request Body** — [EventRequest](#eventrequest-object) (JSON)

**Validation**

- Same duplicate checks as create: the update is rejected if it would make this
  event's `slug`, `figEventNumber`, or `title` + `startDate` match a
  *different* existing event.

**Responses**

| Status | Description |
|--------|-------------|
| 200 OK | Event updated; returns the updated [EventResponse](#eventresponse-object) |
| 401 Unauthorized | Not logged in |
| 404 Not Found | No event with the given ID |
| 409 Conflict | The update would duplicate another existing event's `slug`, `figEventNumber`, or `title` + `startDate` |

---

### DELETE /api/events/{id}

Deletes an event by ID. Requires a login.

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | Long | Event ID |

**Responses**

| Status | Description |
|--------|-------------|
| 204 No Content | Event deleted |
| 401 Unauthorized | Not logged in |
| 404 Not Found | No event with the given ID |
| 409 Conflict | The event still has dependent `Competition` or `Participant` records and cannot be deleted |

---

## Data Objects

### EventSummaryResponse Object

Returned by `GET /api/events`.

| Field | Type | Description |
|-------|------|-------------|
| slug | String | The event's name in addresses, e.g. `2026-world-championships` |
| title | String | Event name |
| startDate | LocalDate | First day of competition (ISO 8601) |
| endDate | LocalDate | Last day of competition (ISO 8601) |
| city | String | Host city |
| countryCode | String | Host country as a 3-character IOC code (e.g. `NED`) |
| level | String | Competitive tier code (e.g. `WORLD_CHAMPIONSHIPS`) |
| divisions | List | `{discipline, ageCategory}` for each discipline and age category with results, e.g. `{"discipline": "WAG", "ageCategory": "SR"}` |

### EventDetailResponse Object

Returned by `GET /api/events/{slug}`. The fields of
[EventSummaryResponse](#eventsummaryresponse-object), plus:

| Field | Type | Description |
|-------|------|-------------|
| venue | String | Venue or arena name, or `null` |
| figEventNumber | String | FIG-assigned event code, or `null` |
| apparatusSuppliers | String | Equipment manufacturer(s), or `null` |
| divisions | List | `{discipline, ageCategory, rankings, competitions}`, where `rankings` lists [RankingSummaryResponse](api-ranking.md#rankingsummaryresponse-object) objects for the division's rankings with no competition of their own (a mixed team's qualification, which ranks the men's and women's Competition I), held before its competitions, and `competitions` lists [CompetitionSummaryResponse](api-competition.md#competitionsummaryresponse-object) objects in the order they're held: Competition I, team final, all-around final, apparatus finals, apparatus in Olympic order, then elimination rounds, and a split competition's combined row before its parts, since it holds the result the competition is decided on |

**Example** (abridged)

```json
{
  "slug": "2026-world-championships",
  "title": "54th Artistic Gymnastics World Championships",
  "startDate": "2026-10-17",
  "endDate": "2026-10-25",
  "city": "Rotterdam",
  "countryCode": "NED",
  "venue": "Rotterdam Ahoy",
  "level": "WORLD_CHAMPIONSHIPS",
  "figEventNumber": "17247",
  "apparatusSuppliers": "Spieth",
  "divisions": [
    {
      "discipline": "WAG",
      "ageCategory": "SR",
      "rankings": [],
      "competitions": [
        {
          "id": 15, "slug": "qualification", "name": "Qualification", "shortName": "Qualification",
          "discipline": "WAG", "ageCategory": "SR", "type": "C1", "apparatus": null, "round": null, "part": null,
          "purposes": { "team": "QUALIFYING", "allAround": "QUALIFYING", "apparatus": "QUALIFYING" },
          "date": "2026-10-18", "endDate": null
        },
        {
          "id": 11, "slug": "beam-final", "name": "Balance Beam Final", "shortName": "Final",
          "discipline": "WAG", "ageCategory": "SR", "type": "C3", "apparatus": "BB", "round": null, "part": null,
          "purposes": { "team": null, "allAround": null, "apparatus": "FINAL" },
          "date": "2026-10-25", "endDate": null
        }
      ]
    }
  ]
}
```

### EventResponse Object

Returned by the `POST` and `PUT` endpoints.

| Field | Type | Description |
|-------|------|-------------|
| id | Long | Unique identifier. |
| figEventNumber | String | FIG-assigned event code, or `null` for non-FIG events |
| slug | String | The event's name in addresses |
| title | String | Event name |
| shortName | String | A few words for where the title won't fit, e.g. `Euros 2026` |
| startDate | LocalDate | First day of competition (ISO 8601, e.g. `2026-04-20`) |
| endDate | LocalDate | Last day of competition (ISO 8601, e.g. `2026-04-26`) |
| city | String | Host city |
| countryCode | String | Host country as a 3-character IOC code, as used by World Gymnastics (e.g. `GER`, not ISO-3166 `DEU`) |
| venue | String | Venue or arena name where the event is hosted and `null` if not known |
| apparatusSuppliers | String | Equipment manufacturer(s) supplying the apparatus, or `null` if not known |
| level | String | Competitive tier code of the event (e.g. `CONTINENTAL_CHAMPIONSHIPS`, `WORLD_CUP`) or `UNKNOWN` if not known |
| creationTimestamp | Instant | ISO 8601 UTC timestamp of record creation |
| lastUpdateTimestamp | Instant | ISO 8601 UTC timestamp of last update |

### EventRequest Object

Request body for `POST /api/events` and `PUT /api/events/{id}`.

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| figEventNumber | String | No | Max 20 characters | FIG-assigned event code, or no value for non-FIG events |
| slug | String | Yes | Max 100 characters; lowercase words separated by hyphens | The event's name in addresses |
| title | String | Yes | Max 200 characters | Event name |
| shortName | String | Yes | Max 40 characters | For where the title won't fit: the name readers use, then the year, e.g. `Euros 2026`, `Worlds 2026`, `Baku WC 2026`. The events of one competition share it |
| startDate | LocalDate | Yes | ISO 8601 | First day of competition |
| endDate | LocalDate | Yes | ISO 8601 | Last day of competition |
| city | String | Yes | Max 100 characters | Host city |
| countryCode | String | Yes | 3-character IOC code (e.g. `GER`, not ISO-3166 `DEU`) | Host country |
| venue | String | No | Max 150 characters | Venue/arena name |
| apparatusSuppliers | String | No | Max 100 characters | Equipment manufacturer(s) supplying the apparatus |
| level | String | Yes | `EventLevel` enum code | Competitive tier code of the event (e.g. `CONTINENTAL_CHAMPIONSHIPS`, `WORLD_CUP`) or `UNKNOWN` if not known |

**Example**

```json
{
  "figEventNumber": "FIG-2026-EURO",
  "slug": "2026-european-championships",
  "title": "2026 European Championships",
  "shortName": "Euros 2026",
  "startDate": "2026-04-20",
  "endDate": "2026-04-26",
  "city": "Stuttgart",
  "countryCode": "GER",
  "venue": "Schleyerhalle",
  "apparatusSuppliers": "Spieth",
  "level": "CONTINENTAL_CHAMPIONSHIPS"
}
```
