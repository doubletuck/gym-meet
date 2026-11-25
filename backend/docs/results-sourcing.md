# Sourcing Results

How a meet goes from "on the calendar" to a folder that is ready for the `parse-results`
skill: which files track the meets, what the meet folder holds, and the
[`fig_events.py`](../tools/results-sourcing/fig_events.py) script that fills both from the
World Gymnastics (FIG) site. Turning the folder's PDFs into import files is
[instructions-results-parsing.md](instructions-results-parsing.md); loading them is
[import-process.md](import-process.md).

## The files

Everything lives under `data/<year>/` at the repository root.

| File | Written by | What it holds |
|---|---|---|
| `<year>-ARTISTIC-GYMNASTICS-MEETS.csv` | you, and the script for `Folder`, links and derived `Status` | The meets list: every MAG/WAG meet you might cover, FIG or not, with its priority |
| `<year>-FIG-EVENTS.csv` | the script only (`sync`); never edit it | One row per FIG MAG/WAG event of the year, as the FIG site describes it |
| `<FOLDER>/` | the script (`fetch`), then `parse-results` | One meet: its results books, FIG records and import files |

### Meets list

The list is hand-curated: most meets on it (NCAA, national championships, invitationals)
are not on the FIG calendar. Columns:

| Column | Description |
|---|---|
| Date … Event Type | The meet. For a row linked to FIG events, FIG is the source of truth: `sync` sets Date to the earliest FIG start date, and Location to FIG's city and country when the row names another city |
| Priority | Your order of work, `1` first. Blank means not planned |
| Status | `Downloaded` and `Parsed` are set by the script from the folder, as the least advanced of the row's FIG events (see [Status of a FIG event](#status-of-a-fig-event)); for a row with no FIG events, `Parsed` when the folder has any `*-IMPORT.json`, `Downloaded` when it has any PDF. `Imported`, `Cancelled`, `No results` and any other value are set by hand, and the script never changes them |
| FIG Event | The FIG event page(s), comma separated. One meet can be several FIG events (senior and junior, or MAG and WAG) |
| Results | Where the results book(s) came from, comma separated |
| Folder | The meet folder under `data/<year>/`, e.g. `2026-ASIAN-GAMES` |

Set Status to `Imported` once the importer has loaded the meet; the script cannot see the
database.

### FIG events

Rewritten by every `sync`. Committing it makes `git diff` show what FIG changed since the
last sync: new results books, moved dates, cancellations.

| Column | Description |
|---|---|
| FIG Event | FIG's event id: the EVENT.csv `FIG Event Number` |
| Title | As FIG publishes it |
| Priority | From the meets-list row linked to this event |
| Status | The event's own state in its folder, or the meets-list Status when that was set by hand. `Imported` holds only for an event that is parsed: the 2026 African Championships junior event showed `Downloaded` beside the imported seniors until it was parsed. The hand-set Status covers the whole row, so a newly parsed event of an imported row shows `Imported` before the importer has loaded it |
| Start Date, End Date, City, Country, Venue | As FIG publishes them; the dates are the whole event's span |
| Level | FIG's level name (`Continental Games`, `World Challenge Cup`) |
| FIG Group | FIG's competition group (`Group 1` … `Group 4`). Where FIG gives none, a group set by hand is kept by `sync` (the 2026 Central American and Caribbean Games: `Group 4`) |
| Categories | Discipline and age category pairs, MAG/WAG only (`MAG SR, WAG JR`) |
| Apparatus Suppliers | Blank when FIG has none or says "Not Known" |
| FIG Status | FIG's status for the event (`approved`) |
| Results Book | The FIG asset link of the Media results book, when FIG has one |
| Digital Results | FIG's results page, when FIG publishes rankings online. These carry only ranks and totals, not enough to import |
| Folder | The meet folder holding this FIG event |
| Meet | The meets-list row linked to this event |

### Meet folder

`data/<year>/<FOLDER>/`, where the folder name is `<year>-<MEET-NAME>`: the same name prefixes
every import file.

| File | Description |
|---|---|
| `<figId>-ResultsbookMedia.pdf` | The FIG Media results book. A book from another site keeps its file name behind the FIG id: `18608-AG2026_GAR_RB_v1.pdf` |
| `fig-<figId>.json` | FIG's full record of the event (dates, venue, suppliers, categories, files), kept as the source of the EVENT.csv values |
| `<FOLDER>-EVENT.csv` | One row per discipline and age category ([import-file-model.md](import-file-model.md#eventcsv)). Drafted by `fetch`, finished by `parse-results` |

The script finds which FIG events a folder holds from all three: `fig-<id>.json` names, the
id in front of a PDF name, and EVENT.csv's `FIG Event Number`.

One meet folder often holds several FIG events. The European Championships are four, one per
discipline and age category; the African Championships are two, seniors and juniors. Fetch
each into the same folder: `fetch` adds the new event's rows to the existing EVENT.csv.
`sync` flags a FIG event that is in no folder but shares a city and dates (within three days)
with an event that is ("part of <FOLDER>?"). Some are not part of the meet: the 2026 Worlds
have a separate "Team registration" event with no results.

### Status of a FIG event

How far one FIG event has got in its folder:

- **Parsed**: every EVENT.csv row with its FIG number has its `<PREFIX>-IMPORT.json`.
- **Downloaded**: any of these holds:
  - a PDF named for it (`<id>-…pdf`);
  - some of its rows are parsed;
  - the folder has PDFs but none carries a FIG id (folders from before the naming, such as the Euros).
- **Blank**: nothing yet.

## The script

Run it from the repository root. It needs only Python 3 and network access to
`www.gymnastics.sport`.

```sh
python3 -I backend/tools/results-sourcing/fig_events.py sync  --year 2026
python3 -I backend/tools/results-sourcing/fig_events.py fetch --year 2026 --folder 2026-YOUTH-OLYMPIC-GAMES 18178
python3 -I backend/tools/results-sourcing/fig_events.py fetch --year 2026 --folder 2026-ASIAN-GAMES \
    --book-url https://agu-gymnastics.com/wp-content/uploads/2026/10/AG2026_GAR_RB_v1.pdf 18608
python3 -I backend/tools/results-sourcing/fig_events.py link  --year 2026 \
    --meet "WAG European Championships" --folder 2026-EUROPEAN-CHAMPIONSHIPS 18233 18234
```

**`sync`** reads the year's FIG calendar and:

1. rewrites `<year>-FIG-EVENTS.csv`;
2. fills an empty `Folder` in the meets list when the row's FIG events are all in one folder;
3. takes Date and Location from FIG for linked rows (see the meets list's columns);
4. sets a script-maintained `Status` from the folder;
5. reports these lists, each sorted by priority:
   - results published but not downloaded;
   - FIG events in no folder that may be part of a folder's meet;
   - downloaded but not parsed;
   - results published for events not linked to any meets-list row, each with the rows that may be the same meet (same city, starting within a week). Link the right row with `link`, or add one with `link --new`.

**`fetch <figId>… --folder <FOLDER>`** creates the folder if needed, then:

1. saves `fig-<id>.json` for each event;
2. downloads its Media results book. If the FIG page has none, it says so: pass `--book-url` for a book published elsewhere (one event at a time);
3. drafts `<FOLDER>-EVENT.csv` rows for the disciplines and age categories it lacks, without
   changing existing rows. When FIG lists an event under a category the folder already has
   from another FIG event, it reports it instead: FIG's categories are sometimes wrong (it
   lists the 2026 Junior African Championships as `WAG SR, MAG JR`);
4. records the FIG links, book link and folder on the meets-list row, found by FIG id or folder, or by `--meet "<Event>"`.

Files already present are not downloaded again.

**`link --meet "<Event>" [--folder <FOLDER>] [--new] [<figId>…]`** records FIG events and a
folder on a meets-list row without downloading. With `--new` it first adds the row, from the
first FIG event: Date, Event (the `--meet` name), Location, Disciplines and Event Type, placed
among the unprioritised rows by date. It adds a FIG results-book link only when the row has
no `Results` yet, since some rows cite another source on purpose. Without `--folder`, it uses
the folder that holds those FIG events, if any.

### The drafted EVENT.csv

| Column | Drafted from |
|---|---|
| Prefix, Slug | `<FOLDER>-<DISCIPLINE>-<AGE>` and its lowercase form |
| Title | FIG's title, as is. Check it against the book and the conventions of existing rows |
| Short Name | Left blank: it follows the naming convention in import-file-model.md |
| Disciplines, Age Category | FIG's MAG/WAG categories (`Senior` → `SR`, `Junior` → `JR`) |
| Level | Mapped from FIG's level where the mapping is settled (table below); otherwise blank |
| Start Date, End Date | FIG's span for the whole event. For multi-sport Games this is wider than the gymnastics days; take them from the book's competition schedule |
| City, Country, Venue, FIG Event Number, Apparatus Suppliers | FIG's values (city in title case without region) |

| FIG level | EventLevel |
|---|---|
| Olympic Games | `OLYMPIC_GAMES` |
| Youth Olympic Games | `YOUTH_OLYMPIC_GAMES` |
| World Championships | `WORLD_CHAMPIONSHIPS` |
| World Cup | `WORLD_CUP` |
| World Challenge Cup | `WORLD_CHALLENGE_CUP` |
| Continental Championships, Junior Continental Championships | `CONTINENTAL_CHAMPIONSHIPS` |
| Continental Games | `CONTINENTAL_GAMES` |
| Mediterranean Games, Commonwealth Games | `REGIONAL_GAMES` |
| Other Regional Championships / Games | `REGIONAL_COMPETITION` |
| International Tournaments | `INTERNATIONAL_TOURNAMENTS` |

Other FIG levels are left blank until a meet settles them; add the mapping to `LEVELS` in the
script when it does. FIG's levels mix its competition categories with its competition groups
(Groups 1–4, defined in the General Judges' Rules), which the FIG events list keeps in its
own column; how `EventLevel` classifies events is still to be settled.

### Tests

```sh
python3 -I -m unittest discover -s backend/tools/results-sourcing
```

They cover everything except the network calls.

## The FIG site

The script uses the JSON API behind the site's event search. It is undocumented and may
change; these calls are the ones the site's own pages make:

| Call | Returns |
|---|---|
| `/api/sportevents/?from=&to=&discipline=` | Events in a date range (`discipline`: 2 = MAG, 3 = WAG) |
| `/api/sporteventswithresult/?from=&to=&discipline=` | The same, limited to events with results, with `resultbook` (an asset id, sometimes the Delegation edition) and `digitalresult` |
| `/api/sportevents/<id>/` | One event: venue, level, suppliers, categories and its files, including `Results book (Media)` |
| `/asset.php?id=fidb_<asset>` | A file |

The "has results" flag in the search list is not reliable (some events with a book show none),
which is why `sync` uses the results call and the event's file list.
