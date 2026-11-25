"""Parse the 2026 Commonwealth Games (Glasgow) artistic gymnastics results book into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_commonwealth_games.py \\
        data/2026/2026-COMMONWEALTH-GAMES/18222-ResultsbookMedia.pdf

Writes PARTICIPANTS, JUDGES, SCORES-{QUAL,AA,EVENT}-<APP>, SUMMARY-QUAL-{TEAM,AA} and
SUMMARY-FINAL-AA, and an IMPORT.json, per discipline next to the PDF, reading event metadata from
the EVENT.csv already there. Exits non-zero if any check fails (docs/instructions-results-parsing.md
§3; this source format is §5.19).

The book is the Games' own print (Longines timing) of ORIS-style reports, every page with text and a
footer code like GARM1APFX-------------QUAL--------_73I. The "Team Final and Individual Qualification"
round decides the team titles; the all-around and apparatus finals follow (§4.9). Athletes compete
for Commonwealth Games Associations (ENG, SCO, WAL, NIR, IOM, ...), written as printed (§4.8).

Sources: the apparatus tables give every qualification and final routine, except vault: its
qualification table lists only the two-vault athletes, so the other first vaults come from the team
report and the all-around qualification report (which agree wherever both print one). The
all-around final has no apparatus tables; its routines come from its all-around report. Start lists,
tie-break reports and the medallists pages are cross-checks.
"""
import os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first as split_name

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-COMMONWEALTH-GAMES'
PAGES = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
out = common.Output(OUT, common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err))

PREFIX = {d: f'{EVENT_PREFIX}-{d}-SR' for d in ('MAG', 'WAG')}
G = {'MAG': 'M', 'WAG': 'W'}
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
APP_NAME = {'Floor Exercise': 'FX', 'Pommel Horse': 'PH', 'Rings': 'SR', 'Vault': 'VT', 'Parallel Bars': 'PB',
            'Horizontal Bar': 'HB', 'Uneven Bars': 'UB', 'Balance Beam': 'BB'}
# Apparatus finals by day, in the order of the Competition Schedule, the start lists and the
# Judges Assignments columns (men left, women right)
FINALS_DAY = {1: {'MAG': ['FX', 'PH', 'SR'], 'WAG': ['VT', 'UB']},
              2: {'MAG': ['VT', 'PB', 'HB'], 'WAG': ['BB', 'FX']}}
# From the Competition Schedule page (§4.4); each results page's header date agrees (checked)
SESSION_DATE = {
    'MAG': {'QUAL': '2026-07-24', 'AA': '2026-07-26'},
    'WAG': {'QUAL': '2026-07-25', 'AA': '2026-07-26'},
}
FINALS_DATE = {1: '2026-07-27', 2: '2026-07-28'}
for day, by_disc in FINALS_DAY.items():
    for disc, apps in by_disc.items():
        for app in apps:
            SESSION_DATE[disc][('EVENT', app)] = FINALS_DATE[day]
MONTHS = {m: i + 1 for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split())}
MARKERS = ('Q', 'R1', 'R2', 'R3', 'R4', 'NR')
SCORE = r'\d+\.\d{3}'
ROUTINE_KEYS = ['Status', 'D', 'E', 'B', 'Penalty', 'SJ Penalty', 'Total']

def session_date(disc, rnd, app):
    return SESSION_DATE[disc][('EVENT', app)] if rnd == 'EVENT' else SESSION_DATE[disc][rnd]

# ---------------------------------------------------------------- page lookup
def footer_code(page):
    """GARM1APFX-------------QUAL--------_73I 1.0  Report Created ... -> GARM1APFXQUAL_73I"""
    m = re.search(r'^(GAR\S+)\s+v?[\d.]+\s+Report Created', page, re.M)
    return m.group(1).replace('-', '') if m else ''

CODES = [footer_code(p) for p in PAGES]

def find(code):
    """The pages of one report. The shared apparatus finals start lists and judges pages are
    printed twice, once in each discipline's section: the copies must be identical."""
    idx = [i for i, c in enumerate(CODES) if c == code]
    if not idx:
        raise SystemExit(f'no pages with code {code}')
    runs = [[idx[0]]]
    for i in idx[1:]:
        if i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    for run in runs[1:]:
        if [PAGES[i] for i in run] != [PAGES[i] for i in runs[0]]:
            err(f'{code}: pages {[i + 1 for i in run]} differ from pages {[i + 1 for i in runs[0]]}')
    return runs[0]

def lines(idx):
    return [l for i in idx for l in PAGES[i].split('\n')]

def check_page_date(idx, want, ctx):
    """The date in a results page's header is the day of competition (the footer's is print time)."""
    for i in idx:
        m = re.search(r'(?:MON|TUE|WED|THU|FRI|SAT|SUN) (\d{1,2}) ([A-Z]{3}) (\d{4})', '\n'.join(PAGES[i].split('\n')[:6]))
        got = m and f'{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}'
        if got != want:
            err(f'{ctx}: page {i + 1} header date {got}, session date {want}')

def empty_routine():
    return dict.fromkeys(ROUTINE_KEYS, '')

def dns_routine():
    return dict(empty_routine(), Status='DNS')

def check_routine(ctx, r):
    if r['Status'] != 'DNS':
        checks.check_sum(ctx, r['Total'], r['D'].lstrip('!'), r['E'], r['B'], r['Penalty'])

def vault_status(r):
    """An attempt scored 0.000 is an invalid vault (§4.3)."""
    if r['Status'] == 'COMPLETED' and D(r['Total']) == 0:
        r['Status'] = 'INVALID_VAULT'
    return r

# ---------------------------------------------------------------- participants
NAMES = {}                   # disc -> bib -> (name, noc)
BY_NAME = {}                 # disc -> (name, noc) -> bib
COMPETED = defaultdict(set)  # disc -> bibs with at least one routine

def participants(disc):
    ctx = f'{disc} participants'
    ev = EVENTS[PREFIX[disc]]
    rows, NAMES[disc] = [], {}
    noc = None
    ls = lines(find(f'GAR{G[disc]}_32A'))
    for l in ls:
        m = re.match(r'^\s+([A-Z]{3}) - \S', l)
        if m:
            noc = m.group(1); continue
        m = re.match(r'^\s+(\S.*?)\s{2,}(\d+)\s+(\d{3})\s+(\d{1,2}) ([A-Z]{3}) (\d{4})\s*$', l)
        if not m:
            continue
        name, lic, bib, d, mon, y = m.groups()
        sur, giv = split_name(name)
        if not sur or not giv:
            err(f'{ctx}: name split {name!r} -> {sur!r}/{giv!r}')
        if bib in NAMES[disc]:
            err(f'{ctx}: duplicate bib {bib}')
        NAMES[disc][bib] = (name, noc)
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                     'Event Start Date': ev['Start Date'], 'Order': str(len(rows) + 1), 'NOC Code': noc,
                     'Bib Number': bib, 'FIG License': lic, 'Name': name, 'Surname': sur, 'Given Name': giv,
                     'Birth Year': y, 'Birth Date': f'{y}-{MONTHS[mon]:02d}-{int(d):02d}'})
    n_dates = sum(1 for l in ls if re.search(r'\d{3}\s+\d{1,2} [A-Z]{3} \d{4}\s*$', l))
    if n_dates != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_dates} entries')
    BY_NAME[disc] = {v: b for b, v in NAMES[disc].items()}
    print(f'  {ctx}: {len(rows)} entries')
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)

def check_name(disc, ctx, bib, name, noc):
    """A results row's identity against the entry list; long names are cut short in some
    reports (VICENTE HUMPHRIES, KAITHERI PUTHALATH), and the tie-break reports print initials."""
    if bib not in NAMES[disc]:
        err(f'{ctx}: bib {bib} not in participants'); return name
    full, pnoc = NAMES[disc][bib]
    if noc is not None and pnoc != noc:
        err(f'{ctx}: bib {bib} NOC {noc} != participants {pnoc}')
    if name != full and not full.startswith(name):
        err(f'{ctx}: bib {bib} {name!r} != participants {full!r}')
    return full

def qualification_start_lists(disc):
    """Every bib on the qualification start lists (team members, individuals and the italic
    alternates) is on the entry list with the same name and CGA."""
    n = 0
    for l in lines(find(f'GAR{G[disc]}GENQUAL_51{"A" if disc == "MAG" else "B"}')):
        for m in re.finditer(r'(?<!\S)(\d{3})\s{2,}(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', l):
            check_name(disc, f'{disc} qualification start list', m.group(1), m.group(2), m.group(3))
            n += 1
    if not n:
        err(f'{disc} qualification start list: no entries')

# ---------------------------------------------------------------- judges
FUNCTION = {'Time Judge': 'T', 'Time Judge 1': 'T1', 'Time Judge 2': 'T2',
            'Line Judge': 'L', 'Line Judge 1': 'L1', 'Line Judge 2': 'L2'}
PANEL_ENTRY = re.compile(r'(D\d|E\d|Time Judge(?: \d)?|Line Judge(?: \d)?|R\d)\s+(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)')
SJ_ENTRY = re.compile(r'(?:Superior Jury:)?\s*([A-Z][A-Za-z\'-]*(?: [A-Za-z\'-]+)+?)\s{2,}'
                      r'(President|[A-Z][A-Za-z &]+? Supervisor)(?=\s{2,}|\s*$)')
SPLIT = 60   # columns: a panel (or the men's side of a finals page) left of this, the next right of it

def supervisor_apps(fn, ctx):
    if fn == 'President':
        return ['']
    apps = [APP_NAME.get(a.strip()) for a in fn.removesuffix(' Supervisor').split('&')]
    if None in apps:
        err(f'{ctx}: unknown supervisor {fn!r}')
    return [a for a in apps if a]

def judge_pages(disc, code, rnd, grid, rows, ctx):
    """One Judges Assignments page. `grid(side, block)` names a panel's apparatus: QUAL and the
    all-around final print two panels per row in the legend's order; the finals pages print the
    men's panels down the left and the women's down the right. Reserves are listed per page."""
    ls = lines(find(code))
    block = {0: -1, 1: -1}
    in_reserves = False
    seen_sj = False
    for l in ls:
        if l.strip().startswith('Legend'):
            break
        if re.match(r'^\s+Function\s+Name', l):
            for side in (0, 1):
                if side == 0 or l.find('Function', SPLIT) >= 0:
                    block[side] += 1
            continue
        if re.match(r'^\s+Reserves', l):
            in_reserves = True; continue
        if block[0] < 0:
            for m in SJ_ENTRY.finditer(l):
                side = 0 if m.start(1) < SPLIT or grid(1, 0) is None else 1
                d = sj_disc(disc, side)
                if d is None:
                    continue
                seen_sj = True
                fn = 'President' if m.group(2) == 'President' else 'SV'
                for app in supervisor_apps(m.group(2), ctx):
                    rows[d].append(dict(Round=rnd, Apparatus=app, Function=fn, Name=m.group(1), NOC=''))
            continue
        for m in PANEL_ENTRY.finditer(l):
            side = 0 if m.start() < SPLIT else 1
            fn, name, noc = m.groups()
            if in_reserves:
                d = sj_disc(disc, side)
                if d is not None:
                    rows[d].append(dict(Round=rnd, Apparatus=None, Function=fn, Name=name, NOC=noc, side=side))
                continue
            d, app = grid(side, block[side])
            rows[d].append(dict(Round=rnd, Apparatus=app, Function=FUNCTION.get(fn, fn), Name=name, NOC=noc))
        n_fn = len(re.findall(r'(?<!\S)(?:D\d|E\d|R\d|Time Judge|Line Judge)(?!\S)', l))
        if n_fn != len(PANEL_ENTRY.findall(l)):
            err(f'{ctx}: unparsed judges line {l!r}')
    if not seen_sj:
        err(f'{ctx}: no Superior Jury')
    return block

def sj_disc(disc, side):
    """On a finals page the men's side is left, the women's right; elsewhere one discipline."""
    if disc is not None:
        return disc
    return ('MAG', 'WAG')[side]

def judges():
    rows = {'MAG': [], 'WAG': []}
    for disc in ('MAG', 'WAG'):
        g, apps = G[disc], APPS[disc]
        grid = lambda side, block, apps=apps, disc=disc: (disc, apps[block * 2 + side]) \
            if 0 <= block * 2 + side < len(apps) else err(f'{disc} judges: panel {block},{side}') or (disc, '?')
        for code, rnd in ((f'GAR{g}GENQUAL_57{"A" if disc == "MAG" else "B"}', 'QUAL'),
                          (f'GAR{g}1AAFNL_57{"A" if disc == "MAG" else "B"}', 'AA')):
            n0 = len(rows[disc])
            block = judge_pages(disc, code, rnd, grid, rows, f'{disc} judges {rnd}')
            if block[0] + 1 != len(apps) // 2:
                err(f'{disc} judges {rnd}: {block[0] + 1} panel rows')
            for r in rows[disc][n0:]:
                if r['Apparatus'] is None:      # the round's reserves serve every panel
                    r['Apparatus'] = ''
    for day in (1, 2):
        sides = (FINALS_DAY[day]['MAG'], FINALS_DAY[day]['WAG'])
        grid = lambda side, block, sides=sides: (('MAG', 'WAG')[side], sides[side][block]) \
            if block < len(sides[side]) else err(f'finals judges day {day}: panel {block},{side}') or ('MAG', '?')
        ns = {d: len(rows[d]) for d in rows}
        block = judge_pages(None, f'GARG1APFNLPART{day}_57D', 'EVENT', grid, rows, f'finals judges day {day}')
        if (block[0] + 1, block[1] + 1) != tuple(len(s) for s in sides):
            err(f'finals judges day {day}: {block} panels')
        for disc in rows:
            for r in rows[disc][ns[disc]:]:
                if r['Apparatus'] is None:
                    # A day's reserves serve that day's finals: one row per final (§4.7)
                    r['Apparatus'] = FINALS_DAY[day][disc][0]
                    for app in FINALS_DAY[day][disc][1:]:
                        rows[disc].append(dict(r, Apparatus=app))
    officials = official_list()
    for disc in rows:
        ev = EVENTS[PREFIX[disc]]
        seen, written = set(), []
        for r in rows[disc]:
            key = (r['Round'], r['Apparatus'], r['Function'], r['Name'])
            if key in seen:           # the finals Superior Jury is printed on both days
                continue
            seen.add(key)
            sur, giv = split_name(r['Name'])
            if not sur or not giv:
                err(f'{disc} judges: name split {r["Name"]!r}')
            written.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                            'Event Start Date': ev['Start Date'], 'Round': r['Round'],
                            'Apparatus': r['Apparatus'], 'Function': r['Function'], 'Name': r['Name'],
                            'Surname': sur, 'Given Name': giv, 'NOC Code': r['NOC']})
        check_judges(disc, written, officials)
        out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, written)

def official_list():
    """Competition Officials pages: surname -> set of organisations, per discipline."""
    found = {}
    for disc in ('MAG', 'WAG'):
        found[disc] = defaultdict(set)
        for l in lines(find(f'GAR{G[disc]}_35')):
            m = re.search(r'(?:^|\s{2,})([A-Z][A-Za-z\'-]*(?: [A-Za-z\'-]+)+?)\s{2,}([A-Z]{3})\s*$', l)
            if m:
                found[disc][surname_key(split_name(m.group(1))[0])].add(m.group(2))
    return found

# Judges the Competition Officials list credits to another CGA than every Judges Assignments page
# does; written as the assignments print them: (disc, name) -> (assignments, officials list)
OFFICIALS_DIFFER = {('WAG', 'PADDOCK Samantha'): ('ENG', {'WAL'})}

def surname_key(s):
    return re.sub(r'[^A-Z]', '', s.upper())

def check_judges(disc, rows, officials):
    by_panel = defaultdict(set)
    for r in rows:
        by_panel[(r['Round'], r['Apparatus'])].add(r['Function'])
    for rnd in ('QUAL', 'AA', 'EVENT'):
        n_e = 5 if rnd == 'EVENT' else 4
        want = {'D1', 'D2'} | {f'E{i}' for i in range(1, n_e + 1)} | {'SV'}
        for app in APPS[disc]:
            fns = by_panel[(rnd, app)]
            if not want <= fns or f'E{n_e + 1}' in fns:
                err(f'{disc} judges {rnd} {app}: panel {sorted(fns)}')
        if 'President' not in by_panel[(rnd, '')]:
            err(f'{disc} judges {rnd}: no President')
    # Every panel judge is on the discipline's Competition Officials list, credited to the same
    # CGA (given names differ between the two lists: HANLEY Nikki / Nicola)
    noc = defaultdict(set)
    for r in rows:
        if r['NOC Code']:
            noc[r['Name']].add(r['NOC Code'])
            listed = officials[disc].get(surname_key(r['Surname']), set())
            if OFFICIALS_DIFFER.get((disc, r['Name'])) == (r['NOC Code'], listed):
                continue
            if r['NOC Code'] not in listed:
                err(f'{disc} judges: {r["Name"]} {r["NOC Code"]} not on the officials list')
    for name, nocs in noc.items():
        if len(nocs) > 1:
            err(f'{disc} judges: {name} credited to {sorted(nocs)}')
    print(f'  {disc} judges: {len(rows)} rows, {len({r["Name"] for r in rows})} judges')

# ---------------------------------------------------------------- apparatus tables
ID = r'^\s*(\d+)?\s+(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})\s+'

def split_values(vals, ctx, bonus_after=False):
    """`D E [Pen.] [Bonus] Score` (one routine); a negative value is a penalty and a positive one a
    bonus, whatever their order. Returns the routine."""
    r = dict(empty_routine(), Status='COMPLETED')
    if len(vals) < 3:
        err(f'{ctx}: values {vals}'); return r
    r['D'], r['E'], r['Total'] = vals[0], vals[1], vals[-1]
    if not re.fullmatch(r'!?' + SCORE, r['D']) or not re.fullmatch(SCORE, r['E']) \
            or not re.fullmatch(SCORE, r['Total']):
        err(f'{ctx}: unexpected values {vals}')
    for v in vals[2:-1]:
        key = 'Penalty' if v.startswith('-') else 'B'
        if not re.fullmatch(r'-?\d+\.\d', v) or r[key]:
            err(f'{ctx}: unexpected value {v!r} in {vals}')
        r[key] = v
    check_routine(ctx, r)
    return r

def single_table(disc, rnd, app):
    """One-routine apparatus table -> rows in printed order. Finals print the qualification rank
    and start order after the score."""
    ctx = f'{disc} {rnd} {app}'
    idx = find(f'GAR{G[disc]}1AP{app}{"QUAL" if rnd == "QUAL" else "FNL"}_73I')
    check_page_date(idx, session_date(disc, rnd, app), ctx)
    ls = lines(idx)
    rows = []
    for l in ls:
        m = re.match(ID + r'(.*)$', l)
        if not m:
            continue
        rank, bib, name, noc, rest = m.groups()
        vals = rest.split()
        row = dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, Q='', QRank='', Start='')
        if vals == ['DNS']:
            if rank:
                err(f'{ctx}: ranked DNS {l!r}')
            rows.append(row | dns_routine()); continue
        if rnd == 'QUAL' and vals[-1] in MARKERS:
            row['Q'] = vals.pop()
        if rnd == 'EVENT':
            if not (vals[-1].isdigit() and vals[-2].isdigit()):
                err(f'{ctx} bib {bib}: no qualification rank and start order {vals}')
            row['Start'], row['QRank'] = vals.pop(), vals.pop()
        r = split_values(vals, f'{ctx} bib {bib}')
        if r['B'] and disc == 'WAG':
            err(f'{ctx} bib {bib}: a WAG bonus')
        if not rank:
            err(f'{ctx} bib {bib}: unranked routine')
        rows.append(row | r)
    n_rank = sum(1 for l in ls if re.match(r'^\s*\d+\s+\d{3}\s+[A-Z]', l))
    n_dns = sum(1 for l in ls if re.search(r'\sDNS\s*$', l))
    if n_rank + n_dns != len(rows):
        err(f'{ctx}: parsed {len(rows)} rows, counted {n_rank} ranked + {n_dns} DNS')
    checks.check_rank_order(ctx, rows)
    return rows

def vault_line(vals, ctx):
    """One attempt: `D E [Pen.] [Bonus] Score`, then on the first line WAG's combined `Bonus`
    (+0.2, printed after the vault score)."""
    i = max(k for k, v in enumerate(vals) if re.fullmatch(SCORE, v))
    r = split_values(vals[:i + 1], ctx)
    after = vals[i + 1:]
    if len(after) > 1 or (after and not re.fullmatch(r'\d\.\d', after[0])):
        err(f'{ctx}: unexpected values after the score {after}')
    return vault_status(r), (after[0] if after else '')

def double_table(disc, rnd):
    """Two-vault table: each vaulter on two lines (`1 …`, `2 …`) -> rows with v1, v2, Total."""
    ctx = f'{disc} {rnd} VT'
    idx = find(f'GAR{G[disc]}1APVT{"QUAL" if rnd == "QUAL" else "FNL"}_73J')
    check_page_date(idx, session_date(disc, rnd, 'VT'), ctx)
    ls = lines(idx)
    rows, cur = [], None
    for l in ls:
        m = re.match(ID + r'1\s+(.*)$', l)
        if m:
            rank, bib, name, noc, rest = m.groups()
            vals = rest.split()
            cur = dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, Q='', QRank='', Start='')
            if rnd == 'QUAL' and vals[-1] in MARKERS:
                cur['Q'] = vals.pop()
            if rnd == 'EVENT':
                cur['Start'], cur['QRank'] = vals.pop(), vals.pop()
            total = vals.pop()
            if total != 'DNF' and not re.fullmatch(SCORE, total):
                err(f'{ctx} bib {bib}: bad total {total!r}')
            cur['v1'], cur['Bonus'] = vault_line(vals, f'{ctx} bib {bib} v1')
            cur['Total'] = '' if total == 'DNF' else total
            if bool(rank) == (total == 'DNF'):
                err(f'{ctx} bib {bib}: rank {rank!r} with total {total}')
            rows.append(cur)
            continue
        m = re.match(r'^\s+2\s+(.*)$', l)
        if m and cur is not None and 'v2' not in cur:
            vals = m.group(1).split()
            if vals == ['DNS']:
                cur['v2'] = dns_routine()
                if cur['Total']:
                    err(f'{ctx} bib {cur["Bib"]}: vault 2 DNS with a result')
            else:
                cur['v2'], extra = vault_line(vals, f'{ctx} bib {cur["Bib"]} v2')
                if extra:
                    err(f'{ctx} bib {cur["Bib"]}: a bonus on the vault 2 line')
                checks.check_vault_average(f'{ctx} bib {cur["Bib"]}', cur['v1']['Total'], cur['v2']['Total'],
                                           cur['Bonus'], cur['Total'])
            continue
        if re.match(r'^\s*\d+\s+\d{3}\s+[A-Z]', l):
            err(f'{ctx}: unparsed {l!r}')
    if any('v2' not in r for r in rows):
        err(f'{ctx}: missing vault 2 line')
    n_id = sum(1 for l in ls if re.match(ID + r'1\s', l))
    if n_id != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_id}')
    if disc == 'MAG' and any(r['Bonus'] for r in rows):
        err(f'{ctx}: a combined bonus on MAG')
    checks.check_rank_order(ctx, rows)
    return rows

# ---------------------------------------------------------------- team and all-around reports
def span_of(starts, pos):
    """The column a value printed at `pos` belongs to: columns start a little left of their
    anchors (the team line's `(rank)`, or each routine's D value)."""
    k = None
    for i, s in enumerate(starts):
        if s is not None and pos >= s - 3:
            k = i
    return k

def detail_line(l, starts, apps, ctx):
    """The E line and the bonus/penalty line(s) under a member's routines: each value goes to the
    column it's printed in; 3 decimals is E, a signed 1-decimal value a penalty, unsigned a bonus."""
    for m in re.finditer(r'(?<![\d.])-?\d+\.\d+(?![\d.])', l):
        k = span_of(starts, m.start())
        x = apps.get(APP_ORDER[k]) if k is not None else None
        if not x or x['Status'] == 'DNS':
            err(f'{ctx}: value {m.group()} at {m.start()} under no routine'); continue
        v = m.group()
        key = 'E' if re.fullmatch(SCORE, v) else 'Penalty' if v.startswith('-') else 'B'
        if x[key]:
            err(f'{ctx}: two values for {key} under {APP_ORDER[k]}')
        x[key] = v

APP_ORDER = []

def team_report(disc):
    """Team results: a team line (`(rank) total` per apparatus, then the team total or DNF), then
    each member's D line (`D score` per apparatus, or DNS), E line and B/P line (WAG: one `E P`
    line). The columns have icon headings, in the legend's order; values are placed by position
    under the team line's `(rank)` anchors."""
    global APP_ORDER
    APP_ORDER = APPS[disc]
    n = len(APP_ORDER)
    ctx0 = f'{disc} QUAL team'
    idx = find(f'GAR{G[disc]}TEAMFNL_73{"C" if disc == "MAG" else "D"}')
    check_page_date(idx, SESSION_DATE[disc]['QUAL'], ctx0)
    teams = []
    for i in idx:
        ls = PAGES[i].split('\n')
        anchors = None
        for l in ls:
            a = [m.start() for m in re.finditer(r'\(\d+\)\s+' + SCORE, l)]
            if len(a) == n:
                anchors = a; break
        team, member = None, None
        for j, l in enumerate(ls):
            m = re.match(r'^\s*(\d+)?\s+([A-Z]{3}) - (\S.*?)\s{2,}(\(.*)$', l)
            if m:
                rank, noc, _, rest = m.groups()
                if anchors is None:
                    err(f'{ctx0}: page {i + 1} has no full team line'); break
                totals = {}
                for t in re.finditer(r'\((\d+)\)\s+(' + SCORE + ')', l):
                    k = span_of(anchors, t.start())
                    totals[APP_ORDER[k]] = t.group(2)
                total = l.split()[-1]
                if total != 'DNF' and not re.fullmatch(SCORE, total):
                    err(f'{ctx0} {noc}: total {total!r}')
                team = dict(Rank=rank or '', NOC=noc, totals=totals, Total='' if total == 'DNF' else total,
                            members=[])
                if bool(rank) == (total == 'DNF'):
                    err(f'{ctx0} {noc}: rank {rank!r} with total {total}')
                teams.append(team)
                continue
            m = re.match(r'^\s+(\d{3}) (\S.*?)\s{2,}D(?=\s|$)(.*)$', l)
            if m and team is not None:
                bib, name, rest = m.groups()
                ctx = f'{ctx0} {team["NOC"]} bib {bib}'
                check_name(disc, ctx, bib, name, team['NOC'])
                apps = {}
                start = m.start(3)
                for t in re.finditer(r'(' + SCORE + r')\s+(' + SCORE + r')|DNS', rest):
                    pos = start + t.start() + (2 if t.group() == 'DNS' else 0)
                    app = APP_ORDER[span_of(anchors, pos)]
                    if app in apps:
                        err(f'{ctx}: two routines under {app}')
                    apps[app] = dns_routine() if t.group() == 'DNS' else \
                        dict(empty_routine(), Status='COMPLETED', D=t.group(1), Total=t.group(2))
                # The detail lines follow: MAG `E` and `BP`, WAG `EP`
                for dl in ls[j + 1:j + 3]:
                    dm = re.match(r'^\s+(E|BP|EP)(?=\s|$)', dl)
                    if dm:
                        detail_line(dl[dm.end():].rjust(len(dl)), anchors, apps, ctx)
                for app, x in apps.items():
                    if x['Status'] == 'COMPLETED':
                        if app == 'VT':
                            vault_status(x)
                        if not x['E']:
                            err(f'{ctx} {app}: no E value')
                        check_routine(f'{ctx} {app}', x)
                team['members'].append(dict(Bib=bib, apps=apps))
    for t in teams:
        ctx = f'{ctx0} {t["NOC"]}'
        for app in APP_ORDER:
            sc = sorted((D(x['apps'][app]['Total']) for x in t['members']
                         if app in x['apps'] and x['apps'][app]['Status'] != 'DNS'), reverse=True)
            if not sc:
                if app in t['totals']:
                    err(f'{ctx} {app}: a total with no scores')
                continue
            if sum(sc[:3]) != D(t['totals'].get(app)):
                err(f'{ctx} {app}: best three {sum(sc[:3])} != {t["totals"].get(app)}')
        if t['Total'] and sum(D(v) for v in t['totals'].values()) != D(t['Total']):
            err(f'{ctx}: apparatus totals != {t["Total"]}')
        if t['Total'] and len(t['totals']) != len(APP_ORDER):
            err(f'{ctx}: a ranked team without every apparatus')
    checks.check_rank_order(ctx0, [dict(Rank=t['Rank'], Total=t['Total'], Bib=t['NOC']) for t in teams])
    print(f'  {ctx0}: {len(teams)} teams')
    return teams

def aa_report(disc, rnd):
    """All-around results: per athlete a D line (`rank bib name CGA D`, then `D score (Rk)` per
    apparatus or DNS, the total and any marker), an E line and a B/P line (WAG: `E P`)."""
    global APP_ORDER
    APP_ORDER = APPS[disc]
    n = len(APP_ORDER)
    ctx0 = f'{disc} {rnd} AA'
    idx = find(f'GAR{G[disc]}1AA{"QUAL" if rnd == "QUAL" else "FNL"}_73{"G" if disc == "MAG" else "H"}')
    check_page_date(idx, SESSION_DATE[disc][rnd], ctx0)
    ls = lines(idx)
    athletes = []
    for j, l in enumerate(ls):
        m = re.match(r'^\s*(\d+)?\s+(\d{3}) (\S.*?)\s{2,}([A-Z]{3})\s+D(?=\s)(.*)$', l)
        if not m:
            continue
        rank, bib, name, noc, rest = m.groups()
        ctx = f'{ctx0} bib {bib}'
        name = check_name(disc, ctx, bib, name, noc)
        start = m.start(5)
        tail = rest.split()
        q = tail.pop() if tail[-1] in MARKERS else ''
        total = tail.pop()
        if total not in ('DNF', 'DNS') and not re.fullmatch(SCORE, total):
            err(f'{ctx}: total {total!r}')
        body = rest[:rest.rfind(total)]
        slots = list(re.finditer(r'(' + SCORE + r')\s+(' + SCORE + r')\s+\((\d+)\)|DNS', body))
        if len(slots) != n:
            err(f'{ctx}: {len(slots)} apparatus'); continue
        apps, starts = {}, []
        for app, t in zip(APP_ORDER, slots):
            starts.append(start + t.start())
            apps[app] = dns_routine() if t.group() == 'DNS' else \
                dict(empty_routine(), Status='COMPLETED', D=t.group(1), Total=t.group(2), Rank=t.group(3))
        for dl in ls[j + 1:j + 3]:
            dm = re.match(r'^\s+(E P|E|BP)(?=\s|$)', dl)
            if dm:
                detail_line(' ' * dm.end() + dl[dm.end():], starts, apps, ctx)
        for app, x in apps.items():
            if x['Status'] == 'COMPLETED':
                if app == 'VT':
                    vault_status(x)
                if not x['E']:
                    err(f'{ctx} {app}: no E value')
                check_routine(f'{ctx} {app}', x)
        if total in ('DNF', 'DNS'):
            if rank:
                err(f'{ctx}: ranked {total}')
            total = ''
        else:
            s = sum(D(x['Total']) for x in apps.values())
            if s != D(total) or any(x['Status'] == 'DNS' for x in apps.values()):
                err(f'{ctx}: apparatus sum {s} != {total}')
        athletes.append(dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, apps=apps, Total=total, Q=q))
    n_id = sum(1 for l in ls if re.match(r'^\s*(\d+)?\s+\d{3} \S.*?\s{2,}[A-Z]{3}\s+D\s', l))
    if n_id != len(athletes):
        err(f'{ctx0}: parsed {len(athletes)} of {n_id}')
    checks.check_rank_order(ctx0, athletes)
    if rnd == 'QUAL' and any(a['Q'] for a in athletes if not a['Total']):
        err(f'{ctx0}: a marker on an unranked athlete')
    return athletes

# ---------------------------------------------------------------- writing scores
def meta(disc, rnd, app, rank, bib, name, noc):
    COMPETED[disc].add(bib)
    return {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
            'Session Start Date': session_date(disc, rnd, app), 'Round': rnd, 'Part': '', 'Apparatus': app,
            'Rank': rank, 'Bib': bib, 'Name': check_name(disc, f'{disc} {rnd} {app}', bib, name, noc),
            'NOC Code': noc}

def routine_of(r):
    return {k: r[k] for k in ROUTINE_KEYS}

def vault_cols(n, v):
    return {f'{k}{n}': v[k] for k in ROUTINE_KEYS}

def same_routine(ctx, a, b, keys=ROUTINE_KEYS):
    if {k: a[k] for k in keys} != {k: b[k] for k in keys}:
        err(f'{ctx}: {routine_of(a)} != {routine_of(b)}')

def qual_scores(disc, app, teams, aaq):
    """SCORES-QUAL-<app>; returns the written rows. Team and all-around report routines must match
    the table's (vault: the first vault, from either list)."""
    ctx = f'{disc} QUAL {app}'
    reported = {}   # bib -> (routine, source); a bib can be in both reports, which must agree
    for t in teams:
        for x in t['members']:
            if app in x['apps']:
                reported[x['Bib']] = (x['apps'][app], f'team report {t["NOC"]}')
    aa_rank = {}
    for a in aaq:
        x = a['apps'][app]
        if a['Bib'] in reported:
            same_routine(f'{ctx} bib {a["Bib"]}: team vs all-around report', reported[a['Bib']][0], x)
        reported[a['Bib']] = (x, 'all-around report')
        aa_rank[a['Bib']] = x.get('Rank', '')
    rows = []
    if app != 'VT':
        for r in single_table(disc, 'QUAL', app):
            if r['Bib'] in reported:
                x, src = reported.pop(r['Bib'])
                same_routine(f'{ctx} bib {r["Bib"]} ({src})', x, r)
            rows.append(meta(disc, 'QUAL', app, r['Rank'], r['Bib'], r['Name'], r['NOC']) | routine_of(r)
                        | {'Qualification': r['Q'], 'Qualification Rank': r['Rank']})
        for bib, (_, src) in reported.items():
            err(f'{ctx} bib {bib}: in the {src} but not in the table')
        return rows
    double = double_table(disc, 'QUAL')
    for r in double:
        # A specialist from a CGA without a team (NIR's McATEER) is in neither report
        if r['Bib'] in reported:
            same_routine(f'{ctx} bib {r["Bib"]} vault 1 ({reported[r["Bib"]][1]})', reported[r['Bib']][0], r['v1'])
        elif r['NOC'] in {t['NOC'] for t in teams}:
            err(f'{ctx} bib {r["Bib"]}: a team member missing from the team report')
        rows.append(meta(disc, 'QUAL', app, aa_rank.get(r['Bib'], ''), r['Bib'], r['Name'], r['NOC'])
                    | vault_cols(1, r['v1']) | vault_cols(2, r['v2'])
                    | {'Combined Bonus': r['Bonus'], 'Total': r['Total'], 'Qualification': r['Q'],
                       'Qualification Rank': r['Rank']})
    in_double = {r['Bib'] for r in double}
    singles = []
    for bib, (x, src) in reported.items():
        if bib in in_double:
            continue
        name, noc = NAMES[disc][bib]
        singles.append(meta(disc, 'QUAL', app, aa_rank.get(bib, ''), bib, name, noc) | vault_cols(1, x)
                       | vault_cols(2, empty_routine())
                       | {'Combined Bonus': '', 'Total': x['Total'], 'Qualification': '', 'Qualification Rank': ''})
    singles.sort(key=lambda r: (r['Status1'] == 'DNS', -D(r['Total1']), int(r['Bib'])))
    rows += singles
    return rows

def check_vault_ranks(disc, rows, ctx):
    """The all-around report ranks each all-arounder's first vault against the whole field: a
    rank r means fewer than r first vaults beat it and at least r are as good or better."""
    field = [D(r['Total1']) for r in rows if r['Status1'] != 'DNS']
    for r in rows:
        if not r['Rank']:
            continue
        t = D(r['Total1'])
        better = sum(1 for v in field if v > t)
        same = sum(1 for v in field if v == t)
        if not better < int(r['Rank']) <= better + same:
            err(f'{ctx} bib {r["Bib"]}: vault 1 rank {r["Rank"]} for {t}, {better} better and {same} equal')
    ranked = sorted((r for r in rows if r['Rank']), key=lambda r: int(r['Rank']))
    checks.check_rank_order(ctx + ' vault 1', [dict(Rank=r['Rank'], Total=r['Total1'], Bib=r['Bib']) for r in ranked])

def check_against_tables(disc, rnd, athletes, rows_by_app):
    """Every all-around report routine is in that round's apparatus table with the same values
    and rank (vault qualification: its first vault, and the Rk column ranks the whole field)."""
    for a in athletes:
        for app, x in a['apps'].items():
            ctx = f'{disc} {rnd} AA bib {a["Bib"]} {app}'
            row = next((r for r in rows_by_app[app] if r['Bib'] == a['Bib']), None)
            if row is None:
                err(f'{ctx}: not in the apparatus table'); continue
            if app == 'VT' and rnd == 'QUAL':
                same_routine(ctx, x, {k: row[f'{k}1'] for k in ROUTINE_KEYS})
                continue
            same_routine(ctx, x, row)
            if x['Status'] != 'DNS' and x['Rank'] != row['Rank']:
                err(f'{ctx}: rank {x["Rank"]}, table {row["Rank"]}')

def aa_scores(disc, aaf):
    """SCORES-AA-<app> from the all-around final report (single-attempt vault), ordered by the
    apparatus rank its Rk column gives."""
    by_app = {}
    for app in APPS[disc]:
        rows = []
        for a in aaf:
            x = a['apps'][app]
            rows.append(meta(disc, 'AA', app, x.get('Rank', ''), a['Bib'], a['Name'], a['NOC']) | routine_of(x))
        rows.sort(key=lambda r: (not r['Rank'], int(r['Rank'] or 0)))
        checks.check_rank_order(f'{disc} AA {app}', rows)
        out.csv(f'{PREFIX[disc]}-SCORES-AA-{app}.csv', common.score_header(False, False), rows)
        by_app[app] = rows
    return by_app

def event_scores(disc, app):
    ctx = f'{disc} EVENT {app}'
    rows, printed = [], []
    if app == 'VT':
        for r in double_table(disc, 'EVENT'):
            rows.append(meta(disc, 'EVENT', app, r['Rank'], r['Bib'], r['Name'], r['NOC'])
                        | vault_cols(1, r['v1']) | vault_cols(2, r['v2'])
                        | {'Combined Bonus': r['Bonus'], 'Total': r['Total']})
            printed.append(r)
        out.csv(f'{PREFIX[disc]}-SCORES-EVENT-VT.csv', common.score_header(True, False), rows)
    else:
        for r in single_table(disc, 'EVENT', app):
            rows.append(meta(disc, 'EVENT', app, r['Rank'], r['Bib'], r['Name'], r['NOC']) | routine_of(r))
            printed.append(r)
        out.csv(f'{PREFIX[disc]}-SCORES-EVENT-{app}.csv', common.score_header(False, False), rows)
    if len(rows) != 8:
        err(f'{ctx}: {len(rows)} finalists')
    return rows, printed

# ---------------------------------------------------------------- finals checks
def finals_start_lists():
    """Apparatus finals start lists: the men's finals down the left, the women's down the right,
    in the schedule's order; each lists its eight finalists in start order, then the reserves
    (R1-R3 and the NR athletes ranked among them) by name."""
    found = {}
    for day in (1, 2):
        blocks = {0: [], 1: []}
        for l in lines(find(f'GARG1APFNLPART{day}_51G')):
            if re.match(r'^\s+Bib\s+Name', l):
                blocks[0].append([])
                if l.find('Bib', SPLIT) >= 0:
                    blocks[1].append([])
                continue
            for m in re.finditer(r'(?:(?<!\S)(\d{3})|(?<!\S)(R\d|NR))\s+(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', l):
                side = 0 if m.start() < SPLIT else 1
                blocks[side][-1].append(m.groups())
        for side, disc in ((0, 'MAG'), (1, 'WAG')):
            bl = [b for b in blocks[side] if b]
            if len(bl) != len(FINALS_DAY[day][disc]):
                err(f'finals start lists day {day} {disc}: {len(bl)} lists'); continue
            for app, b in zip(FINALS_DAY[day][disc], bl):
                finalists = [bib for bib, mark, name, noc in b if bib]
                reserves = {}
                for bib, mark, name, noc in b:
                    if bib:
                        check_name(disc, f'{disc} EVENT {app} start list', bib, name, noc)
                    else:
                        rb = BY_NAME[disc].get((name, noc))
                        if rb is None:
                            err(f'{disc} EVENT {app} start list: reserve {name} {noc} not on the entry list')
                        reserves[rb] = mark
                found[(disc, app)] = (finalists, reserves)
    return found

def check_final(disc, app, qual_rows, final_rows, printed, start_list):
    """Finalists: their start order and qualification rank as the qualification and the start
    list have them; every finalist qualified, or came in as a reserve or (two per country) an NR
    compatriot; the start list's reserves carry the table's markers."""
    ctx = f'{disc} EVENT {app}'
    qrank_key = 'Qualification Rank'
    marks = {r['Bib']: r['Qualification'] for r in qual_rows}
    qrank = {r['Bib']: r[qrank_key] for r in qual_rows}
    noc = {r['Bib']: r['NOC Code'] for r in qual_rows}
    finalists, reserves = start_list
    by_start = [r['Bib'] for r in sorted(printed, key=lambda r: int(r['Start']))]
    if by_start != finalists or sorted(int(r['Start']) for r in printed) != list(range(1, 9)):
        err(f'{ctx}: start order {by_start} != start list {finalists}')
    for r in printed:
        if qrank.get(r['Bib']) != r['QRank']:
            err(f'{ctx} bib {r["Bib"]}: qualification rank {r["QRank"]}, qualification has {qrank.get(r["Bib"])}')
    for b, m in reserves.items():
        if marks.get(b) != m:
            err(f'{ctx}: start list reserve {b} {m}, qualification has {marks.get(b)}')
    fin = {r['Bib'] for r in final_rows}
    absent = sorted(b for b, m in marks.items() if m == 'Q' and b not in fin)
    came_in = sorted(b for b in fin if marks.get(b) != 'Q')
    for b in came_in:
        ok = marks.get(b, '').startswith('R') or \
            (marks.get(b) == 'NR' and any(noc[a] == noc[b] for a in absent))
        if not ok:
            err(f'{ctx}: bib {b} in the final without qualifying ({marks.get(b)})')
    if absent or came_in:
        print(f'  {ctx}: qualifiers {absent} replaced by {[(b, marks[b]) for b in came_in]}')
    if sum(1 for m in marks.values() if m == 'Q') != 8:
        err(f'{ctx}: {sum(1 for m in marks.values() if m == "Q")} qualifiers')

def check_aa_final(disc, qual, final):
    ctx = f'{disc} AA final'
    marks = {a['Bib']: a['Q'] for a in qual}
    noc = {a['Bib']: a['NOC'] for a in qual}
    q = {b for b, m in marks.items() if m == 'Q'}
    fin = {a['Bib'] for a in final}
    for b in fin - q:
        # A withdrawn qualifier's compatriot ranked above the first reserve may take the place
        # (WAG: DARIES Zelme, NR, for ROOSKRANTZ, both RSA)
        ok = marks.get(b, '').startswith('R') or \
            (marks.get(b) == 'NR' and any(noc[a] == noc[b] for a in q - fin))
        if not ok:
            err(f'{ctx}: bib {b} competed without qualifying ({marks.get(b)})')
    # Rotation 1 of the start list names all the finalists
    first = find(f'GAR{G[disc]}1AAFNL_51{"E" if disc == "MAG" else "F"}')[0]
    listed = set()
    for l in PAGES[first].split('\n'):
        if l.strip().startswith('Reserves'):
            break
        for m in re.finditer(r'(?<!\S)(\d{3})\s{2,}(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', l):
            check_name(disc, f'{ctx} start list', m.group(1), m.group(2), m.group(3))
            listed.add(m.group(1))
    if listed != fin:
        err(f'{ctx}: start list {sorted(listed ^ fin)} differ from the results')
    print(f'  {ctx}: {len(fin)} athletes; qualifiers absent {sorted(q - fin)}, reserves in {sorted(fin - q)}')

def check_tie_breaks(disc, tables):
    """Tie Break reports print the ranks and totals the tables carry for each tied athlete.
    `tables` maps (round, apparatus or 'AA') to bib -> (rank, total)."""
    g = G[disc]
    for i, c in enumerate(CODES):
        m = re.fullmatch(rf'GAR{g}1(AA|AP(\w\w))(QUAL|FNL)_77\w', c)
        if not m:
            continue
        key = ('QUAL' if m.group(3) == 'QUAL' else ('AA' if m.group(1) == 'AA' else 'EVENT'), m.group(2) or 'AA')
        ctx = f'{disc} {key} tie break (p. {i + 1})'
        n = 0
        for l in PAGES[i].split('\n'):
            t = re.match(r'^\s*=?(\d+)\s+(\d{3})\s+\S.*?\s{2,}([A-Z]{3})\s+(' + SCORE + ')', l)
            if not t:
                continue
            n += 1
            rank, bib, _, total = t.groups()
            if tables[key].get(bib) != (rank, total):
                err(f'{ctx}: bib {bib} rank {rank} total {total}, the results have {tables[key].get(bib)}')
        if not n:
            err(f'{ctx}: no rows')

EVENT_NAME = {'Team': 'TEAM', 'All-Around': 'AA', 'Floor Exercise': 'FX', 'Pommel Horse': 'PH', 'Rings': 'SR',
              'Vault': 'VT', 'Parallel Bars': 'PB', 'Horizontal Bar': 'HB', 'Uneven Bars': 'UB',
              'Balance Beam': 'BB'}

def check_medallists(podiums):
    """Medallists by Event (a summary page, §3.9) against the results: `podiums` maps
    (disc, event) to {(medal, CGA, name or None for a team)}."""
    got = defaultdict(set)
    event = None
    for l in lines(find('GAR_93')):
        m = re.match(r"^(Men|Women)'s (\S.*?)\s{2,}", l)
        if m:
            event = ('MAG' if m.group(1) == 'Men' else 'WAG', EVENT_NAME.get(m.group(2)))
        m = re.search(r'(GOLD|SILVER|BRONZE)\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', l)
        if m and event:
            got[event].add((m.group(1), m.group(3), None if event[1] == 'TEAM' else m.group(2)))
    if set(got) != set(podiums):
        err(f'medallists: events {sorted(set(got) ^ set(podiums))}')
    for k, want in podiums.items():
        if got.get(k) != want:
            err(f'medallists {k}: page {sorted(got.get(k, ()))}, results {sorted(want)}')

def podium(rows, name_key='Name'):
    medal = {'1': 'GOLD', '2': 'SILVER', '3': 'BRONZE'}
    return {(medal[r['Rank']], r['NOC Code'], r.get(name_key)) for r in rows if r['Rank'] in medal}

# ---------------------------------------------------------------- summaries
def summary_aa(disc, rnd, athletes):
    ev = EVENTS[PREFIX[disc]]
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part', 'Rank', 'Bib', 'Name',
           'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total']
    if rnd == 'QUAL':
        hdr.append('Qualification')
    rows = []
    for a in athletes:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Round': rnd, 'Part': '', 'Rank': a['Rank'], 'Bib': a['Bib'], 'Name': a['Name'], 'NOC Code': a['NOC'],
             'SJ Penalty': '', 'Total': a['Total'], 'Qualification': a['Q']}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = a['apps'][app]['Total']
        rows.append(r)
    out.csv(f'{PREFIX[disc]}-SUMMARY-{"QUAL" if rnd == "QUAL" else "FINAL"}-AA.csv', hdr, rows)
    return rows

def summary_team(disc, teams):
    ev = EVENTS[PREFIX[disc]]
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part', 'Rank', 'NOC Code'] + \
          [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for t in teams:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Round': 'QUAL', 'Part': '', 'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': '',
             'Total': t['Total'], 'Qualification': ''}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = t['totals'].get(app, '')
        rows.append(r)
    out.csv(f'{PREFIX[disc]}-SUMMARY-QUAL-TEAM.csv', hdr, rows)
    return rows

def check_team_members(disc, teams, qual):
    """A team's members with routines are exactly its CGA's athletes in the qualification tables,
    and their team-report routines are the tables' (vault: the first vault)."""
    for t in teams:
        members = {x['Bib'] for x in t['members']}
        tabled = {r['Bib'] for app in APPS[disc] for r in qual[app] if r['NOC Code'] == t['NOC']}
        active = {x['Bib'] for x in t['members'] if x['apps']}
        if active != tabled or not active <= members:
            err(f'{disc} QUAL team {t["NOC"]}: members {sorted(active)} != table athletes {sorted(tabled)}')
        for x in t['members']:
            for app, r in x['apps'].items():
                row = next((q for q in qual[app] if q['Bib'] == x['Bib']), None)
                ctx = f'{disc} QUAL team {t["NOC"]} bib {x["Bib"]} {app}'
                if row is None:
                    err(f'{ctx}: not in the table'); continue
                same_routine(ctx, r, {k: row[f'{k}1'] for k in ROUTINE_KEYS} if app == 'VT' else row)
        idle = members - active
        if idle:
            print(f'  {disc} QUAL team {t["NOC"]}: members with no routine {sorted(idle)}')

# ---------------------------------------------------------------- run
judges()
for disc in ('MAG', 'WAG'):
    participants(disc)
    qualification_start_lists(disc)
START_LISTS = finals_start_lists()
podiums = {}
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    teams = team_report(disc)
    aaq = aa_report(disc, 'QUAL')
    aaf = aa_report(disc, 'AA')
    qual, tie = {}, defaultdict(dict)
    for app in APPS[disc]:
        rows = qual_scores(disc, app, teams, aaq)
        if app == 'VT':
            check_vault_ranks(disc, rows, f'{disc} QUAL VT')
            out.csv(f'{PREFIX[disc]}-SCORES-QUAL-VT.csv', common.score_header(True, True), rows)
            tie[('QUAL', 'VT')] = {r['Bib']: (r['Qualification Rank'], r['Total']) for r in rows
                                   if r['Qualification Rank']}
        else:
            out.csv(f'{PREFIX[disc]}-SCORES-QUAL-{app}.csv', common.score_header(False, True), rows)
            tie[('QUAL', app)] = {r['Bib']: (r['Rank'], r['Total']) for r in rows}
        qual[app] = rows
        final, printed = event_scores(disc, app)
        check_final(disc, app, rows, final, printed, START_LISTS[(disc, app)])
        tie[('EVENT', app)] = {r['Bib']: (r['Rank'], r['Total']) for r in final}
        podiums[(disc, app)] = podium(final)
    check_against_tables(disc, 'QUAL', aaq, qual)
    check_team_members(disc, teams, qual)
    aa_by_app = aa_scores(disc, aaf)
    q_rows = summary_aa(disc, 'QUAL', aaq)
    f_rows = summary_aa(disc, 'AA', aaf)
    check_aa_final(disc, aaq, aaf)
    t_rows = summary_team(disc, teams)
    tie[('QUAL', 'AA')] = {r['Bib']: (r['Rank'], r['Total']) for r in q_rows}
    tie[('AA', 'AA')] = {r['Bib']: (r['Rank'], r['Total']) for r in f_rows}
    check_tie_breaks(disc, tie)
    podiums[(disc, 'AA')] = podium(f_rows)
    podiums[(disc, 'TEAM')] = {(m, n, None) for m, n, _ in podium(t_rows, name_key='-')}
    missing = set(NAMES[disc]) - COMPETED[disc]
    print(f'  {disc}: {len(COMPETED[disc])} of {len(NAMES[disc])} entries competed; none: {sorted(missing)}')
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])

check_medallists(podiums)
out.corrections.finish()
checks.finish()
