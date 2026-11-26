"""Parse the 2026 World Challenge Cup Varna results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_world_challenge_cup_varna.py \\
        data/2026/2026-WORLD-CHALLENGE-CUP-VARNA/18226-ResultsbookMedia.pdf

Writes PARTICIPANTS / JUDGES / SCORES-C1-<APP> / SCORES-C3-<APP> CSVs and an IMPORT.json
per discipline next to the PDF, reading event metadata from the EVENT.csv already there and
applying the event's CORRECTIONS.csv. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.11).

The Bulgarian Federation's media book, typed in Word: the entry list and the results tables have
text, one table to a page under a title (`Qualification FX - MAG`, `Apparatus Finals UB - WAG`),
some followed by a tie-break page. The judging assignments and start lists are images, transcribed
in transcriptions/2026-WORLD-CHALLENGE-CUP-VARNA/.
"""
import os, re, sys
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-WORLD-CHALLENGE-CUP-VARNA'
PREFIX = {disc: f'{EVENT_PREFIX}-{disc}-SR' for disc in ('MAG', 'WAG')}
TRANSCRIPTIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transcriptions', EVENT_PREFIX)

BOOK = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err)
out = common.Output(OUT, corrections)

APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
# Competition Schedule (pp. 2-3): qualification on Thursday MAG FX-PH-SR / WAG VT-UB, Friday the
# rest; finals on Saturday MAG FX-PH-SR / WAG VT-UB, Sunday the rest (the finals start lists agree).
DAY = {'MAG': {'FX': 1, 'PH': 1, 'SR': 1, 'VT': 2, 'PB': 2, 'HB': 2},
       'WAG': {'VT': 1, 'UB': 1, 'BB': 2, 'FX': 2}}
DATES = {'QUAL': {1: '2026-05-07', 2: '2026-05-08'}, 'EVENT': {1: '2026-05-09', 2: '2026-05-10'}}
ENTRY_COUNTS_PAGE = 4
MEDALLISTS_PAGE = 5
# Entries by NOC (p. 4) prints Mongolia as MNG; the entry list, results and start lists print MGL.
P4_NOC = {'MNG': 'MGL'}
# Names printed differently from the entry list, by context and bib. The row takes the entry
# list's name; these are only reported.
NAME_MISPRINTS = {('MAG QUAL FX', '154'): 'Ihor DYSHYK', ('WAG EVENT VT', '226'): 'Julia WESSENHOFFER',
                  ('WAG EVENT VT', '203'): 'Dabiz ALIYEVA'}
# Bibs printed beside another athlete's name (WAG uneven bars final): the row is that athlete's,
# by the finals start list. Logged in CORRECTIONS.csv as BIB corrections, which write the bib.
BIB_MISPRINTS = {('WAG EVENT UB', '216'): '251', ('WAG EVENT UB', '206'): '214'}
# On a qualification start list but with no result and no DNS row in the book.
NO_RESULT = {('MAG', 'FX'): {'151'}, ('WAG', 'BB'): {'212'}}
# Finalists beyond the eight qualifiers: WAG beam's start list and final have nine, STOIMENOVA
# (R1 in qualification) starting first; the start list's reserves are the R2 and R3.
EXTRA_FINALISTS = {('WAG', 'BB'): {'208'}}
# The tie-break page after the MAG high bar final is titled `Tie–Break Finals PB – MAG`.
TIE_TITLE_MISPRINTS = {('MAG', 'EVENT', 'HB'): 'PB'}

NUM = r'\d+[.,]\d{3}'

def page(n):
    return BOOK[n - 1]

def num(s):
    """Values print with a decimal comma (rings qualification: a point); written with a point."""
    return s.replace(',', '.')

def penalty(s):
    """Neutral deductions (`ND`) print unsigned, `0,000` when none; written negative, or blank."""
    return '' if not s or D(num(s)) == 0 else '-' + num(s)

def read_transcription(name):
    with open(os.path.join(TRANSCRIPTIONS, name), encoding='utf-8') as f:
        return [l.rstrip('\n').split('|') for l in f if l.strip() and not l.startswith('#')]

# ---------------------------------------------------------------- finding reports
TITLE = re.compile(r'^\s*(Qualification|Apparatus Finals) (FX|PH|SR|VT|PB|HB|UB|BB) [-–] (MAG|WAG)\s*$', re.M)
TIE_TITLE = re.compile(r'^\s*Tie[-–]Break (?:Qualification|Finals?) (FX|PH|SR|VT|PB|HB|UB|BB) [-–] (MAG|WAG)\s*$', re.M)

def find_reports():
    """(disc, round, app) -> (results page, tie-break page or None). A tie-break page follows its
    table."""
    reports, last = {}, None
    for n in range(1, len(BOOK) + 1):
        if m := TITLE.search(page(n)):
            key = (m.group(3), 'QUAL' if m.group(1) == 'Qualification' else 'EVENT', m.group(2))
            if key in reports:
                err(f'p. {n}: {key} twice')
            reports[key], last = [n, None], key
        elif m := TIE_TITLE.search(page(n)):
            if last is None or n != reports[last][0] + 1 or m.group(2) != last[0]:
                err(f'p. {n}: tie-break page out of place')
                continue
            if m.group(1) != TIE_TITLE_MISPRINTS.get(last, last[2]):
                err(f'p. {n}: tie-break page for {m.group(1)} after {last}')
            reports[last][1] = n
    for disc in APPS:
        for rnd in ('QUAL', 'EVENT'):
            for app in APPS[disc]:
                if (disc, rnd, app) not in reports:
                    err(f'no results page for {disc} {rnd} {app}')
    return reports

REPORTS = find_reports()

# ---------------------------------------------------------------- participants
PARTICIPANTS = {}   # disc -> bib -> participant row

def participants():
    """Entry List by NF (pp. 7-10): `bib NOC licence SURNAME Given Function`, one discipline's
    entries mixed with the other's, by country. A hors concours entry prints its function over two
    lines around the athlete's, `MAG Gymnast` / `(Hors Concours)`."""
    rows = {'MAG': [], 'WAG': []}
    pages = [n for n in range(1, len(BOOK) + 1) if re.search(r'^\s*\d{3}\s+[A-Z]{3}\s+\d+\s', page(n), re.M)
             and not TITLE.search(page(n))]
    for n in pages:
        lines = page(n).split('\n')
        for i, l in enumerate(lines):
            m = re.match(r'^(\d{3})\s+([A-Z]{3})\s+(\d+)\s+(\S.*?)\s{2,}(\S.*?)(?:\s{2,}((?:MAG|WAG) Gymnast))?\s*$', l)
            if not m:
                if re.match(r'^\d{3}\s', l):
                    err(f'participants p. {n}: unparsed {l!r}')
                continue
            bib, noc, licence, surname, given, function = m.groups()
            disc = {'1': 'MAG', '2': 'WAG'}[bib[0]]
            hc = i + 1 < len(lines) and '(Hors Concours)' in lines[i + 1]
            if function is None:
                # The function is split over the lines above and below
                above = lines[i - 1].strip() if i else ''
                if not hc or above != f'{disc} Gymnast':
                    err(f'participants p. {n}: bib {bib} function {above!r}')
            elif function != f'{disc} Gymnast' or hc:
                err(f'participants p. {n}: bib {bib} function {function!r}')
            ev = EVENTS[PREFIX[disc]]
            rows[disc].append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                               'Event Start Date': ev['Start Date'], 'Order': len(rows[disc]) + 1, 'NOC Code': noc,
                               'Bib Number': bib, 'FIG License': licence, 'Name': f'{surname} {given}',
                               'Surname': surname, 'Given Name': given, 'Birth Year': '', 'Birth Date': '',
                               'Entry Status': 'HORS_CONCOURS' if hc else ''})
    for disc in APPS:
        out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS + ['Entry Status'], rows[disc])
        by_bib = {}
        for r in rows[disc]:
            if r['Bib Number'] in by_bib:
                err(f'{disc} participants: bib {r["Bib Number"]} twice')
            by_bib[r['Bib Number']] = r
        PARTICIPANTS[disc] = by_bib

def check_entry_counts():
    """Number of Entries by NOC (p. 4): men and women per country, with hors concours entries
    added (`6 + 4 (HC)`), and the totals."""
    printed, total = defaultdict(Counter), None
    count = r'(\d+)(?: \+ (\d+) \(HC\))?'
    for l in page(ENTRY_COUNTS_PAGE).split('\n'):
        if m := re.match(rf'^\s*([A-Z]{{3}})\s+{count}\s+{count}\s+(\d+)\s*$', l):
            noc, men, men_hc, women, women_hc, both = m.groups()
            noc = P4_NOC.get(noc, noc)
            men, women = int(men) + int(men_hc or 0), int(women) + int(women_hc or 0)
            if men + women != int(both):
                err(f'entries by NOC: {l.strip()!r} doesn\'t add up')
            printed['MAG'][noc] += men
            printed['WAG'][noc] += women
        if m := re.match(r'^\s*Total Countries – \d+\s+Total:\s+(\d+)\s+(\d+)\s+(\d+)\s*$', l):
            total = {'MAG': int(m.group(1)), 'WAG': int(m.group(2))}
    for disc in APPS:
        counted = Counter(p['NOC Code'] for p in PARTICIPANTS[disc].values())
        book = +printed[disc]
        if counted != book or total is None or sum(counted.values()) != total[disc]:
            err(f'{disc} entries by NOC: list {dict(sorted(counted.items()))} != p. 4 {dict(book)}, total {total}')

def identify(disc, ctx, bib, name, noc):
    """A row's printed `Given SURNAME` and NOC against the entry list."""
    bib = BIB_MISPRINTS.get((ctx, bib), bib)
    p = PARTICIPANTS[disc].get(bib)
    if p is None:
        err(f'{ctx}: bib {bib} not on the entry list'); return None
    entered = f'{p["Given Name"]} {p["Surname"]}'
    if noc != p['NOC Code'] or name != entered and NAME_MISPRINTS.get((ctx, bib)) != name:
        err(f'{ctx}: bib {bib} printed {name} {noc}, entered {entered} {p["NOC Code"]}')
    elif name != entered:
        print(f'  {ctx}: bib {bib} printed {name!r}, entered {entered!r}')
    return p

# ---------------------------------------------------------------- results tables
ROW = re.compile(r'^\s*(?:(\d{1,2})\s+)?(\d{3})\s+(\S.*?)\s+([A-Z]{3})((?:\s+' + NUM + r')*)\s*(Q|R\d|DNS)?\s*$')
VALUES = re.compile(r'^((?:\s+' + NUM + r')+)\s*$')
TIE = re.compile(r'^\s*(\d+)\s+(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})\s+(' + NUM + r')\s+(' + NUM + r')(?:\s+(' + NUM + r'))?\s*$')

def read_table(disc, rnd, app):
    """A results page -> athlete rows, each with the value lines that belong to it: non-vault one
    line `D E ND [B] Final`; vault the athlete's line and the attempt lines below (§5.11)."""
    ctx = f'{disc} {rnd} {app}'
    n, _ = REPORTS[(disc, rnd, app)]
    rows = []
    for l in page(n).split('\n'):
        if m := ROW.match(l):
            rank, bib, name, noc, values, mark = m.groups()
            rows.append(dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, lines=[num(values).split()],
                             Q='' if mark == 'DNS' else mark or '', dns=mark == 'DNS'))
        elif m := VALUES.match(l):
            if not rows:
                err(f'{ctx}: values before any athlete {l!r}'); continue
            rows[-1]['lines'].append(num(m.group(1)).split())
        elif re.match(r'^\s*(?:\d+\s+)?\d{3}\s', l):
            err(f'{ctx} p. {n}: unparsed {l!r}')
    # Ranked rows and DNS rows (bib at the margin), counted independently of the row pattern
    n_ids = len(re.findall(r'^\s*(?:\d{1,2}\s+)?\d{3}\s+[A-Z][a-z]', page(n), re.M))
    if n_ids != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_ids} rows')
    return rows

def read_ties(disc, rnd, app):
    _, n = REPORTS[(disc, rnd, app)]
    if n is None:
        return []
    ties = []
    for l in page(n).split('\n'):
        if m := TIE.match(l):
            ties.append(dict(zip(('Rank', 'Bib', 'Name', 'NOC', 'Total', 'E', 'D'), m.groups())))
        elif re.match(r'^\s*\d+\s+\d{3}\s', l):
            err(f'{disc} {rnd} {app} tie break p. {n}: unparsed {l!r}')
    return ties

def routine(ctx, values):
    """`D E ND [B] Final` -> the routine's values. Only MAG prints a bonus."""
    if len(values) == 4:
        d, e, nd, total = values
        b = ''
    elif len(values) == 5:
        d, e, nd, b, total = values
    else:
        err(f'{ctx}: values {values}'); return None
    return dict(D=d, E=e, ND=nd, B=b, Total=total)

def attempt(ctx, values, bonus_where, wag):
    """A vault attempt `D E ND [B] Score` (WAG qualification: `D E ND Score [B]`). MAG's bonus is in
    the attempt's score; WAG's +0.2 is the vault score's (`Combined Bonus`), on vault 2's line."""
    if len(values) == 4:
        d, e, nd, score = values
        b = ''
    elif len(values) == 5:
        d, e, nd, *rest = values
        b, score = rest if bonus_where == 'before' else rest[::-1]
    else:
        err(f'{ctx}: attempt {values}'); return None
    return dict(D=d, E=e, ND=nd, B=b if not wag else '', VB=b if wag else '', Total=score)

def vault(ctx, r, rnd, wag):
    """The vault layouts (§5.11). Returns (vault 1, vault 2 or None, printed average, max, final).
    MAG qualification: `D E ND [B] Score Avg Final` on the athlete's line, vault 2 below. Finals add
    `Max` before `Final`. WAG qualification: vault 1 on the athlete's line, `Avg Max Final` centred
    on a line of its own, then vault 2 `D E ND Score [B]`; a vaulter with one printed vault has it
    all on one line. WAG finals print as MAG's, the bonus before vault 2's score."""
    lines = r['lines']
    if wag and rnd == 'QUAL' and len(lines) == 3 and len(lines[1]) == 3:
        v1, (avg, mx, final), v2 = lines
        where = 'after'
    elif wag and rnd == 'QUAL' and len(lines) == 1:
        v1, (avg, mx, final), v2 = lines[0][:-3], lines[0][-3:], None
        where = 'after'
    elif len(lines) == 2:
        # MAG qualification prints `Avg Final`, finals `Avg Max Final`
        tail = 2 if rnd == 'QUAL' else 3
        v1, rest, v2 = lines[0][:-tail], lines[0][-tail:], lines[1]
        (avg, final), mx = (rest, None) if tail == 2 else ((rest[0], rest[2]), rest[1])
        where = 'before'
    else:
        err(f'{ctx}: bib {r["Bib"]} lines {lines}'); return None
    a1 = attempt(f'{ctx} bib {r["Bib"]} vault 1', v1, where, wag)
    a2 = attempt(f'{ctx} bib {r["Bib"]} vault 2', v2, where, wag) if v2 is not None else None
    if a1 and a1['VB']:
        err(f'{ctx}: bib {r["Bib"]} a vault bonus on vault 1')
    return a1, a2, avg, mx, final

def check_vault_printed(ctx, r, rnd, wag, a1, a2, avg, mx, final):
    """The printed average, maximum and final against the attempts. WAG qualification's `Avg`
    leaves the bonus out and its `Final` adds it; elsewhere `Avg` is the final."""
    c = f'{ctx} bib {r["Bib"]}'
    if a2 is None:
        return
    vb = a2['VB']
    checks.check_vault_average(c, a1['Total'], a2['Total'], vb, final)
    if wag and rnd == 'QUAL':
        checks.check_vault_average(c, a1['Total'], a2['Total'], '', avg)
    elif avg != final:
        err(f'{c}: average {avg} != final {final}')
    if mx is not None and D(mx) != max(D(a1['Total']), D(a2['Total'])):
        err(f'{c}: max {mx} isn\'t the higher vault')

def tie_key(r, app):
    """Equal totals are ranked on E, then D (MAG floor qualification: TOURNICOURT over MOLNAR on E;
    BOURDET and ZAVORY equal on both, sharing 5th). Vault: the higher vault."""
    if app == 'VT':
        return (max(D(r['Total1'] or 0), D(r['Total2'] or 0)),)
    return (D(r['E']), D(r['D']))

def check_ties(ctx, rows, ties, app):
    """Equal totals are ordered by the tie-break key, and equal on all of it share a rank. A
    tie-break page, where one is printed, lists every tied athlete with the table's rank, total, E
    (and D where E is equal)."""
    groups = defaultdict(list)
    for r in rows:
        if r['Rank']:
            groups[r['Total']].append(r)
    for group in groups.values():
        for a, b in zip(group, group[1:]):
            ka, kb = tie_key(a, app), tie_key(b, app)
            if ka < kb or (ka == kb) != (a['Rank'] == b['Rank']):
                err(f'{ctx}: tie {a["Bib"]} / {b["Bib"]} ranked {a["Rank"]} / {b["Rank"]} on {ka} / {kb}')
    if not ties:
        return
    by_bib = {r['Bib']: r for r in rows}
    tied = [r['Bib'] for r in rows if r['Rank'] and len(groups[r['Total']]) > 1]
    if [t['Bib'] for t in ties] != tied:
        err(f'{ctx} tie break: lists {[t["Bib"] for t in ties]}, tied {tied}')
    for t in ties:
        r = by_bib.get(t['Bib'])
        if r is None or (t['Rank'], num(t['Total']), num(t['E'])) != (r['Rank'], r['Total'], r['E']) \
                or t['D'] and num(t['D']) != r['D']:
            err(f'{ctx} tie break: bib {t["Bib"]} {t} differs from the table')

def vault_attempt(n, v, wag):
    if v is None:
        # Not printed; any value comes from CORRECTIONS.csv
        return {f'Status{n}': '', f'D{n}': '', f'E{n}': '', f'B{n}': '', f'Penalty{n}': '', f'SJ Penalty{n}': '',
                f'Total{n}': ''}
    if v == 'DNS':
        return {f'Status{n}': 'DNS', f'D{n}': '', f'E{n}': '', f'B{n}': '', f'Penalty{n}': '', f'SJ Penalty{n}': '',
                f'Total{n}': ''}
    invalid = D(v['Total']) == 0
    return {f'Status{n}': 'INVALID_VAULT' if invalid else 'COMPLETED', f'D{n}': v['D'], f'E{n}': v['E'],
            f'B{n}': v['B'], f'Penalty{n}': penalty(v['ND']), f'SJ Penalty{n}': '', f'Total{n}': v['Total']}

def check_written(ctx, rows, app):
    """Arithmetic on the rows as written, after corrections: each routine's parts add up to its
    score, and a two-vault total is the average plus any combined bonus."""
    for r in rows:
        c = f'{ctx} bib {r["Bib"]}'
        if app != 'VT':
            if r['Status'] != 'DNS':
                checks.check_sum(c, r['Total'], r['D'], r['E'], r['B'], r['Penalty'])
            continue
        for n in (1, 2):
            if r[f'Status{n}'] in ('COMPLETED', 'INVALID_VAULT'):
                checks.check_sum(f'{c} vault {n}', r[f'Total{n}'], r[f'D{n}'], r[f'E{n}'], r[f'B{n}'], r[f'Penalty{n}'])
            elif r[f'Status{n}'] != 'DNS':
                err(f'{c}: vault {n} status {r[f"Status{n}"]!r}')
        if r['Status2'] == 'COMPLETED':
            checks.check_vault_average(c, r['Total1'], r['Total2'], r['Combined Bonus'], r['Total'])
        elif r['Total'] or r['Rank']:
            err(f'{c}: a ranked vault row without two vaults')

COMPETED = defaultdict(set)   # (disc, app) -> bibs with a qualification routine
DNS = defaultdict(set)        # (disc, app) -> bibs with a qualification DNS row

def results(disc, rnd, app):
    ctx = f'{disc} {rnd} {app}'
    wag = disc == 'WAG'
    qual = rnd == 'QUAL'
    rows = read_table(disc, rnd, app)
    written = []
    for r in rows:
        p = identify(disc, ctx, r['Bib'], r['Name'], r['NOC'])
        if p is None:
            continue
        if r['Q'] and not qual:
            err(f'{ctx}: bib {r["Bib"]} marker {r["Q"]} on a final')
        if qual:
            (DNS if r['dns'] else COMPETED)[(disc, app)].add(p['Bib Number'])
        row = {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
               'Competition Start Date': DATES[rnd][DAY[disc][app]], 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app,
               'Rank': r['Rank'], 'Bib': r['Bib'], 'Name': p['Name'], 'NOC Code': p['NOC Code']}
        if r['dns']:
            if r['Rank'] or r['lines'] != [[]]:
                err(f'{ctx}: bib {r["Bib"]} a DNS row with values')
            if app == 'VT':
                row |= vault_attempt(1, 'DNS', wag) | vault_attempt(2, 'DNS', wag) | {'Combined Bonus': '', 'Total': ''}
            else:
                row |= {'Status': 'DNS', 'D': '', 'E': '', 'B': '', 'Penalty': '', 'SJ Penalty': '', 'Total': ''}
        elif app == 'VT':
            got = vault(ctx, r, rnd, wag)
            if got is None or got[0] is None:
                continue
            a1, a2, avg, mx, final = got
            check_vault_printed(ctx, r, rnd, wag, a1, a2, avg, mx, final)
            row |= vault_attempt(1, a1, wag) | vault_attempt(2, a2, wag)
            row |= {'Combined Bonus': a2['VB'] if a2 else '', 'Total': final}
        else:
            if len(r['lines']) != 1:
                err(f'{ctx}: bib {r["Bib"]} lines {r["lines"]}')
            v = routine(f'{ctx} bib {r["Bib"]}', r['lines'][0])
            if v is None:
                continue
            if wag and v['B']:
                err(f'{ctx}: bib {r["Bib"]} a WAG bonus')
            row |= {'Status': 'COMPLETED', 'D': v['D'], 'E': v['E'], 'B': v['B'], 'Penalty': penalty(v['ND']),
                    'SJ Penalty': '', 'Total': v['Total']}
        if qual:
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        written.append(row)
    checks.check_rank_order(ctx, written)
    check_ties(ctx, written, read_ties(disc, rnd, app), app)
    out.csv(f'{PREFIX[disc]}-SCORES-{common.COMPETITION[rnd]}-{app}.csv', common.score_header(app == 'VT', qual), written)
    check_written(ctx, written, app)
    for row in written:
        if PARTICIPANTS[disc][row['Bib']]['Name'] != row['Name']:
            err(f'{ctx}: bib {row["Bib"]} written beside {row["Name"]}')
    return written

# ---------------------------------------------------------------- qualifiers, finals, start lists
def check_qualifiers(disc, app, rows):
    """Q on the top eight, at most two per country (no `NR` printed), then three reserves."""
    expected, per_noc, q, reserves = {}, Counter(), 0, 0
    for r in rows:
        if not r['Rank'] or per_noc[r['NOC Code']] >= 2 and q < 8:
            continue
        if q < 8:
            expected[r['Bib']] = 'Q'
            per_noc[r['NOC Code']] += 1
            q += 1
        elif reserves < 3:
            reserves += 1
            expected[r['Bib']] = f'R{reserves}'
    printed = {r['Bib']: r['Qualification'] for r in rows if r['Qualification']}
    if printed != expected:
        err(f'{disc} QUAL {app}: markers {printed}, expected {expected}')

def finals_start_lists():
    lists = {}
    for disc, app, starters, reserves in read_transcription('FINALS-START-LISTS.txt'):
        lists[(disc, app)] = (starters.split(','), reserves.split(','))
    return lists

def check_final(disc, app, qual_rows, final_rows, start_list):
    """The final's athletes are its start list's starters: the eight qualifiers, plus any known
    extra finalist. The start list's reserves are the R-marked athletes not starting, in order."""
    starters, reserves = start_list
    finalists = {r['Bib'] for r in final_rows}
    qualified = {r['Bib'] for r in qual_rows if r['Qualification'] == 'Q'}
    extra = EXTRA_FINALISTS.get((disc, app), set())
    if finalists != set(starters) or finalists != qualified | extra or len(starters) != 8 + len(extra):
        err(f'{disc} EVENT {app}: finalists {sorted(finalists)}, start list {sorted(starters)}, qualified {sorted(qualified)}')
    marked = [r['Bib'] for r in qual_rows if r['Qualification'].startswith('R') and r['Bib'] not in finalists]
    if reserves != marked:
        err(f'{disc} EVENT {app}: start list reserves {reserves}, marked {marked}')
    if extra:
        print(f'  {disc} EVENT {app}: {sorted(extra)} started beyond the eight qualifiers')

def check_qual_start_lists(disc):
    """Every qualification routine is on the start list for that apparatus, and those listed without
    a result are hors concours or the known NO_RESULT athletes. Names and the `(HC)` marker are
    checked against the entry list."""
    listed = defaultdict(set)
    for app, group, noc, bib, name in read_transcription(f'{disc}-START-QUAL.txt'):
        p = PARTICIPANTS[disc].get(bib)
        hc = name.endswith(' (HC)')
        name = name.removesuffix(' (HC)')
        if p is None or (noc, name.upper()) != (p['NOC Code'], p['Name'].upper()) \
                or hc != (p['Entry Status'] == 'HORS_CONCOURS'):
            err(f'{disc} start list {app} group {group}: bib {bib} {noc} {name}, entered {p and p["Name"]}')
        listed[app].add(bib)
    hors_concours = {b for b, p in PARTICIPANTS[disc].items() if p['Entry Status'] == 'HORS_CONCOURS'}
    for app in APPS[disc]:
        missing = (COMPETED[(disc, app)] | DNS[(disc, app)]) - listed[app]
        extra = listed[app] - COMPETED[(disc, app)] - DNS[(disc, app)] - hors_concours
        if missing or extra != NO_RESULT.get((disc, app), set()):
            err(f'{disc} QUAL {app} start list: not listed {sorted(missing)}, listed without a result {sorted(extra)}')
        if listed[app] & hors_concours:
            print(f'  {disc} QUAL {app}: hors concours {sorted(listed[app] & hors_concours)} on the start list, '
                  f'no result printed')
    if hors_concours - set().union(*listed.values()):
        err(f'{disc}: hors concours {sorted(hors_concours - set().union(*listed.values()))} on no start list')

def check_medallists(finals):
    """Medallists are printed on p. 5 and after each final; both against the final's ranks (a
    cross-check only, §3.9: printed, not failed). Names wrap, so each medal's NOC is compared and
    the medallist's surname looked for near it."""
    for (disc, app), rows in finals.items():
        podium = [r for r in sorted(rows, key=lambda r: int(r['Rank'] or 99)) if r['Rank'] in ('1', '2', '3')]
        n = REPORTS[(disc, 'EVENT', app)][1] or REPORTS[(disc, 'EVENT', app)][0]
        n += 1
        text = page(n)
        if 'MEDALISTS' not in text:
            err(f'{disc} {app}: no medallists page at p. {n}'); continue
        nocs = re.findall(r'(?:GOLD|SILVER|BRONZE) MEDAL.*?([A-Z]{3})\s*$', text, re.M)
        names = [r['Surname'] for r in (PARTICIPANTS[disc][p['Bib']] for p in podium)]
        if sorted(nocs) != sorted(p['NOC Code'] for p in podium) or any(s not in text for s in names):
            print(f'  medallists {disc} {app} (p. {n}): printed {nocs}, final {[(s, p["NOC Code"]) for s, p in zip(names, podium)]}')
    by_event = page(MEDALLISTS_PAGE)
    for (disc, app), rows in finals.items():
        podium = [PARTICIPANTS[disc][r['Bib']]['Surname'] for r in rows if r['Rank'] in ('1', '2', '3')]
        missing = [s for s in podium if s not in by_event]
        if missing:
            print(f'  medallists {disc} {app} (p. 5): {missing} not printed')

# ---------------------------------------------------------------- judges
FUNCTIONS = {'Line Judge': 'L', 'Time Judge': 'T', 'Line Judge 1': 'L1', 'Line Judge 2': 'L2'}

def judges(disc, rnd):
    """Judging assignments (transcribed): the Technical Delegate (`TD`, no NOC), panels `D1 D2 E1-E5`
    plus time and line judges, and WAG's round reserves. `Time Judge` printed twice on a panel (beam)
    is `T1`, `T2`."""
    ev = EVENTS[PREFIX[disc]]
    base = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
            'Competition': common.COMPETITION[rnd]}
    rows, panels = [], defaultdict(list)
    for app, func, name, noc in read_transcription(f'{disc}-JUDGES-{rnd}.txt'):
        if app != '-' and app not in APPS[disc]:
            err(f'{disc} {rnd} judges: apparatus {app}')
        if app != '-':
            panels[app].append(func)
        # Judges print `SURNAME Given`; the WAG Technical Delegate, from the cover, `Given SURNAME`
        split = common.split_surname_first if name.split()[0].isupper() else common.split_given_first
        surname, given = split(name)
        rows.append(base | {'Apparatus': '' if app == '-' else app, 'Function': FUNCTIONS.get(func, func),
                            'Name': name, 'Surname': surname, 'Given Name': given, 'NOC Code': noc})
    for app in APPS[disc]:
        timers = [r for r in rows if r['Apparatus'] == app and r['Function'] == 'T']
        if len(timers) == 2:
            timers[0]['Function'], timers[1]['Function'] = 'T1', 'T2'
        if panels[app][:7] != ['D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5']:
            err(f'{disc} {rnd} {app}: panel {panels[app]}')
    if [r['Function'] for r in rows].count('TD') != 1:
        err(f'{disc} {rnd} judges: technical delegate')
    for r in rows:
        if not r['Surname'] or not r['Given Name']:
            err(f'{disc} {rnd} judges: {r["Name"]!r} doesn\'t split')
        if not re.fullmatch(r'TD|D[12]|E[1-5]|[TL][12]?|R\d', r['Function']):
            err(f'{disc} {rnd} judges: function {r["Function"]}')
    return rows

# ---------------------------------------------------------------- run
participants()
starts = finals_start_lists()
finals = {}
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    rounds = ('QUAL',) if disc == 'MAG' else ('QUAL', 'EVENT')   # no MAG finals judges page
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, [r for rnd in rounds for r in judges(disc, rnd)])
    for app in APPS[disc]:
        q = results(disc, 'QUAL', app)
        check_qualifiers(disc, app, q)
        finals[(disc, app)] = results(disc, 'EVENT', app)
        check_final(disc, app, q, finals[(disc, app)], starts[(disc, app)])
    check_qual_start_lists(disc)
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])
check_entry_counts()
check_medallists(finals)

corrections.finish()
checks.finish()
