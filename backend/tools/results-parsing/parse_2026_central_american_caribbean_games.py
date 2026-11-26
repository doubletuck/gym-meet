"""Parse the 2026 Central American and Caribbean Games (Santo Domingo) artistic gymnastics results
book into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_central_american_caribbean_games.py \\
        data/2026/2026-CENTRAL-AMERICAN-CARIBBEAN-GAMES/18666-ResultsbookMedia.pdf

Writes PARTICIPANTS, JUDGES, SCORES-{C1,C2,C3}-<APP>, RANKING-FINAL-TEAM (Competition I decides the
team title), RANKING-QUAL-AA and RANKING-FINAL-AA, and an IMPORT.json, per discipline next to the PDF, reading event metadata from
the EVENT.csv already there. Exits non-zero if any check fails (docs/instructions-results-parsing.md
§3; this source format is §5.20).

The book is the Games' own print (Bornan timing) of ORIS-style reports, every page with text and a
footer code like GARM1APFX-------------QUAL--------_73I; pages 110-193 are the rhythmic and
trampoline books, skipped. The "Individual Qualification & Team Final" round decides the team titles;
the all-around and apparatus finals follow (§4.9), as at the Commonwealth Games.

Sources: the apparatus tables give every qualification and final routine, except vault: its
qualification table lists only the two-vault athletes, so the other first vaults come from the team
report and the all-around qualification report (which agree wherever both print one). The
all-around final has no apparatus tables; its routines come from its all-around report. The
qualification results by team (scores only), the start lists, lists of qualifiers, tie-break
reports and the medallists pages are cross-checks.
"""
import os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first as split_name

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-CENTRAL-AMERICAN-CARIBBEAN-GAMES'
PAGES = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
out = common.Output(OUT, common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err))

PREFIX = {d: f'{EVENT_PREFIX}-{d}-SR' for d in ('MAG', 'WAG')}
G = {'MAG': 'M', 'WAG': 'W'}
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
# Apparatus finals by day, in the order of the Competition Schedule and the start lists
FINALS_DAY = {1: {'MAG': ['FX', 'PH', 'SR'], 'WAG': ['VT', 'UB']},
              2: {'MAG': ['VT', 'PB', 'HB'], 'WAG': ['BB', 'FX']}}
# From the Competition Schedule page (§4.4); each results page's header date agrees (checked)
SESSION_DATE = {
    'MAG': {'QUAL': '2026-08-02', 'AA': '2026-08-04'},
    'WAG': {'QUAL': '2026-08-03', 'AA': '2026-08-04'},
}
FINALS_DATE = {1: '2026-08-05', 2: '2026-08-06'}
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

def bonus(v):
    """Bonuses print signed (`+0.1`); they are written unsigned."""
    return v.removeprefix('+')

# ---------------------------------------------------------------- page lookup
def footer_code(page):
    """GARM1APFX-------------QUAL--------_73I 1  Report Created ... -> GARM1APFXQUAL_73I (the
    judges pages have no Report Created stamp)."""
    m = re.search(r'^\s*(GAR\S+)\s+\d+(?:\s|$)', page, re.M)
    return m.group(1).replace('-', '') if m else ''

CODES = [footer_code(p) for p in PAGES]

def find(code, disc=None):
    """The pages of one report, in one run. The entry lists share a code across disciplines:
    `disc` keeps the pages headed Men or Women."""
    idx = [i for i, c in enumerate(CODES) if c == code]
    if disc:
        word = 'Men' if disc == 'MAG' else 'Women'
        idx = [i for i in idx if re.search(rf'^\s+{word}\s*$', '\n'.join(PAGES[i].split('\n')[:8]), re.M)]
    if not idx:
        raise SystemExit(f'no pages with code {code}')
    if idx != list(range(idx[0], idx[-1] + 1)):
        err(f'{code}: pages {[i + 1 for i in idx]} not in one run')
    return idx

def lines(idx):
    return [l for i in idx for l in PAGES[i].split('\n')]

def check_page_date(idx, want, ctx):
    """The date in a results page's header is the day of competition (the footer's is print time)."""
    for i in idx:
        m = re.search(r'(?:MON|TUE|WED|THU|FRI|SAT|SUN) (\d{1,2}) ([A-Z]{3}) (\d{4})', '\n'.join(PAGES[i].split('\n')[:8]))
        got = m and f'{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}'
        if got != want:
            err(f'{ctx}: page {i + 1} header date {got}, competition date {want}')

def empty_routine():
    return dict.fromkeys(ROUTINE_KEYS, '')

def dns_routine():
    return dict(empty_routine(), Status='DNS')

def check_routine(ctx, r):
    if r['Status'] != 'DNS':
        checks.check_sum(ctx, r['Total'], r['D'], r['E'], r['B'], r['Penalty'])

def vault_status(r):
    """An attempt scored 0.000 is an invalid vault (§4.3)."""
    if r['Status'] == 'COMPLETED' and D(r['Total']) == 0:
        r['Status'] = 'INVALID_VAULT'
    return r

# ---------------------------------------------------------------- participants
NAMES = {}                   # disc -> bib -> (name, noc), names as written (after corrections)
BY_NAME = {}                 # disc -> (name, noc) -> bib
COMPETED = defaultdict(set)  # disc -> bibs with at least one routine

def participants(disc):
    ctx = f'{disc} participants'
    ev = EVENTS[PREFIX[disc]]
    rows = []
    noc = None
    ls = lines(find('GAR_32A', disc))
    for l in ls:
        m = re.match(r'^\s+([A-Z]{3}) -\s+\S', l)
        if m:
            noc = m.group(1); continue
        m = re.match(r'^\s+(\S.*?)\s{2,}(\d+)\s+(\d{3})\s+(\d{1,2}) ([A-Z]{3}) (\d{4})\s*$', l)
        if not m:
            continue
        name, lic, bib, d, mon, y = m.groups()
        sur, giv = split_name(name)
        if not sur or not giv:
            err(f'{ctx}: name split {name!r} -> {sur!r}/{giv!r}')
        if any(r['Bib Number'] == bib for r in rows):
            err(f'{ctx}: duplicate bib {bib}')
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                     'Event Start Date': ev['Start Date'], 'Order': str(len(rows) + 1), 'NOC Code': noc,
                     'Bib Number': bib, 'FIG License': lic, 'Name': name, 'Surname': sur, 'Given Name': giv,
                     'Birth Year': y, 'Birth Date': f'{y}-{MONTHS[mon]:02d}-{int(d):02d}'})
    n_dates = sum(1 for l in ls if re.search(r'\d{3}\s+\d{1,2} [A-Z]{3} \d{4}\s*$', l))
    if n_dates != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_dates} entries')
    # The Number of Entries by NOC page counts every entry
    counts = entries_by_noc(disc)
    got = defaultdict(int)
    for r in rows:
        got[r['NOC Code']] += 1
    if dict(got) != counts:
        err(f'{ctx}: per NOC {dict(got)} != entries by NOC {counts}')
    print(f'  {ctx}: {len(rows)} entries')
    # Corrections (a name the entry list cuts short) apply as the file is written; the results
    # are checked against the written names
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)
    NAMES[disc] = {r['Bib Number']: (r['Name'], r['NOC Code']) for r in rows}
    BY_NAME[disc] = {v: b for b, v in NAMES[disc].items()}

def entries_by_noc(disc):
    """Number of Entries by NOC: Men, Women and Total columns, a blank for none, placed by the
    right edge of each column heading."""
    ls = lines(find('GAR_30'))
    head = next(l for l in ls if re.search(r'\bMen\s+Women\s+Total', l))
    edges = [head.find(w) + len(w) for w in ('Men', 'Women', 'Total')]
    col = 0 if disc == 'MAG' else 1
    counts = {}
    for l in ls:
        m = re.match(r'^\s*([A-Z]{3}) - ', l)
        if not m:
            continue
        for n in re.finditer(r'\d+', l[m.end():]):
            end = m.end() + n.end()
            k = min(range(3), key=lambda i: abs(edges[i] - end))
            if abs(edges[k] - end) > 4:
                err(f'entries by NOC: {m.group(1)} value {n.group()} under no column')
            if k == col:
                counts[m.group(1)] = int(n.group())
    return counts

def name_matches(printed, full):
    """A results row's name against the entry list. Reports cut long names short (`FERNANDEZ
    RODRIGUEZ Melissa Del`) or print the given names as initials, sometimes after a shortened
    surname (`TAPERIO JAYES MRJ`, `SOTO J` for SOTO RODRIGUEZ Jensuel Jose)."""
    if printed == full or full.startswith(printed):
        return True
    words = printed.split(' ')
    sur, giv = split_name(full)
    initials = ''.join(w[0] for w in giv.split(' '))
    return len(words) > 1 and re.fullmatch(r'[A-Z]+', words[-1]) is not None \
        and initials.startswith(words[-1]) and sur.split(' ')[:len(words) - 1] == words[:-1]

def check_name(disc, ctx, bib, name, noc):
    """A results row's identity against the entry list; returns the entry list's name."""
    if bib not in NAMES[disc]:
        err(f'{ctx}: bib {bib} not in participants'); return name
    full, pnoc = NAMES[disc][bib]
    if noc is not None and pnoc != noc:
        err(f'{ctx}: bib {bib} NOC {noc} != participants {pnoc}')
    if not name_matches(name, full):
        err(f'{ctx}: bib {bib} {name!r} != participants {full!r}')
    return full

def qualification_start_lists(disc):
    """Every bib on the qualification start lists (team members, individuals and the italic
    alternates) is on the entry list with the same name and NOC."""
    n = 0
    for sub in (1, 2):
        for l in lines(find(f'GAR{G[disc]}QUAL00000{sub}_51{"A" if disc == "MAG" else "B"}')):
            for m in re.finditer(r'(?<!\S)(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', l):
                check_name(disc, f'{disc} qualification start list', m.group(1), m.group(2), m.group(3))
                n += 1
    if not n:
        err(f'{disc} qualification start list: no entries')

# ---------------------------------------------------------------- judges
FUNCTION = {'AS': 'SV', 'Time Judge': 'T', 'Time Judge 1': 'T1', 'Time Judge 2': 'T2',
            'Line Judge': 'L', 'Line Judge 1': 'L1', 'Line Judge 2': 'L2'}
PANEL_ENTRY = re.compile(r'(?<!\S)(AS|D\d|E\d|Time Judge(?: \d)?|Line Judge(?: \d)?)\s+(\S.*?)\s{2,}([A-Z]{3,4})(?=\s|$)')
SJ_ENTRY = re.compile(r'Superior Jury:\s+(\S.*?)\s{2,}([A-Z]{3,4})\s{2,}(President|Technical Delegate)\s*$')
SJ_FUNCTION = {'President': 'President', 'Technical Delegate': 'TD'}

def judge_noc(noc):
    """Judges credited to the Pan American union (`UPAG`: the Superior Jury and the apparatus
    supervisors) are blank here; CORRECTIONS.csv fills each one's federation from other meets (§4.7)."""
    return '' if noc == 'UPAG' else noc

def judge_page(disc, code, rnd, rows):
    """One Judges Assignments page: the Superior Jury, then panels two to a row in the grid MAG
    FX/PH, SR/VT, PB/HB and WAG VT/UB, BB/FX (the icons; the WAG pages' legend prints the men's
    apparatus). A panel's time and line judges follow its E4; the right panel's are printed right
    of the column where its Function heading starts."""
    ctx = f'{disc} judges {rnd}'
    apps = APPS[disc]
    ls = lines(find(code))
    block, split, n_sj = -1, None, 0
    for l in ls:
        if l.strip().startswith('Legend'):
            break
        m = SJ_ENTRY.search(l)
        if m:
            n_sj += 1
            rows.append(dict(Round=rnd, Apparatus='', Function=SJ_FUNCTION[m.group(3)], Name=m.group(1),
                             NOC=judge_noc(m.group(2))))
            continue
        if re.match(r'^\s+Function\s+Name', l):
            block += 1
            split = l.find('Function', l.find('Function') + 1)
            if split < 0:
                err(f'{ctx}: a panel row with one panel')
            continue
        for m in PANEL_ENTRY.finditer(l):
            side = 0 if m.start() < split - 2 else 1
            k = block * 2 + side
            if not 0 <= k < len(apps):
                err(f'{ctx}: panel {block},{side}'); continue
            fn, name, noc = m.groups()
            rows.append(dict(Round=rnd, Apparatus=apps[k], Function=FUNCTION.get(fn, fn), Name=name,
                             NOC=judge_noc(noc)))
        n_fn = len(re.findall(r'(?<!\S)(?:AS|D\d|E\d|Time Judge|Line Judge)(?!\S)', l))
        if n_fn != len(PANEL_ENTRY.findall(l)):
            err(f'{ctx}: unparsed judges line {l!r}')
    if n_sj != 1:
        err(f'{ctx}: {n_sj} Superior Jury lines')
    if block + 1 != len(apps) // 2:
        err(f'{ctx}: {block + 1} panel rows')

def judges(disc):
    rows = []
    s = 'A' if disc == 'MAG' else 'B'
    for code, rnd in ((f'GAR{G[disc]}QUAL_57{s}', 'QUAL'), (f'GAR{G[disc]}1AAFNL_57{s}', 'AA'),
                      (f'GAR{G[disc]}1APFNL_57{s}', 'EVENT')):
        judge_page(disc, code, rnd, rows)
    ev = EVENTS[PREFIX[disc]]
    written = []
    for r in rows:
        sur, giv = split_name(r['Name'])
        if not sur or not giv:
            err(f'{disc} judges: name split {r["Name"]!r}')
        written.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                        'Event Start Date': ev['Start Date'], 'Competition': common.COMPETITION[r['Round']],
                        'Apparatus': r['Apparatus'], 'Function': r['Function'], 'Name': r['Name'],
                        'Surname': sur, 'Given Name': giv, 'NOC Code': r['NOC']})
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, written)
    check_judges(disc, written)

def check_judges(disc, rows):
    """Every panel is D1 D2 E1-E4 with its supervisor; a Superior Jury per round; one function per
    judge per panel; each judge credited to one federation (checked as written)."""
    by_panel = defaultdict(list)
    for r in rows:
        by_panel[(r['Competition'], r['Apparatus'])].append(r['Function'])
    want = {'SV', 'D1', 'D2', 'E1', 'E2', 'E3', 'E4'}
    for rnd in ('QUAL', 'AA', 'EVENT'):
        for app in APPS[disc]:
            fns = by_panel[(common.COMPETITION[rnd], app)]
            if not want <= set(fns) or len(fns) != len(set(fns)) or 'E5' in fns:
                err(f'{disc} judges {rnd} {app}: panel {sorted(fns)}')
        if len(by_panel[(common.COMPETITION[rnd], '')]) != 1:
            err(f'{disc} judges {rnd}: Superior Jury {by_panel[(common.COMPETITION[rnd], "")]}')
    noc = defaultdict(set)
    for r in rows:
        if r['NOC Code']:
            noc[r['Name']].add(r['NOC Code'])
    for name, nocs in noc.items():
        if len(nocs) > 1:
            err(f'{disc} judges: {name} credited to {sorted(nocs)}')
    print(f'  {disc} judges: {len(rows)} rows, {len({r["Name"] for r in rows})} judges')

# ---------------------------------------------------------------- apparatus tables
ID = r'^\s*(\d+)?\s+(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})\s+'

def split_values(vals, ctx):
    """`D E [Pen.] [Bonus] Score` (one routine); a negative value is a penalty and a signed
    positive one a bonus. D prints with one decimal in the tables and three in the reports."""
    r = dict(empty_routine(), Status='COMPLETED')
    if len(vals) < 3:
        err(f'{ctx}: values {vals}'); return r
    r['D'], r['E'], r['Total'] = vals[0], vals[1], vals[-1]
    if not re.fullmatch(r'\d+\.\d{1,3}', r['D']) or not re.fullmatch(SCORE, r['E']) \
            or not re.fullmatch(SCORE, r['Total']):
        err(f'{ctx}: unexpected values {vals}')
    for v in vals[2:-1]:
        key = 'Penalty' if v.startswith('-') else 'B'
        if not re.fullmatch(r'[-+]\d+\.\d', v) or r[key]:
            err(f'{ctx}: unexpected value {v!r} in {vals}')
        r[key] = bonus(v)
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

# The vault 2 line, after a name that wrapped (`Carmen` under FERNANDEZ RODRIGUEZ Melissa Del)
VAULT2 = re.compile(r'^\s+(?:[^\d\s][^\d]*?\s{2,})?2\s+(\d.*|DNS)\s*$')

def double_table(disc, rnd):
    """Two-vault table: each vaulter on two lines (`1 …`, `2 …`), each `D E [Pen.] Score`; the
    first line ends with WAG's combined `+0.2` bonus (if any) and the vault score -> rows."""
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
            cur = dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, Q='', QRank='', Start='', Bonus='')
            if rnd == 'QUAL' and vals[-1] in MARKERS:
                cur['Q'] = vals.pop()
            if rnd == 'EVENT':
                cur['Start'], cur['QRank'] = vals.pop(), vals.pop()
            total = vals.pop()
            if total != 'DNF' and not re.fullmatch(SCORE, total):
                err(f'{ctx} bib {bib}: bad total {total!r}')
            if re.fullmatch(r'\+\d\.\d', vals[-1]):
                cur['Bonus'] = bonus(vals.pop())
            cur['v1'] = vault_status(split_values(vals, f'{ctx} bib {bib} v1'))
            cur['Total'] = '' if total == 'DNF' else total
            if bool(rank) == (total == 'DNF'):
                err(f'{ctx} bib {bib}: rank {rank!r} with total {total}')
            rows.append(cur)
            continue
        m = VAULT2.match(l)
        if m and cur is not None and 'v2' not in cur:
            vals = m.group(1).split()
            if vals == ['DNS']:
                cur['v2'] = dns_routine()
                if cur['Total']:
                    err(f'{ctx} bib {cur["Bib"]}: vault 2 DNS with a result')
            else:
                cur['v2'] = vault_status(split_values(vals, f'{ctx} bib {cur["Bib"]} v2'))
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
    """The column a value printed at `pos` belongs to: the last column starting at or before it."""
    k = None
    for i, s in enumerate(starts):
        if s is not None and pos >= s:
            k = i
    return k

def detail_line(values, apps, ctx):
    """The E line under a row of routines: the E scores of the routines done, in order, each
    followed by its penalty (`-0.3`) or bonus (`+0.1`). The print drifts against the D line, so a
    bonus can sit nearer the next routine's E (MAG NUÑEZ FARFAN's rings `+0.1`); the order holds."""
    done = iter([x for x in apps.values() if x['Status'] == 'COMPLETED'])
    x = None
    for v in values.split():
        if re.fullmatch(SCORE, v):
            x = next(done, None)
            if x is None:
                err(f'{ctx}: E {v} for no routine'); return
            x['E'] = v
            continue
        key = 'Penalty' if v.startswith('-') else 'B'
        if x is None or not re.fullmatch(r'[-+]\d\.\d', v) or x[key]:
            err(f'{ctx}: unexpected {v!r} in the E line {values!r}'); continue
        x[key] = bonus(v)

def e_line(dl):
    """An E line's values: it may start with the end of a long name (`Gabriel   E 7.300`)."""
    m = re.match(r'^\s*(?:\S.*?\s{2,})?E\s+(?=[-+]?\d)', dl)
    return dl[m.end():] if m else None

def finish_routines(apps, ctx):
    for app, x in apps.items():
        if x['Status'] == 'COMPLETED':
            if app == 'VT':
                vault_status(x)
            if not x['E']:
                err(f'{ctx} {app}: no E value')
            check_routine(f'{ctx} {app}', x)

def team_report(disc):
    """Team results (`_73C`/`_73D`, titled Final, printed on qualification day): a team line
    (`total (rank)` per apparatus, then the team score), any `* Penalty -1.0` line, then each
    member's D line (`D score` per apparatus, or DNS) and E line (with penalties and bonuses).
    The columns have icon headings in the legend's order; a routine's apparatus is the team
    column its score starts in, and the E line's values sit under the member's D values."""
    apps_order = APPS[disc]
    n = len(apps_order)
    ctx0 = f'{disc} QUAL team'
    idx = find(f'GAR{G[disc]}TEAMFNL_73{"C" if disc == "MAG" else "D"}')
    check_page_date(idx, SESSION_DATE[disc]['QUAL'], ctx0)
    teams = []
    for i in idx:
        ls = PAGES[i].split('\n')
        team = None
        for j, l in enumerate(ls):
            m = re.match(r'^\s*(\d+)?\s+([A-Z]{3}) - (\S.*?)\s{2,}(' + SCORE + r' \(.*)$', l)
            if m:
                rank, noc, _, rest = m.groups()
                found = list(re.finditer(r'(' + SCORE + r') \((\d+)\)', l))
                if len(found) != n:
                    err(f'{ctx0} {noc}: {len(found)} apparatus totals'); continue
                anchors = [t.start() for t in found]
                total = l.split()[-1]
                if not re.fullmatch(SCORE, total):
                    err(f'{ctx0} {noc}: total {total!r}')
                team = dict(Rank=rank or '', NOC=noc, anchors=anchors, Penalty='', Total=total, members=[],
                            totals={a: t.group(1) for a, t in zip(apps_order, found)},
                            ranks={a: t.group(2) for a, t in zip(apps_order, found)})
                teams.append(team)
                continue
            m = re.match(r'^\s+\*\s*Penalty (-\d+\.\d)\s*$', l)
            if m and team is not None:
                if team['Penalty']:
                    err(f'{ctx0} {team["NOC"]}: two penalties')
                team['Penalty'] = m.group(1)
                continue
            m = re.match(r'^\s+(\d{3}) (\S.*?)\s{2,}D(?=\s|$)(.*)$', l)
            if m and team is not None:
                bib, name, rest = m.groups()
                ctx = f'{ctx0} {team["NOC"]} bib {bib}'
                check_name(disc, ctx, bib, name, team['NOC'])
                apps = {}
                start = m.start(3)
                for t in re.finditer(r'(\d+\.\d{3})\s+(' + SCORE + r')|DNS', rest):
                    pos = start + (t.start(2) if t.group(2) else t.start())
                    k = span_of(team['anchors'], pos)
                    app = apps_order[k] if k is not None else None
                    if app is None or app in apps or apps and apps_order.index(app) < apps_order.index(list(apps)[-1]):
                        err(f'{ctx}: routine at {pos} out of place ({app})'); continue
                    apps[app] = dns_routine() if t.group() == 'DNS' else \
                        dict(empty_routine(), Status='COMPLETED', D=t.group(1), Total=t.group(2))
                dl = e_line(ls[j + 1]) if j + 1 < len(ls) else None
                if dl is not None:
                    detail_line(dl, apps, ctx)
                elif any(x['Status'] == 'COMPLETED' for x in apps.values()):
                    err(f'{ctx}: no E line')
                finish_routines(apps, ctx)
                team['members'].append(dict(Bib=bib, apps=apps))
    for t in teams:
        ctx = f'{ctx0} {t["NOC"]}'
        for app in apps_order:
            sc = sorted((D(x['apps'][app]['Total']) for x in t['members']
                         if app in x['apps'] and x['apps'][app]['Status'] != 'DNS'), reverse=True)
            if sum(sc[:3]) != D(t['totals'].get(app)):
                err(f'{ctx} {app}: best three {sum(sc[:3])} != {t["totals"].get(app)}')
        if sum(D(v) for v in t['totals'].values()) + D(t['Penalty']) != D(t['Total']):
            err(f'{ctx}: apparatus totals and penalty {t["Penalty"]} != {t["Total"]}')
    checks.check_rank_order(ctx0, [dict(Rank=t['Rank'], Total=t['Total'], Bib=t['NOC']) for t in teams])
    for app in apps_order:
        ranked = sorted(teams, key=lambda t: int(t['ranks'][app]))
        checks.check_rank_order(f'{ctx0} {app}', [dict(Rank=t['ranks'][app], Total=t['totals'][app], Bib=t['NOC'])
                                                  for t in ranked])
    print(f'  {ctx0}: {len(teams)} teams')
    return teams

def team_qual_report(disc, teams, aaq, vault1):
    """Qualification results by team (`_73A`/`_73B`, scores only): each team's apparatus totals,
    ranks, penalty and score as the team report has them; every member's and individual's
    scores (vault: the first vault, then the two-vault athletes' second vault and result) and
    all-around total and rank as the other reports have them. `vault1` maps bib -> (vault 1
    total, two-vault row or None)."""
    ctx0 = f'{disc} QUAL team results'
    apps_order = APPS[disc]
    idx = find(f'GAR{G[disc]}QUAL_73{"A" if disc == "MAG" else "B"}')
    check_page_date(idx, SESSION_DATE[disc]['QUAL'], ctx0)
    by_noc = {t['NOC']: t for t in teams}
    aa = {a['Bib']: a for a in aaq}
    noc, seen_teams, n_rows = None, [], 0
    for l in lines(idx):
        m = re.match(r'^\s*(\d+)?\s+([A-Z]{3}) - \S', l)
        if m:
            noc = m.group(2)
            if m.group(1):
                seen_teams.append((m.group(1), noc))
            continue
        m = re.match(r'^\s+Total\s+(.*)$', l)
        if m:
            t = by_noc.get(noc)
            found = re.findall(r'(' + SCORE + r') \((\d+)\)', m.group(1))
            if t is None or found != [(t['totals'][a], t['ranks'][a]) for a in apps_order] \
                    or m.group(1).split()[-1] != t['Total']:
                err(f'{ctx0} {noc}: {m.group(1).split()} != the team report')
            continue
        m = re.match(r'^\s+\*\s*Penalty (-\d+\.\d)\s*$', l)
        if m:
            if by_noc.get(noc, {}).get('Penalty') != m.group(1):
                err(f'{ctx0} {noc}: penalty {m.group(1)} != the team report')
            continue
        m = re.match(r'^\s+(\d{3}) (\S.*?)\s{2,}((?:[-+]?\d+\.\d{3}|DNS|DNF|\+\d\.\d|\(\d+\))(?:\s+|$).*)$', l)
        if not m:
            continue
        bib, name, rest = m.groups()
        n_rows += 1
        ctx = f'{ctx0} bib {bib}'
        check_name(disc, ctx, bib, name, noc)
        # Every score, in apparatus order (vault: vault 1, then for a two-vaulter vault 2, any
        # bonus and the result), then the all-around total and rank if an all-arounder
        want, apparatus_scores = [], []
        for app in apps_order:
            x = routine_of_bib(disc, app, bib)
            if x is None:
                continue
            apparatus_scores.append(x)
            if app == 'VT':
                v1, double = vault1[bib]
                want.append(v1)
                if double is not None:
                    want += [double['v2']['Total'] or 'DNS'] + ([f'+{double["Bonus"]}'] if double['Bonus'] else []) \
                        + [double['Total'] or 'DNF']
            else:
                want.append(x)
        a = aa.get(bib)
        if a is not None:
            want += [a['Total'] or 'DNF'] + ([f'({a["Rank"]})'] if a['Rank'] else [])
        else:
            want.append(str(sum(D(v) for v in apparatus_scores if re.fullmatch(SCORE, v))))
        got = rest.split()
        if got != want and [v for v in want if not v.startswith('+')] == got:
            # An individual's line leaves out the vault bonus (WAG MANCIA POLANCO)
            print(f'  {ctx}: no vault bonus printed')
        elif got != want:
            err(f'{ctx}: {rest.split()} != {want}')
    if seen_teams != [(t['Rank'], t['NOC']) for t in teams]:
        err(f'{ctx0}: teams {seen_teams}')
    print(f'  {ctx0}: {n_rows} athletes checked')

QUAL_ROWS = {}   # (disc, app) -> written QUAL rows

def routine_of_bib(disc, app, bib):
    """A bib's qualification score on an apparatus as printed (vault: vault 1), or None."""
    row = next((r for r in QUAL_ROWS[(disc, app)] if r['Bib'] == bib), None)
    if row is None:
        return None
    st, total = (row['Status1'], row['Total1']) if app == 'VT' else (row['Status'], row['Total'])
    return 'DNS' if st == 'DNS' else total

def aa_report(disc, rnd):
    """All-around results: per athlete a D line (`rank bib name NOC D`, then `D score (Rk)` per
    apparatus or DNS, the total and any marker), maybe a line with the rest of the name, and an E
    line (with penalties and bonuses)."""
    apps_order = APPS[disc]
    n = len(apps_order)
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
        tail = rest.split()
        q = tail.pop() if tail[-1] in MARKERS else ''
        total = tail.pop()
        if total not in ('DNF', 'DNS') and not re.fullmatch(SCORE, total):
            err(f'{ctx}: total {total!r}')
        body = rest[:rest.rfind(total)]
        slots = list(re.finditer(r'(\d+\.\d{3})\s+(' + SCORE + r')\s+\((\d+)\)|DNS', body))
        if len(slots) != n:
            err(f'{ctx}: {len(slots)} apparatus'); continue
        apps = {}
        for app, t in zip(apps_order, slots):
            apps[app] = dns_routine() if t.group() == 'DNS' else \
                dict(empty_routine(), Status='COMPLETED', D=t.group(1), Total=t.group(2), Rank=t.group(3))
        dl = next((e_line(x) for x in ls[j + 1:j + 3] if e_line(x) is not None), None)
        if dl is not None:
            detail_line(dl, apps, ctx)
        finish_routines(apps, ctx)
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
            'Competition Start Date': session_date(disc, rnd, app), 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app,
            'Rank': rank, 'Bib': bib, 'Name': check_name(disc, f'{disc} {rnd} {app}', bib, name, noc),
            'NOC Code': noc}

def routine_of(r):
    return {k: r[k] for k in ROUTINE_KEYS}

def vault_cols(n, v):
    return {f'{k}{n}': v[k] for k in ROUTINE_KEYS}

def same_routine(ctx, a, b, keys=ROUTINE_KEYS):
    """Two prints of one routine agree; D is printed to one or three decimals."""
    def norm(r):
        return {k: (D(r[k]) if k == 'D' and r[k] else r[k]) for k in keys}
    if norm(a) != norm(b):
        err(f'{ctx}: {routine_of(a)} != {routine_of(b)}')

def qual_scores(disc, app, teams, aaq):
    """SCORES-C1-<app>; returns the written rows. Team and all-around report routines must match
    the table's (vault: the first vault, from either report)."""
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
        return rows, None
    double = double_table(disc, 'QUAL')
    for r in double:
        # An individual who isn't an all-arounder (MAG CRC VALVERDE) is in neither report
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
    return rows, {r['Bib']: r for r in double}

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
    """SCORES-C2-<app> from the all-around final report (single-attempt vault), ordered by the
    apparatus rank its Rk column gives."""
    for app in APPS[disc]:
        rows = []
        for a in aaf:
            x = a['apps'][app]
            rows.append(meta(disc, 'AA', app, x.get('Rank', ''), a['Bib'], a['Name'], a['NOC']) | routine_of(x))
        rows.sort(key=lambda r: (not r['Rank'], int(r['Rank'] or 0)))
        checks.check_rank_order(f'{disc} AA {app}', rows)
        out.csv(f'{PREFIX[disc]}-SCORES-C2-{app}.csv', common.score_header(False, False), rows)

def event_scores(disc, app):
    rows, printed = [], []
    if app == 'VT':
        for r in double_table(disc, 'EVENT'):
            rows.append(meta(disc, 'EVENT', app, r['Rank'], r['Bib'], r['Name'], r['NOC'])
                        | vault_cols(1, r['v1']) | vault_cols(2, r['v2'])
                        | {'Combined Bonus': r['Bonus'], 'Total': r['Total']})
            printed.append(r)
        out.csv(f'{PREFIX[disc]}-SCORES-C3-VT.csv', common.score_header(True, False), rows)
    else:
        for r in single_table(disc, 'EVENT', app):
            rows.append(meta(disc, 'EVENT', app, r['Rank'], r['Bib'], r['Name'], r['NOC']) | routine_of(r))
            printed.append(r)
        out.csv(f'{PREFIX[disc]}-SCORES-C3-{app}.csv', common.score_header(False, False), rows)
    if len(rows) != 8:
        err(f'{disc} EVENT {app}: {len(rows)} finalists')
    return rows, printed

# ---------------------------------------------------------------- finals checks
STARTER = re.compile(r'(?:(?<!\S)(\d{3})|(?<!\S)(R\d|NR))\s+(\S.*?)(?:\s{2,}| (?=[A-Z]{3}(?:\s{2,}|\s*$)))([A-Z]{3})(?=\s|$)')

def finals_start_lists():
    """Apparatus finals start lists (`GAR-1AP…FNL-PART<day>_51G`, revised): per day, blocks headed
    `Start Time: hh:mm`, the men's finals down the left and the women's down the right, in the
    schedule's order. Each lists its eight finalists in start order, then the reserves (R1-R3 and
    the NR athletes ranked among them) by name, without a bib."""
    found = {}
    for day in (1, 2):
        blocks = {0: [], 1: []}
        split = None
        for l in lines(find(f'GAR1APFNLPART{day}_51G')):
            if re.match(r'^\s+Men\s+Women\s*$', l):
                split = (l.find('Men') + l.find('Women')) // 2
            if 'Start Time:' in l:
                for m in re.finditer(r'Start Time:', l):
                    blocks[0 if m.start() < split else 1].append([])
                continue
            for m in STARTER.finditer(l):
                side = 0 if m.start() < split else 1
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

def lists_of_qualifiers(disc):
    """List of Qualifiers for the apparatus finals: per apparatus (the legend's grid, two to a
    row) the qualifying order 1-8, then the reserves `NR`/`R1`-`R3`, each with the qualification
    score. -> {app: [(order or marker, bib, score)]}."""
    apps = APPS[disc]
    found = {a: [] for a in apps}
    block = -1
    split = None
    for l in lines(find(f'GAR{G[disc]}1APFNL_53{"B" if disc == "MAG" else "C"}')):
        if re.match(r'^\s*Qualifying\s+.*Qualifying', l):
            block += 1
            split = l.rfind('Qualifying')
            continue
        for m in re.finditer(r'(?<!\S)(\d|R\d|NR)\s+(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})\s+(' + SCORE + ')', l):
            app = apps[block * 2 + (0 if m.start() < split - 2 else 1)]
            check_name(disc, f'{disc} {app} list of qualifiers', m.group(2), m.group(3), m.group(4))
            found[app].append((m.group(1), m.group(2), m.group(5)))
    return found

def check_qualifiers(disc, app, qual_rows, listed):
    """The list of qualifiers names the table's Q athletes in rank order (vault: the two-vault
    rank) and its marked reserves, with their qualification scores."""
    ctx = f'{disc} {app} list of qualifiers'
    rank_key = 'Qualification Rank'
    marked = sorted((r for r in qual_rows if r['Qualification']), key=lambda r: int(r[rank_key]))
    want = []
    n = 0
    for r in marked:
        if r['Qualification'] == 'Q':
            n += 1
            want.append((str(n), r['Bib'], r['Total']))
    want += [(r['Qualification'], r['Bib'], r['Total']) for r in marked if r['Qualification'] != 'Q']
    if sorted(listed) != sorted(want) or [x for x in listed if x[0].isdigit()] != [x for x in want if x[0].isdigit()]:
        err(f'{ctx}: {listed} != {want}')

def check_final(disc, app, qual_rows, final_rows, printed, start_list):
    """Finalists: their start order and qualification rank as the qualification and the start
    list have them; every finalist qualified, or came in as a reserve or (two per country) an NR
    compatriot; the start list's reserves carry the table's markers."""
    ctx = f'{disc} EVENT {app}'
    marks = {r['Bib']: r['Qualification'] for r in qual_rows}
    qrank = {r['Bib']: r['Qualification Rank'] for r in qual_rows}
    noc = {r['Bib']: r['NOC Code'] for r in qual_rows}
    finalists, reserves = start_list
    by_start = [r['Bib'] for r in sorted(printed, key=lambda r: int(r['Start']))]
    if by_start != finalists or sorted(int(r['Start']) for r in printed) != list(range(1, 9)):
        err(f'{ctx}: start order {by_start} != start list {finalists}')
    for r in printed:
        if qrank.get(r['Bib']) != r['QRank']:
            err(f'{ctx} bib {r["Bib"]}: qualification rank {r["QRank"]}, qualification has {qrank.get(r["Bib"])}')
    fin = {r['Bib'] for r in final_rows}
    # A start list printed after a reserve came in renumbers the reserves left (WAG floor)
    left = sorted((b for b, m in marks.items() if re.fullmatch(r'R\d', m) and b not in finalists),
                  key=lambda b: marks[b])
    renumbered = {b: f'R{i + 1}' for i, b in enumerate(left)}
    for b, m in reserves.items():
        if renumbered.get(b, marks.get(b)) != m:
            err(f'{ctx}: start list reserve {b} {m}, qualification has {marks.get(b)}')
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
    """All-around finalists qualified (or came in as a reserve or NR compatriot); the List of
    Qualifiers has the qualification's markers in order; the start list's first rotation names
    every finalist."""
    ctx = f'{disc} AA final'
    marks = {a['Bib']: a['Q'] for a in qual}
    noc = {a['Bib']: a['NOC'] for a in qual}
    total = {a['Bib']: a['Total'] for a in qual}
    q = {b for b, m in marks.items() if m == 'Q'}
    fin = {a['Bib'] for a in final}
    for b in fin - q:
        ok = marks.get(b, '').startswith('R') or \
            (marks.get(b) == 'NR' and any(noc[a] == noc[b] for a in q - fin))
        if not ok:
            err(f'{ctx}: bib {b} competed without qualifying ({marks.get(b)})')
    listed = []
    for l in lines(find(f'GAR{G[disc]}1AAFNL_53A')):
        m = re.match(r'^\s*(\d+|R\d|NR)\s+(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})\s+(' + SCORE + r')\s*$', l)
        if m:
            check_name(disc, f'{ctx} list of qualifiers', m.group(2), m.group(3), m.group(4))
            listed.append((m.group(1), m.group(2), m.group(5)))
    want = [(str(i + 1), a['Bib'], a['Total']) for i, a in enumerate(a for a in qual if a['Q'] == 'Q')] + \
           [(a['Q'], a['Bib'], a['Total']) for a in qual if a['Q'] and a['Q'] != 'Q']
    if listed != want:
        err(f'{ctx}: list of qualifiers {listed} != {want}')
    first = find(f'GAR{G[disc]}1AAFNL_51{"E" if disc == "MAG" else "F"}')[0]
    on_list = set()
    for l in PAGES[first].split('\n'):
        if l.strip().startswith('Legend'):
            break
        for m in re.finditer(r'(?<!\S)(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', l):
            check_name(disc, f'{ctx} start list', m.group(1), m.group(2), m.group(3))
            on_list.add(m.group(1))
    if on_list != fin:
        err(f'{ctx}: start list {sorted(on_list ^ fin)} differ from the results')
    print(f'  {ctx}: {len(fin)} athletes; qualifiers absent {sorted(q - fin)}, others in {sorted(fin - q)}')

def check_tie_breaks(disc, tables):
    """Tie Break reports print the ranks and totals the tables carry for each tied athlete.
    `tables` maps (round, apparatus or 'AA') to bib -> (rank, total)."""
    g = G[disc]
    n_reports = 0
    for i, c in enumerate(CODES):
        m = re.fullmatch(rf'GAR{g}1(AA|AP(\w\w))(QUAL|FNL)_77\w', c)
        if not m:
            continue
        n_reports += 1
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
    print(f'  {disc}: {n_reports} tie-break reports checked')

EVENT_NAME = {'Team': 'TEAM', 'All-Around': 'AA', 'Floor Exercise': 'FX', 'Pommel Horse': 'PH', 'Rings': 'SR',
              'Vault': 'VT', 'Parallel Bars': 'PB', 'Horizontal Bar': 'HB', 'Uneven Bars': 'UB',
              'Balance Beam': 'BB'}

def check_medallists(podiums):
    """Medallists by Event (a summary page, §3.9) against the results: `podiums` maps
    (disc, event) to {(medal, NOC, name or None for a team)}."""
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
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'Bib', 'Name',
           'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total']
    if rnd == 'QUAL':
        hdr.append('Qualification')
    rows = []
    for a in athletes:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Competition': common.COMPETITION[rnd], 'Part': '', 'Rank': a['Rank'], 'Bib': a['Bib'], 'Name': a['Name'], 'NOC Code': a['NOC'],
             'SJ Penalty': '', 'Total': a['Total'], 'Qualification': a['Q']}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = a['apps'][app]['Total']
        rows.append(r)
    out.ranking(PREFIX[disc], 'AA', hdr, rows, EVENTS[PREFIX[disc]])
    return rows

def summary_team(disc, teams):
    """The team penalty (a wrong start order) is the summary's SJ Penalty (§4.3)."""
    ev = EVENTS[PREFIX[disc]]
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'NOC Code'] + \
          [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for t in teams:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Competition': 'C1', 'Part': '', 'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': t['Penalty'],
             'Total': t['Total'], 'Qualification': ''}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = t['totals'].get(app, '')
        rows.append(r)
    out.ranking(PREFIX[disc], 'TEAM', hdr, rows, EVENTS[PREFIX[disc]])
    return rows

def check_team_members(disc, teams, qual):
    """A team's members with routines are exactly its NOC's athletes in the qualification tables,
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

# ---------------------------------------------------------------- run
for disc in ('MAG', 'WAG'):
    participants(disc)
    qualification_start_lists(disc)
    judges(disc)
START_LISTS = finals_start_lists()
podiums = {}
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    teams = team_report(disc)
    aaq = aa_report(disc, 'QUAL')
    aaf = aa_report(disc, 'AA')
    qualifiers = lists_of_qualifiers(disc)
    qual, tie, vault1 = {}, defaultdict(dict), {}
    for app in APPS[disc]:
        rows, double = qual_scores(disc, app, teams, aaq)
        if app == 'VT':
            check_vault_ranks(disc, rows, f'{disc} QUAL VT')
            out.csv(f'{PREFIX[disc]}-SCORES-C1-VT.csv', common.score_header(True, True), rows)
            tie[('QUAL', 'VT')] = {r['Bib']: (r['Qualification Rank'], r['Total']) for r in rows
                                   if r['Qualification Rank']}
            vault1 = {r['Bib']: ('DNS' if r['Status1'] == 'DNS' else r['Total1'], double.get(r['Bib']))
                      for r in rows}
        else:
            out.csv(f'{PREFIX[disc]}-SCORES-C1-{app}.csv', common.score_header(False, True), rows)
            tie[('QUAL', app)] = {r['Bib']: (r['Rank'], r['Total']) for r in rows}
        qual[app] = QUAL_ROWS[(disc, app)] = rows
        check_qualifiers(disc, app, rows, qualifiers[app])
        final, printed = event_scores(disc, app)
        check_final(disc, app, rows, final, printed, START_LISTS[(disc, app)])
        tie[('EVENT', app)] = {r['Bib']: (r['Rank'], r['Total']) for r in final}
        podiums[(disc, app)] = podium(final)
    check_against_tables(disc, 'QUAL', aaq, qual)
    check_team_members(disc, teams, qual)
    team_qual_report(disc, teams, aaq, vault1)
    aa_scores(disc, aaf)
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
