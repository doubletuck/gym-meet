"""Parse the 2026 African Championships results books (senior and junior) into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_african_championships.py \\
        data/2026/2026-AFRICAN-CHAMPIONSHIPS/18377-ResultsbookMedia.pdf     # seniors
    python3 -I parse_2026_african_championships.py \\
        data/2026/2026-AFRICAN-CHAMPIONSHIPS/18378-ResultsbookMedia.pdf     # juniors

The book is chosen by the FIG event number the file name starts with. Writes PARTICIPANTS, JUDGES,
SCORES-C1-*, SCORES-C3-*, RANKING-FINAL-TEAM, RANKING-FINAL-AA (Competition I decides both titles) and an IMPORT.json for that book's MAG
and WAG next to the PDF, reading event metadata from the EVENT.csv already there. Exits non-zero if any
check fails (docs/instructions-results-parsing.md §3; this source format is §5.15).

The organizer's media books. The senior book was laid out in CorelDRAW: the schedule, entry counts
and entry list have text, but every results page is text converted to outlines (or, for the judges,
a photograph). The junior book is a scan with no text layer at all, and adds an "Individual Judges
Scores" page per table. The pages without text were read with OCR and checked by eye into
`transcriptions/2026-AFRICAN-CHAMPIONSHIPS/` (seniors) and its `JR/` folder (juniors), format in the
README there; this parser reads them and checks every report against the others. Qualification
decides the team and all-around titles (no team or all-around final); the top eight per apparatus,
two per country, go to the finals.
"""
import os, re, sys
from decimal import Decimal, ROUND_DOWN

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-AFRICAN-CHAMPIONSHIPS'
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err

# What differs between the two books, keyed by the FIG event number.
BOOKS = {
    '18377': dict(
        age='SR', folder='',
        # From the Competition Schedule (pp. 2-3): senior qualification on Thu 23 April.
        qual_date='2026-04-23',
        # The entry list and counts have text (pp. 4-5).
        entries_from_pdf=True,
        # The "Number of Entries by NOC" page (p. 4) disagrees with the entry list for WAG: it counts
        # one Namibian (the list has five, all of whom competed) and three Senegalese (two), 26 in all
        # (29). Per country: (page, listed).
        count_slips={'WAG': {'NAM': (1, 5), 'SEN': (3, 2)}},
        count_total_slips=set(),
        # Results print one athlete's given name differently from the entry list (HANDURA Nagaititue).
        printed_names={'131': 'Ngaititue'},
        # Namibia's fifth WAG entry (HANDURA, born 2010) is not on its team page: an individual.
        individuals={'131'},
        # The WAG uneven bars final prints a Q beside every finalist, a leftover of the qualification layout.
        final_marks={('WAG', 'UB')},
        # Vault: WAG's +0.2 is printed on the vault 2 line and added to the two-vault average.
        vault_bonus='combined',
        judge_scores=False,
        judge_score_pen_slips=set()),
    '18378': dict(
        age='JR', folder='JR',
        # From the Competition Schedule (pp. 2-3): junior qualification on Fri 24 April; the finals
        # follow the seniors' each day. The tables' footers print the same dates.
        qual_date='2026-04-24',
        entries_from_pdf=False,
        # The counts page (p. 4) counts five South African men (the list has three; three competed)
        # and three Senegalese women (two), and leaves out DR Congo's one woman (RDC).
        count_slips={'MAG': {'RSA': (5, 3)}, 'WAG': {'SEN': (3, 2), 'RDC': (0, 1)}},
        # Mali's row prints the code in the Country cell and no Total.
        count_total_slips={'MLI'},
        printed_names={},
        individuals=set(),
        final_marks=set(),
        # Vault: a bonus printed beside a vault is that vault's own (MAG ABOUWARD's vault 2: 3.600 +
        # 9.266 - 0.100 + 0.100 = 12.866); the two-vault total is the plain average.
        vault_bonus='vault',
        judge_scores=True,
        # The WAG vault judges' scores print a vault 2 ND that disagrees with the penalty total beside
        # it (ND 0.000, total 0.100: ELGARHI, SAFADI; 0.300: FEKI, STRAUSS; ND 0.300, total 0.100:
        # BADENHORST). The total agrees with the score and the vault table.
        judge_score_pen_slips={('WAG', 'QUAL', '145', 2), ('WAG', 'QUAL', '157', 2), ('WAG', 'QUAL', '156', 2),
                               ('WAG', 'QUAL', '165', 2), ('WAG', 'QUAL', '160', 2)}),
}
FIG_ID = os.path.basename(PDF).split('-')[0]
if FIG_ID not in BOOKS:
    raise SystemExit(f'{PDF}: expected a file name starting 18377 (seniors) or 18378 (juniors)')
BOOK = BOOKS[FIG_ID]
AGE = BOOK['age']
TRANSCRIPTIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transcriptions', EVENT_PREFIX,
                              BOOK['folder'])
PAGES = common.pdf_pages(PDF) if BOOK['entries_from_pdf'] else None

PREFIX = {d: f'{EVENT_PREFIX}-{d}-{AGE}' for d in ('MAG', 'WAG')}
EVENT_NAME = EVENTS[PREFIX['MAG']]['Title']
EVENT_START = EVENTS[PREFIX['MAG']]['Start Date']
if any(EVENTS[p]['Title'] != EVENT_NAME or EVENTS[p]['Start Date'] != EVENT_START for p in PREFIX.values()):
    raise SystemExit('MAG and WAG rows in EVENT.csv are expected to share a title and start date')
if any(EVENTS[p]['FIG Event Number'] != FIG_ID for p in PREFIX.values()):
    raise SystemExit(f'EVENT.csv rows for {AGE} are not FIG event {FIG_ID}')
corrections = common.Corrections(OUT, EVENT_PREFIX, [f'MAG-{AGE}', f'WAG-{AGE}'], err)
out = common.Output(OUT, corrections)
# The book's apparatus order (all-around and team reports), and the RANKING column order.
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
# Qualification (book-specific date); finals day 1 on Sat 25 April (MAG FX/PH/SR, WAG VT/UB), day 2 on
# Sun 26 April (MAG VT/PB/HB, WAG BB/FX), for both books (schedule pp. 2-3; the footers agree).
QUAL_DATE = BOOK['qual_date']
FINAL_DATE = {'MAG': {'FX': '2026-04-25', 'PH': '2026-04-25', 'SR': '2026-04-25',
                      'VT': '2026-04-26', 'PB': '2026-04-26', 'HB': '2026-04-26'},
              'WAG': {'VT': '2026-04-25', 'UB': '2026-04-25', 'BB': '2026-04-26', 'FX': '2026-04-26'}}
# The team reports print the country's name.
COUNTRY = {'Algeria': 'ALG', 'Cameroon': 'CMR', 'Egypt': 'EGY', 'Namibia': 'NAM', 'Senegal': 'SEN',
           'South Africa': 'RSA', 'Tunisia': 'TUN'}
# The counts page prints Zimbabwe as ZIM, where the entry list and results print ZWE (written ZIM, a
# correction).
COUNT_PAGE_CODES = {'ZIM': 'ZWE'}
PRINTED_NAMES = BOOK['printed_names']
INDIVIDUALS = BOOK['individuals']
FINAL_MARKS = BOOK['final_marks']

def read(name):
    """A transcription's lines, without comments and blank lines, as (line number, fields)."""
    rows = []
    for n, l in enumerate(open(os.path.join(TRANSCRIPTIONS, name), encoding='utf-8'), 1):
        l = l.rstrip('\n')
        if not l.strip() or l.startswith('#'):
            continue
        if l.startswith('!'):
            err(f'{name}:{n}: unreviewed line {l[:80]!r}')
            l = l[1:]
        rows.append((n, l.split('|')))
    return rows

# ---------------------------------------------------------------- participants
PEOPLE = {}   # bib -> dict(name, noc, words)

def entry_counts_pdf():
    """p. 4, `No. Country NOC MAG WAG Total`, a blank where a country entered none."""
    rows = []
    lines = PAGES[3].splitlines()
    head = next(l for l in lines if re.search(r'\bMAG\s+WAG\s+Total', l))
    # Columns by position under the header (right edges): a blank MAG or WAG cell leaves two numbers
    cols = [(c, head.index(c) + len(c)) for c in ('MAG', 'WAG', 'Total')]
    for l in lines:
        m = re.match(r'\s*\d+\s+[A-Z][A-Z ]+?\s{2,}([A-Z]{3})\s+(.*)$', l)
        if not m:
            continue
        cells = {}
        for x in re.finditer(r'\d+', m.group(2)):
            end = m.start(2) + x.end()
            col = min(cols, key=lambda c: abs(c[1] - end))[0]
            if col in cells:
                err(f'entry counts: {l!r}')
            cells[col] = int(x.group())
        rows.append((m.group(1), cells))
    return rows, None

def entry_counts_transcribed():
    """ENTRY-COUNTS.txt: `No.|Country|NOC|MAG|WAG|Total` as printed, then `T|Total||MAG|WAG|Total`."""
    rows, total = [], None
    for n, f in read('ENTRY-COUNTS.txt'):
        if len(f) != 6 or not all(re.fullmatch(r'\d*', v) for v in f[3:]):
            err(f'ENTRY-COUNTS.txt:{n}: {f}'); continue
        cells = {c: int(v) for c, v in zip(('MAG', 'WAG', 'Total'), f[3:]) if v}
        if f[0] == 'T':
            total = cells
        else:
            # Mali's row prints the code in the Country cell and leaves NOC blank
            rows.append((f[2] or f[1], cells))
    return rows, total

def entry_counts():
    """Entries per discipline and country from the counts page, each row checked to add up."""
    rows, total = entry_counts_pdf() if BOOK['entries_from_pdf'] else entry_counts_transcribed()
    counts = {'MAG': {}, 'WAG': {}}
    for noc, cells in rows:
        if (cells.get('MAG', 0) + cells.get('WAG', 0) != cells.get('Total')) != (noc in BOOK['count_total_slips']):
            err(f'entry counts {noc}: {cells}')
        for disc in ('MAG', 'WAG'):
            if cells.get(disc):
                counts[disc][COUNT_PAGE_CODES.get(noc, noc)] = cells[disc]
    if total is not None:
        sums = {c: sum(cells.get(c, 0) for _, cells in rows) for c in ('MAG', 'WAG', 'Total')}
        if sums != total:
            err(f'entry counts: column sums {sums} != printed total {total}')
    return counts

def birth_date(s, noc):
    """`dd/mm/yyyy`, except Egypt's rows: `yyyy/mm/dd`."""
    m = re.fullmatch(r'(\d\d)/(\d\d)/(\d{4})', s)
    if m:
        return f'{m.group(3)}-{m.group(2)}-{m.group(1)}'
    m = re.fullmatch(r'(\d{4})/(\d\d)/(\d\d)', s)
    if m and noc == 'EGY':
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    err(f'participants: birth date {s!r} ({noc})')
    return ''

def entries_pdf():
    """p. 5, "Entries List by NOC": `# NOC SURNAME Given Discipline FIG-ID BIB dd/mm/yyyy`."""
    for l in PAGES[4].splitlines():
        m = re.fullmatch(r'\s*(\d+)\s+([A-Z]{3})\s+(.+?)\s+(MAG|WAG)\s+(\d+)\s+(\d{3})\s+([\d/]+)\s*', l)
        if not m:
            if re.match(r'\s*\d+\s+[A-Z]{3}\s', l):
                err(f'participants: unparsed line {l!r}')
            continue
        yield m.groups()

def entries_transcribed():
    """ENTRIES.txt: `#|NOC|SURNAME Given|Discipline|FIG ID|BIB|Date of Birth` as printed."""
    for n, f in read('ENTRIES.txt'):
        if len(f) != 7 or not re.fullmatch(r'\d+', f[0]) or not re.fullmatch(r'[A-Z]{3}', f[1]) or \
                f[3] not in ('MAG', 'WAG') or not re.fullmatch(r'\d+', f[4]) or not re.fullmatch(r'\d{3}', f[5]):
            err(f'ENTRIES.txt:{n}: {f}'); continue
        yield f

def participants():
    rows = {'MAG': [], 'WAG': []}
    counts = {'MAG': {}, 'WAG': {}}
    for order, noc, name, disc, lic, bib, born in (entries_pdf() if BOOK['entries_from_pdf'] else entries_transcribed()):
        sur, giv = split_surname_first(name)
        if not sur or not giv:
            err(f'participants: name split {name!r} -> {sur!r}/{giv!r}')
        if bib in PEOPLE:
            err(f'participants: bib {bib} twice')
        PEOPLE[bib] = dict(name=name, noc=noc, disc=disc, words=name.upper().replace('-', ' ').split())
        counts[disc][noc] = counts[disc].get(noc, 0) + 1
        date = birth_date(born, noc)
        rows[disc].append({'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE,
                           'Event Start Date': EVENT_START, 'Order': order, 'NOC Code': noc, 'Bib Number': bib,
                           'FIG License': lic, 'Name': name, 'Surname': sur, 'Given Name': giv,
                           'Birth Year': date[:4], 'Birth Date': date})
    if [int(r['Order']) for d in ('MAG', 'WAG') for r in rows[d]] != list(range(1, len(PEOPLE) + 1)):
        err('participants: entry list numbering has gaps')
    printed = entry_counts()
    for disc in ('MAG', 'WAG'):
        want = dict(printed[disc])
        for noc, (page, listed) in BOOK['count_slips'].get(disc, {}).items():
            if want.get(noc, 0) != page:
                err(f'participants {disc}: count page slip for {noc} no longer {page}')
            want[noc] = listed
        if counts[disc] != want:
            err(f'participants {disc}: entries by NOC {counts[disc]} != count page {want}')
        out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows[disc])

def check_identity(ctx, bib, name, noc=None, disc=None):
    """Results print names in several forms (`ALHAMIDI Nadir`, `Nadir HAMIDI` for ALHAMIDI Yacer
    Nadir): every printed word must be part of a word of the entry list's name."""
    p = PEOPLE.get(bib)
    if not p:
        err(f'{ctx}: bib {bib} not in participants'); return
    if disc and p['disc'] != disc:
        err(f'{ctx}: bib {bib} is {p["disc"]}')
    if noc and noc != p['noc']:
        err(f'{ctx}: bib {bib} NOC {noc} != entry {p["noc"]}')
    for w in name.upper().replace('-', ' ').split():
        if not any(w in e for e in p['words']) and w != PRINTED_NAMES.get(bib, '').upper():
            err(f'{ctx}: bib {bib} {name!r} does not match entry {p["name"]!r}')
            return

# ---------------------------------------------------------------- judges
def judges(disc):
    """`APP|function|SURNAME|Given|NOC`, as printed. MAG's Competition Jury has no apparatus or
    function printed and is written as the Technical Delegate (`TD`), credited to UAG (blank). WAG
    panels are headed by `AS` (apparatus supervisor, seniors only), written `SV`; WAG's
    `SUPERIOR JURY <n>` is written `Member`."""
    rows = []
    for rnd in ('QUAL', 'EVENT'):
        n0 = len(rows)
        for n, f in read(f'{disc}-JUDGES-{rnd}.txt'):
            if len(f) != 5:
                err(f'{disc}-JUDGES-{rnd}.txt:{n}: {f}'); continue
            app, fn, sur, giv, noc = f
            if fn == 'AS' and disc == 'WAG':
                fn = 'SV'
            if re.fullmatch(r'SUPERIOR JURY \d', fn) and disc == 'WAG':
                fn = 'Member'
            if app and app not in APPS[disc] or not re.fullmatch(r'TD|Member|SV|D[12]|E[1-5]|T[12]?|L[12]?', fn):
                err(f'{disc}-JUDGES-{rnd}.txt:{n}: {app!r} {fn!r}')
            if (fn in ('TD', 'Member')) != (app == '') or not re.fullmatch(r'[A-Z]{3}', noc):
                err(f'{disc}-JUDGES-{rnd}.txt:{n}: {f}')
            # A surname left blank is supplied by a correction (WAG Superior Jury 2, printed `Rawan`)
            if not sur and fn != 'Member':
                err(f'{disc}-JUDGES-{rnd}.txt:{n}: no surname')
            rows.append({'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE,
                         'Event Start Date': EVENT_START, 'Competition': common.COMPETITION[rnd], 'Apparatus': app, 'Function': fn,
                         'Name': f'{sur} {giv}'.strip(), 'Surname': sur, 'Given Name': giv,
                         'NOC Code': '' if noc == 'UAG' else noc})
        panels = {(r['Apparatus'], r['Function']) for r in rows[n0:]}
        if len(panels) != len(rows) - n0:
            err(f'{disc} judges {rnd}: a function listed twice on a panel')
        for app in APPS[disc]:
            if not {(app, f) for f in ('D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5')} <= panels:
                err(f'{disc} judges {rnd} {app}: incomplete panel')
        print(f'  judges {disc} {rnd}: {len(rows) - n0}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, rows)

# ---------------------------------------------------------------- values
SCORE = r'\d+\.\d{3}'

def penalty(p):
    """PEN prints unsigned; written negative, as deducted."""
    return f'-{p}' if p else ''

def check_routine(ctx, d, e, pen, bonus, total):
    """D + E + bonus - PEN = Total; a score never goes below zero (MAG pommel horse MGBAKOBO:
    1.000 + 4.300 - 6.000 prints 0.000)."""
    if D(total) == 0 and D(d) + D(e) + D(bonus) - D(pen) < 0:
        return
    checks.check_sum(ctx, total, d, e, bonus, penalty(pen))

def routine(ctx, d, e, pen, bonus, total):
    """One routine as printed (`D E PEN [BONUS] Total`)."""
    for v in (d, e, total):
        if not re.fullmatch(SCORE, v):
            err(f'{ctx}: value {v!r}')
    for v in (pen, bonus):
        if v and not re.fullmatch(SCORE, v):
            err(f'{ctx}: value {v!r}')
    check_routine(ctx, d, e, pen, bonus, total)
    return dict(D=d, E=e, Pen=pen, B=bonus, Total=total)

def routine_cols(g, suffix=''):
    if g is None:
        return {f'{c}{suffix}': '' for c in common.ROUTINE}
    if g == 'DNS':
        return {**{f'{c}{suffix}': '' for c in common.ROUTINE}, f'Status{suffix}': 'DNS'}
    return {f'Status{suffix}': 'COMPLETED', f'D{suffix}': g['D'], f'E{suffix}': g['E'], f'B{suffix}': g['B'],
            f'Penalty{suffix}': penalty(g['Pen']), f'SJ Penalty{suffix}': '', f'Total{suffix}': g['Total']}

def meta(disc, rnd, app, rank, bib):
    return {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE,
            'Competition Start Date': QUAL_DATE if rnd == 'QUAL' else FINAL_DATE[disc][app], 'Competition': common.COMPETITION[rnd], 'Part': '',
            'Apparatus': app, 'Rank': rank, 'Bib': bib, 'Name': PEOPLE[bib]['name'], 'NOC Code': PEOPLE[bib]['noc']}

def check_ranks(ctx, rows, key='Total'):
    """Ranks as printed: never decreasing, totals never increasing, ties equal, and no rank skipped
    except after a tie."""
    ranked = [r for r in rows if r['Rank']]
    checks.check_rank_order(ctx, [dict(Rank=r['Rank'], Total=r[key], Bib=r['Bib']) for r in ranked])
    for i, r in enumerate(ranked):
        if int(r['Rank']) != i + 1 and (i == 0 or r['Rank'] != ranked[i - 1]['Rank']):
            err(f'{ctx}: rank {r["Rank"]} at position {i + 1} (bib {r["Bib"]})')

# ---------------------------------------------------------------- all-around report
def aa_report(disc):
    """`rank|bib|SURNAME Given|NOC|total` (`<partial total> DNF` for an incomplete all-around), then
    `APP|D|E|P|Total|RK` per routine. The report prints no bonus, and `0.000` for no penalty; RK is
    the routine's rank on that apparatus over the whole field."""
    name = f'{disc}-QUAL-AA.txt'
    athletes, cur = [], None
    for n, f in read(name):
        ctx = f'{name}:{n}'
        if f[0] in APPS[disc]:
            if cur is None or f[0] in cur['apps'] or len(f) != 6:
                err(f'{ctx}: routine {f}'); continue
            app, d, e, p, total, rk = f
            for v in (d, e, p, total):
                if not re.fullmatch(SCORE, v):
                    err(f'{ctx}: value {v!r}')
            if not re.fullmatch(r'\d+', rk):
                err(f'{ctx}: RK {rk!r}')
            cur['apps'][app] = dict(D=d, E=e, P=p, Total=total, RK=rk)
            continue
        if len(f) != 5 or not re.fullmatch(r'\d*', f[0]) or not re.fullmatch(r'\d{3}', f[1]):
            err(f'{ctx}: athlete line {f}'); cur = None; continue
        check_identity(ctx, f[1], f[2], f[3], disc)
        cur = dict(rank=f[0], bib=f[1], printed=f[4], apps={}, ctx=ctx)
        athletes.append(cur)
    for a in athletes:
        ctx = f'{disc} AA bib {a["bib"]}'
        total = sum((D(g['Total']) for g in a['apps'].values()), Decimal(0))
        m = re.fullmatch(rf'({SCORE})( DNF)?', a['printed'])
        if not m or D(m.group(1)) != total:
            err(f'{ctx}: total {a["printed"]!r}, apparatus sum {total}')
        complete = len(a['apps']) == len(APPS[disc])
        if complete == bool(m and m.group(2)) or complete != bool(a['rank']):
            err(f'{ctx}: {len(a["apps"])} routines, rank {a["rank"]!r}, total {a["printed"]!r}')
        a['Total'] = m.group(1) if m and complete else ''
    check_ranks(f'{disc} QUAL AA', [dict(Rank=a['rank'], Total=a['Total'], Bib=a['bib']) for a in athletes])
    bibs = [a['bib'] for a in athletes]
    entered = {b for b, p in PEOPLE.items() if p['disc'] == disc}
    if len(bibs) != len(set(bibs)) or set(bibs) != entered:
        err(f'{disc} AA: athletes {sorted(set(bibs) ^ entered)} differ from the entry list')
    return {a['bib']: a for a in athletes}

def summary_aa(disc, aa):
    """All-around decided in qualification (no final). An incomplete all-around keeps its row with
    Rank and Total blank (§4.3)."""
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'Bib', 'Name',
           'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for a in aa.values():
        r = {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE, 'Event Start Date': EVENT_START,
             'Competition': 'C1', 'Part': '', 'Rank': a['rank'], 'Bib': a['bib'], 'Name': PEOPLE[a['bib']]['name'],
             'NOC Code': PEOPLE[a['bib']]['noc'], 'SJ Penalty': '', 'Total': a['Total'], 'Qualification': ''}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = a['apps'].get(app, {}).get('Total', '')
        rows.append(r)
    out.ranking(PREFIX[disc], 'AA', hdr, rows, EVENTS[PREFIX[disc]])

def same_as_aa(ctx, aa, bib, app, g):
    """A routine in an apparatus table against the all-around report (which prints no bonus and
    `0.000` for no penalty)."""
    a = aa.get(bib, {}).get('apps', {}).get(app)
    if a is None:
        err(f'{ctx}: not in the all-around report'); return None
    want = [g['D'], g['E'], g['Pen'] or '0.000', g['Total']]
    if [a['D'], a['E'], a['P'], a['Total']] != want:
        err(f'{ctx}: {want} != all-around {[a["D"], a["E"], a["P"], a["Total"]]}')
    return a

# ---------------------------------------------------------------- team report
def team_report(disc, aa):
    """`T|rank|Country|total`, then `M|bib|Given SURNAME|values…` per member in the book's apparatus
    order, `*` before a score printed in bold (counting). The report prints no apparatus totals: the
    summary's are the sums of the bold scores, which must be each apparatus's best three and add up
    to the printed total."""
    name = f'{disc}-QUAL-TEAM.txt'
    n = len(APPS[disc])
    teams = []
    for ln, f in read(name):
        ctx = f'{name}:{ln}'
        if f[0] == 'T' and len(f) == 4 and f[2] in COUNTRY:
            teams.append(dict(Rank=f[1], NOC=COUNTRY[f[2]], Total=f[3], members={}))
        elif f[0] == 'M' and teams and len(f) == n + 3:
            check_identity(ctx, f[1], f[2], teams[-1]['NOC'], disc)
            vals = {}
            for app, v in zip(APPS[disc], f[3:]):
                if v and not re.fullmatch(rf'\*?{SCORE}', v):
                    err(f'{ctx}: value {v!r}')
                vals[app] = v
            teams[-1]['members'][f[1]] = vals
        else:
            err(f'{ctx}: line {f}')
    rows = []
    for t in teams:
        c = f'{disc} team {t["NOC"]}'
        totals = {}
        for app in APPS[disc]:
            printed = {b: v[app] for b, v in t['members'].items() if v[app]}
            for b, v in printed.items():
                g = aa.get(b, {}).get('apps', {}).get(app)
                if not g or g['Total'] != v.lstrip('*'):
                    err(f'{c} bib {b} {app}: {v} != all-around {g and g["Total"]}')
            for b in t['members']:
                if b not in printed and app in aa.get(b, {}).get('apps', {}):
                    err(f'{c} bib {b} {app}: missing a routine the all-around report has')
            scores = sorted((D(v.lstrip('*')) for v in printed.values()), reverse=True)
            bold = [D(v[1:]) for v in printed.values() if v.startswith('*')]
            if len(bold) != min(3, len(scores)) or sorted(bold, reverse=True) != scores[:len(bold)]:
                err(f'{c} {app}: bold {bold} are not the best three of {scores}')
            totals[app] = sum(bold, Decimal(0))
        if sum(totals.values()) != D(t['Total']):
            err(f'{c}: bold scores {sum(totals.values())} != {t["Total"]}')
        r = {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE, 'Event Start Date': EVENT_START,
             'Competition': 'C1', 'Part': '', 'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': '',
             'Total': t['Total'], 'Qualification': ''}
        for app in APPS[disc]:
            r[f'{app} Total'] = f'{totals[app]:.3f}'
        rows.append(r)
    # Every athlete of a team's country is on its team page, except those entered as individuals
    for t in teams:
        members = {b for b, p in PEOPLE.items() if p['noc'] == t['NOC'] and p['disc'] == disc} - INDIVIDUALS
        if set(t['members']) != members:
            err(f'{disc} team {t["NOC"]}: members {sorted(t["members"])} != entries {sorted(members)}')
    check_ranks(f'{disc} team', [dict(Rank=r['Rank'], Total=r['Total'], Bib=r['NOC Code']) for r in rows])
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'NOC Code'] + \
          [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    out.ranking(PREFIX[disc], 'TEAM', hdr, rows, EVENTS[PREFIX[disc]])

# ---------------------------------------------------------------- apparatus tables
def table(disc, rnd, app):
    """Non-vault: `rank|bib|SURNAME Given|NOC|D|E|PEN|BONUS|Total|mark` (WAG prints no BONUS column:
    blank); a finalist who didn't start prints only `DNS` in Total. Vault, seniors:
    `rank|bib|SURNAME Given|NOC|D|E|PEN|Score|Total|mark` for vault 1, then `V2|D|E|PEN|Score|Bonus`
    (the combined bonus) or `V2|DNS`; juniors: `rank|bib|SURNAME Given|NOC|D|E|PEN|Score|Bonus|Total|mark`
    and `V2|D|E|PEN|Score|Bonus`, each bonus that vault's own. Total is the two-vault result, `DNF`,
    or blank for one vault. Marks: `Q`, `R` as printed."""
    name = f'{disc}-{rnd}-{app}.txt'
    per_vault = BOOK['vault_bonus'] == 'vault'
    rows, cur = [], None
    for n, f in read(name):
        ctx = f'{name}:{n}'
        if f[0] == 'V2':
            if cur is None or 'v2' in cur or app != 'VT':
                err(f'{ctx}: vault 2 out of place'); continue
            if f[1:] == ['DNS']:
                cur['v2'] = 'DNS'
            elif len(f) == 6 and per_vault:
                cur['v2'] = routine(f'{ctx} bib {cur["bib"]} vault 2', f[1], f[2], f[3], f[5], f[4])
                cur['vb'] = ''
            elif len(f) == 6:
                cur['v2'] = routine(f'{ctx} bib {cur["bib"]} vault 2', f[1], f[2], f[3], '', f[4])
                cur['vb'] = f[5]
                if f[5] not in ('', '0.200') or f[5] and disc != 'WAG':
                    err(f'{ctx}: vault bonus {f[5]!r}')
            else:
                err(f'{ctx}: vault 2 {f}')
            continue
        width = 11 if app == 'VT' and per_vault else 10
        if len(f) != width or not re.fullmatch(r'\d*', f[0]) or not re.fullmatch(r'\d{3}', f[1]):
            err(f'{ctx}: athlete line {f}'); cur = None; continue
        rank, bib, nm, noc = f[:4]
        mk = f[-1]
        check_identity(ctx, bib, nm, noc, disc)
        if rnd == 'EVENT' and (disc, app) in FINAL_MARKS and mk == 'Q':
            mk = ''
        if mk not in ('', 'Q', 'R') or mk and rnd != 'QUAL':
            err(f'{ctx}: mark {mk!r}')
        if f[-2] == 'DNS':
            # A finalist who didn't start: no values, no rank
            if rnd != 'EVENT' or rank or any(f[4:-2]):
                err(f'{ctx}: DNS row {f}')
            cur = dict(rank='', bib=bib, mk=mk, total='DNS', **({'v1': 'DNS', 'v2': 'DNS'} if app == 'VT' else {'g': 'DNS'}))
        elif app == 'VT':
            d, e, pen, score = f[4:8]
            b1 = f[8] if per_vault else ''
            cur = dict(rank=rank, bib=bib, mk=mk, v1=routine(f'{ctx} bib {bib} vault 1', d, e, pen, b1, score),
                       total=f[-2])
        else:
            d, e, pen, x, total = f[4:9]
            if x and disc == 'WAG':
                err(f'{ctx}: WAG bonus {x!r}')
            cur = dict(rank=rank, bib=bib, mk=mk, g=routine(f'{ctx} bib {bib}', d, e, pen, x, total), total=total)
        rows.append(cur)
    if len({r['bib'] for r in rows}) != len(rows):
        err(f'{name}: a bib listed twice')
    for r in rows:
        if app != 'VT' or r['total'] == 'DNS':
            continue
        ctx = f'{disc} {rnd} VT bib {r["bib"]}'
        v2 = r.get('v2')
        if isinstance(v2, dict):
            checks.check_vault_average(ctx, r['v1']['Total'], v2['Total'], r['vb'], r['total'])
            if not r['rank']:
                err(f'{ctx}: two vaults but no rank')
        elif r['total'] != ('DNF' if v2 == 'DNS' else '') or r['rank'] or r['mk']:
            err(f'{ctx}: rank {r["rank"]!r}, total {r["total"]!r} with {"no" if v2 is None else v2} vault 2')
    return rows

def markers(ctx, rows):
    """Q on eight (two per country), then two plain R, written R1, R2 in rank order (§4.6)."""
    ranked = [r for r in rows if r['rank']]
    qs = [r for r in ranked if r['mk'] == 'Q']
    rs = [r for r in ranked if r['mk'] == 'R']
    if len(qs) != 8 or len(rs) != 2:
        err(f'{ctx}: {len(qs)} Q, {len(rs)} R')
    last_q = max((i for i, r in enumerate(ranked) if r['mk'] == 'Q'), default=-1)
    first_r = min((i for i, r in enumerate(ranked) if r['mk'] == 'R'), default=len(ranked))
    if first_r < last_q:
        err(f'{ctx}: a reserve ranked above a qualifier')
    nocs = {}
    for r in ranked[:first_r]:
        noc = PEOPLE[r['bib']]['noc']
        nocs[noc] = nocs.get(noc, 0) + 1
        # Unmarked above the reserves: only the two-per-country rule leaves one out (no NR printed)
        if (r['mk'] == 'Q') != (nocs[noc] <= 2):
            err(f'{ctx}: bib {r["bib"]} mark {r["mk"]!r} breaks two per country')
    for r in rs:
        if sum(PEOPLE[x['bib']]['noc'] == PEOPLE[r['bib']]['noc'] for x in qs) >= 2:
            err(f'{ctx}: reserve {r["bib"]} from a country with two qualifiers')
    marks = {r['bib']: 'Q' for r in qs}
    marks.update({r['bib']: f'R{i}' for i, r in enumerate(rs, 1)})
    return marks

def qual(disc, app, aa):
    rows = table(disc, 'QUAL', app)
    ctx = f'{disc} QUAL {app}'
    out_rows = []
    for r in rows:
        c = f'{ctx} bib {r["bib"]}'
        if app == 'VT':
            a = same_as_aa(c + ' vault 1', aa, r['bib'], 'VT', r['v1'])
            v2 = r.get('v2')
            # Rank: the all-around report's vault RK, which ranks the whole field on vault 1 (the
            # vault that counts for the all-around and team); this list ranks the two-vault results.
            w = {**meta(disc, 'QUAL', 'VT', a['RK'] if a else '', r['bib']), **routine_cols(r['v1'], '1'),
                 **routine_cols(v2, '2'), 'Combined Bonus': r.get('vb', ''),
                 'Total': r['total'] if isinstance(v2, dict) else '' if v2 == 'DNS' else r['v1']['Total'],
                 'Qualification Rank': r['rank']}
        else:
            a = same_as_aa(c, aa, r['bib'], app, r['g'])
            if a and a['RK'] != r['rank']:
                err(f'{c}: rank {r["rank"]} != all-around RK {a["RK"]}')
            w = {**meta(disc, 'QUAL', app, r['rank'], r['bib']), **routine_cols(r['g']),
                 'Qualification Rank': r['rank']}
        out_rows.append(w)
    marks = markers(ctx, rows)
    for w in out_rows:
        w['Qualification'] = marks.get(w['Bib'], '')
    performed = {b for b, a in aa.items() if app in a['apps']}
    if {w['Bib'] for w in out_rows} != performed:
        err(f'{ctx}: athletes differ from the all-around report: {sorted({w["Bib"] for w in out_rows} ^ performed)}')
    if app == 'VT':
        check_ranks(ctx + ' two-vault', [dict(Rank=r['rank'], Total=r['total'], Bib=r['bib']) for r in rows])
        # The whole-field vault 1 ranking: ranks in order of vault 1 scores
        v1 = sorted((w for w in out_rows if w['Rank']), key=lambda w: int(w['Rank']))
        checks.check_rank_order(ctx + ' vault 1', [dict(Rank=w['Rank'], Total=w['Total1'], Bib=w['Bib']) for w in v1])
    else:
        check_ranks(ctx, out_rows)
    out.csv(f'{PREFIX[disc]}-SCORES-C1-{app}.csv', common.score_header(app == 'VT', True), out_rows)
    return marks, rows

def final(disc, app, marks, starts):
    rows = table(disc, 'EVENT', app)
    ctx = f'{disc} EVENT {app}'
    out_rows = []
    for r in rows:
        if r['total'] == 'DNS':
            w = {**meta(disc, 'EVENT', app, '', r['bib']),
                 **({**routine_cols('DNS', '1'), **routine_cols('DNS', '2'), 'Combined Bonus': '', 'Total': ''}
                    if app == 'VT' else routine_cols('DNS'))}
        elif app == 'VT':
            if not isinstance(r.get('v2'), dict):
                err(f'{ctx} bib {r["bib"]}: two vaults expected'); continue
            w = {**meta(disc, 'EVENT', 'VT', r['rank'], r['bib']), **routine_cols(r['v1'], '1'),
                 **routine_cols(r['v2'], '2'), 'Combined Bonus': r['vb'], 'Total': r['total']}
        else:
            w = {**meta(disc, 'EVENT', app, r['rank'], r['bib']), **routine_cols(r['g'])}
        out_rows.append(w)
    if len(out_rows) != 8:
        err(f'{ctx}: {len(out_rows)} finalists')
    finalists = {w['Bib'] for w in out_rows}
    q = {b for b, m in marks.items() if m == 'Q'}
    noc = lambda b: PEOPLE[b]['noc']
    # A qualifier who doesn't start is replaced by a reserve, or by a compatriot the two-per-country
    # rule had left out (§4.6); markers stay as printed.
    absent = q - finalists
    for b in finalists - q:
        kind = 'reserve' if marks.get(b, '').startswith('R') else \
            'compatriot' if any(noc(a) == noc(b) for a in absent) else None
        if not kind:
            err(f'{ctx}: finalist {b} is neither a qualifier, a reserve nor a compatriot of an absent qualifier')
    if absent:
        print(f'  {ctx}: qualifiers {sorted(absent)} absent; in their place {sorted(finalists - q)}')
    dns = sorted(w['Bib'] for w in out_rows if w['Status' if app != 'VT' else 'Status1'] == 'DNS')
    if dns:
        print(f'  {ctx}: {dns} did not start')
    # The finals start list already shows the changes known when it was printed; its eight and the
    # final's eight must differ only by such replacements.
    start = [b for pos, b in starts.get(app, []) if pos.isdigit()]
    reserves = [b for pos, b in starts.get(app, []) if pos.startswith('R')]
    if len(start) != 8 or len(reserves) != 2:
        err(f'{ctx}: start list {starts.get(app)}')
    for b in finalists - set(start):
        if b not in reserves and not any(noc(a) == noc(b) for a in set(start) - finalists):
            err(f'{ctx}: finalist {b} not on the start list')
    if set(start) != q:
        print(f'  {ctx}: start list leaves out {sorted(q - set(start))}, adds {sorted(set(start) - q)}')
    if set(start) != finalists:
        print(f'  {ctx}: final leaves out start list {sorted(set(start) - finalists)}, '
              f'adds {sorted(finalists - set(start))}')
    check_ranks(ctx, out_rows)
    out.csv(f'{PREFIX[disc]}-SCORES-C3-{app}.csv', common.score_header(app == 'VT', False), out_rows)
    return rows

def finals_start(disc):
    """`APP|#|bib|Given SURNAME|NOC`: the Apparatus Finals Start List."""
    starts = {}
    for n, f in read(f'{disc}-FINALS-START.txt'):
        if len(f) != 5 or f[0] not in APPS[disc] or not re.fullmatch(r'[1-8]|R[12]', f[1]):
            err(f'{disc}-FINALS-START.txt:{n}: {f}'); continue
        check_identity(f'{disc}-FINALS-START.txt:{n}', f[2], f[3], f[4], disc)
        starts.setdefault(f[0], []).append((f[1], f[2]))
    return starts

def tie_breaks(disc, tables):
    """The Tie Break pages, as printed (`08.366`): `APP|rank|bib|SURNAME Given|NOC|Total|E|D`, or for
    vault `VT|…|Total|highest vault|E|D`. Each page prints only the value that decides (E, or the
    higher vault), or E and D where E is equal. Checked against the tables: same rank and total, and
    the deciding values order the tied athletes; equal on them, the rank is shared (junior MAG pommel
    horse DAVIES VANEETVELDE and LECHHEB, 4th)."""
    pairs = {}
    for n, f in read(f'{disc}-TIE-BREAKS.txt'):
        ctx = f'{disc}-TIE-BREAKS.txt:{n}'
        vault = f[0] == 'VT'
        if f[0] not in tables or len(f) != (9 if vault else 8):
            err(f'{ctx}: {f}'); continue
        app, rank, bib, nm, noc, total = f[:6]
        check_identity(ctx, bib, nm, noc, disc)
        r = {x['bib']: x for x in tables[app]}.get(bib)
        if not r:
            err(f'{ctx}: bib {bib} not in the {app} table'); continue
        if vault:
            best = max((v for v in (r['v1'], r.get('v2')) if isinstance(v, dict)), key=lambda v: D(v['Total']))
            got = [best['Total'], best['E'], best['D']]
        else:
            got = [r['g']['E'], r['g']['D']]
        printed = f[6:]
        if r['rank'] != rank or D(r['total']) != D(total) or \
                any(p and D(p) != D(g) for p, g in zip(printed, got)) or not printed[0]:
            err(f'{ctx}: {f[1:]} != table {[r["rank"], r["total"]] + got}')
        pairs.setdefault((app, total), []).append((int(rank), [D(p) for p in printed if p]))
    for (app, total), tied in pairs.items():
        tied.sort()
        if len(tied) < 2 or any((a[0] == b[0]) != (a[1] == b[1]) or a[1] < b[1] for a, b in zip(tied, tied[1:])):
            err(f'{disc} tie break {app} {total}: {tied}')
    # Every equal total in a qualification ranking has its tie-break
    for app, rows in tables.items():
        totals = [D(r['total']) for r in rows if r['rank']]
        tied = {t for t in totals if totals.count(t) > 1}
        if tied != {D(t) for a, t in pairs if a == app}:
            err(f'{disc} {app}: tied totals {sorted(tied)} vs tie-break pages')

# ---------------------------------------------------------------- judges' scores (juniors)
PENALTY_PARTS = ('ND', 'L1', 'L2', 'Time', 'PEN', 'Line', 'T1', 'T2')

def trunc(x):
    return x.quantize(Decimal('0.001'), rounding=ROUND_DOWN)

def judge_scores(disc, rnd, app, rows):
    """`<DISC>-SCORES-<ROUND>-<APP>.txt`, the "Individual Judges Scores" page: an `H|…` line names the
    printed columns (E is the E-score total, Pen the penalty total, Total the score; vault: Score each
    vault's, Bonus its bonus, Total the two-vault result), then one line per athlete as printed, and a
    `V2|…` line for vault 2 without the leading identity columns and Total. A cross-check, not
    written: every routine's E must be the mean of the middle three judges' marks, truncated; the
    penalty parts add up to the penalty total; D + E - penalty + bonus is the score; and every value
    and rank agrees with the apparatus table."""
    name = f'{disc}-SCORES-{rnd}-{app}.txt'
    lines = read(name)
    if not lines or lines[0][1][0] != 'H':
        err(f'{name}: no H line'); return
    cols = lines[0][1][1:]
    table_rows = {r['bib']: r for r in rows}
    seen, cur = [], None
    for n, f in lines[1:]:
        ctx = f'{name}:{n}'
        if f[0] == 'V2':
            if app != 'VT' or cur is None:
                err(f'{ctx}: vault 2 out of place'); continue
            v = dict(zip(cols[4:-1], f[1:]))
            if len(f) != len(cols) - 4:
                err(f'{ctx}: {len(f)} fields'); continue
            judged(ctx, disc, rnd, app, cur, v, 2)
            continue
        if len(f) != len(cols):
            err(f'{ctx}: {len(f)} fields, header has {len(cols)}'); cur = None; continue
        v = dict(zip(cols, f))
        bib = v['BIB']
        check_identity(ctx, bib, v['Name'], v['NOC'], disc)
        cur = table_rows.get(bib)
        if cur is None:
            err(f'{ctx}: bib {bib} not in the {app} table'); continue
        seen.append(bib)
        if v['Rank'] != cur['rank']:
            err(f'{ctx}: rank {v["Rank"]!r} != table {cur["rank"]!r}')
        if v['Total'] == 'DNS' or cur['total'] == 'DNS':
            if v['Total'] != cur['total'] or any(v[c] for c in cols[4:-1]):
                err(f'{ctx}: DNS row {f}')
            continue
        if app == 'VT':
            if v['Total'] != (cur['total'] if isinstance(cur.get('v2'), dict) else ''):
                err(f'{ctx}: total {v["Total"]!r} != table {cur["total"]!r}')
        judged(ctx, disc, rnd, app, cur, v, 1)
    if seen != [r['bib'] for r in rows]:
        err(f'{name}: athletes {seen} differ from the {app} table {[r["bib"] for r in rows]}')

def judged(ctx, disc, rnd, app, row, v, vault):
    """One routine on a judges' scores page, against the apparatus table's row."""
    for c, x in v.items():
        if c in ('Rank', 'BIB', 'Name', 'NOC'):
            continue
        if x and not re.fullmatch(SCORE, x):
            err(f'{ctx}: {c} {x!r}')
    es = [D(v[f'E{i}']) for i in range(1, 6)]
    if trunc(sum(sorted(es)[1:4]) / 3) != D(v['E']):
        err(f'{ctx}: E {v["E"]} is not the mean of the middle three of {[str(e) for e in es]}')
    parts = sum((D(v[c]) for c in PENALTY_PARTS if c in v), Decimal(0))
    if parts != D(v['Pen']) and (disc, rnd, row['bib'], vault) not in BOOK['judge_score_pen_slips']:
        err(f'{ctx}: penalty parts {parts} != total {v["Pen"]!r}')
    score_col = 'Score' if app == 'VT' else 'Total'
    bonus = v.get('BONUS', v.get('Bonus', ''))
    check_routine(ctx, v['D'], v['E'], v['Pen'], bonus, v[score_col])
    g = row['g'] if app != 'VT' else row['v1'] if vault == 1 else row.get('v2')
    if not isinstance(g, dict):
        err(f'{ctx}: no vault {vault} in the table'); return
    want = [g['D'], g['E'], D(g['Pen']), g['B'], g['Total']]
    got = [v['D'], v['E'], D(v['Pen']), bonus, v[score_col]]
    if got != want:
        err(f'{ctx}: {[str(x) for x in got]} != table {[str(x) for x in want]}')

# ---------------------------------------------------------------- main
participants()
for disc in ('MAG', 'WAG'):
    judges(disc)
    aa = aa_report(disc)
    summary_aa(disc, aa)
    team_report(disc, aa)
    starts = finals_start(disc)
    tables = {}
    for app in APPS[disc]:
        marks, tables[app] = qual(disc, app, aa)
        finals = final(disc, app, marks, starts)
        if BOOK['judge_scores']:
            judge_scores(disc, 'QUAL', app, tables[app])
            judge_scores(disc, 'EVENT', app, finals)
    tie_breaks(disc, tables)
    for app in APPS[disc]:
        performed = sum(app in a['apps'] for a in aa.values())
        print(f'  {disc} {app}: {performed} routines in qualification')

for disc in ('MAG', 'WAG'):
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])
corrections.finish()
checks.finish()
