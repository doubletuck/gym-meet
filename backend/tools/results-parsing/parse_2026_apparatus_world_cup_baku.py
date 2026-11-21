"""Parse the 2026 Baku Apparatus World Cup results book into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_apparatus_world_cup_baku.py \\
        data/2026/2026-APPARATUS-WORLD-CUP-BAKU/17935-ResultsbookMedia.pdf

Writes PARTICIPANTS, JUDGES and SCORES-{QUAL,EVENT}-<APP>, and an IMPORT.json, per discipline next
to the PDF, reading event metadata from the EVENT.csv already there. Exits non-zero if any check
fails (docs/instructions-results-parsing.md §3; this source format is §5.7).

The book is the organizer's (Microplus timing) print of FIG-style reports, the same family as the
Mediterranean Games book (§5.6): footer codes like GARM1APFX----...QUAL..._C73I, internal codes on
the entry list (MAG_SEN_000269) and List Of Qualifiers (_000291). An apparatus competition: each
apparatus's qualification is its own session, then the finals; no team or all-around round. Every
SCORES file comes from a "Results By Apparatus" table; the start lists, tie-break reports, List Of
Qualifiers and entry counts are cross-checks.
"""
import os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first as split_name

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-APPARATUS-WORLD-CUP-BAKU'
PAGES = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
out = common.Output(OUT, common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err))

PREFIX = {d: f'{EVENT_PREFIX}-{d}-SR' for d in ('MAG', 'WAG')}
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
# Panels in the Judges Assignment grid and blocks of the List Of Qualifiers and finals start
# lists, left-to-right then top-to-bottom (the legend's order). The time and line judges agree:
# MAG FX T/L1/L2 and VT L; WAG VT L, UB T, BB T1/T2, FX T/L1/L2 (checked in judges()).
GRID = APPS
# From the Competition Schedule pages (§4.4); the medallists list dates the finals the same way.
DAY1 = {'MAG': {'FX', 'PB', 'SR'}, 'WAG': {'VT', 'UB'}}

def session_date(disc, rnd, app):
    day1 = app in DAY1[disc]
    if rnd == 'QUAL':
        return '2026-03-05' if day1 else '2026-03-06'
    return '2026-03-07' if day1 else '2026-03-08'

GENDER = {'MAG': "Men's Artistic Gymnastics", 'WAG': "Women's Artistic Gymnastics"}
ROUND_TITLE = {'QUAL': 'Qualification', 'EVENT': 'Apparatus Final'}
MARKERS = ('Q', 'R1', 'R2', 'R3', 'NR')
NOC = r'[A-Z]{3}\d?'   # AIN1/AIN2, the neutral athletes' codes (§4.8)

def strip_inquiry(d):
    return d.lstrip('!').strip()

# ---------------------------------------------------------------- page lookup
TITLES = ('Number of Entries by NOC', 'Entry List By BIB', 'Judges Assignment', 'Results By Apparatus',
          'Tie Break', 'List Of Qualifiers', 'Start List')

def page_info(i):
    ls = [l.strip() for l in PAGES[i].split('\n') if l.strip()]
    if not any(l.endswith('Artistic Gymnastics') for l in ls[:2]):
        return dict(disc=None, rnd=None, title='', code='', app=None)   # covers
    disc = next((d for d, g in GENDER.items() if g in ls[:4]), 'ALL')
    rnd = next((r for r, t in ROUND_TITLE.items() if t in ls[:5]), None)
    title = next((t for l in ls[1:6] for t in TITLES if l.startswith(t)), '')
    code = next((l.split()[0] for l in reversed(ls) if re.search(r'Page \d+ / \d+$', l)), '')
    app = re.match(r'GAR[MW]1AP([A-Z]{2})-', code)
    return dict(disc=disc, rnd=rnd, title=title, code=code, app=app.group(1) if app else None)

INFO = [page_info(i) for i in range(len(PAGES))]

def find(disc, title, rnd=None, app=None):
    idx = [i for i, p in enumerate(INFO) if p['disc'] == disc and p['title'] == title
           and (rnd is None or p['rnd'] == rnd) and (app is None or p['app'] == app)]
    if not idx:
        raise SystemExit(f'no pages for {disc} {title} {rnd} {app}')
    return idx

def lines(idx):
    return [l for i in idx for l in PAGES[i].split('\n')]

def two_columns(idx, ctx, row):
    """Rows of a two-column grid report (judges, qualifiers, finals start lists): each block starts
    at a repeated heading and holds two apparatus, split at the second heading word. Yields
    (block, side, match) for each half-line matching `row`."""
    block, split_at = -1, None
    for l in lines(idx):
        m = re.match(r'^\s*(Function|Order)\s+(Name|Bib)\s', l)
        if m and l.count(m.group(1)) == 2:
            block += 1
            split_at = l.index(m.group(1), m.end())
            continue
        if l.strip().startswith(('LEGEND', 'NOTE')) or re.search(r'Page \d+ / \d+\s*$', l):
            split_at = None   # the page's end: a page header follows, then the next block's heading
            continue
        if split_at is None or not l.strip():
            continue
        for side, part in ((0, l[:split_at]), (1, l[split_at:])):
            if not part.strip():
                continue
            m = re.match(row, part)
            if m:
                yield block, side, m
            else:
                err(f'{ctx}: unparsed {part!r}')

# ---------------------------------------------------------------- participants
NAMES = {}                     # disc -> bib -> (name, noc)
COMPETED = defaultdict(set)    # disc -> bibs with at least one routine

def entry_rows(idx, pattern):
    return [m.groups() for l in lines(idx) for m in [re.match(pattern, l)] if m]

def participants(disc):
    ctx = f'{disc} participants'
    ev = EVENTS[PREFIX[disc]]
    rows, NAMES[disc] = [], {}
    for order, noc, bib, lic, name, y in entry_rows(
            find(disc, 'Entry List By BIB'),
            r'^\s+(\d+)\s+(' + NOC + r')\s+(\d+)\s+(\d+)\s+(\S.*?)\s{2,}(\d{4})\s*$'):
        sur, giv = split_name(name)
        if not sur or not giv:
            err(f'{ctx}: name split {name!r} -> {sur!r}/{giv!r}')
        if bib in NAMES[disc]:
            err(f'{ctx}: duplicate bib {bib}')
        NAMES[disc][bib] = (name, noc)
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                     'Event Start Date': ev['Start Date'], 'Order': order, 'NOC Code': noc,
                     'Bib Number': bib, 'FIG License': lic, 'Name': name, 'Surname': sur,
                     'Given Name': giv, 'Birth Year': y, 'Birth Date': ''})
    if [int(r['Order']) for r in rows] != list(range(1, len(rows) + 1)):
        err(f'{ctx}: entry list order is not 1..{len(rows)}')
    # The discipline's "Number of Entries by NOC" pages repeat every entry under a country heading
    by_bib = {r['Bib Number']: r for r in rows}
    n, country = 0, None
    for l in lines(find(disc, 'Number of Entries by NOC')):
        m = re.match(r'^\s+(' + NOC + r') - \S', l)
        if m:
            country = m.group(1); continue
        m = re.match(r'^\s{10,}(\S.*?)\s{2,}(\d+)\s+(\d+)\s+(\d{4})\s*$', l)
        if not m:
            continue
        n += 1
        name, bib, lic, y = m.groups()
        r = by_bib.get(bib)
        if not r or (r['Name'], r['NOC Code'], r['FIG License'], r['Birth Year']) != (name, country, lic, y):
            err(f'{ctx}: entries-by-NOC bib {bib} {name} {country} differs from the entry list')
    if n != len(rows):
        err(f'{ctx}: {n} on the entries-by-NOC list, {len(rows)} on the entry list')
    print(f'  {ctx}: {len(rows)} entries')
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)

def check_name(disc, ctx, bib, name, noc):
    """The results' name and NOC against the entry list; vault tables truncate long names to the
    surname. Returns the entry list's name."""
    if bib not in NAMES[disc]:
        err(f'{ctx}: bib {bib} not in participants'); return name
    full, pnoc = NAMES[disc][bib]
    if pnoc != noc:
        err(f'{ctx}: bib {bib} NOC {noc} != participants {pnoc}')
    if name != full and not full.startswith(name + ' '):
        err(f'{ctx}: bib {bib} {name!r} != participants {full!r}')
    return full

def check_entry_counts():
    """The general "Number of Entries by NOC" page counts each country's gymnasts with a routine."""
    ls = lines(find('ALL', 'Number of Entries by NOC'))
    h = next(l for l in ls if re.match(r'^\s+Men\s+Women\s+Total', l))
    heads = [h.index(w) + len(w) for w in ('Men', 'Women', 'Total')]
    n, totals = 0, None
    for l in ls:
        m = re.match(r'^\s+Total Countries: (\d+)\s+Total:\s+(\d+)\s+(\d+)\s+(\d+)\s*$', l)
        if m:
            totals = [int(v) for v in m.groups()]
        m = re.match(r'^\s+(' + NOC + r') - .+?\s{2,}(\d.*)$', l)
        if not m:
            continue
        n += 1
        printed = {}
        for v in re.finditer(r'\d+', l[m.start(2):]):   # right-aligned under their headings
            end = m.start(2) + v.end()
            printed[min(range(3), key=lambda k: abs(heads[k] - end))] = int(v.group())
        for k, disc in ((0, 'MAG'), (1, 'WAG')):
            got = sum(1 for b in COMPETED[disc] if NAMES[disc][b][1] == m.group(1))
            if got != printed.get(k, 0):
                err(f'entry counts {m.group(1)} {disc}: {got} competed, page says {printed.get(k, 0)}')
        if printed.get(0, 0) + printed.get(1, 0) != printed.get(2):
            err(f'entry counts {m.group(1)}: total {printed}')
    nocs = {NAMES[d][b][1] for d in COMPETED for b in COMPETED[d]}
    want = [len(nocs), len(COMPETED['MAG']), len(COMPETED['WAG'])]
    if n != len(nocs) or not totals or totals[:3] != want or totals[3] != want[1] + want[2]:
        err(f'entry counts: {n} countries listed, totals {totals}, competed {want}')
    for disc in COMPETED:
        idle = sorted(set(NAMES[disc]) - COMPETED[disc])
        if idle:
            print(f'  {disc}: entered without a routine: {idle}')

# ---------------------------------------------------------------- judges
FUNCTION = r'(TD|SV|D\d|E\d|[TL]\d?|RES(?: \d)?)'

def judge_fn(f):
    m = re.fullmatch(r'RES(?: (\d))?', f)
    return 'R' + (m.group(1) or '') if m else f

def judges(disc):
    ev = EVENTS[PREFIX[disc]]
    rows = []
    def add(rnd, app, fn, name, sur, giv, noc):
        if not sur or not giv:
            err(f'judges {disc}: name split {name!r}')
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                     'Event Start Date': ev['Start Date'], 'Round': rnd, 'Apparatus': app, 'Function': fn,
                     'Name': name, 'Surname': sur, 'Given Name': giv, 'NOC Code': noc})
    for rnd in ('QUAL', 'EVENT'):
        idx = find(disc, 'Judges Assignment', rnd)
        if len(idx) != 1:
            err(f'judges {disc} {rnd}: {len(idx)} pages')
        n0 = len(rows)
        # The Superior Jury is one Technical Delegate, printed `Given Surname` in mixed case and
        # credited to FIG, which isn't a federation: NOC written blank (§4.7)
        tds = [m.groups() for l in lines(idx) for m in [re.match(r'^\s+TD\s+(\S.*?)\s{2,}FIG\s*$', l)] if m]
        if len(tds) != 1:
            err(f'judges {disc} {rnd}: {len(tds)} technical delegates')
        for (name,) in tds:
            *giv, sur = name.split(' ')
            add(rnd, '', 'TD', name, sur.upper(), ' '.join(giv), '')
        row = r'^\s*' + FUNCTION + r'\s+(\S.*?)\s{2,}(' + NOC + r')\s*$'
        blocks = set()
        for block, side, m in two_columns(idx, f'judges {disc} {rnd}', row):
            blocks.add(block)
            sur, giv = split_name(m.group(2))
            add(rnd, GRID[disc][block * 2 + side], judge_fn(m.group(1)), m.group(2), sur, giv, m.group(3))
        if len(blocks) != len(GRID[disc]) // 2:
            err(f'judges {disc} {rnd}: {len(blocks)} panel rows')
        fns = defaultdict(set)
        for r in rows[n0:]:
            if r['Apparatus']:
                if r['Function'] in fns[r['Apparatus']]:
                    err(f'judges {disc} {rnd} {r["Apparatus"]}: two {r["Function"]}')
                fns[r['Apparatus']].add(r['Function'])
        for app in GRID[disc]:
            if not {'SV', 'D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5'} <= fns[app]:
                err(f'judges {disc} {rnd} {app}: incomplete panel {sorted(fns[app])}')
        # Time and line judges prove the grid's apparatus order
        timing = {a: sorted(f for f in fns[a] if f[0] in 'TL') for a in GRID[disc]}
        want = {'MAG': {'FX': ['L1', 'L2', 'T'], 'PH': [], 'SR': [], 'VT': ['L'], 'PB': [], 'HB': []},
                'WAG': {'VT': ['L'], 'UB': ['T'], 'BB': ['T1', 'T2'], 'FX': ['L1', 'L2', 'T']}}[disc]
        if timing != want:
            err(f'judges {disc} {rnd}: time/line judges {timing}')
        print(f'  judges {disc} {rnd}: {len(rows) - n0}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, rows)

# ---------------------------------------------------------------- apparatus tables
ID = r'^\s*(\d+)?\s+(\d{1,3})\s+(\S.*?)\s{2,}(' + NOC + r')\s+'
ROUTINE_KEYS = ['Status', 'D', 'E', 'B', 'Penalty', 'SJ Penalty', 'Total']

def header(ls):
    return next((l for l in ls if re.match(r'^\s*Rank\s+Bib\s', l)), '')

def col(h, label):
    m = re.search(r'(?<!\S)' + re.escape(label) + r'(?!\S)', h)
    return m.start() if m else None

def is_two_vault(i):
    # The header splits `Vault Score` over two lines; the two-vault list has a `Vault` (attempt)
    # column on the `Rank` line, the vault 1 list none
    return col(header(PAGES[i].split('\n')), 'Vault') is not None

def blank_routine(status):
    return dict.fromkeys(ROUTINE_KEYS, '') | {'Status': status}

def routine(tokens, h, ctx, vault_line=False):
    """Values of one routine, in the header's order: D/E (either order), B (MAG but pommel horse),
    then a penalty, and the score. `tokens` are (start, text)."""
    vals = [t for _, t in tokens]
    if len(vals) == 2 and re.fullmatch(r'\d+\.\d', vals[0]) and D(vals[1]) == 0:
        # An invalid vault prints D and the zero score; its E is blank (§4.3)
        if abs(tokens[0][0] - col(h, 'D')) >= abs(tokens[0][0] - col(h, 'E')):
            err(f'{ctx}: lone value {vals[0]} not under D')
        return blank_routine('INVALID_VAULT') | dict(D=vals[0], Total=vals[1])
    e_first = col(h, 'E') < col(h, 'D')
    has_b = col(h, 'B') is not None
    r = blank_routine('COMPLETED')
    if '!' in vals[:2]:
        err(f'{ctx}: detached inquiry mark')
    r['E'], r['D'] = (vals[0], vals[1]) if e_first else (vals[1], vals[0])
    i = 2
    if has_b:
        r['B'] = vals[i]; i += 1
    if not re.fullmatch(r'!?\d+\.\d', r['D']) or not re.fullmatch(r'\d+\.\d{3}', r['E']) \
            or (has_b and not re.fullmatch(r'\d\.\d', r['B'])):
        err(f'{ctx}: unexpected values {vals}')
    for pos, v in tokens[i:-1]:
        if not re.fullmatch(r'-\d+\.\d+', v) or r['Penalty']:
            err(f'{ctx}: unexpected token {v!r}'); continue
        r['Penalty'] = v
    r['Total'] = vals[-1]
    if not re.fullmatch(r'\d+\.\d{3}', r['Total']):
        err(f'{ctx}: bad score {r["Total"]!r}')
    checks.check_sum(ctx, r['Total'], strip_inquiry(r['D']), r['E'], r['B'], r['Penalty'])
    if vault_line and D(r['Total']) == 0:
        r['Status'] = 'INVALID_VAULT'
    return r

def tokens_of(l, start):
    return [(start + m.start(), m.group()) for m in re.finditer(r'\S+', l[start:])]

def count_ids(ls, pattern=ID):
    return sum(1 for l in ls if re.match(pattern, l))

def single_table(idx, ctx, vault=False):
    """One-routine "Results By Apparatus" table -> rows in printed order."""
    ls = lines(idx)
    h = header(ls)
    rows = []
    for l in ls:
        m = re.match(ID + r'(.*)$', l)
        if not m or not h:
            continue
        rank, bib, name, noc, _ = m.groups()
        t = tokens_of(l, m.start(5))
        if t[-1][1] == 'DNS':
            if rank or [v for _, v in t[:-1]] not in ([], ['0.000']):
                err(f'{ctx}: odd DNS row {l!r}')
            rows.append(dict(Rank='', Bib=bib, Name=name, NOC=noc, Q='', **blank_routine('DNS')))
            continue
        q = t.pop()[1] if t[-1][1] in MARKERS else ''
        r = routine(t, h, f'{ctx} bib {bib}', vault_line=vault)
        rows.append(dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, Q=q, **r))
    if count_ids(ls) != len(rows):
        err(f'{ctx}: parsed {len(rows)} rows, counted {count_ids(ls)}')
    checks.check_rank_order(ctx, rows)
    return rows

def double_table(idx, ctx):
    """Two-vault table: each vaulter on two lines (`1 …` and `2 …`); the first carries the vault
    score (`*` when the +0.2 bonus is included), any SJ penalty on the combined score (printed
    unsigned, between the attempt's score and the vault score) and the marker."""
    ls = lines(idx)
    h = header(ls)
    rows, cur = [], None
    for l in ls:
        m = re.match(ID + r'1\s+(.*)$', l)
        if m:
            rank, bib, name, noc, _ = m.groups()
            t = tokens_of(l, m.start(5))
            q = t.pop()[1] if t[-1][1] in MARKERS else ''
            total = t.pop()[1]
            bonus = ''
            if total.endswith('*'):
                total, bonus = total[:-1], '0.2'
            if total != 'DNF' and not re.fullmatch(r'\d+\.\d{3}', total):
                err(f'{ctx} bib {bib}: bad total {total!r}')
            sj = ''
            if re.fullmatch(r'\d+\.\d', t[-1][1]):
                # Written negative, as deducted (§4.3); it sits under the SJ Pen. heading
                pos, v = t.pop()
                if abs(pos - col(h, 'SJ Pen.')) > 4:
                    err(f'{ctx} bib {bib}: {v} not under SJ Pen.')
                sj = '-' + v
            v1 = routine(t, h, f'{ctx} bib {bib} v1', vault_line=True)
            cur = dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, v1=v1, Bonus=bonus, SJ=sj,
                       Total='' if total == 'DNF' else total, Q=q)
            rows.append(cur)
            continue
        m = re.match(r'^\s+2\s+(.*)$', l)
        if m and cur is not None and 'v2' not in cur:
            t = tokens_of(l, m.start(1))
            if t[-1][1] == 'DNS':
                if len(t) != 1 or cur['Total'] or cur['Rank']:
                    err(f'{ctx} bib {cur["Bib"]}: odd vault 2 DNS {l!r}')
                cur['v2'] = blank_routine('DNS')
            else:
                cur['v2'] = routine(t, h, f'{ctx} bib {cur["Bib"]} v2', vault_line=True)
                checks.check_vault_average(f'{ctx} bib {cur["Bib"]}', cur['v1']['Total'], cur['v2']['Total'],
                                           D(cur['Bonus']) + D(cur['SJ']), cur['Total'])
            continue
        if re.match(r'^\s*\d+\s+\d{1,3}\s+[A-Z]', l):
            err(f'{ctx}: unparsed {l!r}')
    if any('v2' not in r for r in rows):
        err(f'{ctx}: missing vault 2 line')
    n_id = count_ids(ls, ID + r'1\s')
    if n_id != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_id}')
    checks.check_rank_order(ctx, rows)
    return rows

def meta(disc, rnd, app):
    return {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
            'Session Start Date': session_date(disc, rnd, app), 'Round': rnd, 'Part': '', 'Apparatus': app}

def ident(disc, rnd, app, r):
    COMPETED[disc].add(r['Bib'])
    return meta(disc, rnd, app) | {'Rank': r['Rank'], 'Bib': r['Bib'], 'NOC Code': r['NOC'],
                                   'Name': check_name(disc, f'{disc} {rnd} {app}', r['Bib'], r['Name'], r['NOC'])}

def vault_cols(n, v):
    return {f'{k}{n}': v[k] for k in ROUTINE_KEYS}

def two_vault_extra(r):
    return {'Combined Bonus': r['Bonus'], 'Combined SJ Penalty': r['SJ'], 'Total': r['Total']}

VAULT_HEADER = {qual: common.score_header(True, qual, combined_sj_penalty=True) for qual in (False, True)}
RANKED = defaultdict(dict)   # (disc, rnd, app or 'VT2') -> bib -> (Rank, Total), for the tie breaks

def app_results(disc, rnd, app):
    """SCORES-<rnd>-<app>; returns the rows as written, for the qualifier cross-checks."""
    ctx = f'{disc} {rnd} {app}'
    idx = find(disc, 'Results By Apparatus', rnd, app)
    qual = rnd == 'QUAL'
    rows = []
    if app == 'VT':
        doubles = [i for i in idx if is_two_vault(i)]
        singles = [i for i in idx if i not in doubles]
        double = double_table(doubles, ctx + ' two-vault')
        for r in double:
            RANKED[(disc, rnd, 'VT2')][r['Bib']] = (r['Rank'], r['Total'])
        if not qual:
            if singles:
                err(f'{ctx}: unexpected vault 1 pages {singles}')
            for r in double:
                rows.append(ident(disc, rnd, app, r) | vault_cols(1, r['v1']) | vault_cols(2, r['v2'])
                            | two_vault_extra(r))
            out.csv(f'{PREFIX[disc]}-SCORES-EVENT-VT.csv', VAULT_HEADER[False], rows)
            return rows
        # Qualification: the vault 1 list ranks the field on the first vault, the two-vault list
        # on the vault score (§4.5); every vaulter is on both
        single = single_table(singles, ctx + ' vault 1', vault=True)
        by_bib = {r['Bib']: r for r in double}
        if set(by_bib) != {s['Bib'] for s in single}:
            err(f'{ctx}: the lists differ: {sorted(set(by_bib) ^ {s["Bib"] for s in single})}')
        for s in single:
            RANKED[(disc, rnd, app)][s['Bib']] = (s['Rank'], s['Total'])
            r = by_bib.get(s['Bib'])
            if r is None:
                continue
            v1 = {k: s[k] for k in ROUTINE_KEYS}
            if r['v1'] != v1:
                err(f'{ctx} bib {s["Bib"]}: vault 1 differs between lists: {v1} vs {r["v1"]}')
            rows.append(ident(disc, rnd, app, s) | vault_cols(1, v1) | vault_cols(2, r['v2']) | two_vault_extra(r)
                        | {'Qualification': r['Q'], 'Qualification Rank': r['Rank']})
        out.csv(f'{PREFIX[disc]}-SCORES-QUAL-VT.csv', VAULT_HEADER[True], rows)
        return rows
    for r in single_table(idx, ctx):
        RANKED[(disc, rnd, app)][r['Bib']] = (r['Rank'], r['Total'])
        if r['Q'] and not qual:
            err(f'{ctx} bib {r["Bib"]}: marker {r["Q"]} on a final')
        row = ident(disc, rnd, app, r) | {k: r[k] for k in ROUTINE_KEYS}
        if qual:
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        rows.append(row)
    out.csv(f'{PREFIX[disc]}-SCORES-{rnd}-{app}.csv', common.score_header(False, qual), rows)
    return rows

# ---------------------------------------------------------------- cross-checks
LIST_ROW = r'^\s*(\d+|R\d|NR)\s+(\d{1,3})\s+\S.*?\s{2,}(' + NOC + r')\s*$'

def grid_lists(disc, title, rnd):
    """List Of Qualifiers / finals start list: per apparatus, bib -> `1`…`8` or `R1`…`R3`."""
    lists = {app: {} for app in APPS[disc]}
    for block, side, m in two_columns(find(disc, title, rnd), f'{disc} {title}', LIST_ROW):
        lists[GRID[disc][block * 2 + side]][m.group(2)] = m.group(1)
    return lists

def check_qualifiers(disc, app, rows, listed, start):
    """The table's markers against the List Of Qualifiers (a Q is listed by its order) and the
    final's start list (its eight starters and the same reserves)."""
    ctx = f'{disc} QUAL {app} qualifiers'
    rank_key = 'Qualification Rank'
    got = {r['Bib']: r['Qualification'] for r in rows if r['Qualification']}
    if got != {b: 'Q' if v.isdigit() else v for b, v in listed.items()}:
        err(f'{ctx}: table {got} != list {listed}')
    qs = [(int(r[rank_key]), int(listed.get(r['Bib'], '0'))) for r in rows if r['Qualification'] == 'Q']
    if sorted(qs) != sorted(qs, key=lambda x: x[1]):
        err(f'{ctx}: list numbers out of rank order {qs}')
    if len(qs) != 8:
        err(f'{ctx}: {len(qs)} qualifiers')
    reserves = {b: v for b, v in listed.items() if not v.isdigit()}
    if {b: v for b, v in start.items() if not v.isdigit()} != reserves:
        err(f'{ctx}: start list reserves differ from the qualifiers list')

def check_final(disc, app, qual_rows, final_rows, start):
    """The final's athletes are its start list's eight; any who didn't qualify were reserves."""
    marks = {r['Bib']: r['Qualification'] for r in qual_rows}
    finalists = {r['Bib'] for r in final_rows}
    starters = {b for b, v in start.items() if v.isdigit()}
    if finalists != starters:
        err(f'{disc} EVENT {app}: finalists {sorted(finalists)} != start list {sorted(starters)}')
    absent = sorted(b for b, m in marks.items() if m == 'Q' and b not in finalists)
    came_in = sorted(b for b in finalists if marks.get(b) != 'Q')
    for b in came_in:
        if marks.get(b) not in ('R1', 'R2', 'R3'):
            err(f'{disc} EVENT {app}: bib {b} in the final without qualifying ({marks.get(b)})')
    if absent or came_in:
        print(f'  {disc} EVENT {app}: qualifiers {absent} replaced by {[(b, marks[b]) for b in came_in]}')

def check_tie_breaks(disc):
    """Tie Break reports print the ranks the tables carry for every tied athlete. One follows the
    table it breaks; for vault, the vault 1 list or the two-vault list."""
    for i, p in enumerate(INFO):
        if p['disc'] != disc or p['title'] != 'Tie Break':
            continue
        ctx = f'{disc} {p["rnd"]} {p["app"]} tie break (p. {i + 1})'
        key = 'VT2' if p['app'] == 'VT' and is_two_vault(i - 1) else p['app']
        ranked = RANKED[(disc, p['rnd'], key)]
        n = 0
        for l in PAGES[i].split('\n'):
            m = re.match(r'^\s*=?(\d+)\s+(\d{1,3})\s+\S.*?\s{2,}(' + NOC + r')\s+(\d+\.\d{3})', l)
            if not m:
                continue
            n += 1
            rank, bib, _, total = m.groups()
            if ranked.get(bib) != (rank, total):
                err(f'{ctx}: bib {bib} rank {rank} total {total}, the results have {ranked.get(bib)}')
        if not n:
            err(f'{ctx}: no rows')

def check_qual_start_lists(disc):
    """The qualification start lists (subdivisions × rotations) name the same athletes as the
    results. They don't list one row per routine (an athlete appears in more rotations than they
    have routines), so only the sets are compared."""
    listed = set()
    for l in lines(find(disc, 'Start List', 'QUAL')):
        for m in re.finditer(r'(?<!\S)\d{1,2}\s+(\d{3})\s+\S.*?\s{2,}(' + NOC + r')(?!\S)', l):
            listed.add(m.group(1))
    if listed != COMPETED[disc]:
        err(f'{disc} QUAL start lists: differ from the results {sorted(listed ^ COMPETED[disc])}')

# ---------------------------------------------------------------- run
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    participants(disc)
    judges(disc)
    listed = grid_lists(disc, 'List Of Qualifiers', 'QUAL')
    starts = grid_lists(disc, 'Start List', 'EVENT')
    for app in APPS[disc]:
        q = app_results(disc, 'QUAL', app)
        check_qualifiers(disc, app, q, listed[app], starts[app])
        check_final(disc, app, q, app_results(disc, 'EVENT', app), starts[app])
    check_qual_start_lists(disc)
    check_tie_breaks(disc)
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])

check_entry_counts()
out.corrections.finish()
checks.finish()
