"""Parse the 2026 Apparatus World Cup Cairo results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_apparatus_world_cup_cairo.py \\
        data/2026/2026-APPARATUS-WORLD-CUP-CAIRO/17939-ResultsbookMedia.pdf

Writes PARTICIPANTS / JUDGES / SCORES-QUAL-<APP> / SCORES-EVENT-<APP> CSVs and an IMPORT.json
per discipline next to the PDF, reading event metadata from the EVENT.csv already there and
applying the event's CORRECTIONS.csv. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.9).

The Egyptian Federation's media book: every page has text except the cover. Its reports carry
no codes, so the pages are named below and checked against their printed titles.
"""
import os, re, sys, unicodedata
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-APPARATUS-WORLD-CUP-CAIRO'
PREFIX = {disc: f'{EVENT_PREFIX}-{disc}-SR' for disc in ('MAG', 'WAG')}

BOOK = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err)
out = common.Output(OUT, corrections)

APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
# Competition Schedule (pp. 2-3): qualification day 1 MAG FX-PH-SR / WAG VT-UB, day 2 the rest;
# the finals split the same way. (The medallists page dates every final 5 April.)
DAY = {'MAG': {'FX': 1, 'PH': 1, 'SR': 1, 'VT': 2, 'PB': 2, 'HB': 2},
       'WAG': {'VT': 1, 'UB': 1, 'BB': 2, 'FX': 2}}
DATES = {'QUAL': {1: '2026-04-03', 2: '2026-04-04'}, 'EVENT': {1: '2026-04-05', 2: '2026-04-06'}}

# Physical pages (1-based): results table pages, then its tie-break report page.
TABLES = {
    ('WAG', 'QUAL', 'VT'): ([13, 14], 15), ('WAG', 'QUAL', 'UB'): ([16], 17),
    ('WAG', 'QUAL', 'BB'): ([18], 19), ('WAG', 'QUAL', 'FX'): ([20], 21),
    ('WAG', 'EVENT', 'VT'): ([24], None), ('WAG', 'EVENT', 'UB'): ([25], None),
    ('WAG', 'EVENT', 'BB'): ([26], None), ('WAG', 'EVENT', 'FX'): ([27], None),
    ('MAG', 'QUAL', 'FX'): ([35], 36), ('MAG', 'QUAL', 'PH'): ([37], 38),
    ('MAG', 'QUAL', 'SR'): ([39], None), ('MAG', 'QUAL', 'VT'): ([40, 41], 42),
    ('MAG', 'QUAL', 'PB'): ([43], 44), ('MAG', 'QUAL', 'HB'): ([45], 46),
    ('MAG', 'EVENT', 'FX'): ([49], 50), ('MAG', 'EVENT', 'PH'): ([51], 52),
    ('MAG', 'EVENT', 'SR'): ([53], None), ('MAG', 'EVENT', 'VT'): ([54], None),
    ('MAG', 'EVENT', 'PB'): ([55], None), ('MAG', 'EVENT', 'HB'): ([56], None),
}
ENTRY_PAGES = {'MAG': [28, 29], 'WAG': [6, 7]}
ENTRY_COUNTS_PAGE = 4
MEDALLISTS_PAGE = 5
JUDGES_PAGE = {('MAG', 'QUAL'): 34, ('WAG', 'QUAL'): 12, ('MAG', 'EVENT'): 48, ('WAG', 'EVENT'): 23}
# Qualification start lists (Elevien): per day, groups with one column per apparatus still
# rotating, in competition order; an apparatus's column is placed as on the day's first page.
START_PAGES = {('WAG', 1): [8, 9], ('WAG', 2): [10, 11], ('MAG', 1): [30, 31], ('MAG', 2): [32, 33]}
# On a qualification start list but with no result and no DNS row in the book.
NO_RESULT = {('MAG', 'HB'): {'154'}, ('WAG', 'VT'): {'200'}, ('WAG', 'UB'): {'193'}, ('WAG', 'BB'): {'200'},
             ('WAG', 'FX'): {'200', '234'}}
# Finals start lists: blocks of apparatus side by side, under icons.
FINALS_START = {'WAG': (22, [['VT', 'UB'], ['BB', 'FX']]), 'MAG': (47, [['FX', 'PH', 'SR'], ['VT', 'PB', 'HB']])}
APP_TITLE = {'FX': 'Floor Exercise', 'PH': 'Pommel Horse', 'SR': 'Still Rings', 'VT': 'Vault',
             'PB': 'Par[ae]llel Bars', 'HB': 'High Bar', 'UB': 'Uneven Bars', 'BB': 'Balance Beam'}

NUM = r'\d+\.\d{3}'

def page(n):
    return BOOK[n - 1]

def penalty(s):
    """Penalties are printed unsigned in their own column; written negative, as deducted."""
    return '-' + s if s else ''

def fold(s):
    """Names compare without accents, case or the hyphen the results drop (HAMAMES MOALLIC)."""
    s = unicodedata.normalize('NFKD', s)
    return re.sub(r'[^A-Z]', '', ''.join(c for c in s if not unicodedata.combining(c)).upper())

# ---------------------------------------------------------------- participants
PARTICIPANTS = {}   # disc -> bib -> participant row, as written (corrections applied)

def participants(disc):
    """Number of Entries by NOC (per discipline): `NOC SURNAME Given bib licence birth-year`."""
    ev = EVENTS[PREFIX[disc]]
    rows = []
    for n in ENTRY_PAGES[disc]:
        for l in page(n).split('\n'):
            m = re.match(r'^\s*([A-Z]{3})\s+(\S.*?)\s+(\d{3})\s+(\d+)\s+(\d{4})\s*$', l)
            if not m:
                if re.search(r'\s\d{3}\s+\d+\s+\d{4}\s*$', l):
                    err(f'{disc} participants p. {n}: unparsed {l!r}')
                continue
            noc, name, bib, licence, year = m.groups()
            surname, given = split_surname_first(name)
            rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                         'Event Start Date': ev['Start Date'], 'Order': len(rows) + 1, 'NOC Code': noc,
                         'Bib Number': bib, 'FIG License': licence, 'Name': name, 'Surname': surname,
                         'Given Name': given, 'Birth Year': year, 'Birth Date': ''})
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)
    by_bib = {}
    for r in rows:
        if r['Bib Number'] in by_bib:
            err(f'{disc} participants: bib {r["Bib Number"]} twice')
        if not r['Surname'] or not r['Given Name']:
            err(f'{disc} participants: bib {r["Bib Number"]} name {r["Name"]!r} doesn\'t split')
        by_bib[r['Bib Number']] = r
    PARTICIPANTS[disc] = by_bib

def check_entry_counts():
    """Number of Entries by NOC (p. 4): men and women per country, against the entry lists."""
    printed = {}
    for l in page(ENTRY_COUNTS_PAGE).split('\n'):
        m = re.match(r'^\s*([A-Z]{3})\s+(.*)$', l)
        if m and m.group(1) != 'NOC':
            cells = re.finditer(r'\d+', m.group(2))
            # Man and Women columns by position; the last number is the country's total
            counts = {'MAG': 0, 'WAG': 0}
            for c in list(cells)[:-1]:
                counts['MAG' if c.start() + len(m.group(0)) - len(m.group(2)) < 40 else 'WAG'] = int(c.group())
            printed[m.group(1)] = counts
        m = re.match(r'^\s*Total\s+(\d+)\s+(\d+)\s+(\d+)\s*$', l)
        if m:
            total = {'MAG': int(m.group(1)), 'WAG': int(m.group(2))}
    for disc in ('MAG', 'WAG'):
        counted = Counter(p['NOC Code'] for p in PARTICIPANTS[disc].values())
        book = {noc: c[disc] for noc, c in printed.items() if c[disc]}
        if dict(counted) != book or sum(counted.values()) != total[disc]:
            err(f'{disc} entries by NOC: list {dict(sorted(counted.items()))} != p. 4 {book}, total {total[disc]}')

def identify(disc, ctx, bib, name, noc):
    """A results row's printed `Given SURNAME` and NOC against the entry list."""
    p = PARTICIPANTS[disc].get(bib)
    if p is None:
        err(f'{ctx}: bib {bib} not on the entry list'); return None
    if fold(name) != fold(p['Given Name'] + p['Surname']):
        err(f'{ctx}: bib {bib} printed {name!r}, entered {p["Name"]!r}')
    if noc != p['NOC Code']:
        err(f'{ctx}: bib {bib} NOC {noc}, entered {p["NOC Code"]}')
    return p

# ---------------------------------------------------------------- results tables
# The NOC is the code before the values (a name can end in a three-letter surname: Qiyuan QIU)
ROW = r'^\s*(?:(\d+)\s+)?(\d{3})\s+(\S.*?)\s+([A-Z]{3})(?=\s{2,}(?:\d|DNS)|\s*$)(.*)$'
VALUES = r'^\s+((?:' + NUM + r'|DNS|DNF)(?:\s+(?:' + NUM + r'|DNS|DNF))*)\s*$'
HEADER_COLS = {'D-Score': 'D', 'E-Score': 'E', 'PEN': 'PEN', 'BONUS': 'B', 'Total': 'Total'}

def check_title(disc, rnd, app, n, tie):
    head = [l.strip() for l in page(n).split('\n')[:12] if l.strip()]
    want = [f'{disc} {"Qualifications" if rnd == "QUAL" else "Finals"}', APP_TITLE[app]]
    if (len(head) < 6 or head[4] != want[0] or not re.fullmatch(want[1], head[5])
            # The vault tie-break pages print no `Tie Break` heading, only their columns
            or ('Tie Break' in head or any('Heighst' in h for h in head)) != tie):
        err(f'{disc} {rnd} {app}: page {n} is not that report ({head[4:7]})')

def footer_date(n):
    m = re.search(r'^\s*(\d+) April 2026\s', page(n), re.M)
    return f'2026-04-{int(m.group(1)):02d}' if m else None

def by_position(header, values, ctx):
    """Non-vault rows: each value sits under its column's heading (PEN and BONUS are optional)."""
    cols = [(m.start(), HEADER_COLS[m.group()]) for m in re.finditer(r'\S+', header) if m.group() in HEADER_COLS]
    got = {}
    for start, value in values:
        x, col = min(cols, key=lambda c: abs(c[0] - start))
        if col in got or abs(x - start) > 4:
            err(f'{ctx}: value {value} not under a column'); return None
        got[col] = value
    return got

def vault_line(tokens, first):
    """A vault line: D E [PEN] Score [Bonus], plus the vault score on the first line. The
    optional values sit either side of the attempt's score, which is larger than both."""
    if first:
        tokens, total = tokens[:-1], tokens[-1]
    d, e, *rest = tokens
    if len(rest) == 3:
        pen, score, bonus = rest
    elif len(rest) == 2 and D(rest[0]) > D(rest[1]):
        pen, (score, bonus) = '', rest
    elif len(rest) == 2:
        (pen, score), bonus = rest, ''
    elif len(rest) == 1:
        pen, score, bonus = '', rest[0], ''
    else:
        return None
    v = dict(D=d, E=e, PEN=pen, Score=score, B=bonus)
    return (v, total) if first else v

def read_table(disc, rnd, app, pages):
    """Results pages -> rows: Rank, Bib, Name, NOC, Q, and a routine or, for vault, v1/v2 and the
    vault score (Total). Long names wrap their surname onto the next line."""
    ctx = f'{disc} {rnd} {app}'
    rows, header = [], None
    for n in pages:
        check_title(disc, rnd, app, n, False)
        if footer_date(n) != DATES[rnd][DAY[disc][app]]:
            err(f'{ctx}: page {n} dated {footer_date(n)}')
        last = None
        for l in page(n).split('\n'):
            if l.startswith('Rank'):
                header = l
                continue
            if app == 'VT' and (m := re.match(VALUES, l)):
                tokens = m.group(1).split()
                if not rows or 'v2' in rows[-1] or 'v1' not in rows[-1]:
                    err(f'{ctx} p. {n}: vault line out of place {l!r}'); continue
                r = rows[-1]
                if tokens == ['DNS', 'DNF'] and r['v1'] == 'DNS':
                    r['v2'] = 'DNS'
                elif r['v1'] != 'DNS' and (v := vault_line(tokens, False)):
                    r['v2'] = v
                else:
                    err(f'{ctx} p. {n}: bib {r["Bib"]}: vault 2 {l!r}')
                last = None
                continue
            m = re.match(ROW, l)
            if not m:
                if last and re.fullmatch(r"\s+[A-Z][A-Z' -]*", l):
                    last['Name'] += ' ' + l.strip()
                elif re.match(r'^\s*(?:\d+\s+)?\d{3}\s', l):
                    err(f'{ctx} p. {n}: unparsed {l!r}')
                last = None
                continue
            rank, bib, name, noc, rest = m.groups()
            q = re.search(r'\s(Q|R)\s*$', rest)
            if q:
                rest = rest[:q.start()]
            row = dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, Q=q.group(1) if q else '')
            offset = m.start(5)
            values = [(v.start() + offset, v.group()) for v in re.finditer(r'\S+', rest)]
            tokens = [v for _, v in values]
            if app == 'VT':
                if tokens in (['DNS', 'DNS'], ['DNS', 'DNF']):
                    # Neither vault done: `DNS DNS` over `DNS DNF`, or a single `DNS DNF` line
                    row |= dict(v1='DNS', Total='')
                    if tokens == ['DNS', 'DNF']:
                        row['v2'] = 'DNS'
                elif (parsed := vault_line(tokens, True)):
                    row['v1'], row['Total'] = parsed
                else:
                    err(f'{ctx} p. {n}: bib {bib}: vault 1 {l!r}'); continue
            elif tokens == ['DNS']:
                row |= dict(Status='DNS', D='', E='', B='', PEN='', Total='')
            else:
                got = by_position(header, values, f'{ctx} p. {n} bib {bib}')
                if got is None or not {'D', 'E', 'Total'} <= got.keys():
                    err(f'{ctx} p. {n}: bib {bib}: values {tokens}'); continue
                row |= dict(Status='COMPLETED', B='', PEN='') | got
            rows.append(row)
            last = row
    if any(app == 'VT' and 'v2' not in r for r in rows):
        err(f'{ctx}: a vault row without its second line')
    # Unranked rows (DNS) print the bib at the margin
    n_ids = sum(len(re.findall(r'^\s*(?:\d+\s+)?\d{3}\s+[A-Z]', page(n), re.M)) for n in pages)
    if n_ids != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_ids} rows')
    return rows

def read_tie_break(disc, rnd, app, n):
    """Tie Break: the tied athletes' rank and total, then the E score (vault: the higher vault)
    and, where E doesn't separate them, the D score; E and D print a leading zero."""
    check_title(disc, rnd, app, n, True)
    rows = []
    for l in page(n).split('\n'):
        m = re.match(r'^(\d+)\s+(\d{3})\s+(\S.*?)\s+([A-Z]{3})\s+(' + NUM + r')\s+(\d+\.\d{3})(?:\s+(\d+\.\d{3}))?\s*$', l)
        if m:
            rank, bib, name, noc, total, first, d = m.groups()
            rows.append(dict(Rank=rank, Bib=bib, Total=total, first=str(D(first)), D=str(D(d)) if d else None))
        elif re.match(r'^\d+\s+\d{3}\s', l):
            err(f'{disc} {rnd} {app} tie break: unparsed {l!r}')
    return rows

def check_rows(ctx, rows, app, wag):
    for r in rows:
        c = f'{ctx} bib {r["Bib"]}'
        if app != 'VT':
            if r['Status'] != 'DNS':
                checks.check_sum(c, r['Total'], r['D'], r['E'], r['B'], penalty(r['PEN']))
            continue
        if r['v1'] == 'DNS':
            if r['v2'] != 'DNS' or r['Rank'] or r['Total']:
                err(f'{c}: a DNS vault row with values')
            continue
        for n in (1, 2):
            v = r[f'v{n}']
            # MAG's bonus is inside the attempt's score; WAG's is the vault score's (Combined Bonus)
            checks.check_sum(f'{c} vault {n}', v['Score'], v['D'], v['E'], '' if wag else v['B'], penalty(v['PEN']))
        if wag and r['v1']['B']:
            err(f'{c}: a bonus on vault 1')
        checks.check_vault_average(c, r['v1']['Score'], r['v2']['Score'], r['v2']['B'] if wag else '', r['Total'])
    checks.check_rank_order(ctx, rows)

def check_tie_break(ctx, rows, tie_rows, app):
    """The tie-break page lists every group of equal totals, with the table's ranks; the athlete
    ranked higher has the higher E score (vault: the higher vault), else the higher D score."""
    by_bib = {r['Bib']: r for r in rows}
    groups = defaultdict(list)
    for r in rows:
        if r['Rank']:
            groups[r['Total']].append(r['Bib'])
    tied = {b for bibs in groups.values() if len(bibs) > 1 for b in bibs}
    if {t['Bib'] for t in tie_rows} != tied:
        err(f'{ctx} tie break: lists {sorted(t["Bib"] for t in tie_rows)}, tied {sorted(tied)}')
    for t in tie_rows:
        r = by_bib.get(t['Bib'])
        if r is None:
            continue
        first = max(D(r['v1']['Score']), D(r['v2']['Score'])) if app == 'VT' else D(r['E'])
        if (t['Rank'], t['Total']) != (r['Rank'], r['Total']) or D(t['first']) != first or \
                (t['D'] is not None and D(t['D']) != D(r['D'])):
            err(f'{ctx} tie break: bib {t["Bib"]} {t} differs from the table')
    for bibs in groups.values():
        key = lambda b: (D(by_bib[b]['Total']), max(D(by_bib[b]['v1']['Score']), D(by_bib[b]['v2']['Score']))
                         if app == 'VT' else D(by_bib[b]['E']), D(by_bib[b].get('D', '0')))
        ranks = [int(by_bib[b]['Rank']) for b in bibs]
        if sorted(ranks) != ranks or any(key(a) < key(b) for a, b in zip(bibs, bibs[1:])):
            err(f'{ctx} tie break: {bibs} out of order')

def vault_attempt(n, v, wag):
    if v == 'DNS':
        return {f'Status{n}': 'DNS', f'D{n}': '', f'E{n}': '', f'B{n}': '', f'Penalty{n}': '',
                f'SJ Penalty{n}': '', f'Total{n}': ''}
    invalid = D(v['Score']) == 0
    return {f'Status{n}': 'INVALID_VAULT' if invalid else 'COMPLETED', f'D{n}': v['D'], f'E{n}': v['E'],
            f'B{n}': '' if wag else v['B'], f'Penalty{n}': penalty(v['PEN']), f'SJ Penalty{n}': '',
            f'Total{n}': v['Score']}

COMPETED = defaultdict(set)   # (disc, app) -> bibs with a qualification row

def results(disc, rnd, app):
    ctx = f'{disc} {rnd} {app}'
    pages, tie = TABLES[(disc, rnd, app)]
    wag = disc == 'WAG'
    rows = read_table(disc, rnd, app, pages)
    check_rows(ctx, rows, app, wag)
    check_tie_break(ctx, rows, read_tie_break(disc, rnd, app, tie) if tie else [], app)
    qual = rnd == 'QUAL'
    written = []
    for r in rows:
        p = identify(disc, ctx, r['Bib'], r['Name'], r['NOC'])
        if p is None:
            continue
        if r['Q'] and not qual:
            err(f'{ctx}: bib {r["Bib"]} marker {r["Q"]} on a final')
        if qual:
            COMPETED[(disc, app)].add(r['Bib'])
        row = {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
               'Session Start Date': DATES[rnd][DAY[disc][app]], 'Round': rnd, 'Part': '', 'Apparatus': app,
               'Rank': r['Rank'], 'Bib': r['Bib'], 'Name': p['Name'], 'NOC Code': p['NOC Code']}
        if app == 'VT':
            row |= vault_attempt(1, r['v1'], wag) | vault_attempt(2, r['v2'], wag)
            row |= {'Combined Bonus': r['v2']['B'] if wag and r['v2'] != 'DNS' else '', 'Total': r['Total']}
        else:
            row |= {'Status': r['Status'], 'D': r['D'], 'E': r['E'], 'B': r['B'], 'Penalty': penalty(r['PEN']),
                    'SJ Penalty': '', 'Total': r['Total']}
        if qual:
            # The tables print the reserves as a plain `R`, numbered here in rank order
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        written.append(row)
    if qual:
        reserves = [w for w in written if w['Qualification'] == 'R']
        for i, w in enumerate(reserves, 1):
            w['Qualification'] = f'R{i}'
    out.csv(f'{PREFIX[disc]}-SCORES-{rnd}-{app}.csv', common.score_header(app == 'VT', qual), written)
    return written

# ---------------------------------------------------------------- qualifiers, finals, start lists
def check_qualifiers(disc, app, rows):
    """The top eight marked Q (the two-per-country rule prints no NR here), the next two R1-R2."""
    marks = [r['Qualification'] for r in rows if r['Qualification']]
    if marks != ['Q'] * 8 + ['R1', 'R2'] or [r['Qualification'] for r in rows[:10]] != marks:
        err(f'{disc} QUAL {app}: markers {marks}')

def finals_start_lists(disc):
    """The final's start list: per apparatus, eight starters then reserves R1 and R2."""
    n, blocks = FINALS_START[disc]
    lists, block = defaultdict(lambda: dict(start=[], reserves=[])), -1
    for l in page(n).split('\n'):
        if l.count('Bib #') > 1:
            # Each block's heading names every column (a stray single `Bib # Name NOC` doesn't)
            block += 1
            continue
        entries = re.findall(r'(?:^|\s)(\d|R\d)\s+(\d{3})\s+\S', l)
        if not entries:
            continue
        if len(entries) != len(blocks[block]):
            err(f'{disc} finals start list: line {l!r}'); continue
        for app, (order, bib) in zip(blocks[block], entries):
            lists[app]['reserves' if order.startswith('R') else 'start'].append(bib)
    return lists

def check_final(disc, app, qual_rows, final_rows, starters):
    """The final's athletes are its start list's eight. A qualifier missing from both was
    replaced by the reserves in order, and the start list's reserves are the next in rank."""
    marks = {r['Bib']: r['Qualification'] for r in qual_rows}
    finalists = {r['Bib'] for r in final_rows}
    if finalists != set(starters['start']) or len(finalists) != 8:
        err(f'{disc} EVENT {app}: finalists {sorted(finalists)} != start list {sorted(starters["start"])}')
    absent = sorted(b for b, m in marks.items() if m == 'Q' and b not in finalists)
    came_in = sorted((marks.get(b), b) for b in finalists if marks.get(b) != 'Q')
    if [m for m, _ in came_in] != ['R1', 'R2'][:len(came_in)] or len(came_in) != len(absent):
        err(f'{disc} EVENT {app}: qualifiers {absent} replaced by {came_in}')
    elif absent:
        print(f'  {disc} EVENT {app}: qualifiers {absent} replaced by {came_in}')
    ranked = [r['Bib'] for r in qual_rows if r['Rank'] and r['Bib'] not in finalists and marks[r['Bib']] != 'Q']
    if starters['reserves'] != ranked[:2]:
        err(f'{disc} EVENT {app}: start list reserves {starters["reserves"]}, next in rank {ranked[:2]}')

def check_qual_start_lists(disc):
    """Every qualification routine is on the day's start list for that apparatus; those listed
    without a result are the known NO_RESULT athletes."""
    listed = defaultdict(set)
    for day in (1, 2):
        apps = [a for a in APPS[disc] if DAY[disc][a] == day]
        columns = None
        for n in START_PAGES[(disc, day)]:
            for l in page(n).split('\n'):
                if 'NOC BIB Competitor' in l:
                    cols = [m.start() for m in re.finditer('#', l)]
                    if columns is None:
                        if len(cols) != len(apps):
                            err(f'{disc} start list day {day}: {len(cols)} columns for {apps}')
                        columns = cols
                    continue
                for m in re.finditer(r'\d\.\s+[A-Z]{3}\s+(\d{3})\s', l):
                    col = min(range(len(columns)), key=lambda i: abs(columns[i] - m.start()))
                    listed[apps[col]].add(m.group(1))
    for app in APPS[disc]:
        missing = COMPETED[(disc, app)] - listed[app]
        extra = listed[app] - COMPETED[(disc, app)]
        if missing or extra != NO_RESULT.get((disc, app), set()):
            err(f'{disc} QUAL {app} start list: not listed {sorted(missing)}, listed without a result {sorted(extra)}')

def check_medallists(finals):
    """Medalists By Event (p. 5), `Given SURNAME`: a cross-check of each final's top three."""
    event = None
    medals = defaultdict(list)
    for l in page(MEDALLISTS_PAGE).split('\n'):
        m = re.match(r'^\s*(?:(FX|PH|SR|VT|PB|HB|UB|BB)\s+(MAG|WAG)\s+\S+\s+)?(GOLD|SILVER|BRONZE)\s+(\S.*?)\s+([A-Z]{3})\s*$', l)
        if not m:
            continue
        if m.group(3) == 'GOLD':
            event = []
        event.append((m.group(4), m.group(5)))
        if m.group(1):
            medals[(m.group(2), m.group(1))] = event
    for key, rows in finals.items():
        podium = [(PARTICIPANTS[key[0]][r['Bib']], r['NOC Code']) for r in rows if r['Rank'] in ('1', '2', '3')]
        printed = medals.get(key, [])
        same = len(printed) == len(podium) == 3 and all(
            fold(name) == fold(p['Given Name'] + p['Surname']) and noc == n for (name, noc), (p, n) in zip(printed, podium))
        if not same:
            print(f'  medallists {key}: printed {printed}, final {[p["Name"] for p, _ in podium]}')

# ---------------------------------------------------------------- judges
FUNCS = r'SV|AS|D\d|[EЕ]\d|T\d?|L\d?|R\d|Reserve'
MAG_JUDGE = r'(' + FUNCS + r')\s+(\d{1,2})\s+(\S.*?)\s+([A-Z]{3}(?: \d)?)(?=\s|$)'
WAG_JUDGE = r'(?:(' + FUNCS + r')\s+)?(\d{1,2})\s+(\d{4,5})\s+(\S.*?)(?:\s+([A-Z]{3}\d?)(?=\s|$)|\s*$)'
GRID = {'MAG': [('FX', 'PH'), ('SR', 'VT'), ('PB', 'HB')], 'WAG': [('VT', 'UB'), ('BB', 'FX')]}
NUMBERS = defaultdict(dict)   # disc -> judge number -> (surname, given), across both rounds
# Brevets printed against the wrong judge: WAG finals' UB and FX time judge MOSTAFA Shadi (5384
# on the qualification page) prints WOOLF's 4094.
WRONG_BREVET = {('EVENT', 'UB', '10', '4094'), ('EVENT', 'FX', '10', '4094')}

def judge_noc(noc):
    """`AIN 1` is AIN1; the TD's `FIG` / `WGYM` (World Gymnastics) is written blank."""
    return '' if noc in ('FIG', 'WGYM') else noc.replace(' ', '')

def judges(disc, rnd):
    """Judges Assignment: the Technical Delegate (one `Given SURNAME` name above the panels,
    written `TD`), then panels two to a row under apparatus icons (GRID). Judges are numbered,
    the same number on every page of a discipline; WAG prints each judge's brevet too."""
    text = page(JUDGES_PAGE[(disc, rnd)])
    ev = EVENTS[PREFIX[disc]]
    base = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
            'Round': rnd}
    m = re.search(r'^\s*(?:TD\s+)?([A-Z][a-z]+) ([A-Za-z]+)\s+(FIG|WGYM)\b', text, re.M)
    given, surname = m.group(1), m.group(2).upper()
    rows = [base | {'Apparatus': '', 'Function': 'TD', 'Name': f'{m.group(1)} {m.group(2)}', 'Surname': surname,
                    'Given Name': given, 'NOC Code': judge_noc(m.group(3))}]
    panels, reserves, block = defaultdict(list), [], -1
    unlabelled, wrapped = None, {}
    for l in text.split('\n'):
        if disc == 'MAG' and 'JUDGES' in l and 'Nation' in l or disc == 'WAG' and re.search(r'Vault|Balance Beam', l):
            block += 1
            continue
        if block < 0:
            continue
        if disc == 'WAG' and re.fullmatch(r'\s*Reserve\s*', l):
            # BB qualification prints its reserve's label on the line below the name
            if unlabelled is None:
                err(f'{disc} {rnd}: a Reserve label with no judge')
            else:
                unlabelled['func'] = 'Reserve'
                unlabelled = None
            continue
        if disc == 'WAG' and wrapped and (m := re.fullmatch(r'\s+(\S.*?)\s+([A-Z]{3}\d?)\s*', l)):
            # A long surname pushes the given name and NOC to the next line
            side, j = wrapped.popitem()
            j['name'] += ' ' + ' '.join(m.group(1).split())
            j['NOC'] = m.group(2)
            continue
        for m in re.finditer(MAG_JUDGE if disc == 'MAG' else WAG_JUDGE, l):
            side = m.start() > 60
            if disc == 'MAG':
                func, number, name, noc = m.groups()
                brevet = None
            else:
                func, number, brevet, name, noc = m.groups()
            j = dict(func=func.replace('Е', 'E') if func else None, number=number, brevet=brevet,
                     name=' '.join(name.split()),
                     NOC=noc or '')
            if not noc:
                wrapped[side] = j
            if func is None:
                unlabelled = j
            if func in ('R1', 'R2'):
                reserves.append(j)   # MAG reserves for the whole round, below the last panel
            else:
                panels[GRID[disc][block][side]].append(j)
    if wrapped or unlabelled:
        err(f'{disc} {rnd} judges: unfinished {wrapped} {unlabelled}')
    brevets = {}
    for app, j in [(app, j) for app in APPS[disc] for j in panels[app]] + [('', j) for j in reserves]:
        surname, given = split_surname_first(j['name'])
        known = NUMBERS[disc].setdefault(j['number'], (surname, given))
        if (surname, given) != known:
            err(f'{disc} {rnd} judges: number {j["number"]} is {known} and {(surname, given)}')
        if j['brevet'] and (rnd, app, j['number'], j['brevet']) not in WRONG_BREVET:
            if brevets.setdefault(j['brevet'], j['number']) != j['number']:
                err(f'{disc} {rnd} judges: brevet {j["brevet"]} on numbers {brevets[j["brevet"]]} and {j["number"]}')
        func = {'AS': 'SV', 'Reserve': 'R'}.get(j['func'], j['func'])
        rows.append(base | {'Apparatus': app, 'Function': func, 'Name': f'{surname} {given}', 'Surname': surname,
                            'Given Name': given, 'NOC Code': judge_noc(j['NOC'])})
    for app in APPS[disc]:
        funcs = [r['Function'] for r in rows if r['Apparatus'] == app]
        if funcs[:8] != ['SV', 'D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5'] or len(set(funcs)) != len(funcs):
            err(f'{disc} {rnd} {app}: panel {funcs}')
    for r in rows:
        if not r['Surname'] or not r['Given Name'] or (r['Function'] != 'TD' and not r['NOC Code']):
            err(f'{disc} {rnd} judges: {r["Name"]!r} {r["NOC Code"]!r}')
    return rows

# ---------------------------------------------------------------- run
finals = {}
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    participants(disc)
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, judges(disc, 'QUAL') + judges(disc, 'EVENT'))
    starts = finals_start_lists(disc)
    for app in APPS[disc]:
        q = results(disc, 'QUAL', app)
        check_qualifiers(disc, app, q)
        finals[(disc, app)] = results(disc, 'EVENT', app)
        check_final(disc, app, q, finals[(disc, app)], starts[app])
    check_qual_start_lists(disc)
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])
check_entry_counts()
check_medallists(finals)

corrections.finish()
checks.finish()
