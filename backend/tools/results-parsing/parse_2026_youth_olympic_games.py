"""Parse the 2026 Youth Olympic Games results book into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_youth_olympic_games.py \\
        data/2026/2026-YOUTH-OLYMPIC-GAMES/18178-ResultsbookMedia.pdf

Writes the MAG and WAG juniors' PARTICIPANTS / JUDGES / SCORES-* / RANKING-* CSVs and the mixed
team's JUDGES / SCORES-* / RANKING-* CSVs (no entry list of its own: its gymnasts are the MAG and
WAG entries), and an IMPORT.json per prefix, next to the PDF, reading event metadata from the
EVENT.csv already there. Exits non-zero if any self-check fails
(docs/instructions-results-parsing.md §3; this source format is §5.23).

FIG / Swiss Timing layout (§5.1) without apparatus tables: Competition I's routines come from the
all-around report, cross-checked against the team report; the team and all-around finals' from
their reports. The mixed team's pages are read from word coordinates (`pdftotext -bbox`), which
are fixed on every page, where the `-layout` text columns shift from page to page.
"""
import html, os, re, subprocess, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first as split_name

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
PAGES = common.pdf_pages(PDF)
checks = common.Checks()
err = checks.err
EVENT_PREFIX = '2026-YOUTH-OLYMPIC-GAMES'
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-JR', 'WAG-JR', 'MIX-JR'], err)
out = common.Output(OUT, corrections)

AGE = 'JR'
PREFIX = {d: f'{EVENT_PREFIX}-{d}-{AGE}' for d in ('MAG', 'WAG', 'MIX')}
EVENTS = common.read_events(OUT, EVENT_PREFIX)
if len({EVENTS[p]['Title'] for p in PREFIX.values()}) != 1:
    raise SystemExit('EVENT.csv rows are expected to share a title')
G = {'MAG': 'M', 'WAG': 'W', 'MIX': 'X'}
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
# From the Competition Schedule (page 10), never from report footers (§4.4)
COMPETITION_DATE = {'MAG': {'QUAL': '2026-11-07', 'TEAM': '2026-11-09', 'AA': '2026-11-10'},
                    'WAG': {'QUAL': '2026-11-08', 'TEAM': '2026-11-09', 'AA': '2026-11-10'},
                    'MIX': {'TEAM': '2026-11-11'}}
# Scores counting toward a team's apparatus total: three up, two count, in qualification and final
TEAM_COUNT = 2
# Finalists who didn't come from the qualification's Q rows: (out, in)
FINAL_CHANGES = {
    # REVISED all-around final start list: "CSUKA Zeno (GER) replaced de SILVA Jaydon (CAN)"
    'MAG AA final': ('111', '130'),
    # Czechia, 9th, in Canada's place; the book gives no reason
    'WAG team final': ('CAN', 'CZE'),
}

def event(disc):
    return EVENTS[PREFIX[disc]]

# ---------------------------------------------------------------- page lookup
def footer(i):
    for l in reversed(PAGES[i].split('\n')):
        if re.search(r'Page \d+\s*/\s*\d+', l):
            return l.split()[0]
    return None

def find(code):
    found = [i for i in range(len(PAGES)) if footer(i) == code]
    if not found:
        raise SystemExit(f'no pages for {code}')
    return found

def code(g, kind, rnd, suffix):
    # e.g. GARMTEAM--------------QUAL--------_73C
    head = f'GAR{g}{kind}'
    return head + '-' * (22 - len(head)) + rnd + '-' * (34 - 22 - len(rnd)) + '_' + suffix

def lines(idx):
    return [l for i in idx for l in PAGES[i].split('\n')]

# ---------------------------------------------------------------- participants
MONTHS = {m: i + 1 for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split())}
NAMES = {}       # bib -> (name, noc), both disciplines
DISCIPLINE = {}  # bib -> MAG / WAG

def participants(disc):
    rows, noc = [], None
    for l in lines(find(code(G[disc], '', '', '32A'))):
        m = re.match(r'^\s+([A-Z]{3}) - \S', l)
        if m:
            noc = m.group(1); continue
        m = re.match(r"^\s+(\S.*?)\s{2,}(\d+)?\s+(\d{3})\s+(\d{1,2}) ([A-Z]{3}) (\d{4})\s*$", l)
        if not m:
            if re.search(r'\s\d{3}\s+\d{1,2} [A-Z]{3} \d{4}\s*$', l):
                err(f'{disc} participants: unparsed {l!r}')
            continue
        name, lic, bib, d, mon, y = m.groups()
        sur, giv = split_name(name)
        if not sur or not giv:
            err(f'{disc} participants: name split {name!r} -> {sur!r}/{giv!r}')
        if bib in NAMES:
            err(f'{disc} participants: duplicate bib {bib}')
        NAMES[bib] = (name, noc)
        DISCIPLINE[bib] = disc
        rows.append({'Event Name': event(disc)['Title'], 'Discipline': disc, 'Age Category': AGE,
                     'Event Start Date': event(disc)['Start Date'], 'Order': len(rows) + 1, 'NOC Code': noc,
                     'Bib Number': bib, 'FIG License': lic or '', 'Name': name, 'Surname': sur,
                     'Given Name': giv, 'Birth Year': y, 'Birth Date': f'{y}-{MONTHS[mon]:02d}-{int(d):02d}'})
    print(f'  {disc} participants: {len(rows)}')
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)
    for r in rows:
        NAMES[r['Bib Number']] = (r['Name'], r['NOC Code'])

def check_name(ctx, bib, noc):
    """The participant's full name for a results row, after checking the bib and NOC."""
    if bib not in NAMES:
        err(f'{ctx}: bib {bib} not in participants'); return ''
    full, pnoc = NAMES[bib]
    if pnoc != noc:
        err(f'{ctx}: bib {bib} NOC {noc} != participants {pnoc}')
    return full

# ---------------------------------------------------------------- judges
SUP = {'Floor Exercise': 'FX', 'Pommel Horse': 'PH', 'Rings': 'SR', 'Vault': 'VT',
       'Parallel Bars': 'PB', 'Horizontal Bar': 'HB', 'Uneven Bars': 'UB', 'Balance Beam': 'BB'}
# Panel order in the icon grid, left to right then top to bottom; the time and line judges confirm it
GRID = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
# The mixed final's sheet: the men's panels on the left, the women's on the right
MIXED_GRID = [('MAG', 'FX'), ('WAG', 'UB'), ('MAG', 'PB'), ('WAG', 'BB'), ('MAG', 'HB'), ('WAG', 'FX')]
FUNCTION = r'(D\d|E\d|(?:Time|Line) Judge(?: \d)?)'

def judge_fn(f):
    m = re.fullmatch(r'(Time|Line) Judge(?: (\d))?', f.strip())
    if m:
        return ('T' if m.group(1) == 'Time' else 'L') + (m.group(2) or '')
    return f.strip()

def judge_sheet(ls, grid, add, ctx):
    """A judges sheet: the Superior Jury (one column, or the men's and women's side by side), the
    panels in the icon grid, two to a row, and the reserves. `add(panel_index_or_None, side, function,
    name, noc)`; `side` 0 is the left column, 1 the right."""
    block, split_at, in_res, res_split = -1, None, False, None
    for l in ls:
        if l.startswith(' Legend:') or l.startswith('Legend:'):
            break
        if block < 0:
            for side, (name, role) in enumerate(re.findall(
                    r'(?:Superior Jury:)?\s*([A-Z][A-Za-z\'-]*(?: [A-Za-z\'-]+)*?)\s{2,}'
                    r'(President|Vice-[Pp]resident|Member|[A-Z][a-z]+(?: [A-Z][a-z]+)? Supervisor)(?=\s{2,}|\s*$)', l)):
                if role.endswith('Supervisor'):
                    add(None, side, ('SV', SUP[role.removesuffix(' Supervisor')]), name, '')
                else:
                    add(None, side, (role, ''), name, '')
        if re.match(r'^\s+Function\s+Name\s+Function\s+Name', l):
            block += 1
            split_at = l.index('Function', l.index('Name'))
            continue
        if 'Reserves' in l:
            in_res = True
            res_split = l.rindex('Reserves') - 10 if l.count('Reserves') > 1 else None
            continue
        if in_res:
            parts = [(0, l[:res_split]), (1, l[res_split:])] if res_split else [(0, l)]
            for side, part in parts:
                m = re.match(r'^\s*R(\d)\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', part)
                if m:
                    add(None, side, (f'R{m.group(1)}', ''), m.group(2), m.group(3))
            continue
        if block >= 0 and split_at:
            for side, part in ((0, l[:split_at]), (1, l[split_at:])):
                m = re.match(r'^\s*' + FUNCTION + r'\s+(.+?)\s{2,}([A-Z]{3})\s*$', part)
                if m:
                    add(block * 2 + side, side, (judge_fn(m.group(1)), None), m.group(2), m.group(3))
                elif part.strip() and part.strip() not in ('NOC', 'Code'):
                    err(f'{ctx}: unparsed {part!r}')
    if block + 1 != len(grid) // 2:
        err(f'{ctx}: {block + 1} panel rows')

def judges(disc):
    sfx = '57A' if disc == 'MAG' else '57B'
    rows = []
    for rnd, c in (('QUAL', code(G[disc], 'GEN', 'QUAL', sfx)), ('TEAM', code(G[disc], 'TEAM', 'FNL', sfx)),
                   ('AA', code(G[disc], '1AA', 'FNL', sfx))):
        n0 = len(rows)
        def add(panel, side, fn, name, noc):
            sur, giv = split_name(name)
            if not sur or not giv:
                err(f'{disc} judges: name split {name!r}')
            function, app = fn
            rows.append({'Event Name': event(disc)['Title'], 'Discipline': disc, 'Age Category': AGE,
                         'Event Start Date': event(disc)['Start Date'], 'Competition': common.COMPETITION[rnd],
                         'Apparatus': GRID[disc][panel] if panel is not None else app, 'Function': function,
                         'Name': name, 'Surname': sur, 'Given Name': giv, 'NOC Code': noc})
        judge_sheet(lines(find(c)), GRID[disc], add, f'{disc} judges {rnd}')
        check_panels(rows[n0:], [(disc, a) for a in GRID[disc]], f'{disc} judges {rnd}')
        print(f'  {disc} judges {rnd}: {len(rows) - n0}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, rows)

def check_panels(rows, panels, ctx):
    for disc, app in panels:
        fns = [r['Function'] for r in rows if r['Apparatus'] == app and r.get('Panel', disc) == disc]
        if not {'SV', 'D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5'} <= set(fns) or len(fns) != len(set(fns)):
            err(f'{ctx} {disc} {app}: functions {fns}')

def mixed_judges():
    rows = []
    def add(panel, side, fn, name, noc):
        sur, giv = split_name(name)
        if not sur or not giv:
            err(f'MIX judges: name split {name!r}')
        function, app = fn
        disc, panel_app = MIXED_GRID[panel] if panel is not None else (('MAG', 'WAG')[side], app)
        # One sheet for the three rounds: Round blank, the judge served each of them
        rows.append({'Event Name': event('MIX')['Title'], 'Discipline': 'MIX', 'Age Category': AGE,
                     'Event Start Date': event('MIX')['Start Date'], 'Competition': 'C4', 'Round': '',
                     'Panel': disc, 'Apparatus': panel_app, 'Function': function, 'Name': name,
                     'Surname': sur, 'Given Name': giv, 'NOC Code': noc})
    judge_sheet(lines(find(code('X', 'TEAM', '', '57E'))), MIXED_GRID, add, 'MIX judges')
    check_panels(rows, MIXED_GRID, 'MIX judges')
    print(f'  MIX judges: {len(rows)}')
    out.csv(f'{PREFIX["MIX"]}-JUDGES.csv', common.mixed_judges_header(), rows)

# ---------------------------------------------------------------- team / all-around reports
NUM = re.compile(r'-?\d+\.\d+')
APP_ITEM = re.compile(r'(\d+\.\d{3})\s+(\d+\.\d{3})(?:\s+\((\d+)\))?|DNS')
MARKERS = ('Q', 'R1', 'R2', 'R3', 'R4', 'NR')

def detail_lines(ls, i, disc, items, ctx):
    """The E (and, for MAG, BP) lines under a D line. `items`: (app_index, start_col, D, score) for each
    apparatus with a routine; E, bonus and penalty are given to an apparatus by column."""
    res = {a: {'E': '', 'B': '', 'Penalty': ''} for a, _, d, _ in items if d is not None}
    starts = sorted((col, a) for a, col, d, s in items if d is not None)
    def owner_nearest(pos):
        return min(starts, key=lambda t: abs(t[0] - pos))[1]
    def owner_left(pos):
        left = [a for col, a in starts if col <= pos + 1]
        return left[-1] if left else starts[0][1]
    j = i + 1
    m = re.match(r'^(?:\s+|\s*\S.*?\s{2,})(E ?P|E)(?:\s|$)', ls[j])
    if not m:
        err(f'{ctx}: expected E line, got {ls[j]!r}'); return res, j
    tag = m.group(1).replace(' ', '')
    for v in NUM.finditer(ls[j][m.end():]):
        pos, val = v.start() + m.end(), v.group()
        if val.startswith('-') and tag == 'EP':
            res[owner_left(pos)]['Penalty'] = val
        else:
            a = owner_nearest(pos)
            if res[a]['E']: err(f'{ctx}: two E values for app {a}')
            res[a]['E'] = val
    j += 1
    if disc == 'MAG':
        m = re.match(r'^\s+BP(\s|$)', ls[j])
        if not m:
            err(f'{ctx}: expected BP line, got {ls[j]!r}')
        else:
            for v in NUM.finditer(ls[j][m.end():]):
                pos, val = v.start() + m.end(), v.group()
                key = 'Penalty' if val.startswith('-') else 'B'
                a = owner_left(pos)
                if res[a][key]: err(f'{ctx}: two {key} for app {a}')
                res[a][key] = val
            j += 1
    return res, j

def routine(d, s, x, rank, ctx):
    checks.check_sum(ctx, s, d, x['E'], x['B'], x['Penalty'])
    return dict(Status='COMPLETED', D=d, E=x['E'], B=x['B'], Penalty=x['Penalty'], Total=s, Rank=rank or '')

DNS = dict(Status='DNS', D='', E='', B='', Penalty='', Total='', Rank='')

def aa_report(disc, rnd):
    """All-Around Qualification (rnd QUAL) or All-Around Final (rnd AA): every gymnast's routines."""
    ls = lines(find(code(G[disc], '1AA', 'QUAL' if rnd == 'QUAL' else 'FNL', '73G' if disc == 'MAG' else '73H')))
    n, ctx0, athletes, i = len(APPS[disc]), f'{disc} {rnd} AA', [], 0
    while i < len(ls):
        m = re.match(r'^\s*(\d+)?\s+(\d{3})\s+(.+?)\s+([A-Z]{3})\s+D\s(.*)$', ls[i])
        if not m:
            if re.match(r'^\s*\d+\s+\d{3}\s', ls[i]): err(f'{ctx0}: unparsed {ls[i]!r}')
            i += 1; continue
        rank, bib, _, noc, _ = m.groups()
        ctx = f'{ctx0} bib {bib}'
        base = m.start(5)
        rest = ls[i][base:]
        items, end = [], 0
        for it in APP_ITEM.finditer(rest):
            if len(items) == n: break
            end = it.end()
            items.append((len(items), base + it.start(), None, None, None) if it.group(0) == 'DNS' else
                         (len(items), base + it.start(), it.group(1), it.group(2), it.group(3)))
        tail = rest[end:].split()
        if len(items) != n or not tail:
            err(f'{ctx}: {len(items)} apparatus items, tail {tail}'); i += 1; continue
        total, q = tail[0], (tail[1] if len(tail) > 1 else '')
        if len(tail) > 2 or (q and q not in MARKERS):
            err(f'{ctx}: tail {tail}')
        det, i = detail_lines(ls, i, disc, [(a, c, d, s) for a, c, d, s, _ in items], ctx)
        apps = {APPS[disc][a]: DNS if d is None else routine(d, s, det[a], rk, f'{ctx} {APPS[disc][a]}')
                for a, _, d, s, rk in items}
        if total not in ('DNF', 'DNS'):
            ssum = sum(D(v['Total']) for v in apps.values())
            if ssum != D(total): err(f'{ctx}: apparatus sum {ssum} != {total}')
        athletes.append(dict(Rank=rank or '', Bib=bib, NOC=noc, apps=apps,
                             Total='' if total in ('DNF', 'DNS') else total, Q=q))
    n_id = sum(1 for l in ls if re.match(r'^\s*(\d+)?\s+\d{3}\s+\S.*?\s+D\s', l))
    if n_id != len(athletes): err(f'{ctx0}: parsed {len(athletes)} of {n_id}')
    checks.check_rank_order(ctx0, athletes)
    return athletes

def team_report(disc, rnd):
    """Team Qualification (rnd QUAL) or Team Final (rnd TEAM): every team and its members' routines."""
    ls = lines(find(code(G[disc], 'TEAM', 'QUAL' if rnd == 'QUAL' else 'FNL', '73C' if disc == 'MAG' else '73D')))
    n, ctx0, teams, team, i = len(APPS[disc]), f'{disc} {rnd} team', [], None, 0
    while i < len(ls):
        l = ls[i]
        m = re.match(r'^\s*(\d+)?\s+([A-Z]{3}) - (.+?)\s{2,}(\(.*)$', l)
        if m:
            rank, noc, _, rest = m.groups()
            base = m.start(4)
            found = list(re.finditer(r'\((\d+)\)\s+(\d+\.\d{3})', rest))
            tail = rest[found[-1].end():].split() if found else []
            if len(found) != n: err(f'{ctx0} {noc}: {len(found)} apparatus totals')
            team = dict(Rank=rank or '', NOC=noc, cols=[base + x.end() for x in found],
                        totals=[x.group(2) for x in found], Total=tail[0] if tail else '',
                        Q=tail[1] if len(tail) > 1 else '', athletes=[], Penalty='')
            if len(tail) > 2 or (team['Q'] and team['Q'] not in MARKERS):
                err(f'{ctx0} {noc}: tail {tail}')
            teams.append(team)
            i += 1; continue
        m = re.match(r'^\s+(\d{3}) (.+?)\s{2,}D(\s.*)?$', l)
        if m and team is not None:
            bib = m.group(1)
            ctx = f'{ctx0} {team["NOC"]} bib {bib}'
            base = m.start(3) if m.group(3) else len(l)
            items = []
            # A team penalty is printed at the end of a member's D line (WAG MEX, -0.300)
            pen = re.search(r'\s(-\d+\.\d{3})\s*$', m.group(3) or '')
            if pen:
                if team['Penalty']: err(f'{ctx}: a second team penalty')
                team['Penalty'] = pen.group(1)
                print(f'  {ctx}: team penalty {pen.group(1)}')
            for it in APP_ITEM.finditer(m.group(3) or ''):
                a = min(range(n), key=lambda k: abs(team['cols'][k] - (base + it.end())))
                if any(x[0] == a for x in items): err(f'{ctx}: two items in app {a}')
                items.append((a, base + it.start(), None, None) if it.group(0) == 'DNS' else
                             (a, base + it.start(), it.group(1), it.group(2)))
            if items:
                det, i = detail_lines(ls, i, disc, items, ctx)
            else:
                i += 3 if disc == 'MAG' else 2
            apps = {APPS[disc][a]: DNS if d is None else routine(d, s, det[a], '', f'{ctx} {APPS[disc][a]}')
                    for a, _, d, s in items}
            team['athletes'].append(dict(Bib=bib, NOC=team['NOC'], apps=apps))
            continue
        i += 1
    for t in teams:
        for a, app in enumerate(APPS[disc]):
            sc = sorted((D(x['apps'][app]['Total']) for x in t['athletes']
                         if app in x['apps'] and x['apps'][app]['Total']), reverse=True)
            if sum(sc[:TEAM_COUNT]) != D(t['totals'][a]):
                err(f'{ctx0} {t["NOC"]} {app}: best {TEAM_COUNT} {sum(sc[:TEAM_COUNT])} != {t["totals"][a]}')
        if sum(D(x) for x in t['totals']) + D(t['Penalty']) != D(t['Total']):
            err(f'{ctx0} {t["NOC"]}: apparatus totals {sum(D(x) for x in t["totals"])} and penalty '
                f'{t["Penalty"] or 0} != {t["Total"]}')
    checks.check_rank_order(ctx0, [dict(t, Bib=t['NOC']) for t in teams])
    return teams

def cross_check(athletes, report, ctx):
    """Every routine a team report prints equals the all-around report's."""
    by_bib = {a['Bib']: a for a in report}
    for a in athletes:
        other = by_bib.get(a['Bib'])
        if other is None:
            err(f'{ctx} bib {a["Bib"]}: not in the all-around report'); continue
        for app, x in a['apps'].items():
            y = other['apps'].get(app)
            if y is None or any(x[k] != y[k] for k in ('Status', 'D', 'E', 'B', 'Penalty', 'Total')):
                err(f'{ctx} bib {a["Bib"]} {app}: {x} vs all-around report {y}')

# ---------------------------------------------------------------- MAG / WAG files
def meta(disc, rnd, app):
    return {'Event Name': event(disc)['Title'], 'Discipline': disc, 'Age Category': AGE,
            'Competition Start Date': COMPETITION_DATE[disc][rnd], 'Competition': common.COMPETITION[rnd],
            'Part': '', 'Apparatus': app}

def scores(disc, rnd, athletes):
    """SCORES-<competition>-<APP>, from a report: one routine per apparatus, vault's too (one vault in
    every competition, there being no vault final)."""
    for app in APPS[disc]:
        rows = []
        for a in athletes:
            x = a['apps'].get(app)
            if x is None:
                continue
            rows.append(meta(disc, rnd, app) | {
                'Rank': x['Rank'], 'Bib': a['Bib'], 'Name': check_name(f'{disc} {rnd} {app}', a['Bib'], a['NOC']),
                'NOC Code': a['NOC'], 'Status': x['Status'], 'D': x['D'], 'E': x['E'], 'B': x['B'],
                'Penalty': x['Penalty'], 'SJ Penalty': '', 'Total': x['Total']})
        rows.sort(key=lambda r: (r['Rank'] == '', int(r['Rank'] or 0)))
        out.csv(f'{PREFIX[disc]}-SCORES-{common.COMPETITION[rnd]}-{app}.csv', common.score_header(False, False), rows)

SUMMARY_HEAD = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part']

def summary_meta(disc, rnd):
    return {'Event Name': event(disc)['Title'], 'Discipline': disc, 'Age Category': AGE,
            'Event Start Date': event(disc)['Start Date'], 'Competition': common.COMPETITION[rnd], 'Part': ''}

def summary_team(disc, rnd, teams):
    hdr = SUMMARY_HEAD + ['Rank', 'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + \
          ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for t in teams:
        r = summary_meta(disc, rnd) | {'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': t['Penalty'],
                                       'Total': t['Total'], 'Qualification': t['Q']}
        for a, app in enumerate(APPS[disc]):
            r[f'{app} Total'] = t['totals'][a]
        rows.append(r)
    out.ranking(PREFIX[disc], 'TEAM', hdr, rows, event(disc))

def summary_aa(disc, rnd, athletes):
    hdr = SUMMARY_HEAD + ['Rank', 'Bib', 'Name', 'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + \
          ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for a in athletes:
        r = summary_meta(disc, rnd) | {'Rank': a['Rank'], 'Bib': a['Bib'],
                                       'Name': check_name(f'{disc} {rnd} AA', a['Bib'], a['NOC']),
                                       'NOC Code': a['NOC'], 'SJ Penalty': '', 'Total': a['Total'],
                                       'Qualification': a['Q']}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = a['apps'][app]['Total']
        rows.append(r)
    out.ranking(PREFIX[disc], 'AA', hdr, rows, event(disc))

def check_finalists(ctx, qual, final, key, n):
    """The final's field is the qualification's Q rows."""
    qualified = {r[key] for r in qual if r['Q'] == 'Q'}
    if len(qualified) != n:
        err(f'{ctx}: {len(qualified)} qualified, expected {n}')
    if ctx in FINAL_CHANGES:
        gone, came = FINAL_CHANGES[ctx]
        qualified = qualified - {gone} | {came}
        print(f'  {ctx}: {came} in place of {gone}')
    if qualified != {r[key] for r in final}:
        err(f'{ctx}: final field {sorted(r[key] for r in final)} != qualified {sorted(qualified)}')

# ---------------------------------------------------------------- mixed team (word coordinates)
# A cell's right edge on every mixed results page: the men's floor, parallel bars and high bar, the
# women's bars, beam and floor, then the team total
MIX_COLUMNS = [(274, 'MAG', 'FX'), (323, 'MAG', 'PB'), (372, 'MAG', 'HB'),
               (421, 'WAG', 'UB'), (470, 'WAG', 'BB'), (519, 'WAG', 'FX')]
MIX_TOTAL = 559
MIX_APPS = [f'{d} {a}' for _, d, a in MIX_COLUMNS]

def bbox_lines(page):
    """The words of a page (0-based index) as lines, top to bottom: [(x_min, x_max, word), ...]."""
    xml = subprocess.run(['pdftotext', '-f', str(page + 1), '-l', str(page + 1), '-bbox', PDF, '-'],
                         check=True, capture_output=True, text=True).stdout
    words = sorted((float(y), float(x0), float(x1), html.unescape(w)) for x0, y, x1, w in re.findall(
        r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="[\d.]+">([^<]*)</word>', xml))
    # A line's words can sit a couple of points apart (a bib and name below the D beside them)
    lines, top = [], None
    for y, x0, x1, w in words:
        if top is None or y - top > 4:
            lines.append([]); top = y
        lines[-1].append((x0, x1, w))
    return [sorted(ws) for ws in lines]

# A member's line tags (D; E, or EP for a woman; a man's BP), printed in their own column
TAG_X = (205, 232)

def tag(ws):
    return ''.join(w for x0, _, w in ws if TAG_X[0] <= x0 < TAG_X[1])

def column(x1, ctx):
    hits = [(d, a) for edge, d, a in MIX_COLUMNS if abs(edge - x1) < 4]
    if len(hits) != 1:
        err(f'{ctx}: a cell ending at {x1} is under no column'); return None
    return hits[0]

def mixed_pages(rnd):
    return [l for i in find(code('X', 'TEAM', rnd, '73K')) for l in bbox_lines(i)]

def mixed_report(rnd):
    """A mixed team results report: each team's cells (an apparatus total, a score, or `CR-x`, done in an
    earlier round), total and marker, and its members' routines, by column."""
    ctx0 = f'MIX {rnd}'
    teams, team, ls, i = [], None, mixed_pages(rnd), 0
    while i < len(ls):
        ws = ls[i]
        words = [w for _, _, w in ws]
        if '-' in words[:3] and re.fullmatch(r'[A-Z]{3}', words[words.index('-') - 1]):
            k = words.index('-')
            rank, noc = (words[0] if k == 2 else ''), words[k - 1]
            cells, total, q = {}, '', ''
            for x0, x1, w in ws[k + 1:]:
                if re.fullmatch(r'\d+\.\d{3}|CR-\d|DNF', w) and abs(x1 - MIX_TOTAL) < 4:
                    total = '' if w == 'DNF' else w
                elif re.fullmatch(r'\d+\.\d{3}|CR-\d', w) and x0 > 240:
                    col = column(x1, f'{ctx0} {noc}')
                    if col:
                        if col in cells: err(f'{ctx0} {noc}: two cells in {col}')
                        cells[col] = w
                elif w in MARKERS and x0 > MIX_TOTAL:
                    q = w
            team = dict(Rank=rank, NOC=noc, cells=cells, Total=total, Q=q, members=[])
            teams.append(team)
            i += 1; continue
        if team is not None and len(words) > 2 and re.fullmatch(r'\d{3}', words[0]) and tag(ws) == 'D':
            bib = words[0]
            ctx = f'{ctx0} {team["NOC"]} bib {bib}'
            routines = {}
            tokens = [t for t in ws if t[0] >= TAG_X[1]]
            j = 0
            while j < len(tokens):
                x0, x1, w = tokens[j]
                if w == 'DNS':
                    col = column(x1, ctx)
                    routines[col] = dict(DNS)
                    j += 1; continue
                if j + 1 < len(tokens) and re.fullmatch(r'\d+\.\d{3}', w) and re.fullmatch(r'\d+\.\d{3}', tokens[j + 1][2]):
                    col = column(tokens[j + 1][1], ctx)
                    routines[col] = dict(D=w, S=tokens[j + 1][2], x0=x0)
                    j += 2; continue
                err(f'{ctx}: unexpected token {w!r}'); j += 1
            # The E line (EP for a woman: E then any penalty) and a man's BP line, matched by position
            details = {col: {'E': '', 'B': '', 'Penalty': ''} for col, r in routines.items() if 'x0' in r}
            starts = sorted((r['x0'], col) for col, r in routines.items() if 'x0' in r)
            def owner(x):
                left = [col for start, col in starts if start <= x + 2]
                return left[-1] if left else (starts[0][1] if starts else None)
            j = i + 1
            while j < len(ls) and tag(ls[j]) in ('E', 'EP', 'BP'):
                line_tag = tag(ls[j])
                for x0, x1, w in ls[j]:
                    if x0 < TAG_X[1]:
                        continue
                    col = owner(x0)
                    if col is None or not NUM.fullmatch(w):
                        err(f'{ctx}: {line_tag} token {w!r}'); continue
                    key = 'E' if line_tag in ('E', 'EP') and not w.startswith('-') else 'Penalty' if w.startswith('-') else 'B'
                    if details[col][key]: err(f'{ctx}: two {key} in {col}')
                    details[col][key] = w
                j += 1
            member = dict(Bib=bib, NOC=team['NOC'], apps={})
            for col, r in routines.items():
                if col is None:
                    continue
                if 'x0' not in r:
                    member['apps'][col] = dict(DNS)
                else:
                    member['apps'][col] = routine(r['D'], r['S'], details[col], '', f'{ctx} {col}')
            team['members'].append(member)
            i = j; continue
        i += 1
    for t in teams:
        if not t['Total'] and not t['Rank']:
            print(f'  {ctx0} {t["NOC"]}: DNF')
    checks.check_rank_order(ctx0, [dict(t, Bib=t['NOC']) for t in teams if t['Total']])
    return teams

def mixed_qualification(c1):
    """The mixed team's qualification: no routines of its own. Each NOC's best Competition I score on
    the men's floor, parallel bars and high bar and the women's bars, beam and floor counts."""
    teams = mixed_report('QUAL')
    entered = defaultdict(set)
    for bib, (_, noc) in NAMES.items():
        entered[noc].add(bib)
    for t in teams:
        ctx = f'MIX QUAL {t["NOC"]}'
        listed = {m['Bib'] for m in t['members']}
        if listed != entered[t['NOC']]:
            err(f'{ctx}: members {sorted(listed)} != entries {sorted(entered[t["NOC"]])}')
        for m in t['members']:
            for (disc, app), x in m['apps'].items():
                if DISCIPLINE.get(m['Bib']) != disc:
                    err(f'{ctx} bib {m["Bib"]}: a {disc} routine')
                y = c1[disc].get((m['Bib'], app))
                if y is None or any(x[k] != y[k] for k in ('Status', 'D', 'E', 'B', 'Penalty', 'Total')):
                    err(f'{ctx} bib {m["Bib"]} {disc} {app}: {x} vs Competition I {y}')
        for _, disc, app in MIX_COLUMNS:
            best = sorted((D(y['Total']) for (bib, a), y in c1[disc].items()
                           if a == app and bib in listed and y['Total']), reverse=True)
            printed = t['cells'].get((disc, app), '')
            if not best and not printed:
                continue
            if not best or D(printed) != best[0]:
                err(f'{ctx} {disc} {app}: best score {best[:1]} != printed {printed!r}')
            elif len(best) > 1 and best[0] == best[1]:
                # Both count, the book not saying whose did (GER men's floor, agreed with the user)
                print(f'  {ctx} {disc} {app}: members tie for the best score {best[0]}; both count')
        if t['Total'] and sum(D(v) for v in t['cells'].values()) != D(t['Total']):
            err(f'{ctx}: cells {sum(D(v) for v in t["cells"].values())} != total {t["Total"]}')
        if bool(t['Total']) != (len(t['cells']) == len(MIX_COLUMNS)):
            err(f'{ctx}: {len(t["cells"])} apparatus totals with total {t["Total"] or "DNF"}')
    q = sum(1 for t in teams if t['Q'] == 'Q')
    if q != 12: err(f'MIX QUAL: {q} qualified, expected 12')
    return teams

def mixed_round(rnd, number, field):
    """A round of the mixed final: each team's pair, one man and one woman, one routine each; earlier
    rounds' apparatus printed `CR-x`. The total is the pair's sum."""
    teams = mixed_report(rnd)
    ctx0 = f'MIX round {number}'
    if {t['NOC'] for t in teams} != field:
        err(f'{ctx0}: teams {sorted(t["NOC"] for t in teams)} != the field {sorted(field)}')
    for t in teams:
        ctx = f'{ctx0} {t["NOC"]}'
        scored = {col: v for col, v in t['cells'].items() if not v.startswith('CR-')}
        done = {col for col, v in t['cells'].items() if v.startswith('CR-')}
        if any(int(t['cells'][col][3]) >= number for col in done):
            err(f'{ctx}: a CR marker of this or a later round')
        if len(done) != 2 * (number - 1):
            err(f'{ctx}: {len(done)} apparatus done in earlier rounds')
        if sorted(d for d, _ in scored) != ['MAG', 'WAG'] or len(t['members']) != 2:
            err(f'{ctx}: cells {scored}, {len(t["members"])} members')
        for m in t['members']:
            if len(m['apps']) != 1:
                err(f'{ctx} bib {m["Bib"]}: {len(m["apps"])} routines'); continue
            (disc, app), x = next(iter(m['apps'].items()))
            if DISCIPLINE.get(m['Bib']) != disc or NAMES.get(m['Bib'], ('', ''))[1] != t['NOC']:
                err(f'{ctx} bib {m["Bib"]}: not a {disc} gymnast of {t["NOC"]}')
            if scored.get((disc, app)) != x['Total']:
                err(f'{ctx} bib {m["Bib"]}: {disc} {app} {x["Total"]} vs team cell {scored.get((disc, app))}')
        if sum(D(v) for v in scored.values()) != D(t['Total']):
            err(f'{ctx}: pair {sum(D(v) for v in scored.values())} != total {t["Total"]}')
    return teams

def mixed_files(qual, rounds):
    ev = event('MIX')
    head = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Round', 'Part']
    def row(t, competition, number):
        r = {'Event Name': ev['Title'], 'Discipline': 'MIX', 'Age Category': AGE,
             'Event Start Date': ev['Start Date'], 'Competition': competition, 'Round': number, 'Part': '',
             'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': '', 'Total': t['Total'], 'Qualification': t['Q']}
        for (disc, app), name in zip([(d, a) for _, d, a in MIX_COLUMNS], MIX_APPS):
            v = t['cells'].get((disc, app), '')
            r[f'{name} Total'] = '' if v.startswith('CR-') else v
        return r
    hdr = head + ['Rank', 'NOC Code'] + [f'{a} Total' for a in MIX_APPS] + ['SJ Penalty', 'Total', 'Qualification']
    qualifying = [row(t, 'C1', '') for t in qual] + \
                 [row(t, 'C4', str(n)) for n, teams in enumerate(rounds[:-1], 1) for t in teams]
    out.ranking(PREFIX['MIX'], 'TEAM', hdr, qualifying, ev, last_round=len(rounds))
    out.ranking(PREFIX['MIX'], 'TEAM', hdr, [row(t, 'C4', str(len(rounds))) for t in rounds[-1]], ev,
                last_round=len(rounds))
    # Each round's routines, a file per discipline's apparatus: SCORES-C4-MAG-FX, SCORES-C4-WAG-FX, ...
    for _, disc, app in MIX_COLUMNS:
        rows = []
        for number, teams in enumerate(rounds, 1):
            for t in teams:
                for m in t['members']:
                    x = m['apps'].get((disc, app))
                    if x is None:
                        continue
                    rows.append({'Event Name': ev['Title'], 'Discipline': 'MIX', 'Age Category': AGE,
                                 'Competition Start Date': COMPETITION_DATE['MIX']['TEAM'], 'Competition': 'C4',
                                 'Round': str(number), 'Part': '', 'Apparatus': app, 'Rank': '', 'Bib': m['Bib'],
                                 'Name': check_name(f'MIX round {number}', m['Bib'], m['NOC']),
                                 'NOC Code': m['NOC'], 'Status': x['Status'], 'D': x['D'], 'E': x['E'],
                                 'B': x['B'], 'Penalty': x['Penalty'], 'SJ Penalty': '', 'Total': x['Total']})
        out.csv(f'{PREFIX["MIX"]}-SCORES-C4-{disc}-{app}.csv', common.score_header(False, False, rounds=True), rows)

# ---------------------------------------------------------------- run
c1 = {}
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    participants(disc)
    judges(disc)

    aaq = aa_report(disc, 'QUAL')
    tq = team_report(disc, 'QUAL')
    cross_check([x for t in tq for x in t['athletes']], aaq, f'{disc} team qual')
    scores(disc, 'QUAL', aaq)
    summary_team(disc, 'QUAL', tq)
    summary_aa(disc, 'QUAL', aaq)
    c1[disc] = {(a['Bib'], app): x for a in aaq for app, x in a['apps'].items()}

    tf = team_report(disc, 'TEAM')
    check_finalists(f'{disc} team final', tq, tf, 'NOC', 8)
    scores(disc, 'TEAM', [x for t in tf for x in t['athletes']])
    summary_team(disc, 'TEAM', tf)

    aaf = aa_report(disc, 'AA')
    check_finalists(f'{disc} AA final', aaq, aaf, 'Bib', 18)
    scores(disc, 'AA', aaf)
    summary_aa(disc, 'AA', aaf)

    out.manifest(PREFIX[disc], event(disc))

print('===== MIX')
mixed_judges()
qual = mixed_qualification(c1)
field = {t['NOC'] for t in qual if t['Q'] == 'Q'}
rounds = []
for number, (rnd, advance) in enumerate((('QFNL', 8), ('SFNL', 4), ('FNL', 0)), 1):
    teams = mixed_round(rnd, number, field)
    rounds.append(teams)
    q = {t['NOC'] for t in teams if t['Q'] == 'Q'}
    if len(q) != advance: err(f'MIX round {number}: {len(q)} qualified, expected {advance}')
    field = q
mixed_files(qual, rounds)
out.manifest(PREFIX['MIX'], event('MIX'))

corrections.finish()
checks.finish()
