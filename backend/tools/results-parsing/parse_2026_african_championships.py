"""Parse the 2026 Senior African Championships results book into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_african_championships.py \\
        data/2026/2026-AFRICAN-CHAMPIONSHIPS/18377-ResultsbookMedia.pdf

Writes PARTICIPANTS, JUDGES, SCORES-QUAL-*, SCORES-EVENT-*, SUMMARY-QUAL-TEAM, SUMMARY-QUAL-AA and an
IMPORT.json for MAG SR and WAG SR next to the PDF, reading event metadata from the EVENT.csv already
there. Exits non-zero if any check fails (docs/instructions-results-parsing.md §3; this source
format is §5.15).

The organizer's media book, laid out in CorelDRAW: the schedule, entry counts and entry list have
text, but every results page is text converted to outlines (or, for the judges, a photograph), so
it has no text layer. Those pages were read with OCR and checked by eye into
`transcriptions/2026-AFRICAN-CHAMPIONSHIPS/` (format in the README there); this parser reads them
and checks every report against the others. Qualification decides the team and all-around titles
(no team or all-around final); the top eight per apparatus, two per country, go to the finals.
"""
import os, re, sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-AFRICAN-CHAMPIONSHIPS'
TRANSCRIPTIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transcriptions', EVENT_PREFIX)
PAGES = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err

PREFIX = {d: f'{EVENT_PREFIX}-{d}-SR' for d in ('MAG', 'WAG')}
EVENT_NAME = EVENTS[PREFIX['MAG']]['Title']
EVENT_START = EVENTS[PREFIX['MAG']]['Start Date']
if any(EVENTS[p]['Title'] != EVENT_NAME or EVENTS[p]['Start Date'] != EVENT_START for p in PREFIX.values()):
    raise SystemExit('MAG and WAG rows in EVENT.csv are expected to share a title and start date')
AGE = 'SR'
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err)
out = common.Output(OUT, corrections)
# The book's apparatus order (all-around and team reports), and the SUMMARY column order.
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
# From the Competition Schedule (pp. 2-3): senior qualification, which decides the team and
# all-around titles, on Thu 23 April; finals day 1 on Sat 25 April (MAG FX/PH/SR, WAG VT/UB),
# day 2 on Sun 26 April (MAG VT/PB/HB, WAG BB/FX). The tables' footers print the same dates.
QUAL_DATE = '2026-04-23'
FINAL_DATE = {'MAG': {'FX': '2026-04-25', 'PH': '2026-04-25', 'SR': '2026-04-25',
                      'VT': '2026-04-26', 'PB': '2026-04-26', 'HB': '2026-04-26'},
              'WAG': {'VT': '2026-04-25', 'UB': '2026-04-25', 'BB': '2026-04-26', 'FX': '2026-04-26'}}
# The team reports print the country's name.
COUNTRY = {'Algeria': 'ALG', 'Cameroon': 'CMR', 'Egypt': 'EGY', 'Namibia': 'NAM', 'Senegal': 'SEN',
           'South Africa': 'RSA'}
# The "Number of Entries by NOC" page (p. 4) disagrees with the entry list for WAG: it counts one
# Namibian (the list has five, all of whom competed) and three Senegalese (two), 26 in all (29).
# It prints Zimbabwe as ZIM, where the entry list and results print ZWE (written ZIM, a correction).
COUNT_PAGE_SLIPS = {'WAG': {'NAM': (1, 5), 'SEN': (3, 2)}}
COUNT_PAGE_CODES = {'ZIM': 'ZWE'}
# Results print one athlete's given name differently from the entry list (HANDURA Nagaititue).
PRINTED_NAMES = {'131': 'Ngaititue'}
# Namibia's fifth WAG entry (HANDURA, born 2010) is not on its team page: an individual.
INDIVIDUALS = {'131'}
# The WAG uneven bars final prints a Q beside every finalist, a leftover of the qualification layout.
FINAL_MARKS = {('WAG', 'UB')}

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

def entry_counts():
    """p. 4, `No. Country NOC MAG WAG Total`, a blank where a country entered none."""
    counts = {'MAG': {}, 'WAG': {}}
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
        if cells.get('MAG', 0) + cells.get('WAG', 0) != cells.get('Total'):
            err(f'entry counts {m.group(1)}: {cells}')
        for disc in ('MAG', 'WAG'):
            if cells.get(disc):
                counts[disc][COUNT_PAGE_CODES.get(m.group(1), m.group(1))] = cells[disc]
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

def participants():
    """p. 5, "Entries List by NOC": `# NOC SURNAME Given Discipline FIG-ID BIB dd/mm/yyyy`."""
    rows = {'MAG': [], 'WAG': []}
    counts = {'MAG': {}, 'WAG': {}}
    for l in PAGES[4].splitlines():
        m = re.fullmatch(r'\s*(\d+)\s+([A-Z]{3})\s+(.+?)\s+(MAG|WAG)\s+(\d+)\s+(\d{3})\s+([\d/]+)\s*', l)
        if not m:
            if re.match(r'\s*\d+\s+[A-Z]{3}\s', l):
                err(f'participants: unparsed line {l!r}')
            continue
        order, noc, name, disc, lic, bib, born = m.groups()
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
        for noc, (page, listed) in COUNT_PAGE_SLIPS.get(disc, {}).items():
            if want.get(noc) != page:
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
    panels are headed by `AS` (apparatus supervisor), written `SV`; WAG's `SUPERIOR JURY <n>` is
    written `Member`."""
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
                         'Event Start Date': EVENT_START, 'Round': rnd, 'Apparatus': app, 'Function': fn,
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
            'Session Start Date': QUAL_DATE if rnd == 'QUAL' else FINAL_DATE[disc][app], 'Round': rnd, 'Part': '',
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
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part', 'Rank', 'Bib', 'Name',
           'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for a in aa.values():
        r = {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE, 'Event Start Date': EVENT_START,
             'Round': 'QUAL', 'Part': '', 'Rank': a['rank'], 'Bib': a['bib'], 'Name': PEOPLE[a['bib']]['name'],
             'NOC Code': PEOPLE[a['bib']]['noc'], 'SJ Penalty': '', 'Total': a['Total'], 'Qualification': ''}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = a['apps'].get(app, {}).get('Total', '')
        rows.append(r)
    out.csv(f'{PREFIX[disc]}-SUMMARY-QUAL-AA.csv', hdr, rows)

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
             'Round': 'QUAL', 'Part': '', 'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': '',
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
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part', 'Rank', 'NOC Code'] + \
          [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    out.csv(f'{PREFIX[disc]}-SUMMARY-QUAL-TEAM.csv', hdr, rows)

# ---------------------------------------------------------------- apparatus tables
def table(disc, rnd, app):
    """Non-vault: `rank|bib|SURNAME Given|NOC|D|E|PEN|BONUS|Total|mark` (WAG prints no BONUS column:
    blank). Vault: `rank|bib|SURNAME Given|NOC|D|E|PEN|Score|Total|mark` for vault 1, then
    `V2|D|E|PEN|Score|Bonus` or `V2|DNS`; Total is the two-vault result, `DNF`, or blank for one
    vault. Marks: `Q`, `R` as printed."""
    name = f'{disc}-{rnd}-{app}.txt'
    rows, cur = [], None
    for n, f in read(name):
        ctx = f'{name}:{n}'
        if f[0] == 'V2':
            if cur is None or 'v2' in cur or app != 'VT':
                err(f'{ctx}: vault 2 out of place'); continue
            if f[1:] == ['DNS']:
                cur['v2'] = 'DNS'
            elif len(f) == 6:
                cur['v2'] = routine(f'{ctx} bib {cur["bib"]} vault 2', f[1], f[2], f[3], '', f[4])
                cur['vb'] = f[5]
                if f[5] not in ('', '0.200') or f[5] and disc != 'WAG':
                    err(f'{ctx}: vault bonus {f[5]!r}')
            else:
                err(f'{ctx}: vault 2 {f}')
            continue
        if len(f) != 10 or not re.fullmatch(r'\d*', f[0]) or not re.fullmatch(r'\d{3}', f[1]):
            err(f'{ctx}: athlete line {f}'); cur = None; continue
        rank, bib, nm, noc, d, e, pen, x, total, mk = f
        check_identity(ctx, bib, nm, noc, disc)
        if rnd == 'EVENT' and (disc, app) in FINAL_MARKS and mk == 'Q':
            mk = ''
        if mk not in ('', 'Q', 'R') or mk and rnd != 'QUAL':
            err(f'{ctx}: mark {mk!r}')
        if app == 'VT':
            cur = dict(rank=rank, bib=bib, mk=mk, v1=routine(f'{ctx} bib {bib} vault 1', d, e, pen, '', x),
                       total=total)
        else:
            if x and disc == 'WAG':
                err(f'{ctx}: WAG bonus {x!r}')
            cur = dict(rank=rank, bib=bib, mk=mk, g=routine(f'{ctx} bib {bib}', d, e, pen, x, total), total=total)
        rows.append(cur)
    if len({r['bib'] for r in rows}) != len(rows):
        err(f'{name}: a bib listed twice')
    for r in rows:
        if app != 'VT':
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
    out.csv(f'{PREFIX[disc]}-SCORES-QUAL-{app}.csv', common.score_header(app == 'VT', True), out_rows)
    return marks, {r['bib']: r for r in rows}

def final(disc, app, marks, starts):
    rows = table(disc, 'EVENT', app)
    ctx = f'{disc} EVENT {app}'
    out_rows = []
    for r in rows:
        if app == 'VT':
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
    out.csv(f'{PREFIX[disc]}-SCORES-EVENT-{app}.csv', common.score_header(app == 'VT', False), out_rows)

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
    higher vault). Checked against the tables: same rank and total, and the deciding values order
    the tied athletes."""
    pairs = {}
    for n, f in read(f'{disc}-TIE-BREAKS.txt'):
        ctx = f'{disc}-TIE-BREAKS.txt:{n}'
        vault = f[0] == 'VT'
        if f[0] not in tables or len(f) != (9 if vault else 8):
            err(f'{ctx}: {f}'); continue
        app, rank, bib, nm, noc, total = f[:6]
        check_identity(ctx, bib, nm, noc, disc)
        r = tables[app].get(bib)
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
        if len(tied) < 2 or any(a[1] <= b[1] for a, b in zip(tied, tied[1:])):
            err(f'{disc} tie break {app} {total}: {tied}')
    # Every equal total in a qualification ranking has its tie-break
    for app, rows in tables.items():
        totals = [D(r['total']) for r in rows.values() if r['rank']]
        tied = {t for t in totals if totals.count(t) > 1}
        if tied != {D(t) for a, t in pairs if a == app}:
            err(f'{disc} {app}: tied totals {sorted(tied)} vs tie-break pages')

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
        final(disc, app, marks, starts)
    tie_breaks(disc, tables)
    for app in APPS[disc]:
        performed = sum(app in a['apps'] for a in aa.values())
        print(f'  {disc} {app}: {performed} routines in qualification')

for disc in ('MAG', 'WAG'):
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])
corrections.finish()
checks.finish()
