"""Parse the 2026 Apparatus World Cup Antalya results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_apparatus_world_cup_antalya.py \\
        data/2026/2026-APPARATUS-WORLD-CUP-ANTALYA/17936-ResultsbookMedia.pdf

Writes PARTICIPANTS / JUDGES / SCORES-C1-<APP> / SCORES-C3-<APP> CSVs and an IMPORT.json
per discipline next to the PDF, reading event metadata from the EVENT.csv already there and
applying the event's CORRECTIONS.csv. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.8).

The organizers' media book (Turkish Federation, EVAL scoring): every page has text except MAG
rings qualification (p. 21), which is read from `transcriptions/2026-APPARATUS-WORLD-CUP-ANTALYA/`.
No report codes, so the pages are named below and checked against their printed titles.
"""
import os, re, sys, unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-APPARATUS-WORLD-CUP-ANTALYA'
TRANSCRIPTIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transcriptions', EVENT_PREFIX)
PREFIX = {disc: f'{EVENT_PREFIX}-{disc}-SR' for disc in ('MAG', 'WAG')}

BOOK = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err)
out = common.Output(OUT, corrections)

APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
# Competition Schedule (p. 2): qualification day 1 MAG FX-PH-SR / WAG VT-UB, day 2 the rest;
# the finals split the same way.
DAY = {'MAG': {'FX': 1, 'PH': 1, 'SR': 1, 'VT': 2, 'PB': 2, 'HB': 2},
       'WAG': {'VT': 1, 'UB': 1, 'BB': 2, 'FX': 2}}
DATES = {'QUAL': {1: '2026-03-12', 2: '2026-03-13'}, 'EVENT': {1: '2026-03-14', 2: '2026-03-15'}}

# Physical pages (1-based): results table pages, then its tie-break report pages.
TABLES = {
    ('MAG', 'QUAL', 'FX'): ([17], [18]), ('MAG', 'QUAL', 'PH'): ([19], [20]),
    ('MAG', 'QUAL', 'SR'): ([], [22]), ('MAG', 'QUAL', 'VT'): ([23], [24]),
    ('MAG', 'QUAL', 'PB'): ([25], [26]), ('MAG', 'QUAL', 'HB'): ([27], [28]),
    ('WAG', 'QUAL', 'VT'): ([29], [30]), ('WAG', 'QUAL', 'UB'): ([31], []),
    ('WAG', 'QUAL', 'BB'): ([32, 33], [34]), ('WAG', 'QUAL', 'FX'): ([35], [36]),
    ('MAG', 'EVENT', 'FX'): ([41], [42]), ('MAG', 'EVENT', 'PH'): ([43], []),
    ('MAG', 'EVENT', 'SR'): ([44], []), ('MAG', 'EVENT', 'VT'): ([45], [46]),
    ('MAG', 'EVENT', 'PB'): ([47], [48]), ('MAG', 'EVENT', 'HB'): ([49], []),
    ('WAG', 'EVENT', 'VT'): ([50], [51]), ('WAG', 'EVENT', 'UB'): ([52], []),
    ('WAG', 'EVENT', 'BB'): ([53], [54]), ('WAG', 'EVENT', 'FX'): ([55], []),
}
ENTRY_PAGE = {'MAG': 5, 'WAG': 6}
JUDGES_PAGE = {('MAG', 'QUAL'): 15, ('WAG', 'QUAL'): 16, ('MAG', 'EVENT'): 39, ('WAG', 'EVENT'): 40}
# Qualification start lists: pages per day. Each group lists one column per apparatus still
# rotating, in the order below; an apparatus drops out after its number of groups (p. 3).
START_PAGES = {('MAG', 1): [7, 8], ('WAG', 1): [9, 10], ('MAG', 2): [11, 12], ('WAG', 2): [13, 14]}
GROUPS = {'MAG': {'FX': 8, 'PH': 8, 'SR': 6, 'VT': 5, 'PB': 6, 'HB': 6},
          'WAG': {'VT': 5, 'UB': 6, 'BB': 10, 'FX': 7}}
FINALS_START_PAGES = [37, 38]
# On a qualification start list but with no result and no DNS row in the book.
NO_RESULT = {('MAG', 'FX'): {'160'}, ('MAG', 'PH'): {'160'}, ('MAG', 'SR'): {'160'},
             ('MAG', 'VT'): {'112', '123', '170', '184', '188'}, ('MAG', 'HB'): {'112', '193'},
             ('WAG', 'VT'): {'316', '334'}, ('WAG', 'UB'): {'316', '339'}, ('WAG', 'BB'): {'363'},
             ('WAG', 'FX'): {'316', '333'}}
APP_TITLE = {'FX': 'Floor Exercises / FX', 'PH': 'Pommel Horse / PH', 'SR': 'Rings / SR', 'VT': 'Vault Table / VT',
             'PB': 'Parallel Bars? / PB', 'HB': '(Horizontal|High) Bar / HB', 'UB': 'Uneven Bars / UB',
             'BB': 'Balance Beam / BB'}

NUM = r'-?\d+[.,]\d{3}'

def page(n):
    return BOOK[n - 1]

def num(s):
    """Decimal commas (D, E, bonus, penalty) and points (totals) are both printed."""
    return s.replace(',', '.')

def penalty(s):
    """Penalties are printed unsigned; written negative, as deducted, and blank when zero."""
    return '' if D(num(s)) == 0 else '-' + num(s)

def fold(s):
    s = unicodedata.normalize('NFKD', s.replace('ı', 'i'))
    return ''.join(c for c in s if not unicodedata.combining(c)).upper()

def unscramble(s):
    """Some names print in a font whose text layer is shifted (`ù(1(5` for ŞENER, `%ø1(5` for
    BİNER, `6R\\DGÕ` for Soyadı): ASCII is 29 code points low, with three Turkish letters apart."""
    special = {'ù': 'Ş', 'ø': 'İ', 'Õ': 'ı'}
    return ''.join(special.get(c) or (chr(ord(c) + 29) if '!' <= c <= 'b' else c) for c in s)

# ---------------------------------------------------------------- participants
PARTICIPANTS = {}   # disc -> bib -> participant

def participants(disc):
    """BIB NUMBERS page: two columns of `bib NOC SURNAME Given`; neutral athletes as AIN2."""
    left, right = [], []
    for l in page(ENTRY_PAGE[disc]).split('\n'):
        for m in re.finditer(r'(\d{3}) ([A-Z]{3}\d?)\s+(\S.*?)\s{2,}(\S.*?)(?=\s{2,}\d{3} |\s*$)', l):
            (left if m.start() < 50 else right).append(m.groups())
    rows, by_bib = [], {}
    for order, (bib, noc, surname, given) in enumerate(left + right, 1):
        if bib in by_bib:
            err(f'{disc} participants: bib {bib} twice')
        by_bib[bib] = dict(NOC=noc, Surname=surname, Given=given, Name=f'{surname} {given}')
        rows.append({'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
                     'Event Start Date': EVENTS[PREFIX[disc]]['Start Date'], 'Order': order, 'NOC Code': noc,
                     'Bib Number': bib, 'FIG License': '', 'Name': f'{surname} {given}', 'Surname': surname,
                     'Given Name': given, 'Birth Year': '', 'Birth Date': ''})
    # The book's entry counts (p. 3) are "as per nominative registration" and don't match the
    # list (MAG 89 for 80 bibs), so there is no total to check against.
    PARTICIPANTS[disc] = by_bib
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)

def identify(disc, ctx, bib, surname, given, noc):
    """A results row's printed name and NOC against the entry list; results print AIN for AIN2."""
    p = PARTICIPANTS[disc].get(bib)
    if p is None:
        err(f'{ctx}: bib {bib} not on the entry list'); return None
    for printed, entered in ((surname, p['Surname']), (given, p['Given'])):
        if fold(entered) not in (fold(printed), fold(unscramble(printed))):
            err(f'{ctx}: bib {bib} printed {printed!r}, entered {entered!r}')
    if noc not in (p['NOC'], p['NOC'][:3]):
        err(f'{ctx}: bib {bib} NOC {noc}, entered {p["NOC"]}')
    return p

# ---------------------------------------------------------------- results tables
NAME_LINE = (r'^\s*(\d+)?\s+(\d{3})\s+(\S.*?)\s{2,}(\S.*?)\s+([A-Z]{3})(?:\s+[A-Z]{3})?'
             r'((?:\s+' + NUM + r')*)(?:\s+(DNS))?(?:\s+(Q|R\d))?\s*$')
VAULT_LINE = r'^\s+(' + NUM + r')\s+(' + NUM + r')\s+(' + NUM + r')\s+(' + NUM + r')\s+(' + NUM + r')\s*$'

def check_title(disc, rnd, app, n, tie):
    text = ' '.join(page(n).split('\n')[:12])
    want = [disc, APP_TITLE[app], 'TIE BREAK' if tie else r'QUA?LIFICATION|Qualification Results' if rnd == 'QUAL'
            else 'Final Results']
    if not all(re.search(w, text) for w in want) or (not tie and 'TIE BREAK' in text):
        err(f'{disc} {rnd} {app}: page {n} is not that report')

def routine(d, e, b, pen, total):
    return dict(D=num(d), E=num(e), B=num(b), Penalty=penalty(pen), Total=num(total))

def read_table(disc, rnd, app, pages, tie=False):
    """Results or tie-break pages -> rows: Rank, Bib, Surname, Given, NOC, Q, and a routine
    (Status, D, E, B, Penalty, Total) or, for vault, v1/v2 and the vault score."""
    ctx = f'{disc} {rnd} {app}' + (' tie break' if tie else '')
    rows, pending = [], []
    for n in pages:
        check_title(disc, rnd, app, n, tie)
        for l in page(n).split('\n'):
            m = re.match(VAULT_LINE, l)
            if m and app == 'VT':
                if rows and 'v2' not in rows[-1] and 'v1' in rows[-1]:
                    rows[-1]['v2'] = routine(*m.groups())
                else:
                    pending.append(routine(*m.groups()))
                continue
            m = re.match(NAME_LINE, l)
            if not m:
                if re.match(r'^\s*\d*\s+\d{3}\s', l):
                    err(f'{ctx} p. {n}: unparsed {l!r}')
                continue
            rank, bib, surname, given, noc, nums, dns, q = m.groups()
            nums = nums.split()
            row = dict(Rank=rank or '', Bib=bib, Surname=surname, Given=given, NOC=noc, Q=q or '')
            if app == 'VT':
                if len(nums) != 1 or len(pending) != 1:
                    err(f'{ctx} p. {n}: bib {bib}: vault layout {l!r}'); pending = []; continue
                row |= dict(v1=pending.pop(), Total=num(nums[0]))
            elif dns or not nums:
                # A DNS row, or a name with no scores at all (WAG BB, DROBNIAK)
                row |= dict(Status='DNS', D='', E='', B='', Penalty='', Total='')
            else:
                if len(nums) != (5 if disc == 'MAG' else 4):
                    err(f'{ctx} p. {n}: bib {bib}: {len(nums)} values'); continue
                d, e, *b, pen, total = nums
                row |= dict(Status='COMPLETED') | routine(d, e, b[0] if b else '', pen, total)
            rows.append(row)
    if pending or any(app == 'VT' and 'v2' not in r for r in rows):
        err(f'{ctx}: vault lines out of place')
    if not tie:
        n_ids = sum(len(re.findall(r'^\s*\d*\s+\d{3}\s+\S', page(n), re.M)) for n in pages)
        if n_ids != len(rows):
            err(f'{ctx}: parsed {len(rows)} of {n_ids} rows')
    return rows

def read_transcription(disc, rnd, app):
    rows = []
    for l in open(os.path.join(TRANSCRIPTIONS, f'{disc}-{rnd}-{app}.txt'), encoding='utf-8'):
        if not l.strip() or l.startswith('#'):
            continue
        rank, bib, surname, given, noc, d, e, b, pen, total, q = l.rstrip('\n').split('|')
        rows.append(dict(Rank=rank, Bib=bib, Surname=surname, Given=given, NOC=noc, Q=q, Status='COMPLETED')
                     | routine(d, e, b, pen, total))
    return rows

def vault_attempt(n, v, wag):
    """MAG prints a bonus inside each vault score; WAG's +0.2 is printed on the second vault's
    line but applies to the vault score (Combined Bonus), so B1/B2 stay blank."""
    invalid = D(v['Total']) == 0
    return {f'Status{n}': 'INVALID_VAULT' if invalid else 'COMPLETED', f'D{n}': v['D'], f'E{n}': v['E'],
            f'B{n}': '' if wag else v['B'], f'Penalty{n}': v['Penalty'], f'SJ Penalty{n}': '', f'Total{n}': v['Total']}

# Routines whose E column prints the execution deductions instead of the E score; the score is
# 10 minus them, which CORRECTIONS.csv writes.
E_AS_DEDUCTIONS = {('MAG EVENT VT', '130', 2)}
# Vault scores that don't follow from the vaults, with the value CORRECTIONS.csv writes.
MISPRINTED_VAULT_SCORE = {('WAG QUAL VT', '314'): '12.583'}

def check_rows(ctx, rows, app, wag):
    for r in rows:
        c = f'{ctx} bib {r["Bib"]}'
        if app != 'VT':
            if r['Status'] != 'DNS':
                checks.check_sum(c, r['Total'], r['D'], r['E'], r['B'], r['Penalty'])
            continue
        for n in (1, 2):
            v = r[f'v{n}']
            e = str(10 + D(v['E'])) if (ctx, r['Bib'], n) in E_AS_DEDUCTIONS else v['E']
            checks.check_sum(f'{c} vault {n}', v['Total'], v['D'], e, '' if wag else v['B'], v['Penalty'])
        if wag and D(r['v1']['B']):
            err(f'{c}: a bonus on vault 1')
        published = MISPRINTED_VAULT_SCORE.get((ctx, r['Bib']), r['Total'])
        checks.check_vault_average(c, r['v1']['Total'], r['v2']['Total'], r['v2']['B'] if wag else '', published)
    checks.check_rank_order(ctx, rows)

def check_tie_break(ctx, rows, tie_rows):
    """A tie-break report repeats the tied athletes' rows; they must be the table's."""
    by_bib = {r['Bib']: r for r in rows}
    for t in tie_rows:
        r = by_bib.get(t['Bib'])
        keys = [k for k in ('Rank', 'Total', 'D', 'E', 'B', 'Penalty', 'v1', 'v2') if k in t]
        # WAG tie-break reports print no bonus column
        if r is None or any(t[k] != r[k] for k in keys if not (k == 'B' and t[k] == '')):
            err(f'{ctx} tie break: bib {t["Bib"]} {t} differs from the table')
    if not tie_rows:
        err(f'{ctx} tie break: no rows')

COMPETED = defaultdict(set)   # (disc, app) -> bibs with a qualification row

def results(disc, rnd, app):
    ctx = f'{disc} {rnd} {app}'
    pages, ties = TABLES[(disc, rnd, app)]
    wag = disc == 'WAG'
    if pages:
        rows = read_table(disc, rnd, app, pages)
    else:
        rows = read_transcription(disc, rnd, app)
    check_rows(ctx, rows, app, wag)
    for n in ties:
        check_tie_break(ctx, rows, read_table(disc, rnd, app, [n], tie=True))
    qual = rnd == 'QUAL'
    written = []
    for r in rows:
        p = identify(disc, ctx, r['Bib'], r['Surname'], r['Given'], r['NOC'])
        if p is None:
            continue
        if r['Q'] and not qual:
            err(f'{ctx}: bib {r["Bib"]} marker {r["Q"]} on a final')
        if qual:
            COMPETED[(disc, app)].add(r['Bib'])
        row = {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
               'Competition Start Date': DATES[rnd][DAY[disc][app]], 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app,
               'Rank': r['Rank'], 'Bib': r['Bib'], 'Name': p['Name'], 'NOC Code': p['NOC']}
        if app == 'VT':
            row |= vault_attempt(1, r['v1'], wag) | vault_attempt(2, r['v2'], wag)
            row |= {'Combined Bonus': r['v2']['B'] if wag and D(r['v2']['B']) else '', 'Total': r['Total']}
        else:
            row |= {k: r[k] for k in ('Status', 'D', 'E', 'B', 'Penalty', 'Total')} | {'SJ Penalty': ''}
        if qual:
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        written.append(row)
    out.csv(f'{PREFIX[disc]}-SCORES-{common.COMPETITION[rnd]}-{app}.csv', common.score_header(app == 'VT', qual), written)
    return written

# ---------------------------------------------------------------- qualifiers, finals, start lists
def check_qualifiers(disc, app, rows):
    """Eight Q (the two-per-country rule prints no NR here), then R1-R3 in rank order; athletes
    tied for a reserve place share it (MAG floor: two R3 at =11)."""
    marked = [r for r in rows if r['Qualification']]
    marks = [r['Qualification'] for r in marked]
    reserves = [m for m in marks if m != 'Q']
    shared = all(a['Rank'] == b['Rank'] for a, b in zip(marked, marked[1:])
                 if a['Qualification'] == b['Qualification'] != 'Q')
    if marks[:8] != ['Q'] * 8 or list(dict.fromkeys(reserves)) != ['R1', 'R2', 'R3'] or not shared:
        err(f'{disc} QUAL {app}: markers {marks}')

def finals_start_lists():
    """The finals start lists (pp. 37-38): two columns, each a run of apparatus blocks headed
    `<APP>  <MAG|WAG>`; starters print `order time bib`."""
    lists, current = defaultdict(set), {}
    for n in FINALS_START_PAGES:
        for l in page(n).split('\n'):
            for m in re.finditer(r'\b(FX|PH|SR|VT|PB|HB|UB|BB)\s+(MAG|WAG)\b', l):
                current[m.start() > 50] = (m.group(2), m.group(1))
            for m in re.finditer(r'(?:^|\s)\d\s+\d\d:\d\d\s+(\d{3})\s', l):
                lists[current[m.start() > 50]].add(m.group(1))
    return lists

def check_final(disc, app, qual_rows, final_rows, starters):
    """The final's athletes are its start list's eight; any who didn't qualify were reserves,
    called up in order."""
    marks = {r['Bib']: r['Qualification'] for r in qual_rows}
    finalists = {r['Bib'] for r in final_rows}
    if finalists != starters or len(finalists) != 8:
        err(f'{disc} EVENT {app}: finalists {sorted(finalists)} != start list {sorted(starters)}')
    absent = sorted(b for b, m in marks.items() if m == 'Q' and b not in finalists)
    came_in = sorted((marks.get(b), b) for b in finalists if marks.get(b) != 'Q')
    if [m for m, _ in came_in] != ['R1', 'R2', 'R3'][:len(came_in)] or len(came_in) != len(absent):
        err(f'{disc} EVENT {app}: qualifiers {absent} replaced by {came_in}')
    elif absent:
        print(f'  {disc} EVENT {app}: qualifiers {absent} replaced by {came_in}')

def check_qual_start_lists(disc):
    """Every qualification routine is on the day's start list for that apparatus; those listed
    without a result are the known NO_RESULT athletes."""
    listed = defaultdict(set)
    for day in (1, 2):
        apps = [a for a in APPS[disc] if DAY[disc][a] == day]
        order = [a for a in ('FX', 'PH', 'SR', 'VT', 'PB', 'HB') if a in apps] if disc == 'MAG' else apps
        group = 0
        for n in START_PAGES[(disc, day)]:
            cols = []
            for l in page(n).split('\n'):
                if re.search(r'Group \d+', l):
                    group = int(re.search(r'Group (\d+)', l).group(1))
                    cols = []
                    continue
                if 'NOC BIB Competitor' in l:
                    cols = [m.start() for m in re.finditer('#', l)]
                    rotating = [a for a in order if GROUPS[disc][a] >= group]
                    if len(cols) != len(rotating):
                        err(f'{disc} start list day {day} group {group}: {len(cols)} columns for {rotating}')
                    continue
                for m in re.finditer(r'\d\.\s+[A-Z]{3}\s+(\d{3})\s', l):
                    col = max(i for i, x in enumerate(cols) if x <= m.start() + 2)
                    listed[rotating[col]].add(m.group(1))
    for app in APPS[disc]:
        missing = COMPETED[(disc, app)] - listed[app]
        extra = listed[app] - COMPETED[(disc, app)]
        if missing or extra != NO_RESULT.get((disc, app), set()):
            err(f'{disc} QUAL {app} start list: not listed {sorted(missing)}, listed without a result {sorted(extra)}')

# ---------------------------------------------------------------- judges
JUDGE = r"(?:(SV|Supervisor|D\d|E\d|T\d?|L\d?|R\d|Line|Time|Reserve)\s+)?(\d{1,2})\s+(?:([A-Z][A-Z' -]*?[A-Z])\s{2,})?(\S.*?)\s+([A-Z]{3})(?=\s|$)"
GRID = {'MAG': [('FX', 'PH'), ('SR', 'VT'), ('PB', 'HB')], 'WAG': [('VT', 'UB'), ('BB', 'FX')]}
NUMBERS = defaultdict(dict)   # disc -> judge number -> (surname, given, noc), across both rounds

def judges(disc, rnd):
    """Judges Assignment: the Superior Jury (one name, written `TD`), then panels two to a row
    under apparatus icons (GRID, confirmed from the icons and the time/line judges). Judges are
    numbered, the same number on every page of a discipline."""
    text = page(JUDGES_PAGE[(disc, rnd)])
    ev = EVENTS[PREFIX[disc]]
    base = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
            'Competition': common.COMPETITION[rnd]}
    rows = []
    if disc == 'MAG':
        name = re.search(r'Competition Jury\s*\n\s+(\S.*?)\s*\n', text).group(1)
        surname, given = split_surname_first(name)
    else:
        # `Given Surname` in mixed case, credited to World Gymnastics / FIG (written blank)
        name = re.search(r'SUPERIOR JURY\s+(\S+(?: \S+)*)', text).group(1)
        given, surname = name.rsplit(' ', 1)
        surname = surname.upper()
    rows.append(base | {'Apparatus': '', 'Function': 'TD', 'Name': name, 'Surname': surname, 'Given Name': given,
                        'NOC Code': ''})
    panels, block, reserves = defaultdict(list), -1, []
    for l in text.split('\n'):
        if 'JUDGES' in l and ('Nation' in l or 'NF' in l):
            block += 1
            continue
        if block < 0:
            continue
        for m in re.finditer(JUDGE, l):
            func, number, surname, given, noc = m.groups()
            surname = surname or ''
            known = NUMBERS[disc].setdefault(number, (surname, given, noc))
            if (surname or known[0], given, noc) != known:
                err(f'{disc} {rnd} judges: number {number} is {known} and {(surname, given, noc)}')
            judge = dict(func=func, Name=f'{surname} {given}'.strip(), Surname=surname, Given=given, NOC=noc)
            if func in ('R1', 'R2'):
                reserves.append(judge)   # MAG reserves for the whole round, below the last panel
            else:
                panels[GRID[disc][block][m.start() > 60]].append(judge)
    for app in APPS[disc]:
        panel = panels[app]
        funcs = [j['func'] for j in panel]
        for i, (j, func) in enumerate(zip(panel, funcs)):
            if func is None:
                # MAG qualification rings prints no label between E1 and E3
                if 0 < i < len(panel) - 1 and (funcs[i - 1], funcs[i + 1]) == ('E1', 'E3'):
                    j['func'] = 'E2'
                else:
                    err(f'{disc} {rnd} {app}: judge {j["Name"]} with no function')
            elif func in ('Time', 'Line'):
                # WAG prints `Time`/`Line` for each; two on a panel are numbered
                same = [k for k, f in enumerate(funcs) if f == func]
                j['func'] = func[0] if len(same) == 1 else f'{func[0]}{same.index(i) + 1}'
            else:
                j['func'] = {'Supervisor': 'SV', 'Reserve': 'R'}.get(func, func)
        panel_funcs = [j['func'] for j in panel]
        if panel_funcs[:8] != ['SV', 'D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5']:
            err(f'{disc} {rnd} {app}: panel {panel_funcs}')
    for app, j in [(app, j) for app in APPS[disc] for j in panels[app]] + [('', j) for j in reserves]:
        rows.append(base | {'Apparatus': app, 'Function': j['func'], 'Name': j['Name'], 'Surname': j['Surname'],
                            'Given Name': j['Given'], 'NOC Code': j['NOC']})
    return rows

# ---------------------------------------------------------------- run
finals_starts = finals_start_lists()
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    participants(disc)
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, judges(disc, 'QUAL') + judges(disc, 'EVENT'))
    for app in APPS[disc]:
        q = results(disc, 'QUAL', app)
        check_qualifiers(disc, app, q)
        check_final(disc, app, q, results(disc, 'EVENT', app), finals_starts[(disc, app)])
    check_qual_start_lists(disc)
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])

corrections.finish()
checks.finish()
