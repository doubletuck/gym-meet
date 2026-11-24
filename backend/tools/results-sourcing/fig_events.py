#!/usr/bin/env python3
"""Track World Gymnastics (FIG) MAG/WAG events and fetch their results books.

    python3 -I fig_events.py sync  --year 2026
    python3 -I fig_events.py fetch --year 2026 --folder 2026-ASIAN-GAMES 18608 \\
        [--book-url URL] [--meet "Asian Games"]
    python3 -I fig_events.py link  --year 2026 --meet "WAG European Championships" 18233 18234 \\
        [--folder 2026-EUROPEAN-CHAMPIONSHIPS] [--new]

`sync` reads the FIG calendar for the year and writes `data/<year>/<year>-FIG-EVENTS.csv`,
one row per MAG/WAG event, with its results book and the meet folder that holds it. It then
updates the meets list (`<year>-ARTISTIC-GYMNASTICS-MEETS.csv`): Folder, Status, and Date and
Location from FIG, which is the source of truth for its events. It reports results that are
published but not downloaded, downloaded but not parsed, or not linked to a meets-list row
(with the rows and folders that may be the same meet).

`fetch` downloads FIG events into a meet folder: the raw event record (`fig-<id>.json`),
the results book (`<id>-ResultsbookMedia.pdf`, or `--book-url` when the book is hosted
elsewhere), and draft `<FOLDER>-EVENT.csv` rows for any discipline and age category the
folder's EVENT.csv does not have yet. One meet folder can hold several FIG events: the
European Championships are four (MAG/WAG x SR/JR), the African Championships two (SR, JR).

`link` ties a meets-list row to FIG events and/or a meet folder without downloading anything;
`--new` adds the row from FIG when the meets list has none.

See backend/docs/results-sourcing.md.
"""
import argparse, csv, io, json, os, re, sys, time, urllib.parse, urllib.request

SITE = 'https://www.gymnastics.sport'
API = SITE + '/api'
DISCIPLINE_IDS = {'MAG': 2, 'WAG': 3}
USER_AGENT = 'Mozilla/5.0 (gym-meet results tracker)'
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))

# FIG level name -> EventLevel. Levels missing here are left blank in a drafted EVENT.csv,
# so parse-results asks for them. FIG's levels mix competition categories with its groups 1-4
# (kept in the FIG Group column); the EventLevel classification is still to be settled.
LEVELS = {
    'Olympic Games': 'OLYMPIC_GAMES',
    'Youth Olympic Games': 'YOUTH_OLYMPIC_GAMES',
    'World Championships': 'WORLD_CHAMPIONSHIPS',
    'World Cup': 'WORLD_CUP',
    'World Challenge Cup': 'WORLD_CHALLENGE_CUP',
    'Continental Championships': 'CONTINENTAL_CHAMPIONSHIPS',
    'Junior Continental Championships': 'CONTINENTAL_CHAMPIONSHIPS',
    'Continental Games': 'CONTINENTAL_GAMES',
    'Mediterranean Games': 'REGIONAL_GAMES',
    'Commonwealth Games': 'REGIONAL_GAMES',
    'Other Regional Championships / Games': 'REGIONAL_COMPETITION',
    'International Tournaments': 'INTERNATIONAL_TOURNAMENTS',
}
AGE_CATEGORIES = {'Senior': 'SR', 'Junior': 'JR'}
UNKNOWN_SUPPLIER = 'Not Known at the moment'

# Priority and Status follow the title, to read the plan at a glance
FIG_EVENTS_COLUMNS = ['FIG Event', 'Title', 'Priority', 'Status', 'Start Date', 'End Date', 'City', 'Country',
                      'Venue', 'Level', 'FIG Group', 'Categories', 'Apparatus Suppliers', 'FIG Status',
                      'Results Book', 'Digital Results', 'Folder', 'Meet']
EVENT_COLUMNS = ['Prefix', 'Slug', 'Title', 'Short Name', 'Disciplines', 'Age Category', 'Level',
                 'Start Date', 'End Date', 'City', 'Country', 'Venue', 'FIG Event Number',
                 'Apparatus Suppliers']
# Statuses sync derives from a meet folder, least advanced first; any other Status is set by
# hand and kept.
STATES = ['', 'Downloaded', 'Parsed']
DERIVED_STATUSES = set(STATES)
# The meets list's Event Type for a FIG level, where its wording differs.
EVENT_TYPES = {'International Tournaments': 'International Invitational'}

# ---------------------------------------------------------------- FIG site
def get(url, params=None, delay=0.2):
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
    time.sleep(delay)
    return body

def get_json(path, params=None):
    return json.loads(get(API + path, params))['data']

def detail_url(fig_id):
    return f'{SITE}/site/events/detail.php?id={fig_id}&type=sport#loaded'

def asset_url(asset_id):
    return f'{SITE}/asset.php?id=fidb_{asset_id}'

def digital_results_url(fig_id):
    return f'{SITE}/site/events/results.php?idEvent={fig_id}'

def fetch_calendar(year):
    """Every MAG/WAG event of the year: {id: (detail record, results record or None)}."""
    span = {'from': f'{year}-01-01', 'to': f'{year}-12-31'}
    ids, results = set(), {}
    for disc in DISCIPLINE_IDS.values():
        ids |= {e['id'] for e in get_json('/sportevents/', {**span, 'discipline': disc})}
        results |= {e['id']: e for e in get_json('/sporteventswithresult/', {**span, 'discipline': disc})}
    return {i: (get_json(f'/sportevents/{i}/'), results.get(i)) for i in sorted(ids | set(results))}

# ---------------------------------------------------------------- FIG record -> values
def asset_id(file_entry):
    m = re.search(r'fidb_(\d+)', file_entry.get('url') or '')
    return int(m.group(1)) if m else None

def media_book(detail, result=None):
    """Asset id of the event's results book. The Media edition is preferred: the results API's
    `resultbook` sometimes names the Delegation edition (2026 Youth Olympic Games)."""
    books = [f for f in detail.get('files') or [] if f['title'].lower().startswith('results book')]
    for f in books:
        if 'media' in f['title'].lower():
            return asset_id(f)
    if books:
        return asset_id(books[0])
    return (result or {}).get('resultbook')

def city_name(name):
    """FIG prints cities in capitals, sometimes with a region: 'BRISBANE, QLD', 'JESOLO (VE)'."""
    name = re.sub(r'\s*\(.*?\)', '', name.split(',')[0]).strip()
    small = {'de', 'da', 'del', 'do', 'dos', 'la', 'le', 'les', 'on', 'upon', 'sur', 'am', 'an', 'im'}
    parts = re.split(r'([ -])', name.lower())
    words = [p if p in ' -' or (i and p in small) else p[:1].upper() + p[1:] for i, p in enumerate(parts)]
    return ''.join(words)

def categories(detail):
    """[(discipline, age category)] for the MAG/WAG parts of the event, seniors first."""
    pairs = [(d['code'], AGE_CATEGORIES.get(a['name'], a['name'].upper()))
             for d in detail['disciplines'] if d['code'] in DISCIPLINE_IDS
             for a in d.get('agecategories') or []]
    order = list(AGE_CATEGORIES.values())
    return sorted(set(pairs), key=lambda p: (order.index(p[1]) if p[1] in order else 9, p[1], p[0]))

def suppliers(detail):
    return ', '.join(s['name'] for s in detail.get('apparatusSuppliers') or []
                     if s['name'] != UNKNOWN_SUPPLIER)

def level_name(detail):
    return (detail.get('level') or {}).get('name') or ''

def level_group(detail):
    group = (detail.get('level') or {}).get('group')
    return f'Group {group}' if group else ''

def draft_event_rows(folder, details):
    """EVENT.csv rows for a meet folder from its FIG event records. Title is FIG's and Short
    Name is left blank; both follow conventions parse-results checks with the user."""
    rows = {}
    for d in details:
        for disc, age in categories(d):
            prefix = f'{folder}-{disc}-{age}'
            if prefix in rows:
                raise SystemExit(f'{prefix}: FIG events {rows[prefix]["FIG Event Number"]} and {d["id"]} '
                                 'both cover it; draft EVENT.csv by hand')
            rows[prefix] = {
                'Prefix': prefix, 'Slug': prefix.lower(), 'Title': d['title'].strip(), 'Short Name': '',
                'Disciplines': disc, 'Age Category': age, 'Level': LEVELS.get(level_name(d), ''),
                'Start Date': d['startEvent'], 'End Date': d['endEvent'],
                'City': city_name(d['city']['name']), 'Country': d['city']['country']['code'],
                'Venue': (d.get('venue') or '').strip(), 'FIG Event Number': str(d['id']),
                'Apparatus Suppliers': suppliers(d)}
    order = list(AGE_CATEGORIES.values())
    return sorted(rows.values(), key=lambda r: (order.index(r['Age Category'])
                                                if r['Age Category'] in order else 9, r['Disciplines']))

# ---------------------------------------------------------------- meet folders
def year_dir(year):
    return os.path.join(REPO, 'data', str(year))

def meet_folders(year):
    root = year_dir(year)
    return sorted(f for f in os.listdir(root) if os.path.isdir(os.path.join(root, f)))

def folder_fig_ids(path):
    """FIG events a meet folder holds: from EVENT.csv, fig-<id>.json and <id>-*.pdf names."""
    ids = set()
    for name in os.listdir(path):
        if m := re.fullmatch(r'fig-(\d+)\.json', name):
            ids.add(int(m.group(1)))
        elif m := re.match(r'(\d{5,6})-.*\.pdf$', name, re.I):
            ids.add(int(m.group(1)))
        elif name.endswith('-EVENT.csv'):
            with open(os.path.join(path, name), encoding='utf-8', newline='') as f:
                for r in csv.DictReader(f):
                    ids |= {int(n) for n in re.findall(r'\d+', r.get('FIG Event Number') or '')}
    return ids

def folder_state(path):
    names = os.listdir(path) if os.path.isdir(path) else []
    if any(n.endswith('-IMPORT.json') for n in names):
        return 'Parsed'
    if any(n.lower().endswith('.pdf') for n in names):
        return 'Downloaded'
    return ''

def read_event_rows(path):
    rows = []
    for name in sorted(os.listdir(path)) if os.path.isdir(path) else []:
        if name.endswith('-EVENT.csv'):
            with open(os.path.join(path, name), encoding='utf-8', newline='') as f:
                rows += list(csv.DictReader(f))
    return rows

def event_state(path, fig_id):
    """How far one FIG event in a meet folder has got. Parsed: every EVENT.csv row for it has
    its IMPORT.json. Downloaded: a PDF named for it, or (in folders whose PDFs carry no FIG id)
    any PDF, or some of its rows parsed."""
    names = os.listdir(path) if os.path.isdir(path) else []
    prefixes = [r['Prefix'] for r in read_event_rows(path)
                if str(fig_id) in re.findall(r'\d+', r.get('FIG Event Number') or '')]
    parsed = [p for p in prefixes if f'{p}-IMPORT.json' in names]
    if prefixes and len(parsed) == len(prefixes):
        return 'Parsed'
    pdfs = [n for n in names if n.lower().endswith('.pdf')]
    if parsed or any(n.startswith(f'{fig_id}-') for n in pdfs):
        return 'Downloaded'
    if pdfs and not any(re.match(r'\d{5,6}-', n) for n in pdfs):
        return 'Downloaded'
    return ''

def least(states):
    return min(states, key=STATES.index) if states else ''

def fig_index(year):
    """{FIG id: folder} over every meet folder of the year."""
    index = {}
    for folder in meet_folders(year):
        for i in folder_fig_ids(os.path.join(year_dir(year), folder)):
            index.setdefault(i, folder)
    return index

# ---------------------------------------------------------------- meets list
def meets_path(year):
    return os.path.join(year_dir(year), f'{year}-ARTISTIC-GYMNASTICS-MEETS.csv')

def read_csv(path):
    with open(path, encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    return rows[0], [dict(zip(rows[0], r + [''] * (len(rows[0]) - len(r)))) for r in rows[1:]]

def write_csv(path, header, rows):
    out = io.StringIO()
    w = csv.writer(out, lineterminator='\n')
    w.writerow(header)
    w.writerows([r.get(c, '') for c in header] for r in rows)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(out.getvalue())

def meets_header(header):
    """The meets list's column for FIG event links once had no header; it is 'FIG Event'.
    'Folder' names the meet folder under data/<year>/."""
    header = ['FIG Event' if not c and i == 9 else c for i, c in enumerate(header)]
    return header if 'Folder' in header else header + ['Folder']

def read_meets(year):
    header, rows = read_csv(meets_path(year))
    new = meets_header(header)
    return new, [{n: r.get(o, '') for o, n in zip(header + ['Folder'], new)} for r in rows]

def row_fig_ids(row):
    return {int(i) for i in re.findall(r'[?&]id=(\d+)', row.get('FIG Event', ''))}

def row_assets(row):
    return {int(i) for i in re.findall(r'fidb_(\d+)', row.get('Results', ''))}

def row_state(row, year):
    """The least advanced of the row's FIG events in its folder; the folder's own state for a
    row with no FIG events."""
    path = os.path.join(year_dir(year), row['Folder'])
    ids = row_fig_ids(row)
    return least([event_state(path, i) for i in ids]) if ids else folder_state(path)

def update_meets(rows, index, year, calendar=None):
    """Fill Folder from the row's FIG events; take Date (earliest start) and, when the row's
    city is not FIG's, Location from FIG; then Status from the folder's contents.
    Returns a list of change descriptions."""
    changes = []
    def change(r, column, value):
        if value != r.get(column, ''):
            changes.append(f'{r["Event"]}: {column} {r.get(column) or "(blank)"} -> {value or "(blank)"}')
            r[column] = value
    for r in rows:
        if not r.get('Folder'):
            folders = {index[i] for i in row_fig_ids(r) if i in index}
            if len(folders) == 1:
                change(r, 'Folder', folders.pop())
        details = [calendar[i][0] for i in sorted(row_fig_ids(r)) if calendar and i in calendar]
        if details:
            change(r, 'Date', min(d['startEvent'] for d in details))
            location = r.get('Location', '').lower()
            if not any(fig_city_word(d) in location for d in details):
                change(r, 'Location', fig_location(details[0]))
        if r.get('Folder') and r.get('Status', '') in DERIVED_STATUSES:
            change(r, 'Status', row_state(r, year))
    return changes

def fig_city_word(detail):
    return city_name(detail['city']['name']).lower().split(' ')[0].split('-')[0]

def fig_location(detail):
    return f'{city_name(detail["city"]["name"])}, {detail["city"]["country"]["code"]}'

def new_meet_row(name, detail):
    """A meets-list row for a FIG event the list does not have."""
    return {'Date': detail['startEvent'], 'Event': name, 'Location': fig_location(detail),
            'Disciplines': ', '.join(f'{d} {a.title()}' for d, a in categories(detail)),
            'Event Type': EVENT_TYPES.get(level_name(detail), level_name(detail))}

def insert_meet(rows, row):
    """Unprioritised rows sit last, by date."""
    at = next((i for i, r in enumerate(rows) if not r.get('Priority') and r.get('Date', '') > row['Date']),
              len(rows))
    rows.insert(at, row)

def add_link(row, column, url):
    links = [u.strip() for u in row.get(column, '').split(',') if u.strip()]
    if url not in links:
        row[column] = ', '.join(links + [url])

# ---------------------------------------------------------------- commands
def fig_events_rows(year, calendar, index, meets):
    rows = []
    for fig_id, (d, result) in calendar.items():
        book = media_book(d, result)
        meet = next((m for m in meets if fig_id in row_fig_ids(m) or (book and book in row_assets(m))
                     or (m.get('Folder') and m['Folder'] == index.get(fig_id))), None)
        folder = index.get(fig_id, '')
        rows.append({
            'FIG Event': fig_id, 'Title': d['title'].strip(), 'Start Date': d['startEvent'],
            'End Date': d['endEvent'], 'City': city_name(d['city']['name']),
            'Country': d['city']['country']['code'], 'Venue': (d.get('venue') or '').strip(),
            'Level': level_name(d), 'FIG Group': level_group(d), 'Categories': ', '.join(f'{a} {b}' for a, b in categories(d)),
            'Apparatus Suppliers': suppliers(d), 'FIG Status': d.get('status', ''),
            'Results Book': asset_url(book) if book else '',
            'Digital Results': digital_results_url(fig_id) if (result or {}).get('digitalresult') else '',
            'Folder': folder, 'Meet': meet['Event'] if meet else '',
            'Priority': meet.get('Priority', '') if meet else '',
            'Status': fig_event_status(meet, event_state(os.path.join(year_dir(year), folder), fig_id)
                                       if folder else '')})
    return sorted(rows, key=lambda r: (r['Start Date'], r['FIG Event']))

def fig_event_status(meet, state):
    """A hand-set Status from the meets list, except Imported, which can only hold for an event
    that is parsed (the 2026 African Championships row is imported, its junior event is not)."""
    manual = meet.get('Status', '') if meet else ''
    if manual in DERIVED_STATUSES or (manual == 'Imported' and state != 'Parsed'):
        return state
    return manual

def overlaps(a, b, slack=3):
    from datetime import date, timedelta
    pad = timedelta(days=slack)
    return (date.fromisoformat(a['Start Date']) - pad <= date.fromisoformat(b['End Date'])
            and date.fromisoformat(b['Start Date']) - pad <= date.fromisoformat(a['End Date']))

def sibling_folders(fig_row, rows):
    """Folders holding another FIG event in the same city at the same time: this one may be
    part of that meet (a junior event beside the senior one)."""
    return sorted({r['Folder'] for r in rows if r['Folder'] and r['FIG Event'] != fig_row['FIG Event']
                   and r['City'] == fig_row['City'] and overlaps(r, fig_row)})

def candidates(fig_row, meets):
    """Meets-list rows that may be this FIG event: same city, starting within a week."""
    from datetime import date
    start = date.fromisoformat(fig_row['Start Date'])
    city = fig_row['City'].lower().split(' ')[0].split('-')[0]
    found = []
    for m in meets:
        try:
            days = abs((date.fromisoformat(m['Date']) - start).days)
        except ValueError:
            continue
        if days <= 7 and city and city in m.get('Location', '').lower():
            found.append(m)
    return found

def report(rows, meets):
    def line(r):
        has = 'book' if r['Results Book'] else 'digital only'
        return (f'  P{r["Priority"] or "-"} {r["FIG Event"]} {r["Start Date"]} {r["Title"]} '
                f'({r["Categories"]}; {has}){" -> " + r["Folder"] if r["Folder"] else ""}')
    has_results = [r for r in rows if r['Results Book'] or r['Digital Results']]
    sections = [
        ('Results published, not downloaded', [r for r in has_results if not r['Status'] and r['Meet']]),
        ('Not in the folder of a meet it may be part of',
         [r for r in rows if not r['Folder'] and sibling_folders(r, rows)]),
        ('Downloaded, not parsed', [r for r in rows if r['Status'] == 'Downloaded']),
        ('Results published, not linked to a meets-list row', [r for r in has_results if not r['Meet']]),
    ]
    for title, items in sections:
        print(f'\n{title} ({len(items)}):')
        for r in sorted(items, key=lambda r: (r['Priority'] or '9', r['Start Date'])):
            print(line(r))
            if not r['Folder']:
                for folder in sibling_folders(r, rows):
                    print(f'      part of {folder}?')
            if not r['Meet']:
                for m in candidates(r, meets):
                    print(f'      maybe: {m["Date"]} {m["Event"]} (P{m.get("Priority") or "-"})')

def cmd_sync(args):
    print(f'Reading the FIG calendar for {args.year}...', file=sys.stderr)
    calendar = fetch_calendar(args.year)
    index = fig_index(args.year)
    header, meets = read_meets(args.year)
    changes = update_meets(meets, index, args.year, calendar)
    write_csv(meets_path(args.year), header, meets)
    rows = fig_events_rows(args.year, calendar, index, meets)
    out = os.path.join(year_dir(args.year), f'{args.year}-FIG-EVENTS.csv')
    write_csv(out, FIG_EVENTS_COLUMNS, rows)
    print(f'{len(rows)} FIG events -> {os.path.relpath(out, REPO)}')
    print(f'\nMeets list changes ({len(changes)}):')
    for c in changes:
        print('  ' + c)
    report(rows, meets)

def download_pdf(url, path):
    if os.path.exists(path):
        print(f'  {os.path.basename(path)}: already present')
        return
    body = get(url)
    if not body.startswith(b'%PDF'):
        raise SystemExit(f'{url} did not return a PDF')
    with open(path, 'wb') as f:
        f.write(body)
    print(f'  {os.path.basename(path)}: {len(body) // 1024} KB')

def cmd_fetch(args):
    if args.book_url and len(args.ids) != 1:
        raise SystemExit('--book-url needs exactly one FIG event')
    path = os.path.join(year_dir(args.year), args.folder)
    os.makedirs(path, exist_ok=True)
    details, books = [], {}
    for fig_id in args.ids:
        d = get_json(f'/sportevents/{fig_id}/')
        details.append(d)
        with open(os.path.join(path, f'fig-{fig_id}.json'), 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
            f.write('\n')
        print(f'{fig_id} {d["title"].strip()}')
        if args.book_url:
            books[fig_id] = args.book_url
            name = f'{fig_id}-' + os.path.basename(urllib.parse.urlparse(args.book_url).path)
            download_pdf(args.book_url, os.path.join(path, name))
        elif book := media_book(d):
            books[fig_id] = asset_url(book)
            download_pdf(books[fig_id], os.path.join(path, f'{fig_id}-ResultsbookMedia.pdf'))
        else:
            print('  no results book on the FIG event page; pass --book-url if it is published elsewhere')

    draft_event_csv(os.path.join(path, f'{args.folder}-EVENT.csv'), args.folder, details)

    link_meet(args.year, args.meet, args.ids, args.folder, books)

def draft_event_csv(event_csv, folder, details):
    """Write draft rows for the disciplines and age categories EVENT.csv lacks. Existing rows
    are never changed; a FIG event that claims an existing row's prefix is reported."""
    header, existing = read_csv(event_csv) if os.path.exists(event_csv) else (EVENT_COLUMNS, [])
    have = {r['Prefix']: r for r in existing}
    new = []
    for r in draft_event_rows(folder, details):
        old = have.get(r['Prefix'])
        if old is None:
            new.append(r)
        elif r['FIG Event Number'] not in re.findall(r'\d+', old.get('FIG Event Number') or ''):
            print(f'  {r["Prefix"]}: already in EVENT.csv for FIG {old.get("FIG Event Number")}, but FIG lists '
                  f'it under {r["FIG Event Number"]} too; check the categories')
    name = os.path.basename(event_csv)
    if not new:
        print(f'{name}: no rows to add')
        return
    write_csv(event_csv, header, existing + new)
    blanks = sorted({c for r in new for c in EVENT_COLUMNS if not r[c]})
    print(f'{name}: drafted {", ".join(r["Prefix"] for r in new)}. Review Title, and Start/End Date '
          f'(FIG\'s span for the whole event); fill in: {", ".join(blanks) or "nothing"}')

def link_meet(year, meet, ids, folder, books):
    """Record FIG events, their results books and the folder on one meets-list row."""
    header, meets = read_meets(year)
    matches = ([m for m in meets if m['Event'] == meet] if meet
               else [m for m in meets if set(ids) & row_fig_ids(m) or (folder and m.get('Folder') == folder)])
    if len(matches) != 1:
        print(f'Meets list not updated: {len(matches)} rows match; pass --meet "<Event>"')
        return
    row = matches[0]
    if not folder:
        index = fig_index(year)
        folder = next((index[i] for i in ids if i in index), None)
    if folder:
        row['Folder'] = folder
    for fig_id in ids:
        add_link(row, 'FIG Event', detail_url(fig_id))
        if fig_id in books:
            add_link(row, 'Results', books[fig_id])
    if row.get('Folder') and row.get('Status', '') in DERIVED_STATUSES:
        row['Status'] = row_state(row, year)
    write_csv(meets_path(year), header, meets)
    print(f'Meets list: {row["Event"]} -> Folder {row.get("Folder") or "(none)"}, '
          f'Status {row.get("Status") or "(blank)"}')

def cmd_link(args):
    """Results books are recorded only when the row has no Results link yet: a row may cite
    another source on purpose (European Gymnastics, Swiss Timing)."""
    books = {}
    header, meets = read_meets(args.year)
    row = next((m for m in meets if m['Event'] == args.meet), None)
    details = {i: get_json(f'/sportevents/{i}/') for i in args.ids}
    if args.new:
        if row is not None:
            raise SystemExit(f'The meets list already has a row named "{args.meet}"')
        if not args.ids:
            raise SystemExit('--new needs the FIG event(s) to build the row from')
        row = new_meet_row(args.meet, min(details.values(), key=lambda d: d['startEvent']))
        insert_meet(meets, row)
        write_csv(meets_path(args.year), header, meets)
        print(f'Meets list: added {row["Date"]} {args.meet}')
    elif row is None:
        raise SystemExit(f'No meets-list row named "{args.meet}"; pass --new to add one')
    if not row.get('Results'):
        for fig_id, d in details.items():
            if book := media_book(d):
                books[fig_id] = asset_url(book)
    link_meet(args.year, args.meet, args.ids, args.folder, books)

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('sync', help='refresh <year>-FIG-EVENTS.csv and the meets list Status')
    s.add_argument('--year', type=int, required=True)
    f = sub.add_parser('fetch', help='download FIG events into a meet folder')
    f.add_argument('--year', type=int, required=True)
    f.add_argument('--folder', required=True, help='meet folder under data/<year>/, e.g. 2026-ASIAN-GAMES')
    f.add_argument('--book-url', help='results book hosted outside the FIG site')
    f.add_argument('--meet', help='Event name of the meets-list row, when the FIG id is not on it yet')
    f.add_argument('ids', nargs='+', type=int, metavar='FIG_ID')
    k = sub.add_parser('link', help='tie a meets-list row to FIG events and/or a meet folder')
    k.add_argument('--year', type=int, required=True)
    k.add_argument('--meet', required=True, help='Event name of the meets-list row')
    k.add_argument('--folder', help='meet folder under data/<year>/')
    k.add_argument('--new', action='store_true', help='add the row, from the FIG event, to the meets list')
    k.add_argument('ids', nargs='*', type=int, metavar='FIG_ID')
    args = p.parse_args(argv)
    {'sync': cmd_sync, 'fetch': cmd_fetch, 'link': cmd_link}[args.command](args)

if __name__ == '__main__':
    main()
