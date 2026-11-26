"""Parse the 2026 Mediterranean Games (Taranto) artistic gymnastics results book into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_mediterranean_games.py \\
        data/2026/2026-MEDITERRANEAN-GAMES/2026-MEDITERRANEAN-GAMES-ALL-RESULTS.pdf

Writes PARTICIPANTS, JUDGES, SCORES-{C1,C2,C3}-<APP>, RANKING-FINAL-TEAM (Competition I decides the
team title), RANKING-QUAL-AA and RANKING-FINAL-AA, and an IMPORT.json, per discipline next to the PDF, reading event metadata from
the EVENT.csv already there. Exits non-zero if any check fails (docs/instructions-results-parsing.md
§3; this source format is §5.6).

The book is the organizer's (Microplus timing) print of FIG-style reports: footer codes like
GARM1APFX----...QUAL..._C73I, but its own column layouts. Qualification decides the team title; the
all-around and apparatus finals follow. Every SCORES file comes from a "Results By Apparatus" table
(the all-around final prints one per apparatus too); the all-around, team, tie-break and qualifier
reports are cross-checks and the source of the summaries. The book's rhythmic pages are ignored.
"""
import os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import split_surname_first as split_name

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-MEDITERRANEAN-GAMES'
PAGES = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
out = common.Output(OUT, common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err))

PREFIX = {d: f'{EVENT_PREFIX}-{d}-SR' for d in ('MAG', 'WAG')}
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
# Column order of the icon-headed all-around and team reports; their printed legend lists the
# apparatus in reverse. Proven by the cross-check of every value against the per-apparatus tables.
REPORT_APPS = APPS
# Panels in the Judges Assignment grid, left-to-right then top-to-bottom (the legend's order). The
# data agrees: MAG FX has the time and line judges, VT a line judge; WAG BB has two time judges.
GRID = APPS
# From the Competition Schedule pages (§4.4). Team titles were decided in qualification.
SESSION_DATE = {
    'MAG': {'QUAL': '2026-08-31', 'AA': '2026-09-01', 'EVENT': '2026-09-02'},
    'WAG': {'QUAL': '2026-08-30', 'AA': '2026-09-01', 'EVENT': '2026-09-02'},
}
GENDER = {'MAG': "Men's Artistic Gymnastics", 'WAG': "Women's Artistic Gymnastics"}
ROUND_TITLE = {'QUAL': 'Qualification', 'AA': 'All-Around Final', 'EVENT': 'Apparatus Final'}
MARKERS = ('Q', 'R1', 'R2', 'R3', 'NR')

def strip_inquiry(d):
    return d.lstrip('!').strip()

# ---------------------------------------------------------------- page lookup
TITLES = ('Number of Entries by NOC', 'Entry List By BIB', 'Team Composition', 'Judges Assignment',
          'Results By Apparatus', 'All-Around Results', 'Team Results', 'All-Around Tie Break', 'Tie Break',
          'List Of Qualifiers', 'Start List')

def page_info(i):
    ls = [l.strip() for l in PAGES[i].split('\n') if l.strip()]
    if not any(l.endswith('Artistic Gymnastics') for l in ls[:2]):
        return dict(disc=None, rnd=None, title='', code='', app=None)   # cover, rhythmic pages
    disc = next((d for d, g in GENDER.items() if g in ls[:4]), 'ALL')
    rnd = next((r for r, t in ROUND_TITLE.items() if t in ls[:5]), None)
    title = next((t for l in ls[1:6] for t in TITLES if l.startswith(t)), '')
    code = next((l.split()[0] for l in reversed(ls) if re.search(r'Page \d+ / \d+$', l)), '')
    app = re.match(r'GAR[MW]1AP([A-Z]{2})-', code)
    return dict(disc=disc, rnd=rnd, title=title, code=code, app=app.group(1) if app else None)

INFO = [page_info(i) for i in range(len(PAGES))]

def find(disc, title, rnd=None, app=None, code=None):
    idx = [i for i, p in enumerate(INFO) if p['disc'] == disc and p['title'] == title
           and (rnd is None or p['rnd'] == rnd) and (app is None or p['app'] == app)
           and (code is None or code in p['code'])]
    if not idx:
        raise SystemExit(f'no pages for {disc} {title} {rnd} {app} {code}')
    return idx

def lines(idx):
    return [l for i in idx for l in PAGES[i].split('\n')]

# ---------------------------------------------------------------- participants
MONTHS = {m: i + 1 for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split())}
NAMES = {}            # disc -> bib -> (name, noc)
COMPETED = defaultdict(set)   # disc -> bibs with at least one routine

def entry_rows(idx, pattern):
    return [m.groups() for l in lines(idx) for m in [re.match(pattern, l)] if m]

def participants(disc):
    ctx = f'{disc} participants'
    ev = EVENTS[PREFIX[disc]]
    rows, NAMES[disc] = [], {}
    for order, noc, bib, lic, name, d, mon, y in entry_rows(
            find(disc, 'Entry List By BIB'),
            r'^\s+(\d+)\s+([A-Z]{3})\s+(\d+)\s+(\d+)\s+(\S.*?)\s{2,}(\d{1,2}) ([A-Z][a-z]{2}) (\d{4})\s*$'):
        sur, giv = split_name(name)
        if not sur or not giv:
            err(f'{ctx}: name split {name!r} -> {sur!r}/{giv!r}')
        if bib in NAMES[disc]:
            err(f'{ctx}: duplicate bib {bib}')
        NAMES[disc][bib] = (name, noc)
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                     'Event Start Date': ev['Start Date'], 'Order': order, 'NOC Code': noc,
                     'Bib Number': bib, 'FIG License': lic, 'Name': name, 'Surname': sur,
                     'Given Name': giv, 'Birth Year': y,
                     'Birth Date': f'{y}-{MONTHS[mon]:02d}-{int(d):02d}'})
    if [int(r['Order']) for r in rows] != list(range(1, len(rows) + 1)):
        err(f'{ctx}: entry list order is not 1..{len(rows)}')
    # The "Number of Entries by NOC" list and the Team Composition repeat every entry
    by_bib = {r['Bib Number']: r for r in rows}
    entries = entry_rows(find(disc, 'Number of Entries by NOC'),
                         r'^\s{10,}(\S.*?)\s{2,}(\d+)\s+(\d+)\s+(\d{1,2}) ([A-Z][a-z]{2}) (\d{4})\s*$')
    teams = entry_rows(find(disc, 'Team Composition'),
                       r'^\s+(\d+)\s+(\d+)\s+(\S.*?)\s{2,}(\d{1,2}) ([A-Z][a-z]{2}) (\d{4})\s*$')
    for name, bib, lic, d, mon, y in entries:
        r = by_bib.get(bib)
        if not r or (r['Name'], r['FIG License'], r['Birth Date']) != (name, lic, f'{y}-{MONTHS[mon]:02d}-{int(d):02d}'):
            err(f'{ctx}: entries-by-NOC bib {bib} {name} differs from the entry list')
    if len(entries) != len(rows):
        err(f'{ctx}: {len(entries)} on the entries-by-NOC list, {len(rows)} on the entry list')
    for bib, lic, name, *_ in teams:
        if bib not in by_bib or by_bib[bib]['Name'] != name:
            err(f'{ctx}: team composition bib {bib} {name} not on the entry list')
    print(f'  {ctx}: {len(rows)} entries, {len(teams)} in teams')
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)

def check_name(disc, ctx, bib, name, noc):
    if bib not in NAMES[disc]:
        err(f'{ctx}: bib {bib} not in participants'); return name
    full, pnoc = NAMES[disc][bib]
    if pnoc != noc:
        err(f'{ctx}: bib {bib} NOC {noc} != participants {pnoc}')
    if name != full:
        err(f'{ctx}: bib {bib} {name!r} != participants {full!r}')
    return full

def check_entry_counts():
    """The general "Number of Entries by NOC" page counts each country's competitors: every entry
    with a routine (entered team members who never competed aren't counted)."""
    ls = lines(find('ALL', 'Number of Entries by NOC'))
    h = next(l for l in ls if re.match(r'^\s+Men\s+Women\s+Total', l))
    heads = [h.index(w) + len(w) for w in ('Men', 'Women', 'Total')]
    n = 0
    for l in ls:
        m = re.match(r'^\s+([A-Z]{3}) - .+?\s{2,}(\d.*)$', l)
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
    if n != len({noc for d in COMPETED for b in COMPETED[d] for noc in [NAMES[d][b][1]]}):
        err(f'entry counts: {n} countries listed')

# ---------------------------------------------------------------- judges
FUNCTION = r'(D\d|E\d|[TL]\d?|RES(?: \d)?)'

def judge_fn(f):
    m = re.fullmatch(r'RES(?: (\d))?', f)
    return 'R' + (m.group(1) or '') if m else f

def judges(disc):
    ev = EVENTS[PREFIX[disc]]
    rows = []
    def add(rnd, app, fn, name, noc):
        sur, giv = split_name(name)
        if not sur or not giv:
            err(f'judges {disc}: name split {name!r}')
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                     'Event Start Date': ev['Start Date'], 'Competition': common.COMPETITION[rnd], 'Apparatus': app, 'Function': fn,
                     'Name': name, 'Surname': sur, 'Given Name': giv, 'NOC Code': noc})
    for rnd in ('QUAL', 'AA', 'EVENT'):
        idx = find(disc, 'Judges Assignment', rnd)
        if len(idx) != 1:
            err(f'judges {disc} {rnd}: {len(idx)} pages')
        n0, block, split_at = len(rows), -1, None
        for l in lines(idx):
            m = re.match(r'^\s+(President|Vice-President|Member)\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', l)
            if m and block < 0:
                # The Superior Jury is credited to FIG, which isn't a federation: written blank (§4.7)
                noc = '' if m.group(3) == 'FIG' else m.group(3)
                add(rnd, '', m.group(1), m.group(2), noc)
                continue
            if re.match(r'^\s+Function\s+Name\s+NOC Code\s+Function\s+Name', l):
                block += 1
                split_at = l.index('Function', l.index('NOC Code'))
                continue
            if l.strip().startswith('LEGEND'):
                break
            if block < 0 or not l.strip():
                continue
            for side, part in ((0, l[:split_at]), (1, l[split_at:])):
                if not part.strip():
                    continue
                m = re.match(r'^\s*' + FUNCTION + r'\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', part)
                if m:
                    add(rnd, GRID[disc][block * 2 + side], judge_fn(m.group(1)), m.group(2), m.group(3))
                else:
                    err(f'judges {disc} {rnd}: unparsed {part!r}')
        if block + 1 != len(GRID[disc]) // 2:
            err(f'judges {disc} {rnd}: {block + 1} panel rows')
        for app in GRID[disc]:
            fns = {r['Function'] for r in rows[n0:] if r['Apparatus'] == app}
            if not {'D1', 'D2', 'E1', 'E2', 'E3', 'E4'} <= fns:
                err(f'judges {disc} {rnd} {app}: incomplete panel {sorted(fns)}')
        print(f'  judges {disc} {rnd}: {len(rows) - n0}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, rows)

# ---------------------------------------------------------------- apparatus tables
ID = r'^\s*(\d+)?\s+(\d{1,3})\s+(\S.*?)\s{2,}([A-Z]{3})\s+'

def header(ls, ctx):
    for l in ls:
        if re.match(r'^\s*Rank\s+Bib\s', l):
            return l
    err(f'{ctx}: no header'); return ''

def col(h, label):
    m = re.search(r'(?<!\S)' + re.escape(label) + r'(?!\S)', h)
    return m.start() if m else None

def check_routine(ctx, r):
    checks.check_sum(ctx, r['Total'], strip_inquiry(r['D']), r['E'], r['B'], r['Penalty'], r['SJ Penalty'])

def routine(tokens, h, ctx, vault_line=False):
    """Values of one routine, in the header's order: D/E (either order), B (MAG but pommel horse),
    then Penalty and SJ Pen, placed by position, and the score. `tokens` are (start, text)."""
    e_first = col(h, 'E') < col(h, 'D')
    has_b = col(h, 'B') is not None
    vals = [t for _, t in tokens]
    r = dict(Status='COMPLETED', D='', E='', B='', Penalty='', **{'SJ Penalty': ''}, Total='')
    first, second = vals[0], vals[1]
    if vals[0] == '!' or vals[1] == '!':
        err(f'{ctx}: detached inquiry mark')
    r['E'], r['D'] = (first, second) if e_first else (second, first)
    i = 2
    if has_b:
        r['B'] = vals[i]; i += 1
    score_at = len(vals) - 1
    if not re.fullmatch(r'!?\d+\.\d', r['D']) or not re.fullmatch(r'\d+\.\d{3}', r['E']) \
            or (has_b and not re.fullmatch(r'\d\.\d', r['B'])):
        err(f'{ctx}: unexpected values {vals}')
    pen_col = col(h, 'Pen' if vault_line else 'Penalty')
    sj_col = col(h, 'SJ Pen.') or col(h, 'SJ Pen')
    for pos, v in tokens[i:score_at]:
        if not re.fullmatch(r'-\d+\.\d+', v):
            err(f'{ctx}: unexpected token {v!r}'); continue
        key = 'Penalty' if abs(pos - pen_col) < abs(pos - sj_col) else 'SJ Penalty'
        if r[key]:
            err(f'{ctx}: two values for {key}')
        r[key] = v
    r['Total'] = vals[score_at]
    if not re.fullmatch(r'\d+\.\d{3}', r['Total']):
        err(f'{ctx}: bad score {r["Total"]!r}')
    check_routine(ctx, r)
    return r

def tokens_of(l, start):
    return [(start + m.start(), m.group()) for m in re.finditer(r'\S+', l[start:])]

def single_table(idx, ctx):
    """One-routine "Results By Apparatus" table -> rows in printed order."""
    ls = lines(idx)
    rows = []
    h = None
    for l in ls:
        if re.match(r'^\s*Rank\s+Bib\s', l):
            h = l; continue
        m = re.match(ID + r'(.*)$', l)
        if not m or h is None:
            continue
        rank, bib, name, noc, _ = m.groups()
        t = tokens_of(l, m.start(5))
        vals = [v for _, v in t]
        if vals[-1] == 'DNS':
            if rank or vals[:-1] not in ([], ['0.000']):
                err(f'{ctx}: odd DNS row {l!r}')
            rows.append(dict(Rank='', Bib=bib, Name=name, NOC=noc, Status='DNS', D='', E='', B='', Penalty='',
                             **{'SJ Penalty': ''}, Total='', Q=''))
            continue
        q = ''
        if vals[-1] in MARKERS:
            q = vals[-1]; t = t[:-1]
        r = routine(t, h, f'{ctx} bib {bib}')
        rows.append(dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, Q=q, **r))
    n_rank = sum(1 for l in ls if re.match(r'^\s*\d+\s+\d{1,3}\s+[A-Z]', l))
    n_dns = sum(1 for l in ls if re.search(r'\sDNS\s*$', l))
    if n_rank + n_dns != len(rows):
        err(f'{ctx}: parsed {len(rows)} rows, counted {n_rank} ranked + {n_dns} DNS')
    checks.check_rank_order(ctx, rows)
    return rows

def double_table(idx, ctx):
    """Two-vault table: each vaulter on two lines (`1 …` and `2 …`) -> rows with v1, v2, Total."""
    ls = lines(idx)
    rows, cur, h = [], None, None
    for l in ls:
        if re.match(r'^\s*Rank\s+Bib\s', l):
            h = l; continue
        if h is None:
            continue
        m = re.match(ID + r'1\s+(.*)$', l)
        if m:
            rank, bib, name, noc, _ = m.groups()
            t = tokens_of(l, m.start(5))
            q = ''
            if t[-1][1] in MARKERS:
                q = t.pop()[1]
            total = t.pop()[1]
            bonus = ''
            if total.endswith('*'):
                total, bonus = total[:-1], '0.2'
            if total != 'DNF' and not re.fullmatch(r'\d+\.\d{3}', total):
                err(f'{ctx} bib {bib}: bad total {total!r}')
            v1 = routine(t, h, f'{ctx} bib {bib} v1', vault_line=True)
            cur = dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, v1=v1, Bonus=bonus,
                       Total='' if total == 'DNF' else total, Q=q)
            rows.append(cur)
            continue
        m = re.match(r'^\s+2\s+(.*)$', l)
        if m and cur is not None and 'v2' not in cur:
            t = tokens_of(l, m.start(1))
            if t[-1][1] == 'DNS':
                if [v for _, v in t[:-1]] not in ([], ['0.0']):
                    err(f'{ctx} bib {cur["Bib"]}: odd DNS line {l!r}')
                cur['v2'] = dict(Status='DNS', D='', E='', B='', Penalty='', **{'SJ Penalty': ''}, Total='')
                if cur['Total'] or cur['Rank']:
                    err(f'{ctx} bib {cur["Bib"]}: vault 2 DNS with a result')
            else:
                cur['v2'] = routine(t, h, f'{ctx} bib {cur["Bib"]} v2', vault_line=True)
                checks.check_vault_average(f'{ctx} bib {cur["Bib"]}', cur['v1']['Total'], cur['v2']['Total'],
                                           cur['Bonus'], cur['Total'])
            continue
        if re.match(r'^\s*\d+\s+\d{1,3}\s+[A-Z]', l):
            err(f'{ctx}: unparsed {l!r}')
    if any('v2' not in r for r in rows):
        err(f'{ctx}: missing vault 2 line')
    n_id = sum(1 for l in ls if re.match(ID + r'1\s', l))
    if n_id != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_id}')
    checks.check_rank_order(ctx, rows)
    return rows

def meta(disc, rnd, app):
    return {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
            'Competition Start Date': SESSION_DATE[disc][rnd], 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app}

ROUTINE_KEYS = ['Status', 'D', 'E', 'B', 'Penalty', 'SJ Penalty', 'Total']

def ident(disc, rnd, app, r):
    ctx = f'{disc} {rnd} {app}'
    COMPETED[disc].add(r['Bib'])
    return meta(disc, rnd, app) | {'Rank': r['Rank'], 'Bib': r['Bib'], 'NOC Code': r['NOC'],
                                   'Name': check_name(disc, ctx, r['Bib'], r['Name'], r['NOC'])}

def vault_cols(n, v):
    return {f'{k}{n}': v[k] for k in ROUTINE_KEYS}

SCORES = defaultdict(dict)   # (disc, rnd) -> (app, bib) -> {Rank, D, E, Total, Status}
# Routines a qualification table leaves out (§5.6): WAG vault 1, KURTULUS (TUR)
OMITTED = {('WAG', 'VT'): ['152']}

def remember(disc, rnd, app, bib, rank, r):
    SCORES[(disc, rnd)][(app, bib)] = dict(Rank=rank, D=strip_inquiry(r['D']), E=r['E'], Total=r['Total'],
                                           Status=r['Status'])

def app_results(disc, rnd, app):
    """SCORES-<rnd>-<app>; returns the rows as parsed, for the qualifier cross-checks."""
    ctx = f'{disc} {rnd} {app}'
    idx = find(disc, 'Results By Apparatus', rnd, app)
    qual = rnd == 'QUAL'
    if app == 'VT' and rnd != 'AA':
        doubles = [i for i in idx if 'Vault Score' in header(PAGES[i].split('\n'), ctx)]
        singles = [i for i in idx if i not in doubles]
        if rnd == 'EVENT':
            if singles: err(f'{ctx}: unexpected one-vault pages {singles}')
            rows = []
            for r in double_table(doubles, ctx):
                rows.append(ident(disc, rnd, app, r) | vault_cols(1, r['v1']) | vault_cols(2, r['v2'])
                            | {'Combined Bonus': r['Bonus'], 'Total': r['Total']})
            out.csv(f'{PREFIX[disc]}-SCORES-C3-VT.csv', common.score_header(True, False), rows)
            return rows
        single = single_table(singles, ctx + ' vault 1')
        double = {r['Bib']: r for r in double_table(doubles, ctx + ' two-vault')}
        for bib in OMITTED.get((disc, 'VT'), []):
            # The vault 1 table leaves this vault out; the routine is the all-around report's, its
            # rank (and the shifted ranks below it) are corrections
            if any(s['Bib'] == bib for s in single):
                err(f'{ctx}: bib {bib} is no longer missing from the vault 1 table')
            a = next(a for a in aaq if a['Bib'] == bib)
            x = a['apps']['VT']
            s = dict(Rank='', Bib=bib, Name=a['Name'], NOC=a['NOC'], Status='COMPLETED', D=x['D'], E=x['E'],
                     B=x['B'], Penalty=x['Penalty'], **{'SJ Penalty': ''}, Total=x['Total'])
            at = next(i for i, r in enumerate(single) if not r['Total'] or common.D(r['Total']) < common.D(s['Total']))
            single.insert(at, s)
        rows = []
        for s in single:
            v1 = {k: s[k] for k in ROUTINE_KEYS}
            if v1['Status'] == 'COMPLETED' and common.D(v1['Total']) == 0:
                v1['Status'] = 'INVALID_VAULT'
            s['v1'] = v1
            r = double.pop(s['Bib'], None)
            if r is None:
                v2 = dict.fromkeys(ROUTINE_KEYS, '')
                extra = {'Combined Bonus': '', 'Total': v1['Total'], 'Qualification': '', 'Qualification Rank': ''}
            else:
                if r['v1'] != v1:
                    err(f'{ctx} bib {s["Bib"]}: vault 1 differs between lists: {v1} vs {r["v1"]}')
                v2 = r['v2']
                extra = {'Combined Bonus': r['Bonus'], 'Total': r['Total'], 'Qualification': r['Q'],
                         'Qualification Rank': r['Rank']}
            rows.append(ident(disc, rnd, app, s) | vault_cols(1, v1) | vault_cols(2, v2) | extra)
        if double:
            err(f'{ctx}: two-vault bibs missing from the vault 1 list: {list(double)}')
        out.csv(f'{PREFIX[disc]}-SCORES-C1-VT.csv', common.score_header(True, True), rows)
        # Cross-checks see the written (corrected) ranks
        for s, row in zip(single, rows):
            remember(disc, rnd, app, s['Bib'], row['Rank'], s['v1'])
        checks.check_rank_order(ctx, [dict(Rank=r['Rank'], Total=r['Total1'], Bib=r['Bib']) for r in rows])
        return [r for r in rows if r['Qualification Rank'] or r['Qualification']]
    rows = []
    for r in single_table(idx, ctx):
        if app == 'VT' and r['Status'] == 'COMPLETED' and common.D(r['Total']) == 0:
            r['Status'] = 'INVALID_VAULT'
        remember(disc, rnd, app, r['Bib'], r['Rank'], r)
        if r['Q'] and not qual:
            err(f'{ctx} bib {r["Bib"]}: marker {r["Q"]} on a final')
        row = ident(disc, rnd, app, r) | {k: r[k] for k in ROUTINE_KEYS}
        if qual:
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        rows.append(row)
    out.csv(f'{PREFIX[disc]}-SCORES-{common.COMPETITION[rnd]}-{app}.csv', common.score_header(False, qual), rows)
    return rows

# ---------------------------------------------------------------- qualifiers and tie-breaks
def qualifier_list(disc):
    """List Of Qualifiers: per apparatus (same grid as the judges), the Q athletes numbered by
    rank, then R1-R3 and NR as on the tables."""
    out_ = {app: {} for app in APPS[disc]}
    block, split_at = -1, None
    for l in lines(find(disc, 'List Of Qualifiers')):
        if re.match(r'^\s*Order\s+Bib\s+Description\s+NOC\s+Order', l):
            block += 1
            split_at = l.index('Order', l.index('NOC'))
            continue
        if l.strip().startswith('LEGEND'):
            break
        if block < 0 or not l.strip():
            continue
        for side, part in ((0, l[:split_at]), (1, l[split_at:])):
            if not part.strip():
                continue
            m = re.match(r'^\s*(\d+|R\d|NR)\s+(\d{1,3})\s+\S.*?\s{2,}([A-Z]{3})\s*$', part)
            if not m:
                err(f'{disc} qualifiers: unparsed {part!r}'); continue
            out_[GRID[disc][block * 2 + side]][m.group(2)] = m.group(1)
    return out_

def check_qualifiers(disc, app, rows, listed):
    """The table's markers against the List Of Qualifiers (a Q is listed by its rank)."""
    ctx = f'{disc} QUAL {app} qualifiers'
    rank_key = 'Qualification Rank' if app == 'VT' else 'Rank'
    got = {r['Bib']: r['Qualification'] for r in rows if r['Qualification']}
    if got != {b: 'Q' if v.isdigit() else v for b, v in listed.items()}:
        err(f'{ctx}: table {got} != list {listed}')
    # The list numbers its qualifiers in rank order, one number each even when the table ties them
    qs = [(int(r[rank_key]), int(listed.get(r['Bib'], '0'))) for r in rows if r['Qualification'] == 'Q']
    if sorted(qs) != sorted(qs, key=lambda x: x[1]):
        err(f'{ctx}: list numbers out of rank order {qs}')
    ranks = sorted(rank for rank, _ in qs)
    if len(ranks) < 8 or (len(ranks) > 8 and ranks[7] != ranks[-1]):
        err(f'{ctx}: {len(ranks)} qualifiers, ranks {ranks}')

def check_final(disc, app, qual_rows, final_rows):
    """Every finalist qualified or was a reserve, or, two-per-country, replaced a compatriot;
    report the reserves who came in."""
    marks = {r['Bib']: r['Qualification'] for r in qual_rows}
    noc = {r['Bib']: r['NOC Code'] for r in qual_rows}
    finalists = {r['Bib'] for r in final_rows}
    absent = sorted(b for b, m in marks.items() if m == 'Q' and b not in finalists)
    came_in = sorted(b for b in finalists if marks.get(b) != 'Q')
    for b in came_in:
        ok = marks.get(b) in ('R1', 'R2', 'R3') or \
            (marks.get(b) == 'NR' and any(noc[a] == noc[b] for a in absent))
        if not ok:
            err(f'{disc} EVENT {app}: bib {b} in the final without qualifying ({marks.get(b)})')
    if absent or came_in:
        print(f'  {disc} EVENT {app}: qualifiers {absent} replaced by {[(b, marks[b]) for b in came_in]}')
    if len(finalists) != sum(1 for m in marks.values() if m == 'Q'):
        err(f'{disc} EVENT {app}: {len(finalists)} finalists')

def check_tie_breaks(disc):
    """Tie Break reports print the ranks the tables should carry for every tied athlete."""
    for i, p in enumerate(INFO):
        if p['disc'] != disc or not p['title'].endswith('Tie Break'):
            continue
        rnd = p['rnd']
        ctx = f'{disc} {rnd} {p["app"] or "AA"} tie break (p. {i + 1})'
        # A tie-break report follows the table it breaks; for vault, the vault 1 or the two-vault list
        two_vault = p['app'] == 'VT' and 'Vault Score' in PAGES[i - 1]
        n = 0
        for l in PAGES[i].split('\n'):
            m = re.match(r'^\s*=?(\d+)\s+(\d{1,3})\s+\S.*?\s{2,}([A-Z]{3})\s+(\d+\.\d{3})', l)
            if not m:
                continue
            n += 1
            rank, bib, _, total = m.groups()
            if p['app'] is None:
                want = AA_RANKS[(disc, rnd)].get(bib)
            else:
                want = (VT_DOUBLE[(disc, rnd)] if two_vault else SCORES[(disc, rnd)]).get(
                    bib if two_vault else (p['app'], bib))
            if not want or (want['Rank'], want['Total']) != (rank, total):
                err(f'{ctx}: bib {bib} rank {rank} total {total}, the results have {want}')
        if not n:
            err(f'{ctx}: no rows')

VT_DOUBLE = defaultdict(dict)   # (disc, rnd) -> bib -> {Rank, Total} on the two-vault list

# ---------------------------------------------------------------- all-around and team reports
TRIPLE = re.compile(r'DNS|(!\s*)?(\d+\.\d)\s+(\d+\.\d{3})\s+(\d+)')
E_ITEM = re.compile(r'(?<![\d.])(?:(\d+\.\d{3})\s+)?(-?\d+\.\d{2})(?![\d.])(?:\s+(\d\.\d)(?![\d.]))?')

def heading_columns(l):
    """(D start, Total start) of each apparatus's `D Total Rk.` heading."""
    return [(m.start(1), m.start(2)) for m in re.finditer(r'(?<!\S)(D)\s+(Total)', l)]

def place(cols, m):
    """The column of a `D Total Rk` match (printed under D) or a DNS (printed under Total)."""
    k = 1 if m.group() == 'DNS' else 0
    return min(range(len(cols)), key=lambda a: abs(cols[a][k] - m.start()))

def d_line(l, cols, apps_order, ctx):
    apps = {}
    for t in TRIPLE.finditer(l):
        app = apps_order[place(cols, t)]
        if app in apps:
            err(f'{ctx}: two values under {app}')
        apps[app] = None if t.group() == 'DNS' else dict(D=t.group(2), Total=t.group(3), Rank=t.group(4))
    return apps

def e_line(l, cols, apps, apps_order, ctx):
    """`E Pen. [B]` under each routine's D; a zero penalty prints 0.00 and is written blank. A zero
    E (an invalid vault) prints nothing, and its 0.00 then sits under the Total heading."""
    for m in E_ITEM.finditer(l):
        k, pos = (0, m.start(1)) if m.group(1) else (1, m.start(2))
        app = apps_order[min(range(len(cols)), key=lambda a: abs(cols[a][k] - pos))]
        x = apps.get(app)
        if x is None:
            continue
        if 'E' in x:
            err(f'{ctx}: two E values under {app}')
        x['E'] = m.group(1) or ''
        x['Penalty'] = '' if common.D(m.group(2)) == 0 else m.group(2)
        x['B'] = m.group(3) or ''

def check_against_tables(disc, rnd, ctx, bib, apps):
    for app, x in apps.items():
        want = SCORES[(disc, rnd)].get((app, bib))
        if x is None:
            if not want or want['Status'] != 'DNS':
                err(f'{ctx} {app}: DNS, table has {want}')
            continue
        # A zero E prints blank on the report (an invalid vault)
        got = {k: x[k] for k in ('Rank', 'D', 'E', 'Total') if k in x and (x[k] or common.D(x['Total']))}
        if not want or {k: want[k] for k in got} != got:
            err(f'{ctx} {app}: {got}, table has {want}')
    for (app, b), want in SCORES[(disc, rnd)].items():
        if b == bib and app not in apps:
            err(f'{ctx} {app}: in the apparatus table but not in the report')

AA_RANKS = defaultdict(dict)   # (disc, rnd) -> bib -> {Rank, Total}

def aa_report(disc, rnd):
    """All-Around Results: per athlete a `D Total Rk` line, the identity line, an `E Pen. B` line
    and a total line (with the qualification marker)."""
    ctx0 = f'{disc} {rnd} AA'
    idx = find(disc, 'All-Around Results', rnd)
    ls = lines(idx)
    apps_order = REPORT_APPS[disc]
    athletes, cols = [], []
    for i, l in enumerate(ls):
        if re.match(r'^\s+D\s+Total\s+Rk\.', l):
            cols = heading_columns(l)
            if len(cols) != len(apps_order):
                err(f'{ctx0}: {len(cols)} columns')
            continue
        m = re.match(r'^\s*(\d+)?\s+(\d{1,3})\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', l)
        if not m:
            continue
        rank, bib, name, noc = m.groups()
        ctx = f'{ctx0} bib {bib}'
        apps = d_line(ls[i - 1], cols, apps_order, ctx)
        e_line(ls[i + 1], cols, apps, apps_order, ctx)
        for app, x in apps.items():
            if x is not None and 'E' not in x:
                err(f'{ctx} {app}: no E value'); x.update(E='', B='', Penalty='')
            if x is not None:
                checks.check_sum(f'{ctx} {app}', x['Total'], x['D'], x['E'], x['B'], x['Penalty'])
        tail = ls[i + 2].split()
        if not tail or not re.fullmatch(r'\d+\.\d{3}|DNF', tail[0]) or len(tail) > 2 \
                or (len(tail) == 2 and tail[1] not in MARKERS):
            err(f'{ctx}: total line {ls[i + 2]!r}'); continue
        total, q = tail[0], (tail[1] if len(tail) == 2 else '')
        if total == 'DNF':
            if rank: err(f'{ctx}: ranked DNF')
            total = ''
        else:
            if len(apps) != len(apps_order) or None in apps.values():
                err(f'{ctx}: {len(apps)} apparatus for a full all-around')
            s = sum(common.D(v['Total']) for v in apps.values())
            if s != common.D(total):
                err(f'{ctx}: apparatus sum {s} != {total}')
        athletes.append(dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, apps=apps, Total=total, Q=q))
        AA_RANKS[(disc, rnd)][bib] = dict(Rank=rank or '', Total=total)
    n_id = sum(1 for l in ls if re.match(r'^\s*(\d+)?\s+\d{1,3}\s+\S.*?\s{2,}[A-Z]{3}\s*$', l))
    if n_id != len(athletes):
        err(f'{ctx0}: parsed {len(athletes)} of {n_id}')
    checks.check_rank_order(ctx0, athletes)
    return athletes

def summary_aa(disc, rnd, athletes):
    ev = EVENTS[PREFIX[disc]]
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'Bib', 'Name',
           'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total']
    if rnd == 'QUAL':
        hdr.append('Qualification')
    rows = []
    for a in athletes:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Competition': common.COMPETITION[rnd], 'Part': '', 'Rank': a['Rank'], 'Bib': a['Bib'],
             'Name': check_name(disc, f'{disc} {rnd} AA summary', a['Bib'], a['Name'], a['NOC']),
             'NOC Code': a['NOC'], 'SJ Penalty': '', 'Total': a['Total'], 'Qualification': a['Q']}
        for app in SUMMARY_APPS[disc]:
            x = a['apps'].get(app)
            r[f'{app} Total'] = x['Total'] if x else ''
        rows.append(r)
    out.ranking(PREFIX[disc], 'AA', hdr, rows, EVENTS[PREFIX[disc]])

def check_aa_final(disc, qual, final):
    marks = {a['Bib']: a['Q'] for a in qual}
    q = {b for b, m in marks.items() if m == 'Q'}
    fin = {a['Bib'] for a in final}
    for b in fin - q:
        if not marks.get(b, '').startswith('R'):
            err(f'{disc} AA final: bib {b} competed without qualifying ({marks.get(b)})')
    print(f'  {disc} AA final: {len(fin)} athletes; qualifiers absent {sorted(q - fin)}, '
          f'reserves in {sorted(b for b in fin - q)}')

def team_report(disc):
    """Team Results (qualification): a team line with the apparatus totals, then each member's
    `D Total Rk` line above their name. The E/penalty lines and member totals print out of line
    (pdftotext moves the last column's values onto the name line), so only the D lines are read;
    the member totals are checked against the all-around report."""
    ctx0 = f'{disc} QUAL team'
    ls = lines(find(disc, 'Team Results', 'QUAL'))
    n = len(REPORT_APPS[disc])
    teams, team, cols = [], None, []
    for i, l in enumerate(ls):
        if re.match(r'^\s+D Total Rk\.', l):
            cols = heading_columns(l)
            continue
        m = re.match(r'^\s*(\d+)\s+(\S.*?)\s{2,}([A-Z]{3})\s+((?:\d+\.\d{3}\s+){%d})(?:(\d+\.\d)\s+)?(\d+\.\d{3})\s*$'
                     % n, l)
        if m:
            rank, _, noc, totals, sj, total = m.groups()
            # A team penalty prints unsigned in the SJ Pen column; written negative, as deducted (§4.3)
            team = dict(Rank=rank, NOC=noc, totals=dict(zip(REPORT_APPS[disc], totals.split())), Total=total,
                        SJ='-' + sj if sj else '', members=[])
            teams.append(team)
            continue
        m = re.match(r'^\s{5,}([A-Z][A-Z\'-]+(?: [A-Za-z\'-]+)*?(?: [A-Z][a-z\S]*)+)(?:\s{2,}|\s*$)', l)
        if m and team is not None and not re.search(r'\d+\.\d{3}\s+\d+\s*$', l):
            name = m.group(1).strip()
            apps = d_line(ls[i - 1], cols, REPORT_APPS[disc], f'{ctx0} {name}')
            bib = next((b for b, (nm, noc) in NAMES[disc].items() if nm == name and noc == team['NOC']), None)
            if bib is None:
                err(f'{ctx0} {team["NOC"]}: member {name!r} not on the entry list'); continue
            check_against_tables(disc, 'QUAL', f'{ctx0} {team["NOC"]} bib {bib}', bib, apps)
            team['members'].append(dict(Bib=bib, apps=apps))
    for t in teams:
        for app in REPORT_APPS[disc]:
            sc = sorted((common.D(x['apps'][app]['Total']) for x in t['members']
                         if x['apps'].get(app)), reverse=True)
            if sum(sc[:3]) != common.D(t['totals'][app]):
                err(f'{ctx0} {t["NOC"]} {app}: best three {sum(sc[:3])} != {t["totals"][app]}')
        if sum(common.D(v) for v in t['totals'].values()) + common.D(t['SJ']) != common.D(t['Total']):
            err(f'{ctx0} {t["NOC"]}: apparatus totals != {t["Total"]}')
    n_team = sum(1 for p in INFO if p['disc'] == disc and p['title'] == 'Team Results')
    checks.check_rank_order(ctx0, [dict(Rank=t['Rank'], Total=t['Total'], Bib=t['NOC']) for t in teams])
    # Every member with a routine is in the qualification tables, and the reverse for team countries
    in_teams = {x['Bib'] for t in teams for x in t['members'] if any(x['apps'].values())}
    team_nocs = {t['NOC'] for t in teams}
    tabled = {b for (_, b) in SCORES[(disc, 'QUAL')] if NAMES[disc][b][1] in team_nocs}
    if in_teams != tabled:
        err(f'{ctx0}: members with routines {sorted(in_teams ^ tabled)} differ from the tables')
    print(f'  {ctx0}: {len(teams)} teams on {n_team} pages')
    return teams

def summary_team(disc, teams):
    ev = EVENTS[PREFIX[disc]]
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'NOC Code'] + \
          [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for t in teams:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Competition': 'C1', 'Part': '', 'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': t['SJ'],
             'Total': t['Total'], 'Qualification': ''}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = t['totals'][app]
        rows.append(r)
    out.ranking(PREFIX[disc], 'TEAM', hdr, rows, EVENTS[PREFIX[disc]])

# ---------------------------------------------------------------- run
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    participants(disc)
    judges(disc)
    listed = qualifier_list(disc)
    aaq = aa_report(disc, 'QUAL')   # read first: it supplies routines a table leaves out (OMITTED)
    aaf = aa_report(disc, 'AA')
    for app in APPS[disc]:
        q = app_results(disc, 'QUAL', app)
        if app == 'VT':
            for r in q:
                VT_DOUBLE[(disc, 'QUAL')][r['Bib']] = dict(Rank=r['Qualification Rank'], Total=r['Total'])
        check_qualifiers(disc, app, q, listed[app])
        f = app_results(disc, 'EVENT', app)
        if app == 'VT':
            for r in f:
                VT_DOUBLE[(disc, 'EVENT')][r['Bib']] = dict(Rank=r['Rank'], Total=r['Total'])
        check_final(disc, app, q, f)
        app_results(disc, 'AA', app)
    for rnd, athletes in (('QUAL', aaq), ('AA', aaf)):
        for a in athletes:
            check_against_tables(disc, rnd, f'{disc} {rnd} AA bib {a["Bib"]}', a['Bib'], a['apps'])
    summary_aa(disc, 'QUAL', aaq)
    summary_aa(disc, 'AA', aaf)
    check_aa_final(disc, aaq, aaf)
    summary_team(disc, team_report(disc))
    check_tie_breaks(disc)
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])

check_entry_counts()
out.corrections.finish()
checks.finish()
