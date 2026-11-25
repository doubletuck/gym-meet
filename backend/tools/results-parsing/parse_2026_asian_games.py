"""Parse the 2026 Asian Games (Aichi-Nagoya) artistic gymnastics results book into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_asian_games.py data/2026/2026-ASIAN-GAMES/18608-AG2026_GAR_RB_v1.pdf

Writes PARTICIPANTS, JUDGES, SCORES-{QUAL,TEAM,EVENT}-<APP>, SUMMARY-QUAL-TEAM, SUMMARY-FINAL-TEAM and
SUMMARY-FINAL-AA, and an IMPORT.json, per discipline next to the PDF, reading event metadata from the
EVENT.csv already there. Exits non-zero if any check fails (docs/instructions-results-parsing.md §3;
this source format is §5.21).

The book is the OCA results book (Bornan timing) of ORIS-style reports, the CAC Games' print (§5.20):
every page has text and a footer code like GARM1APFX-------------QUAL--------_73I. "Qualification and
All-Around Final" (MAG 21, WAG 22 September) decides the all-around titles (24 ranked, two per NOC)
and qualifies to the team final (23 September, its own routines) and the apparatus finals (24-25
September). So it is QUAL, holding every routine and the team qualification; the all-around final is
a SUMMARY-FINAL-AA ranking the QUAL routines (`Scores Round` QUAL); the team final has its own SCORES
(§4.9).

Sources: the apparatus tables give every qualification and final routine, except vault: its
qualification table lists only the two-vault athletes, so the other first vaults come from the team
qualification report and the all-around report (which agree wherever both print one). For MAG, a
separate "Results Vault 1" report (VAULT1_PDF, next to the book) lists every first vault with its
whole-field rank: it is the source of each first vault's Rank and of the one vault no report of the
book details (KAMILJANOV), and every other print of a first vault is checked against it. The team final
has no apparatus tables; its routines come from its team report. The qualification results by team
(scores only), the start lists, lists of qualifiers, tie-break reports and the medallists pages are
cross-checks. The apparatus finals start lists and judges pages are printed twice (pp. 52-55 =
113-116); the first copy is read and the second checked identical.
"""
import os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-ASIAN-GAMES'
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
# Apparatus finals by day, in the order of the Competition Schedule, the start lists and judges pages
FINALS_DAY = {1: {'MAG': ['FX', 'PH', 'SR'], 'WAG': ['VT', 'UB']},
              2: {'MAG': ['VT', 'PB', 'HB'], 'WAG': ['BB', 'FX']}}
# From the Competition Schedule page (§4.4); each results page's header date agrees (checked). The
# all-around final is the qualification's ranking, on the same day.
SESSION_DATE = {
    'MAG': {'QUAL': '2026-09-21', 'AA': '2026-09-21', 'TEAM': '2026-09-23'},
    'WAG': {'QUAL': '2026-09-22', 'AA': '2026-09-22', 'TEAM': '2026-09-23'},
}
FINALS_DATE = {1: '2026-09-24', 2: '2026-09-25'}
for day, by_disc in FINALS_DAY.items():
    for disc, apps in by_disc.items():
        for app in apps:
            SESSION_DATE[disc][('EVENT', app)] = FINALS_DATE[day]
MONTHS = {m: i + 1 for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split())}
MARKERS = ('Q', 'R1', 'R2', 'R3', 'R4', 'NR')
SCORE = r'\d+\.\d{3}'
ROUTINE_KEYS = ['Status', 'D', 'E', 'B', 'Penalty', 'SJ Penalty', 'Total']
# The MAG "Results Vault 1" report (`GARM1APVTQUAL_73I`, the same print), published apart from the
# book: every vaulter's first vault with D and E, ranked over the whole field. It is the only source
# of D and E for a one-vault individual in neither the team nor the all-around report (MAG
# KAMILJANOV Ravshan), and gives every first vault its rank (§4.5, §5.21)
VAULT1_PDF = {'MAG': '18608-AG2026-MAG-SR-VAULT-QUAL-C73I_Results.pdf'}
# A two-vault result printed 0.0005 above the truncated average of the printed vaults (MAG
# qualification TRINH Hai Khang: 13.366 and 14.033, printed 13.700; the unrounded E scores average
# to it). Written as printed
VAULT_AVERAGE_ROUNDED = {('MAG', 'QUAL', '159'): '13.700'}
AA_PLACES, AA_PER_NOC = 24, 2
# Names the entry list prints without a SURNAME Given split; their other 2026 entries (same licence)
# split them so (agreed with the user)
SPLIT = {'Muhammad Sharul Aimy': ('AIMY', 'Muhammad Sharul'), 'PAN EI PHYU': ('PHYU', 'Pan Ei')}

def split_name(name):
    return SPLIT.get(name) or split_surname_first(name)

def session_date(disc, rnd, app):
    return SESSION_DATE[disc][('EVENT', app)] if rnd == 'EVENT' else SESSION_DATE[disc][rnd]

def bonus(v):
    """Bonuses print signed (`+0.1`); they are written unsigned."""
    return v.removeprefix('+')

# ---------------------------------------------------------------- page lookup
def footer_code(page):
    """GARM1APFX-------------QUAL--------_73I 1  Report Created ... -> GARM1APFXQUAL_73I (the
    judges pages have no Report Created stamp)."""
    m = re.search(r'^\s*(GA[RY]\S+)\s+\d+(?:\s|$)', page, re.M)
    return m.group(1).replace('-', '') if m else ''

CODES = [footer_code(p) for p in PAGES]

def find(code, disc=None, copies=1):
    """The pages of one report, in one run (or `copies` identical runs: the first is returned). The
    entry lists share a code across disciplines: `disc` keeps the pages headed Men or Women."""
    idx = [i for i, c in enumerate(CODES) if c == code]
    if disc:
        word = 'Men' if disc == 'MAG' else 'Women'
        idx = [i for i in idx if re.search(rf'^\s+{word}\s*$', '\n'.join(PAGES[i].split('\n')[:8]), re.M)]
    if not idx:
        raise SystemExit(f'no pages with code {code}')
    runs = [[idx[0]]]
    for i in idx[1:]:
        if i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    if len(runs) != copies:
        err(f'{code}: pages {[i + 1 for i in idx]} in {len(runs)} runs, expected {copies}')
    for run in runs[1:]:
        if [PAGES[i] for i in run] != [PAGES[i] for i in runs[0]]:
            err(f'{code}: the copy at pages {[i + 1 for i in run]} differs from the first')
    return runs[0]

def lines(idx):
    return [l for i in idx for l in PAGES[i].split('\n')]

def check_page_date(idx, want, ctx):
    """The date in a results page's header is the day of competition (the footer's is print time)."""
    for i in idx:
        m = re.search(r'(?:MON|TUE|WED|THU|FRI|SAT|SUN) (\d{1,2}) ([A-Z]{3}) (\d{4})', '\n'.join(PAGES[i].split('\n')[:8]))
        got = m and f'{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}'
        if got != want:
            err(f'{ctx}: page {i + 1} header date {got}, session date {want}')

def empty_routine():
    return dict.fromkeys(ROUTINE_KEYS, '')

def dns_routine(placeholder=False):
    """A routine not done. Some print a placeholder `0.000` D (and E) before `DNS`, not a score."""
    return dict(empty_routine(), Status='DNS', _ph=placeholder)

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
        m = re.match(r'^\s+([A-Z]{3})\s+-\s+\S', l)
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
    ALL_NAMES.update(r['Name'] for r in rows)
    counts = entries_by_noc(disc)
    got = defaultdict(int)
    for r in rows:
        got[r['NOC Code']] += 1
    if dict(got) != counts:
        err(f'{ctx}: per NOC {dict(got)} != entries by NOC {counts}')
    print(f'  {ctx}: {len(rows)} entries')
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)
    NAMES[disc] = {r['Bib Number']: (r['Name'], r['NOC Code']) for r in rows}
    BY_NAME[disc] = {v: b for b, v in NAMES[disc].items()}

ALL_NAMES = set()

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
    """A results row's name against the entry list. Reports cut long names short (`TAN Alena
    Valerie`, `PAN EI P`) or print the given names as initials (`TAN A`, `CHEN HYJ`), or the whole
    name (`MSA` for Muhammad Sharul Aimy)."""
    if printed == full or full.startswith(printed) or printed == ''.join(w[0] for w in full.split(' ')):
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

def start_list_names(disc, code, ctx):
    """Every bib on a start list (team members, individuals, alternates) is on the entry list with
    the same name and NOC; returns the bibs."""
    bibs = set()
    for l in lines(find(code)):
        for m in re.finditer(r'(?<!\S)(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', l):
            check_name(disc, ctx, m.group(1), m.group(2), m.group(3))
            bibs.add(m.group(1))
    if not bibs:
        err(f'{ctx}: no entries')
    return bibs

def qualification_start_lists(disc):
    n = 0
    for sub in range(1, 4 if disc == 'WAG' else 3):
        n += len(start_list_names(disc, f'GAR{G[disc]}QUAL00000{sub}_51{"A" if disc == "MAG" else "B"}',
                                  f'{disc} qualification start list {sub}'))
    if n != len(NAMES[disc]):
        print(f'  {disc} qualification start lists: {n} of {len(NAMES[disc])} entries')

# ---------------------------------------------------------------- judges
FUNCTION = {'Time Judge': 'T', 'Time Judge 1': 'T1', 'Time Judge 2': 'T2',
            'Line Judge': 'L', 'Line Judge 1': 'L1', 'Line Judge 2': 'L2'}
PANEL_ENTRY = re.compile(r'(?<!\S)(D\d|E\d|Time Judge(?: \d)?|Line Judge(?: \d)?)\s+(\S.*?)\s{2,}([A-Z]{3,4})(?=\s|$)')
SJ_ENTRY = re.compile(r'(\S.*?)\s{2,}([A-Z]{3,4})\s+(President|(?:' + '|'.join(APP_NAME) + r') Supervisor)(?=\s|$)')
RESERVE_ENTRY = re.compile(r'(?<!\S)(R\d)\s+(\S.*?)\s{2,}([A-Z]{3,4})(?=\s|$)')

def judge_noc(noc):
    """Judges credited to the Asian Gymnastics Union (`AGU`: the Superior Jury, the apparatus
    supervisors, one D1) are blank here; CORRECTIONS.csv fills the supervisors' federations (§4.7)."""
    return '' if noc == 'AGU' else noc

def judge_page(code, panels, ctx, copies=1):
    """One Judges Assignments page -> {side: [dict(Apparatus, Function, Name, NOC)]}, side 0 the left
    column, 1 the right. The Superior Jury (President, then one supervisor per apparatus), then
    panel rows headed `Function Name NOC Function Name NOC`, `panels[k]` naming the k-th row's left
    and right apparatus (None for no panel), then the reserves. The apparatus finals pages list the
    men's Superior Jury, panels and reserves on the left and the women's on the right."""
    found = {0: [], 1: []}
    ls = lines(find(code, copies=copies))
    block, split, mid, n_sj = -1, None, None, 0
    reserves = False
    for l in ls:
        if l.strip().startswith('Legend'):
            break
        m = re.match(r'^(\s+)Men\s+Women\s*$', l)
        if m:
            mid = (l.find('Men') + l.find('Women')) // 2
            continue
        if re.match(r'^\s+Reserves(\s+Reserves)?\s*$', l):
            reserves = True
            ws = [x.start() for x in re.finditer('Reserves', l)]
            mid = (ws[0] + ws[1]) // 2 if len(ws) == 2 else mid
            continue
        body = l.replace('Superior Jury:', ' ' * len('Superior Jury:'))
        hits = list(SJ_ENTRY.finditer(body))
        if hits:
            for m in hits:
                side = 0 if mid is None or m.start(1) < mid else 1
                fn = m.group(3)
                app = '' if fn == 'President' else APP_NAME[fn.removesuffix(' Supervisor')]
                found[side].append(dict(Apparatus=app, Function='President' if fn == 'President' else 'SV',
                                        Name=m.group(1), NOC=judge_noc(m.group(2))))
                n_sj += 1
            continue
        if re.match(r'^\s*Function\s+Name', l):
            block += 1
            split = l.find('Function', l.find('Function') + 1)
            if split < 0:
                split = 10 ** 6
            if block >= len(panels):
                err(f'{ctx}: {block + 1} panel rows')
            continue
        if reserves:
            for m in RESERVE_ENTRY.finditer(l):
                side = 0 if mid is None or m.start() < mid else 1
                found[side].append(dict(Apparatus=None, Function=m.group(1), Name=m.group(2),
                                        NOC=judge_noc(m.group(3))))
            continue
        for m in PANEL_ENTRY.finditer(l):
            side = 0 if m.start() < split - 2 else 1
            app = panels[block][side] if 0 <= block < len(panels) else None
            if app is None:
                err(f'{ctx}: panel {block},{side} {l!r}'); continue
            fn, name, noc = m.groups()
            found[side].append(dict(Apparatus=app, Function=FUNCTION.get(fn, fn), Name=name, NOC=judge_noc(noc)))
        n_fn = len(re.findall(r'(?<!\S)(?:D\d|E\d|Time Judge|Line Judge)(?!\S)', l))
        if n_fn != len(PANEL_ENTRY.findall(l)):
            err(f'{ctx}: unparsed judges line {l!r}')
    if block + 1 != len(panels):
        err(f'{ctx}: {block + 1} panel rows, expected {len(panels)}')
    if not n_sj:
        err(f'{ctx}: no Superior Jury')
    return found

def grid(disc):
    """A discipline's panels two to a row, in the legend's order (MAG FX/PH, SR/VT, PB/HB; WAG VT/UB,
    BB/FX), confirmed by floor's time and line judges, vault's line judge, beam's two time judges."""
    a = APPS[disc]
    return [(a[i], a[i + 1]) for i in range(0, len(a), 2)]

def judges(disc, finals_pages):
    rows = []
    s = 'A' if disc == 'MAG' else 'B'
    for code, rnd in ((f'GAR{G[disc]}QUAL_57{s}', 'QUAL'), (f'GAR{G[disc]}TEAMFNL_57{s}', 'TEAM')):
        found = judge_page(code, grid(disc), f'{disc} judges {rnd}')
        if found[1] and any(r['Apparatus'] in ('', None) for r in found[1]):
            err(f'{disc} judges {rnd}: Superior Jury or reserves on the right')
        for r in found[0] + found[1]:
            # A round's reserves serve every panel: apparatus blank
            rows.append(dict(r, Round=rnd, Apparatus=r['Apparatus'] or ''))
    # Apparatus finals, one page per day: the Superior Jury is printed each day (the same, checked);
    # a day's reserves are written once for each of that day's finals (§4.7)
    side = 0 if disc == 'MAG' else 1
    sj = []
    for day, found in finals_pages.items():
        day_sj = [r for r in found[side] if r['Function'] in ('President', 'SV')]
        sj.append(day_sj)
        for r in found[side]:
            if r['Function'] in ('President', 'SV'):
                continue
            if r['Apparatus'] is None:
                for app in FINALS_DAY[day][disc]:
                    rows.append(dict(r, Round='EVENT', Apparatus=app))
            else:
                rows.append(dict(r, Round='EVENT'))
    if any(x != sj[0] for x in sj):
        err(f'{disc} judges EVENT: the Superior Jury differs between days')
    rows += [dict(r, Round='EVENT') for r in sj[0]]
    ev = EVENTS[PREFIX[disc]]
    written = []
    for r in rows:
        sur, giv = split_name(r['Name'])
        if not sur or not giv:
            err(f'{disc} judges: name split {r["Name"]!r}')
        written.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                        'Event Start Date': ev['Start Date'], 'Round': r['Round'],
                        'Apparatus': r['Apparatus'], 'Function': r['Function'], 'Name': r['Name'],
                        'Surname': sur, 'Given Name': giv, 'NOC Code': r['NOC']})
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, written)
    check_judges(disc, written)

def check_judges(disc, rows):
    """Every panel is its supervisor, D1 D2 E1-E5 (and time and line judges); a President per round;
    reserves R1 R2; one function per judge per panel; each judge credited to one federation (checked
    as written, after corrections)."""
    by_panel = defaultdict(list)
    for r in rows:
        by_panel[(r['Round'], r['Apparatus'])].append(r['Function'])
    want = {'SV', 'D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5'}
    for rnd in ('QUAL', 'TEAM', 'EVENT'):
        for app in APPS[disc]:
            fns = by_panel[(rnd, app)]
            core = [f for f in fns if not re.fullmatch(r'R\d', f)]
            if not want <= set(core) or len(core) != len(set(core)) or not set(core) <= want | {'T', 'T1', 'T2', 'L', 'L1', 'L2'}:
                err(f'{disc} judges {rnd} {app}: panel {sorted(fns)}')
            if rnd == 'EVENT' and sorted(f for f in fns if f.startswith('R')) != ['R1', 'R2']:
                err(f'{disc} judges EVENT {app}: reserves {sorted(fns)}')
        # A round's reserves: MAG R1 R2; WAG none in qualification, R1 in the team final
        sj = by_panel[(rnd, '')]
        if rnd != 'EVENT' and (sj[:1] != ['President'] or sj[1:] != [f'R{i + 1}' for i in range(len(sj) - 1)]):
            err(f'{disc} judges {rnd}: Superior Jury and reserves {sj}')
        if rnd == 'EVENT' and by_panel[(rnd, '')] != ['President']:
            err(f'{disc} judges EVENT: {by_panel[(rnd, "")]}')
    noc = defaultdict(set)
    for r in rows:
        if r['NOC Code']:
            noc[r['Name']].add(r['NOC Code'])
    for name, nocs in noc.items():
        if len(nocs) > 1:
            err(f'{disc} judges: {name} credited to {sorted(nocs)}')
    print(f'  {disc} judges: {len(rows)} rows, {len({r["Name"] for r in rows})} judges')

def finals_judges():
    """The apparatus finals judges pages, per day: the men's finals' panels down the left, the
    women's down the right, in the schedule's order."""
    pages = {}
    for day in (1, 2):
        m, w = FINALS_DAY[day]['MAG'], FINALS_DAY[day]['WAG']
        panels = [(m[k] if k < len(m) else None, w[k] if k < len(w) else None) for k in range(max(len(m), len(w)))]
        pages[day] = judge_page(f'GARFNL000{day}00_57D', panels, f'finals judges day {day}', copies=2)
    return pages

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

def dns_values(vals, ctx):
    """`DNS`, maybe after placeholder zeros (`0.0 0.000 DNS`, MAG floor KANETA)."""
    if vals[-1] != 'DNS':
        return False
    if any(D(v) != 0 for v in vals[:-1]) or len(vals) > 3:
        err(f'{ctx}: DNS with values {vals}')
    return True

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
        if dns_values(vals, f'{ctx} bib {bib}'):
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
    n_rank = sum(1 for l in ls if re.match(r'^\s*\d+\s+\d{3}\s+\S', l))
    n_dns = sum(1 for l in ls if re.search(r'\sDNS\s*$', l))
    if n_rank + n_dns != len(rows):
        err(f'{ctx}: parsed {len(rows)} rows, counted {n_rank} ranked + {n_dns} DNS')
    checks.check_rank_order(ctx, rows)
    return rows

# The vault 2 line, after a name that wrapped
VAULT2 = re.compile(r'^\s+(?:[^\d\s][^\d]*?\s{2,})?2\s+(\d.*|DNS)\s*$')

def double_table(disc, rnd):
    """Two-vault table: each vaulter on two lines (`1 …`, `2 …`), each `D E [Pen.] Score`; the
    first line ends with WAG's combined `+0.2` bonus (if any) and the vault score -> rows. A vaulter
    who did neither vault prints `DNS DNS` and `DNS` (MAG MIRVALIEV)."""
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
            if vals == ['DNS', 'DNS']:
                if rank:
                    err(f'{ctx} bib {bib}: ranked DNS')
                cur |= {'v1': dns_routine(), 'Total': ''}
                rows.append(cur)
                continue
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
                if VAULT_AVERAGE_ROUNDED.get((disc, rnd, cur['Bib'])) == cur['Total']:
                    avg = (D(cur['v1']['Total']) + D(cur['v2']['Total'])) / 2 + D(cur['Bonus'])
                    if abs(avg - D(cur['Total'])) > D('0.0005'):
                        err(f'{ctx} bib {cur["Bib"]}: average {avg} != {cur["Total"]}')
                    continue
                checks.check_vault_average(f'{ctx} bib {cur["Bib"]}', cur['v1']['Total'], cur['v2']['Total'],
                                           cur['Bonus'], cur['Total'])
            continue
        if re.match(r'^\s*\d+\s+\d{3}\s+\S', l):
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
    followed by its penalty (`-0.3`) or bonus (`+0.1`); a routine not done with placeholder zeros
    prints a `0.000` E too (MAG KANETA's floor). The print drifts against the D line; the order holds."""
    done = iter([x for x in apps.values() if x['Status'] == 'COMPLETED' or x.get('_ph')])
    x = None
    for v in values.split():
        if re.fullmatch(SCORE, v):
            x = next(done, None)
            if x is None:
                err(f'{ctx}: E {v} for no routine'); return
            if x['Status'] == 'DNS':
                if D(v) != 0:
                    err(f'{ctx}: E {v} for a routine not done')
            else:
                x['E'] = v
            continue
        key = 'Penalty' if v.startswith('-') else 'B'
        if x is None or x['Status'] == 'DNS' or not re.fullmatch(r'[-+]\d\.\d', v) or x[key]:
            err(f'{ctx}: unexpected {v!r} in the E line {values!r}'); continue
        x[key] = bonus(v)
    if next(done, None) is not None:
        err(f'{ctx}: E line {values!r} short')

def e_line(dl):
    """An E line's values: it may start with the end of a long name (`Eldrew   E 8.566`)."""
    m = re.match(r'^\s*(?:\S.*?\s{2,})?E\s+(?=[-+]?\d)', dl)
    return dl[m.end():] if m else None

def finish_routines(apps, ctx):
    for app, x in apps.items():
        x.pop('_ph', None)
        if x['Status'] == 'COMPLETED':
            if app == 'VT':
                vault_status(x)
            if not x['E']:
                err(f'{ctx} {app}: no E value')
            check_routine(f'{ctx} {app}', x)

DNS_SLOT = r'(?:\d+\.\d{3}\s+)?DNS'

def team_report(disc, rnd):
    """Team results (`_73C`/`_73D`), qualification or final: a team line (`total (rank)` per
    apparatus, then the team score, `*` if a penalty was taken, and the qualification marker), any
    `* Penalty -1.0` line, then each member's D line (`D score` per apparatus, or DNS) and E line
    (with penalties and bonuses). The columns have icon headings in the legend's order; a routine's
    apparatus is the team column its score starts in. Members with no routine print no lines."""
    apps_order = APPS[disc]
    n = len(apps_order)
    ctx0 = f'{disc} {rnd} team'
    idx = find(f'GAR{G[disc]}TEAM{"QUAL" if rnd == "QUAL" else "FNL"}_73{"C" if disc == "MAG" else "D"}')
    check_page_date(idx, SESSION_DATE[disc][rnd], ctx0)
    teams = []
    for i in idx:
        ls = PAGES[i].split('\n')
        team = None
        for j, l in enumerate(ls):
            m = re.match(r'^\s*(\d+)?\s+([A-Z]{3}) - (\S.*?)\s{2,}(' + SCORE + r' \(.*)$', l)
            if m:
                rank, noc = m.group(1), m.group(2)
                found = list(re.finditer(r'(' + SCORE + r') \((\d+)\)', l))
                if len(found) != n:
                    err(f'{ctx0} {noc}: {len(found)} apparatus totals'); continue
                tail = l[found[-1].end():].split()
                q = tail.pop() if tail and tail[-1] in MARKERS else ''
                if len(tail) != 1 or not re.fullmatch(SCORE + r'\*?', tail[0]):
                    err(f'{ctx0} {noc}: total {tail}'); continue
                if q and rnd != 'QUAL':
                    err(f'{ctx0} {noc}: marker {q} in the final')
                team = dict(Rank=rank or '', NOC=noc, anchors=[t.start() for t in found], Penalty='',
                            Total=tail[0].rstrip('*'), starred=tail[0].endswith('*'), Q=q, members=[],
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
                for t in re.finditer(r'(\d+\.\d{3})\s+(' + SCORE + r')|' + DNS_SLOT, rest):
                    is_dns = t.group().endswith('DNS')
                    pos = start + (t.end() - 3 if is_dns else t.start(2))
                    k = span_of(team['anchors'], pos)
                    app = apps_order[k] if k is not None else None
                    if app is None or app in apps or apps and apps_order.index(app) < apps_order.index(list(apps)[-1]):
                        err(f'{ctx}: routine at {pos} out of place ({app})'); continue
                    apps[app] = dns_routine(placeholder=t.group() != 'DNS') if is_dns else \
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
            if rnd == 'TEAM' and len(sc) != 3:
                err(f'{ctx} {app}: {len(sc)} routines in the final, not three')
            if sum(sc[:3]) != D(t['totals'].get(app)):
                err(f'{ctx} {app}: best three {sum(sc[:3])} != {t["totals"].get(app)}')
        if sum(D(v) for v in t['totals'].values()) + D(t['Penalty']) != D(t['Total']):
            err(f'{ctx}: apparatus totals and penalty {t["Penalty"]} != {t["Total"]}')
        if t['starred'] != bool(t['Penalty']):
            err(f'{ctx}: total starred {t["starred"]}, penalty {t["Penalty"]!r}')
    checks.check_rank_order(ctx0, [dict(Rank=t['Rank'], Total=t['Total'], Bib=t['NOC']) for t in teams])
    for app in apps_order:
        ranked = sorted(teams, key=lambda t: int(t['ranks'][app]))
        checks.check_rank_order(f'{ctx0} {app}', [dict(Rank=t['ranks'][app], Total=t['totals'][app], Bib=t['NOC'])
                                                  for t in ranked])
    print(f'  {ctx0}: {len(teams)} teams')
    return teams

def team_qual_report(disc, teams, aa, vault1):
    """Qualification results by team (`_73A`/`_73B`, scores only): each team's apparatus totals,
    ranks, score and marker as the team report has them; every member's and individual's scores
    (vault: the first vault, then the two-vault athletes' second vault, bonus and result) and
    all-around total and rank as the other reports have them. `vault1` maps bib -> (vault 1
    total, two-vault row or None)."""
    ctx0 = f'{disc} QUAL team results'
    apps_order = APPS[disc]
    idx = find(f'GAR{G[disc]}QUAL_73{"A" if disc == "MAG" else "B"}')
    check_page_date(idx, SESSION_DATE[disc]['QUAL'], ctx0)
    by_noc = {t['NOC']: t for t in teams}
    aa = {a['Bib']: a for a in aa}
    noc, seen_teams, n_rows, seen = None, [], 0, set()
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
            tail = re.sub(r'.*\(\d+\)', '', m.group(1)).split()
            if t is None or found != [(t['totals'][a], t['ranks'][a]) for a in apps_order] \
                    or tail != [t['Total'] + ('*' if t['starred'] else '')] + ([t['Q']] if t['Q'] else []):
                err(f'{ctx0} {noc}: {m.group(1).split()} != the team report')
            continue
        m = re.match(r'^\s+\*\s*Penalty (-\d+\.\d)\s*$', l)
        if m:
            if by_noc.get(noc, {}).get('Penalty') != m.group(1):
                err(f'{ctx0} {noc}: penalty {m.group(1)} != the team report')
            continue
        m = re.match(BY_TEAM_ROW, l)
        if not m:
            continue
        bib, name, rest = m.groups()
        n_rows += 1
        seen.add(bib)
        ctx = f'{ctx0} bib {bib}'
        check_name(disc, ctx, bib, name, noc)
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
                    # A vaulter who did neither vault prints DNS for the result (MAG MIRVALIEV)
                    want += [double['v2']['Total'] or 'DNS'] + ([f'+{double["Bonus"]}'] if double['Bonus'] else []) \
                        + [double['Total'] or ('DNS' if v1 == 'DNS' else 'DNF')]
            else:
                want.append(x)
        a = aa.get(bib)
        if a is not None:
            want += [a['Total'] or 'DNF'] + ([f'({a["Rank"]})'] if a['Rank'] else [])
        elif any(re.fullmatch(SCORE, v) for v in apparatus_scores):
            want.append(str(sum(D(v) for v in apparatus_scores if re.fullmatch(SCORE, v))))
        got = rest.split()
        if got != want:
            err(f'{ctx}: {got} != {want}')
    if seen_teams != [(t['Rank'], t['NOC']) for t in teams]:
        err(f'{ctx0}: teams {seen_teams}')
    competed = {r['Bib'] for app in apps_order for r in QUAL_ROWS[(disc, app)]}
    if seen != competed:
        err(f'{ctx0}: athletes differ from the tables: {sorted(seen ^ competed)}')
    print(f'  {ctx0}: {n_rows} athletes checked')

QUAL_ROWS = {}   # (disc, app) -> written QUAL rows
BY_TEAM = {}     # disc -> bib -> the qualification results by team's values for the bib

def by_team_values(disc):
    BY_TEAM[disc] = {}
    for l in lines(find(f'GAR{G[disc]}QUAL_73{"A" if disc == "MAG" else "B"}')):
        m = re.match(BY_TEAM_ROW, l)
        if m:
            BY_TEAM[disc][m.group(1)] = m.group(3).split()

BY_TEAM_ROW = r'^\s+(\d{3}) (\S.*?)\s{2,}((?:[-+]?\d+\.\d{3}|DNS|DNF|\+\d\.\d|\(\d+\))(?:\s+|$).*)$'

def routine_of_bib(disc, app, bib):
    """A bib's qualification score on an apparatus as printed (vault: vault 1), or None."""
    row = next((r for r in QUAL_ROWS[(disc, app)] if r['Bib'] == bib), None)
    if row is None:
        return None
    st, total = (row['Status1'], row['Total1']) if app == 'VT' else (row['Status'], row['Total'])
    return 'DNS' if st == 'DNS' else total

def aa_report(disc):
    """The all-around final's results (`_73G`/`_73H`), which rank the qualification's routines: per
    athlete a D line (`rank bib name NOC D`, then `D score (Rk)` per apparatus or DNS, the total),
    maybe a line with the rest of the name, and an E line (with penalties and bonuses). The Rk
    column ranks each routine against the whole qualification field."""
    apps_order = APPS[disc]
    n = len(apps_order)
    ctx0 = f'{disc} AA'
    idx = find(f'GAR{G[disc]}1AAFNL_73{"G" if disc == "MAG" else "H"}')
    check_page_date(idx, SESSION_DATE[disc]['AA'], ctx0)
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
        if tail[-1] in MARKERS:
            err(f'{ctx}: a marker in the all-around final')
        total = tail.pop()
        if total not in ('DNF', 'DNS') and not re.fullmatch(SCORE, total):
            err(f'{ctx}: total {total!r}')
        body = rest[:rest.rfind(total)]
        slots = list(re.finditer(r'(\d+\.\d{3})\s+(' + SCORE + r')\s+\((\d+)\)|' + DNS_SLOT, body))
        if len(slots) != n:
            err(f'{ctx}: {len(slots)} apparatus'); continue
        apps = {}
        for app, t in zip(apps_order, slots):
            apps[app] = dns_routine(placeholder=t.group() != 'DNS') if t.group().endswith('DNS') else \
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
        athletes.append(dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, apps=apps, Total=total))
    n_id = sum(1 for l in ls if re.match(r'^\s*(\d+)?\s+\d{3} \S.*?\s{2,}[A-Z]{3}\s+D\s', l))
    if n_id != len(athletes):
        err(f'{ctx0}: parsed {len(athletes)} of {n_id}')
    checks.check_rank_order(ctx0, athletes)
    check_aa_places(disc, athletes)
    return athletes

def check_aa_places(disc, athletes):
    """The all-around final ranks the best 24 with at most two per NOC; the others keep their totals
    unranked. Totals never increase down the report, unranked athletes included; DNF last."""
    ctx = f'{disc} AA places'
    per_noc, places = defaultdict(int), 0
    totals = [D(a['Total']) for a in athletes if a['Total']]
    if totals != sorted(totals, reverse=True) or any(a['Total'] for a in athletes[len(totals):]):
        err(f'{ctx}: totals out of order')
    for a in athletes:
        if not a['Total']:
            continue
        eligible = per_noc[a['NOC']] < AA_PER_NOC and places < AA_PLACES
        if eligible != bool(a['Rank']):
            err(f'{ctx}: bib {a["Bib"]} rank {a["Rank"]!r}, eligible {eligible}')
        if eligible:
            per_noc[a['NOC']] += 1
            places += 1
    print(f'  {ctx}: {places} ranked, {sum(1 for a in athletes if a["Total"] and not a["Rank"])} unranked with a total')

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
    """Two prints of one routine agree; D is printed to one or three decimals."""
    def norm(r):
        return {k: (D(r[k]) if k == 'D' and r[k] else r[k]) for k in keys}
    if norm(a) != norm(b):
        err(f'{ctx}: {routine_of(a)} != {routine_of(b)}')

def qual_scores(disc, app, teams, aa):
    """SCORES-QUAL-<app>; returns the written rows. Team and all-around report routines must match
    the table's (vault: the first vault, from either report)."""
    ctx = f'{disc} QUAL {app}'
    reported = {}   # bib -> (routine, source); a bib can be in both reports, which must agree
    for t in teams:
        for x in t['members']:
            if app in x['apps']:
                reported[x['Bib']] = (x['apps'][app], f'team report {t["NOC"]}')
    aa_rank = {}
    for a in aa:
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
    if disc in VAULT1_PDF:
        rows = apply_vault1_list(disc, rows, aa_rank)
    return rows, {r['Bib']: r for r in double}

def vault1_list(disc):
    """The Results Vault 1 report: `rank bib name NOC D E [Pen.] [Bonus] Score`, or DNS -> rows in
    printed order."""
    path = os.path.join(OUT, VAULT1_PDF[disc])
    pages = common.pdf_pages(path)
    ctx = f'{disc} QUAL VT vault 1 list'
    if not any(footer_code(p) == f'GAR{G[disc]}1APVTQUAL_73I' for p in pages) \
            or not any(re.search(r'^\s+Results Vault 1\s*$', p, re.M) for p in pages):
        err(f'{ctx}: {VAULT1_PDF[disc]} is not the Results Vault 1 report')
    idx = [i for i, p in enumerate(pages) if p.strip()]
    for i in idx:
        m = re.search(r'(?:MON|TUE|WED|THU|FRI|SAT|SUN) (\d{1,2}) ([A-Z]{3}) (\d{4})', '\n'.join(pages[i].split('\n')[:8]))
        if not m or f'{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}' != SESSION_DATE[disc]['QUAL']:
            err(f'{ctx}: page {i + 1} header date')
    ls = [l for i in idx for l in pages[i].split('\n')]
    rows = []
    for l in ls:
        m = re.match(ID + r'(.*)$', l)
        if not m:
            continue
        rank, bib, name, noc, rest = m.groups()
        vals = rest.split()
        row = dict(Rank=rank or '', Bib=bib, Name=check_name(disc, ctx, bib, name, noc), NOC=noc)
        if vals == ['DNS']:
            if rank:
                err(f'{ctx}: ranked DNS bib {bib}')
            rows.append(row | dns_routine()); continue
        r = vault_status(split_values(vals, f'{ctx} bib {bib}'))
        if not rank:
            err(f'{ctx} bib {bib}: unranked vault')
        rows.append(row | r)
    n_rank = sum(1 for l in ls if re.match(r'^\s*\d+\s+\d{3}\s+\S', l))
    n_dns = sum(1 for l in ls if re.search(r'\sDNS\s*$', l))
    if n_rank + n_dns != len(rows):
        err(f'{ctx}: parsed {len(rows)} rows, counted {n_rank} ranked + {n_dns} DNS')
    checks.check_rank_order(ctx, rows)
    return rows

def apply_vault1_list(disc, rows, aa_rank):
    """Every first vault (two-vault table, team and all-around reports) is the list's, and the
    all-around report's vault Rk is its rank; the list's vaulters are exactly the rows'. Each row's
    `Rank` is the list's; a vaulter on the list only (MAG KAMILJANOV) gets their routine from it."""
    ctx = f'{disc} QUAL VT vault 1 list'
    listed = {r['Bib']: r for r in vault1_list(disc)}
    by_bib = {r['Bib']: r for r in rows}
    for bib, v in listed.items():
        row = by_bib.get(bib)
        if row is None:
            name, noc = NAMES[disc][bib]
            print(f'  {ctx}: bib {bib} {name} from the list only')
            row = meta(disc, 'QUAL', 'VT', '', bib, name, noc) | vault_cols(1, v) | vault_cols(2, empty_routine()) \
                | {'Combined Bonus': '', 'Total': v['Total'], 'Qualification': '', 'Qualification Rank': ''}
            rows.append(row)
        else:
            same_routine(f'{ctx} bib {bib}', v, {k: row[f'{k}1'] for k in ROUTINE_KEYS})
        # The all-around report shares a rank the list breaks on E (HASHIMOTO 13 there, 14 here, level
        # on 13.866 with IDRISSOV); it must be the best list rank at that score
        shared = min((int(x['Rank']) for x in listed.values() if x['Rank'] and x['Total'] == v['Total']), default=None)
        if aa_rank.get(bib) and v['Status'] != 'DNS' and aa_rank[bib] not in (v['Rank'], str(shared)):
            err(f'{ctx} bib {bib}: rank {v["Rank"]}, the all-around report {aa_rank[bib]}')
        elif aa_rank.get(bib) and aa_rank[bib] != v['Rank']:
            print(f'  {ctx}: bib {bib} ranked {v["Rank"]}, shared {aa_rank[bib]} in the all-around report')
        row['Rank'] = v['Rank']
    for bib in set(by_bib) - set(listed):
        err(f'{ctx}: bib {bib} vaulted but is not on the list')
    order = list(listed)
    return sorted(rows, key=lambda r: order.index(r['Bib']))

def check_vault_ranks(rows, ctx):
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

def check_against_tables(disc, athletes, rows_by_app):
    """Every all-around report routine is in the qualification table with the same values and rank
    (vault: its first vault, and the Rk column ranks the whole field)."""
    for a in athletes:
        for app, x in a['apps'].items():
            ctx = f'{disc} AA bib {a["Bib"]} {app}'
            row = next((r for r in rows_by_app[app] if r['Bib'] == a['Bib']), None)
            if row is None:
                err(f'{ctx}: not in the qualification table'); continue
            if app == 'VT':
                same_routine(ctx, x, {k: row[f'{k}1'] for k in ROUTINE_KEYS})
                continue
            same_routine(ctx, x, row)
            if x['Status'] != 'DNS' and x['Rank'] != row['Rank']:
                err(f'{ctx}: rank {x["Rank"]}, table {row["Rank"]}')

def team_scores(disc, teams):
    """SCORES-TEAM-<app> from the team final report (single-attempt vault): no individual ranks."""
    for app in APPS[disc]:
        rows = []
        for t in teams:
            for x in t['members']:
                if app in x['apps']:
                    name, noc = NAMES[disc][x['Bib']]
                    rows.append(meta(disc, 'TEAM', app, '', x['Bib'], name, t['NOC']) | routine_of(x['apps'][app]))
        out.csv(f'{PREFIX[disc]}-SCORES-TEAM-{app}.csv', common.score_header(False, False), rows)

def event_scores(disc, app):
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
        err(f'{disc} EVENT {app}: {len(rows)} finalists')
    return rows, printed

# ---------------------------------------------------------------- finals checks
STARTER = re.compile(r'(?:(?<!\S)(\d{3})|(?<!\S)(R\d|NR))\s+(\S.*?)(?:\s{2,}| (?=[A-Z]{3}(?:\s{2,}|\s*$)))([A-Z]{3})(?=\s|$)')

def finals_start_lists():
    """Apparatus finals start lists (`GAR-FNL-000<day>00_51G`): per day, blocks headed `Start Time:
    hh:mm`, the men's finals down the left and the women's down the right, in the schedule's order.
    Each lists its eight finalists in start order, then the reserves (R1-R3 and the NR athletes
    ranked among them) by name, without a bib. A block's heading can share a line with the other
    side's last reserve."""
    found = {}
    for day in (1, 2):
        blocks = {0: [], 1: []}
        split = None
        for l in lines(find(f'GARFNL000{day}00_51G', copies=2)):
            if re.match(r'^\s+Men\s+Women\s*$', l):
                split = (l.find('Men') + l.find('Women')) // 2
            for m in re.finditer(r'Start Time:', l):
                blocks[0 if m.start() < split else 1].append([])
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
    marked = sorted((r for r in qual_rows if r['Qualification']), key=lambda r: int(r['Qualification Rank']))
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
    compatriot; the start list's reserves carry the table's markers, less one for each reserve
    already in the final (MAG floor: KIM Jaeho, R1, in; ERKHEMBAYAR's R2 printed R1)."""
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
    used = sum(1 for b in finalists if re.fullmatch(r'R\d', marks.get(b, '')))
    for b, m in reserves.items():
        mk = marks.get(b, '')
        want = f'R{int(mk[1:]) - used}' if re.fullmatch(r'R\d', mk) else mk
        if want != m:
            err(f'{ctx}: start list reserve {b} {m}, qualification has {mk}')
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

def check_team_final(disc, qual_teams, final_teams):
    """The team final's teams are the qualification's `Q` teams, as its List of Qualifiers has them
    in order; each final team's members are its entries, and the final's start list names them."""
    ctx = f'{disc} team final'
    q = [(t['NOC'], t['Total']) for t in qual_teams if t['Q'] == 'Q']
    listed = []
    for l in lines(find(f'GAR{G[disc]}TEAMFNL_53D')):
        m = re.match(r'^\s+(\d+)\s+([A-Z]{3}) - .*?\s(' + SCORE + r')\s*$', l)
        if m:
            listed.append((m.group(2), m.group(3)))
    if listed != q:
        err(f'{ctx}: list of qualifiers {listed} != {q}')
    if sorted(t['NOC'] for t in final_teams) != sorted(n for n, _ in q):
        err(f'{ctx}: teams {[t["NOC"] for t in final_teams]} != qualifiers {q}')
    on_list = start_list_names(disc, f'GAR{G[disc]}TEAMFNL000001_51{"C" if disc == "MAG" else "D"}',
                               f'{ctx} start list')
    for t in final_teams:
        for x in t['members']:
            if NAMES[disc][x['Bib']][1] != t['NOC'] or x['Bib'] not in on_list:
                err(f'{ctx} {t["NOC"]}: bib {x["Bib"]} not an entry of the team on the start list')

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
            # The name can run into the NOC (`ERKHEMBAYAR UsukhbayarMGL`)
            t = re.match(r'^\s*=?(\d+)\s+(\d{3})\s+\S.*?\s*([A-Z]{3})\s+(' + SCORE + ')', l)
            if not t:
                continue
            n += 1
            rank, bib, _, total = t.groups()
            if tables[key].get(bib) != (rank, total):
                err(f'{ctx}: bib {bib} rank {rank} total {total}, the results have {tables[key].get(bib)}')
        if not n:
            err(f'{ctx}: no rows')
    print(f'  {disc}: {n_reports} tie-break reports checked')

EVENT_NAME = {'Team': 'TEAM', 'All-Around': 'AA', **APP_NAME}

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
def summary_aa(disc, athletes):
    """The all-around final ranks the qualification's routines (`Scores Round` QUAL, §4.9)."""
    ev = EVENTS[PREFIX[disc]]
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part', 'Rank', 'Bib', 'Name',
           'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Scores Round']
    rows = []
    for a in athletes:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Round': 'AA', 'Part': '', 'Rank': a['Rank'], 'Bib': a['Bib'], 'Name': a['Name'], 'NOC Code': a['NOC'],
             'SJ Penalty': '', 'Total': a['Total'], 'Scores Round': 'QUAL'}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = a['apps'][app]['Total']
        rows.append(r)
    out.csv(f'{PREFIX[disc]}-SUMMARY-FINAL-AA.csv', hdr, rows)
    return rows

def summary_team(disc, rnd, teams):
    """A team penalty (a wrong start order) is the summary's SJ Penalty (§4.3)."""
    ev = EVENTS[PREFIX[disc]]
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part', 'Rank', 'NOC Code'] + \
          [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total'] + (['Qualification'] if rnd == 'QUAL' else [])
    rows = []
    for t in teams:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Round': rnd, 'Part': '', 'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': t['Penalty'],
             'Total': t['Total'], 'Qualification': t['Q']}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = t['totals'].get(app, '')
        rows.append(r)
    out.csv(f'{PREFIX[disc]}-SUMMARY-{"QUAL" if rnd == "QUAL" else "FINAL"}-TEAM.csv', hdr, rows)
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
if set(SPLIT) - ALL_NAMES:
    err(f'name splits not used: {sorted(set(SPLIT) - ALL_NAMES)}')
FINALS_JUDGES = finals_judges()
for disc in ('MAG', 'WAG'):
    judges(disc, FINALS_JUDGES)
START_LISTS = finals_start_lists()
podiums = {}
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    teams_q = team_report(disc, 'QUAL')
    by_team_values(disc)
    aa = aa_report(disc)
    qualifiers = lists_of_qualifiers(disc)
    qual, tie, vault1 = {}, defaultdict(dict), {}
    for app in APPS[disc]:
        rows, double = qual_scores(disc, app, teams_q, aa)
        if app == 'VT':
            check_vault_ranks(rows, f'{disc} QUAL VT')
            out.csv(f'{PREFIX[disc]}-SCORES-QUAL-VT.csv', common.score_header(True, True), rows)
            tie[('QUAL', 'VT')] = {r['Bib']: (r['Qualification Rank'], r['Total']) for r in rows
                                   if r['Qualification Rank']}
            vault1 = {r['Bib']: ('DNS' if r['Status1'] == 'DNS' else r['Total1'], double.get(r['Bib']))
                      for r in rows}
        else:
            out.csv(f'{PREFIX[disc]}-SCORES-QUAL-{app}.csv', common.score_header(False, True), rows)
            tie[('QUAL', app)] = {r['Bib']: (r['Rank'], r['Total']) for r in rows}
        qual[app] = QUAL_ROWS[(disc, app)] = rows
        check_qualifiers(disc, app, rows, qualifiers[app])
        final, printed = event_scores(disc, app)
        check_final(disc, app, rows, final, printed, START_LISTS[(disc, app)])
        tie[('EVENT', app)] = {r['Bib']: (r['Rank'], r['Total']) for r in final}
        podiums[(disc, app)] = podium(final)
    check_against_tables(disc, aa, qual)
    check_team_members(disc, teams_q, qual)
    team_qual_report(disc, teams_q, aa, vault1)
    summary_team(disc, 'QUAL', teams_q)
    teams_f = team_report(disc, 'TEAM')
    check_team_final(disc, teams_q, teams_f)
    team_scores(disc, teams_f)
    t_rows = summary_team(disc, 'TEAM', teams_f)
    f_rows = summary_aa(disc, aa)
    # The all-around Tie Break report ranks the whole field, the athletes the final leaves unranked
    # (a third per NOC) included: MAG TRAN 14th and ERKHEMBAYAR 15th, ranked 13 and 14 in the final
    tie[('AA', 'AA')] = {r['Bib']: (str(i + 1), r['Total']) for i, r in enumerate(x for x in f_rows if x['Total'])}
    check_tie_breaks(disc, tie)
    podiums[(disc, 'AA')] = podium(f_rows)
    podiums[(disc, 'TEAM')] = {(m, n, None) for m, n, _ in podium(t_rows, name_key='-')}
    missing = set(NAMES[disc]) - COMPETED[disc]
    print(f'  {disc}: {len(COMPETED[disc])} of {len(NAMES[disc])} entries competed; none: {sorted(missing)}')
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])

check_medallists(podiums)
out.corrections.finish()
checks.finish()
