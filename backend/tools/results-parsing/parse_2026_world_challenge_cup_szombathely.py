"""Parse the 2026 World Challenge Cup Szombathely results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_world_challenge_cup_szombathely.py \\
        data/2026/2026-WORLD-CHALLENGE-CUP-SZOMBATHELY/18241-ResultsbookMedia.pdf

Writes PARTICIPANTS / JUDGES / SCORES-C1-<APP> / SCORES-C3-<APP> CSVs and an IMPORT.json
per discipline next to the PDF, reading event metadata from the EVENT.csv already there and
applying the event's CORRECTIONS.csv. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.13).

The Hungarian Federation's media book, typed in Excel: every page has text and no report codes.
A Competition Schedule (p. 2), entry counts by NOC (p. 3), medallists and medal standings
(pp. 4-5), then per discipline the Entry List by Bib Number, a qualification start list per
apparatus, the qualification judges, the qualification tables (`MAG - Qualification`, no
apparatus printed: they come in the schedule's apparatus order), a Tie Break Report per table with
equal totals, the List of Qualifiers, the finals Start List, the finals judges, the finals, a
finals tie-break and a Medalists page per final.
"""
import os, re, sys
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-WORLD-CHALLENGE-CUP-SZOMBATHELY'
PREFIX = {disc: f'{EVENT_PREFIX}-{disc}-SR' for disc in ('MAG', 'WAG')}

BOOK = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err)
out = common.Output(OUT, corrections)

APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
APP_NAMES = {'Floor Exercise': 'FX', 'Pommel Horse': 'PH', 'Rings': 'SR', 'Vault': 'VT', 'Parallel Bars': 'PB',
             'Horizontal Bar': 'HB', 'Uneven Bars': 'UB', 'Balance Beam': 'BB', 'Beam': 'BB', 'Floor': 'FX'}
APP_RE = '|'.join(sorted(APP_NAMES, key=len, reverse=True))
DISC = {"Men's": 'MAG', "Women's": 'WAG', 'Men': 'MAG', 'Women': 'WAG'}
MONTHS = {'SEPT': '09', 'SEPTEMBER': '09'}

# The MAG vault qualification table is printed `1/2` and its second page is missing from the book.
# MARKO Levente (135) is on the vault start list with no row; thegymter.net's results have none either.
MISSING_PAGES = {('MAG', 'QUAL', 'VT'): 1}
# On a qualification start list but with no row in the results.
NO_RESULT = {('MAG', 'VT'): {'135'}, ('MAG', 'HB'): {'158', '159'}, ('WAG', 'UB'): {'230'}}
# A qualifier who didn't compete in the final, replaced by the first reserve; both are on the finals
# start list as printed. MAG SOUZA Caio (113) for BUTRIMAS (159) on parallel bars and BRANDENBURGER
# (153) on high bar, the day after his 2.800 in the rings final; WAG VIEUXTEMPS (208) for MAYER (226)
# on floor. The book gives no reason.
REPLACED = {('MAG', 'PB'): ('113', '159'), ('MAG', 'HB'): ('113', '153'), ('WAG', 'FX'): ('208', '226')}
# On the WAG beam start list as `KOVACS Regina (HC)`, but not on the entry list or in the entry
# counts, and no result: left out.
NOT_ENTERED = {('WAG', '224')}
# Tie Break Report values that differ from the table, where the table's add up: MAG pommel horse
# qualification KORBIEL, E `6.66` for 6.066; MAG rings final DAVIDSSON, E `7.9666` for 7.966. Reported only.
TIE_MISPRINTS = {('MAG', 'QUAL', 'PH', '156'): {'E': '6.66'}, ('MAG', 'EVENT', 'SR', '143'): {'E': '7.9666'}}
# List of Qualifiers numbering: MAG pommel horse numbers UDE (6th) `5`, after KOSKI's 5. Reported only.
ORDER_MISPRINTS = {('MAG', 'PH', '123'): '5'}
# The WAG vault finals start list prints ROPER Emily (221) at 1 and 4, and leaves out DRUSCH (248),
# who vaulted in the final; the 4 is taken as hers.
START_MISPRINTS = {('WAG', 'VT', 3): ('221', '248')}

def page(n):
    return BOOK[n - 1]

def lines_of(n):
    return page(n).split('\n')

def pages_titled(pattern):
    return [n for n in range(1, len(BOOK) + 1) if re.search(pattern, page(n), re.M)]

def schedule_date(text):
    """`FRI 18 SEPT` / `18 SEPTEMBER 2026` -> 2026-09-18."""
    m = re.search(r'(\d{1,2}) (SEPT|SEPTEMBER)\b', text)
    return f'2026-{MONTHS[m.group(2)]}-{int(m.group(1)):02d}'

# ---------------------------------------------------------------- schedule
def read_schedule():
    """Competition Schedule (p. 2): a date on each day's first line, then `start finish round
    Men's|Women's <apparatus>`. -> (disc, round, app) -> date."""
    dates, day = {}, None
    for l in lines_of(2):
        m = re.match(r'^\s*(?:([A-Z]{3} \d+ SEPT)\s+)?\d+[:.]\d\d\s+\d+[:.]\d\d\s+Apparatus (Qualifications|Final)\s+'
                     rf"(Men's|Women's) ({APP_RE})\s*$", l)
        if not m:
            if re.search(r'Apparatus (Qualifications|Final)', l):
                err(f'schedule: unparsed {l!r}')
            continue
        if m.group(1):
            day = schedule_date(m.group(1))
        key = (DISC[m.group(3)], 'QUAL' if m.group(2) == 'Qualifications' else 'EVENT', APP_NAMES[m.group(4)])
        if key in dates or day is None:
            err(f'schedule: {key} twice or undated')
        dates[key] = day
    if len(dates) != 20:
        err(f'schedule: {len(dates)} sessions')
    return dates

DATES = read_schedule()

# ---------------------------------------------------------------- participants
PARTICIPANTS = {}   # disc -> bib -> participant row
ENTRY = re.compile(r'^\s*(\d{3})\s+(\d+)\s+(\S.*?)\s{2,}([A-Z]{3})\s+(\d{4})\s*$')

def participants():
    """Entry List by Bib Number (`Men` / `Women`): `Bib Licence SURNAME Given NOC Year`."""
    for disc, label in (('MAG', 'Men'), ('WAG', 'Women')):
        ev = EVENTS[PREFIX[disc]]
        rows, n_lines = [], 0
        for n in pages_titled(rf'Entry List by Bib Number\s*\n\s*{label}\s*\n'):
            n_lines += len(re.findall(r'^\s*\d{3}\s+\d+\s', page(n), re.M))
            for l in lines_of(n):
                m = ENTRY.match(l)
                if not m:
                    if re.match(r'^\s*\d{3}\s', l):
                        err(f'{disc} participants p. {n}: unparsed {l!r}')
                    continue
                b, licence, name, noc, year = m.groups()
                surname, given = common.split_surname_first(name)
                rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                             'Event Start Date': ev['Start Date'], 'Order': len(rows) + 1, 'NOC Code': noc,
                             'Bib Number': b, 'FIG License': licence, 'Name': name, 'Surname': surname,
                             'Given Name': given, 'Birth Year': year, 'Birth Date': ''})
        if n_lines != len(rows) or not rows:
            err(f'{disc} participants: parsed {len(rows)} of {n_lines} entries')
        by_bib = {}
        for r in rows:
            if r['Bib Number'] in by_bib:
                err(f'{disc} participants: bib {r["Bib Number"]} twice')
            if not r['Surname'] or not r['Given Name']:
                err(f'{disc} participants: {r["Name"]!r} doesn\'t split')
            by_bib[r['Bib Number']] = r
        PARTICIPANTS[disc] = by_bib
        out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)

def check_entry_counts():
    """Number of Entries by NOC (p. 3): `NOC men women total`, `-` for none, and the totals."""
    printed, total = {'MAG': Counter(), 'WAG': Counter()}, None
    for l in lines_of(3):
        m = re.match(r'^\s*([A-Z]{3}|Total:)\s+(\d+|-)\s+(\d+|-)\s+(\d+)\s*$', l)
        if not m:
            continue
        men, women, both = (0 if v == '-' else int(v) for v in m.groups()[1:])
        if men + women != both:
            err(f'entries by NOC: {l.strip()!r} doesn\'t add up')
        if m.group(1) == 'Total:':
            total = {'MAG': men, 'WAG': women}
        else:
            printed['MAG'][m.group(1)] += men
            printed['WAG'][m.group(1)] += women
    for disc in APPS:
        counted = Counter(p['NOC Code'] for p in PARTICIPANTS[disc].values())
        if counted != +printed[disc] or total is None or len(PARTICIPANTS[disc]) != total[disc]:
            err(f'{disc} entries by NOC: list {dict(sorted(counted.items()))} != p. 3 {dict(printed[disc])}, total {total}')

def identify(disc, ctx, b, name, noc):
    """A row's printed `SURNAME Given` and NOC against the entry list; the row takes the entry
    list's name."""
    p = PARTICIPANTS[disc].get(b)
    if p is None:
        err(f'{ctx}: bib {b} not on the entry list'); return None
    if noc != p['NOC Code'] or name.upper() != p['Name'].upper():
        err(f'{ctx}: bib {b} printed {name!r} {noc}, entered {p["Name"]} {p["NOC Code"]}')
    return p

# ---------------------------------------------------------------- results tables
FOOTER = re.compile(r'^\s*(\d+)/(\d+)\s+(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s*$', re.M)
HEADER = re.compile(r'^\s*D\s+E\s+.*\bTotal\s*$')
ATHLETE = re.compile(r'^\s*(\d+)?\s+(\d{3})\s+(?:(\S.*?)\s+)?([A-Z]{3})((?:\s+(?:\d+\.\d+|DNF))+)(?:\s+(Q|R))?\s*$')
VALUES = re.compile(r'^\s*(?:(?:\d+\.\d+|DNS)\s*)+$')
NAME_PART = re.compile(r'^\s{5,}([A-Z][^\d]*?)\s*$')

def find_tables():
    """`MAG - Qualification` / `WAG - Final` tables, the apparatus unprinted: each table runs over
    its `k/M` pages, and the tables come in the apparatus order (MAG FX PH SR VT PB HB, WAG VT UB
    BB FX). Proven by the vault layout, the List of Qualifiers, the start lists and the tie-break
    reports."""
    runs = defaultdict(list)   # (disc, rnd) -> [[pages]]
    for n in range(1, len(BOOK) + 1):
        m = re.match(r'^\s*(MAG|WAG) - (Qualification|Final)\s*$', page(n).split('\n', 1)[0])
        if not m:
            continue
        key = (m.group(1), 'QUAL' if m.group(2) == 'Qualification' else 'EVENT')
        f = FOOTER.search(page(n))
        if not f:
            err(f'p. {n}: no page footer'); continue
        if f.group(1) == '1':
            runs[key].append([])
        elif not runs[key] or int(f.group(1)) != len(runs[key][-1]) + 1:
            err(f'p. {n}: page {f.group(1)}/{f.group(2)} out of order'); continue
        runs[key][-1].append(n)
    tables = {}
    for (disc, rnd), tabs in runs.items():
        if len(tabs) != len(APPS[disc]):
            err(f'{disc} {rnd}: {len(tabs)} tables'); continue
        for app, pages in zip(APPS[disc], tabs):
            printed = int(FOOTER.search(page(pages[0])).group(2))
            if len(pages) + MISSING_PAGES.get((disc, rnd, app), 0) != printed:
                err(f'{disc} {rnd} {app}: pages {pages} of {printed}')
            if ('V1' in page(pages[0])) != (app == 'VT'):
                err(f'{disc} {rnd} {app}: p. {pages[0]} vault layout doesn\'t fit')
            date = schedule_date(page(pages[0]).split('\n')[1])
            if date != DATES[(disc, rnd, app)]:
                err(f'{disc} {rnd} {app}: dated {date}, schedule {DATES[(disc, rnd, app)]}')
            tables[(disc, rnd, app)] = pages
    return tables

TABLES = find_tables()

def numbers(line, start=0):
    return [(m.group(), (m.start() + m.end()) / 2) for m in re.finditer(r'\d+\.\d+|DNS|DNF', line) if m.start() >= start]

def place(ctx, extras, cols, allowed):
    """One-decimal values between E and the score, each under the nearest allowed heading
    (`SB` bonus, `T` time, `L` line, `O` other penalty, `VB` vault bonus)."""
    placed = defaultdict(list)
    for v, centre in extras:
        if not re.fullmatch(r'\d+\.\d', v):
            err(f'{ctx}: value {v} where a bonus or penalty belongs'); continue
        name = min((c for c in cols if c in allowed), key=lambda c: abs(cols[c] - centre), default=None)
        if name is None or abs(cols[name] - centre) > 4:
            err(f'{ctx}: {v} under no heading ({cols})'); continue
        placed[name].append(v)
    return placed

def penalty(placed):
    """`T`, `L` and `O` print unsigned; written as one negative penalty (blank when none)."""
    pens = placed['T'] + placed['L'] + placed['O']
    if not pens:
        return ''
    return '-' + (pens[0] if len(pens) == 1 else str(sum(D(p) for p in pens)))

def routine(ctx, values, cols):
    """`D E [SB] [T] [L] [O] score`: the bonus is added and the penalties deducted in the score."""
    if len(values) < 3 or not re.fullmatch(r'\d+\.\d', values[0][0]) or not re.fullmatch(r'\d+\.\d{3}', values[1][0]) \
            or not re.fullmatch(r'\d+\.\d{3}', values[-1][0]):
        err(f'{ctx}: values {[v for v, _ in values]}'); return None
    placed = place(ctx, values[2:-1], cols, {'SB', 'T', 'L', 'O'})
    if len(placed['SB']) > 1:
        err(f'{ctx}: two bonuses')
    return dict(D=values[0][0], E=values[1][0], B=''.join(placed['SB']), Penalty=penalty(placed), Total=values[-1][0])

def read_table(ctx, pages, vault):
    """A table's pages -> rows with `Rank Bib Name NOC`, the values (vault: vault 1 on the line
    above the athlete's, vault 2 below) and the `Q`/`R` marker. A long name wraps above and below
    the athlete's line, which leaves the name blank."""
    rows, n_ids = [], 0
    for n in pages:
        cols, pending_name, items = None, [], []
        for l in lines_of(n):
            if not l.strip() or FOOTER.match(l) or re.fullmatch(r'\s*V[12]\s*', l) or l.strip() in (
                    page(n).split('\n')[0].strip(), page(n).split('\n')[1].strip()):
                continue
            if HEADER.match(l):
                cols = {m.group(): (m.start() + m.end()) / 2 for m in re.finditer(r'\S+', l)}
            elif m := ATHLETE.match(l):
                items.append(('athlete', m, l))
            elif VALUES.match(l):
                items.append(('values', l, None))
            elif m := NAME_PART.match(l):
                items.append(('name', m.group(1), None))
            else:
                err(f'{ctx} p. {n}: unparsed {l!r}')
        if cols is None:
            err(f'{ctx} p. {n}: no column heading'); continue
        n_ids += len(re.findall(r'^\s*(?:\d+\s+)?\d{3}\s+\S', page(n), re.M))
        for i, (kind, m, l) in enumerate(items):
            if kind != 'athlete':
                continue
            rank, b, name, noc, _, mark = m.groups()
            if name is None:
                # The wrapped name: the name line just above and just below
                above = items[i - 1] if i > 0 else None
                below = items[i + 1] if i + 1 < len(items) else None
                if not (above and above[0] == 'name' and below and below[0] == 'name'):
                    err(f'{ctx} p. {n}: bib {b} has no name'); continue
                name = f'{above[1]} {below[1]}'
            row = dict(Rank=rank or '', Bib=b, Name=name, NOC=noc, Q=mark or '', cols=cols,
                       values=numbers(l, m.start(5)))
            if vault:
                before = [x for x in items[:i] if x[0] != 'name']
                after = [x for x in items[i + 1:] if x[0] != 'name']
                if not before or before[-1][0] != 'values' or not after or after[0][0] != 'values':
                    err(f'{ctx} p. {n}: bib {b} without its two vault lines'); continue
                row['v1'], row['v2'] = numbers(before[-1][1]), numbers(after[0][1])
            rows.append(row)
        if vault and sum(k == 'values' for k, _, _ in items) != 2 * sum(k == 'athlete' for k, _, _ in items):
            err(f'{ctx} p. {n}: vault lines don\'t pair up')
    if n_ids != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_ids} rows')
    return rows

TIE_TITLE = re.compile(rf"^\s*(Men's|Women's) ({APP_RE}) (Qualification|Final)\s*$")
TIE = re.compile(r'^\s*(\d+)\s+(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})\s+(\d+\.\d{3})\s+(\d+\.\d+)(?:\s+(\d+\.\d))?\s*$')

def read_ties():
    """Tie Break Report pages: `Rank Bib Name NOC Total E [D]`, D only where E is equal too; vault
    prints the highest vault in place of E."""
    ties = {}
    for n in pages_titled(r'^\s*Tie Break Report\s*$'):
        m = TIE_TITLE.match(page(n).split('\n')[0])
        if not m:
            err(f'tie break p. {n}: title'); continue
        key = (DISC[m.group(1)], 'QUAL' if m.group(3) == 'Qualification' else 'EVENT', APP_NAMES[m.group(2)])
        if key in ties:
            err(f'tie break p. {n}: {key} twice')
        ties[key] = []
        for l in lines_of(n):
            if t := TIE.match(l):
                ties[key].append(dict(zip(('Rank', 'Bib', 'Name', 'NOC', 'Total', 'E', 'D'), t.groups())))
            elif re.match(r'^\s*\d+\s+\d{3}\s', l):
                err(f'tie break p. {n}: unparsed {l!r}')
    return ties

TIES = read_ties()

def tie_key(r, app):
    """Equal totals are ranked on E, then D (vault: the higher vault); equal on both, the rank is shared."""
    if app == 'VT':
        return (max(D(r['Total1']), D(r['Total2'])),)
    return (D(r['E']), D(r['D']))

def check_ties(ctx, key, rows, app):
    """Tied totals ordered by the tie-break key, sharing a rank only where the key is equal; the
    Tie Break Report lists exactly the tied athletes, with the table's values."""
    groups = defaultdict(list)
    for r in rows:
        if r['Total']:
            groups[r['Total']].append(r)
    for group in groups.values():
        for a, b in zip(group, group[1:]):
            ka, kb = tie_key(a, app), tie_key(b, app)
            if ka < kb or (ka == kb) != (a['Rank'] == b['Rank']):
                err(f'{ctx}: tie {a["Bib"]} / {b["Bib"]} ranked {a["Rank"]} / {b["Rank"]} on {ka} / {kb}')
    tied = [r['Bib'] for r in rows if r['Total'] and len(groups[r['Total']]) > 1]
    listed = TIES.get(key, [])
    if [t['Bib'] for t in listed] != tied:
        err(f'{ctx} tie break: lists {[t["Bib"] for t in listed]}, tied {tied}')
    by_bib = {r['Bib']: r for r in rows}
    for t in listed:
        r = by_bib.get(t['Bib'])
        if r is None:
            continue
        misprint = TIE_MISPRINTS.get(key + (t['Bib'],), {})
        if misprint:
            if any(t[f] != v for f, v in misprint.items()):
                err(f'{ctx} tie break: bib {t["Bib"]} misprint {misprint} not as printed')
            print(f'  {ctx} tie break: bib {t["Bib"]} printed {misprint}, table E {r.get("E")}')
            t = t | {'E': r['E']}
        e = str(tie_key(r, app)[0]) if app == 'VT' else r['E']
        same_e = sum(1 for x in groups[r['Total']] if tie_key(x, app)[0] == tie_key(r, app)[0]) > 1
        if (t['Rank'], t['NOC'], t['Total'], t['E']) != (r['Rank'], r['NOC Code'], r['Total'], e) \
                or (t['D'] or None) != (r['D'] if same_e and app != 'VT' else None) \
                or t['Name'].upper() != r['Name'].upper():
            err(f'{ctx} tie break: bib {t["Bib"]} {t} differs from the table')

def check_written(ctx, rows, app):
    """Arithmetic on the rows as written, after corrections."""
    for r in rows:
        c = f'{ctx} bib {r["Bib"]}'
        if app != 'VT':
            checks.check_sum(c, r['Total'], r['D'], r['E'], r['B'], r['Penalty'])
            continue
        for n in (1, 2):
            if r[f'Status{n}'] in ('COMPLETED', 'INVALID_VAULT'):
                checks.check_sum(f'{c} vault {n}', r[f'Total{n}'], r[f'D{n}'], r[f'E{n}'], r[f'B{n}'], r[f'Penalty{n}'])
        if r['Total']:
            checks.check_vault_average(c, r['Total1'], r['Total2'], r['Combined Bonus'], r['Total'])

COMPETED = defaultdict(set)   # (disc, app) -> bibs with a qualification row

def attempt_columns(n, status, a):
    if a is None:
        return {f'Status{n}': status, f'D{n}': '', f'E{n}': '', f'B{n}': '', f'Penalty{n}': '',
                f'SJ Penalty{n}': '', f'Total{n}': ''}
    return {f'Status{n}': 'INVALID_VAULT' if D(a['Total']) == 0 else 'COMPLETED', f'D{n}': a['D'], f'E{n}': a['E'],
            f'B{n}': a['B'], f'Penalty{n}': a['Penalty'], f'SJ Penalty{n}': '', f'Total{n}': a['Total']}

def results(disc, rnd, app):
    """A round's table -> SCORES rows."""
    ctx = f'{disc} {rnd} {app}'
    vault, qual = app == 'VT', rnd == 'QUAL'
    if (disc, rnd, app) not in TABLES:
        return []
    written, reserves = [], 0
    for r in read_table(ctx, TABLES[(disc, rnd, app)], vault):
        p = identify(disc, ctx, r['Bib'], r['Name'], r['NOC'])
        if p is None:
            continue
        if qual:
            COMPETED[(disc, app)].add(r['Bib'])
        row = {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
               'Competition Start Date': DATES[(disc, rnd, app)], 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app,
               'Rank': r['Rank'], 'Bib': r['Bib'], 'Name': p['Name'], 'NOC Code': p['NOC Code']}
        c = f'{ctx} bib {r["Bib"]}'
        if vault:
            # The athlete's line: [VB] and the vault score, or `DNF` over a vault 2 `DNS`
            placed = place(c, r['values'][:-1], r['cols'], {'VB'})
            total = r['values'][-1][0] if r['values'] else ''
            a1 = routine(f'{c} vault 1', r['v1'], r['cols'])
            if total == 'DNF':
                if [v for v, _ in r['v2']] != ['DNS'] or r['Rank'] or placed['VB']:
                    err(f'{c}: DNF row {r}')
                row |= attempt_columns(1, '', a1) | attempt_columns(2, 'DNS', None) | {'Combined Bonus': '', 'Total': ''}
            else:
                a2 = routine(f'{c} vault 2', r['v2'], r['cols'])
                if disc == 'MAG' and placed['VB'] or disc == 'WAG' and (a1 and a1['B'] or a2 and a2['B']):
                    err(f'{c}: bonus in the wrong place')
                row |= attempt_columns(1, '', a1) | attempt_columns(2, '', a2) | {
                    'Combined Bonus': ''.join(placed['VB']), 'Total': total}
        else:
            a = routine(c, r['values'], r['cols'])
            if a is None:
                continue
            if disc == 'WAG' and a['B']:
                err(f'{c}: a WAG bonus')
            row |= {'Status': 'COMPLETED', 'D': a['D'], 'E': a['E'], 'B': a['B'], 'Penalty': a['Penalty'],
                    'SJ Penalty': '', 'Total': a['Total']}
        if qual:
            # A plain `R` on the two athletes after the eight `Q`: written R1, R2 in rank order
            mark = r['Q']
            if mark == 'R':
                reserves += 1
                mark = f'R{reserves}'
            row |= {'Qualification': mark, 'Qualification Rank': r['Rank']}
        elif r['Q']:
            err(f'{c}: marker on a final')
        written.append(row)
    ranked = [r['Rank'] for r in written if r['Rank']]
    if ranked != sorted(ranked, key=int) or len(set(ranked)) + sum(1 for a, b in zip(ranked, ranked[1:]) if a == b) != len(ranked):
        err(f'{ctx}: ranks {ranked}')
    checks.check_rank_order(ctx, written)
    check_ties(ctx, (disc, rnd, app), written, app)
    out.csv(f'{PREFIX[disc]}-SCORES-{common.COMPETITION[rnd]}-{app}.csv', common.score_header(vault, qual), written)
    check_written(ctx, written, app)
    return written

# ---------------------------------------------------------------- qualifiers, finals, start lists
def check_qualifiers(disc, app, rows):
    """Q on the top eight, at most two per country (no `NR` printed), then two reserves."""
    expected, per_noc, q, reserves = {}, Counter(), 0, 0
    for r in rows:
        if not r['Rank']:
            continue
        if per_noc[r['NOC Code']] >= 2 and q < 8:
            continue
        if q < 8:
            expected[r['Bib']] = 'Q'
            per_noc[r['NOC Code']] += 1
            q += 1
        elif reserves < 2:
            reserves += 1
            expected[r['Bib']] = f'R{reserves}'
    printed = {r['Bib']: r['Qualification'] for r in rows if r['Qualification']}
    if printed != expected:
        err(f'{disc} QUAL {app}: markers {printed}, expected {expected}')

def two_column_lists(n, entry):
    """List of Qualifiers / finals Start List: blocks of two lists side by side, each under an
    apparatus heading; a long name pushes the NOC and score onto the next line. The halves split
    where the second `Qualifiing Order` / `Starting` column heading starts. -> app -> the half's
    text, read in order."""
    halves, current, split = defaultdict(str), {}, None
    for l in lines_of(n):
        heads = [(m.start(), APP_NAMES[m.group()]) for m in re.finditer(APP_RE, l)]
        if len(heads) == 2 and not re.search(r'\d', l):
            split, current = None, {'L': heads[0][1], 'R': heads[1][1]}
            continue
        if current and len(starts := [m.start() for m in re.finditer(r'Qualifiing|Starting', l)]) == 2:
            split = starts[1]
            continue
        if split is None:
            continue
        for side, text in (('L', l[:split]), ('R', l[split:])):
            halves[current[side]] += ' ' + text
    return halves

def list_of_qualifiers(disc):
    """List of Qualifiers: per apparatus `order bib Name NOC score`, orders 1-8 then R1, R2."""
    n = pages_titled(rf'^\s*{disc} Apparatus Finals\s*\n.*\n\s*List of Qualifiers')
    if len(n) != 1:
        err(f'{disc} list of qualifiers: pages {n}'); return {}
    lists = {}
    for app, text in two_column_lists(n[0], True).items():
        entries = re.findall(r'(?:^|\s)([1-8]|R[12])\s+(\d{3})\s+\S.*?\s(\d+\.\d{3})(?=\s|$)', text)
        lists[app] = entries
    return lists

def check_list_of_qualifiers(disc, app, rows, listed):
    """The List of Qualifiers names the Q athletes, numbered 1-8 in rank order (a tie for 1st is
    numbered 1 and 2), then R1, R2, with their scores."""
    marked = [r for r in rows if r['Qualification']]
    marked = [(r['Qualification'] if r['Qualification'].startswith('R') else str(i + 1), r['Bib'], r['Total'])
              for i, r in enumerate(marked)]
    expected = {b: order for order, b, _ in marked}
    got = []
    for order, b, score in listed:
        if ORDER_MISPRINTS.get((disc, app, b)) == order:
            print(f'  {disc} list of qualifiers {app}: bib {b} numbered {order} for {expected.get(b)}')
            order = expected.get(b)
        got.append((order, b, score))
    if got != marked:
        err(f'{disc} list of qualifiers {app}: {got}, table {marked}')

def finals_start_list(disc):
    """Start List: per final, the eight starters by start order, then R1, R2."""
    n = pages_titled(rf'^\s*{disc} Apparatus Finals\s*\n.*\n\s*Start List')
    if len(n) != 1:
        err(f'{disc} finals start list: pages {n}'); return {}
    lists = {}
    for app, text in two_column_lists(n[0], False).items():
        entries = re.findall(r'(?:^|\s)([1-8]|R[12])\s+(\d{3})\s', text)
        starters = [b for o, b in entries if not o.startswith('R')]
        for (d, a, i), (printed, actual) in START_MISPRINTS.items():
            if (d, a) == (disc, app):
                if starters[i] != printed:
                    err(f'{disc} finals start list {app}: misprint not as printed')
                print(f'  {disc} finals start list {app}: start {i + 1} printed {printed}, taken as {actual}')
                starters[i] = actual
        if [o for o, _ in entries] != [str(i) for i in range(1, 9)] + ['R1', 'R2']:
            err(f'{disc} finals start list {app}: {entries}')
        lists[app] = (starters, [b for o, b in entries if o.startswith('R')])
    return lists

def check_final(disc, app, qual_rows, final_rows, start_list):
    """The final's athletes are the start list's eight starters and the eight qualifiers; the start
    list's reserves are the R-marked athletes, in order."""
    starters, reserves = start_list
    finalists = {r['Bib'] for r in final_rows}
    qualified = {r['Bib'] for r in qual_rows if r['Qualification'] == 'Q'}
    if (disc, app) in REPLACED:
        absent, reserve = REPLACED[(disc, app)]
        if absent not in qualified or absent not in starters or not reserves or reserve != reserves[0]:
            err(f'{disc} EVENT {app}: replacement {absent} -> {reserve} doesn\'t fit')
        qualified = qualified - {absent} | {reserve}
        starters = [reserve if b == absent else b for b in starters]
        print(f'  {disc} EVENT {app}: qualifier {absent} didn\'t compete, reserve {reserve} did')
    if finalists != set(starters) or finalists != qualified or len(starters) != 8:
        err(f'{disc} EVENT {app}: finalists {sorted(finalists)}, start list {sorted(starters)}, qualified {sorted(qualified)}')
    marked = [r['Bib'] for r in qual_rows if r['Qualification'].startswith('R')]
    if reserves != marked:
        err(f'{disc} EVENT {app}: start list reserves {reserves}, marked {marked}')

START_ENTRY = re.compile(r'^\s*(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})(?:\s+\*)?\s*$')

def qual_start_lists():
    """`Men's Qualification / date / <apparatus> / Start List`: `Bib Name NOC`, `*` on vault (two
    vaults), `(HC)` after a hors concours name. -> (disc, app) -> bibs."""
    listed = {}
    for n in pages_titled(r'^\s*Start List\s*$'):
        head = [l.strip() for l in lines_of(n)[:4]]
        m = re.fullmatch(r"(Men's|Women's) Qualification", head[0])
        if not m or head[2] not in APP_NAMES:
            continue
        disc, app = DISC[m.group(1)], APP_NAMES[head[2]]
        if schedule_date(head[1]) != DATES[(disc, 'QUAL', app)]:
            err(f'{disc} start list {app}: dated {head[1]}')
        bibs = set()
        for l in lines_of(n):
            s = START_ENTRY.match(l)
            if not s:
                if re.match(r'^\s*\d{3}\s', l):
                    err(f'{disc} start list {app} p. {n}: unparsed {l!r}')
                continue
            b, name, noc = s.groups()
            if (disc, b) in NOT_ENTERED:
                print(f'  {disc} start list {app}: bib {b} {name} {noc}, not entered, no result')
                continue
            identify(disc, f'{disc} start list {app}', b, name, noc)
            bibs.add(b)
        listed[(disc, app)] = bibs
    return listed

def check_qual_start_lists(listed):
    """Every qualification row is on its apparatus's start list, and every athlete listed has a
    row, except the known NO_RESULT ones."""
    for disc in APPS:
        for app in APPS[disc]:
            on_list = listed.get((disc, app), set())
            missing = COMPETED[(disc, app)] - on_list
            extra = on_list - COMPETED[(disc, app)]
            if missing or extra != NO_RESULT.get((disc, app), set()):
                err(f'{disc} QUAL {app} start list: not listed {sorted(missing)}, listed without a result {sorted(extra)}')
        on_lists = set().union(*(listed.get((disc, app), set()) for app in APPS[disc]))
        if set(PARTICIPANTS[disc]) - on_lists:
            print(f'  {disc}: entered but on no start list {sorted(set(PARTICIPANTS[disc]) - on_lists)}')

MEDALS = {'GOLD': '1', 'SILVER': '2', 'BRONZE': '3'}

def check_medallists(finals):
    """Medalysts by Event (p. 4) and each final's Medalists page against the finals: a cross-check
    only (§3.9), differences printed. Their dates aren't used (p. 4 has `SAT 20 SEPT`, the final
    pages `FRI 20 SEPT`)."""
    key = None
    for l in lines_of(4):
        if m := re.match(rf"^\s*(Men's|Women's) ({APP_RE})\b", l):
            key = (DISC[m.group(1)], APP_NAMES[m.group(2)])
        if m := re.search(r'\b(GOLD|SILVER|BRONZE)\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', l):
            medal(f'medallists p. 4', finals, key, MEDALS[m.group(1)], m.group(2), m.group(3))
    for n in pages_titled(r'^\s*Medalists\s*$'):
        m = re.match(rf"^\s*(Men's|Women's) ({APP_RE})(?: Final)?\s*$", page(n).split('\n')[0])
        if not m:
            err(f'medallists p. {n}: title'); continue
        key = (DISC[m.group(1)], APP_NAMES[m.group(2)])
        for l in lines_of(n):
            if x := re.match(r'^\s*(Gold|Silver|Bronze)\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', l):
                medal(f'medallists p. {n}', finals, key, MEDALS[x.group(1).upper()], x.group(2), x.group(3))

def medal(ctx, finals, key, rank, name, noc):
    rows = [r for r in finals.get(key, []) if r['Rank'] == rank]
    if len(rows) != 1 or (rows[0]['Name'].upper(), rows[0]['NOC Code']) != (name.upper(), noc):
        err(f'{ctx} {key} {rank}: {name} {noc}, final {[(r["Name"], r["NOC Code"]) for r in rows]}')

# ---------------------------------------------------------------- judges
def judge_row(disc, rnd, app, function, name, surname, given, noc):
    ev = EVENTS[PREFIX[disc]]
    return {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
            'Competition': common.COMPETITION[rnd], 'Apparatus': app, 'Function': function, 'Name': name, 'Surname': surname,
            'Given Name': given, 'NOC Code': noc}

GRID = {'MAG': [('FX', 'PH'), ('SR', 'VT'), ('PB', 'HB')], 'WAG': [('VT', 'UB'), ('BB', 'FX')]}
FUNCTIONS = {'Time': 'T', 'Time 1': 'T1', 'Time 2': 'T2', 'Line': 'L', 'Line 1': 'L1', 'Line 2': 'L2'}
# Names end in a mixed-case given name, so a trailing three-capital word is the NOC
JUDGE = re.compile(r'^\s*(D[12]|E[1-7]|(?:Time|Line)(?: [12])?)\s+(\S.*?)(?:\s+([A-Z]{3}))?(?:\s+([A-Z]{3}))?\s*$')
# The Superior Jury, `SJ: <name> FIG`: MAG prints `Surname Given`, WAG `Given Surname`, in mixed case
SJ_SURNAME_FIRST = {'MAG': True, 'WAG': False}

def judges(disc, rnd):
    """Judges Assignments (`Men's Qualification` / `Men's Apparatus Finals`): `SJ: <name> FIG`
    (the Technical Delegate, `TD`, NOC blank), then panels two to a row in the grid MAG FX/PH,
    SR/VT, PB/HB and WAG VT/UB, BB/FX (from the time and line judges), each judge `Function SURNAME
    Given NOC`. The qualification panels for apparatus competed at the same time print the same
    judges. A long name pushes its NOC onto the next line; one WAG judge prints her NOC twice."""
    title = {'QUAL': f"{'Men' if disc == 'MAG' else 'Women'}'s Qualification",
             'EVENT': f"{'Men' if disc == 'MAG' else 'Women'}'s Apparatus Finals"}[rnd]
    n = pages_titled(rf'^\s*{title}\s*\n.*\n\s*Judges Assignments')
    if len(n) != 1:
        err(f'{disc} {rnd} judges: pages {n}'); return []
    n = n[0]
    m = re.search(r'^\s*SJ: (\S+) (\S+) FIG\s*$', page(n), re.M)
    if not m:
        err(f'{disc} {rnd} judges: no SJ'); return []
    surname, given = (m.group(1), m.group(2)) if SJ_SURNAME_FIRST[disc] else (m.group(2), m.group(1))
    rows = [judge_row(disc, rnd, '', 'TD', f'{m.group(1)} {m.group(2)}', surname.upper(), given, '')]
    block, split, waiting = -1, None, {}
    for l in lines_of(n):
        if len(re.findall(r'\bFunction\b', l)) == 2:
            block += 1
            split = [x.start() for x in re.finditer('Function', l)][1] - 3
            continue
        if split is None or not l.strip():
            continue
        for side, text in ((0, l[:split]), (1, l[split:])):
            if not text.strip() or re.fullmatch(r'\s*(Code|NOC)\s*', text):
                continue
            if re.fullmatch(r'\s*[A-Z]{3}\s*', text) and side in waiting:
                # The NOC of the name on the line above
                waiting.pop(side)['NOC Code'] = text.strip(); continue
            j = JUDGE.match(text)
            if not j:
                err(f'{disc} {rnd} judges p. {n}: unparsed {text.strip()!r}'); continue
            function, name, noc, again = j.groups()
            if again and again != noc:
                err(f'{disc} {rnd} judges p. {n}: {text.strip()!r}')
            surname, given = common.split_surname_first(name)
            row = judge_row(disc, rnd, GRID[disc][block][side], FUNCTIONS.get(function, function), name, surname,
                            given, noc or '')
            if noc is None:
                waiting[side] = row
            rows.append(row)
    for r in rows:
        if r['Apparatus'] and not r['NOC Code']:
            err(f'{disc} {rnd} judges: {r["Name"]} has no NOC')
        if not r['Surname'] or not r['Given Name']:
            err(f'{disc} {rnd} judges: {r["Name"]!r} doesn\'t split')
    for app in APPS[disc]:
        panel = [r['Function'] for r in rows if r['Apparatus'] == app]
        if panel[:7] != ['D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5']:
            err(f'{disc} {rnd} {app}: panel {panel}')
    return rows

# ---------------------------------------------------------------- run
participants()
check_entry_counts()
listed = qual_start_lists()
finals = {}
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, judges(disc, 'QUAL') + judges(disc, 'EVENT'))
    qualifiers, starts = list_of_qualifiers(disc), finals_start_list(disc)
    for app in APPS[disc]:
        q = results(disc, 'QUAL', app)
        check_qualifiers(disc, app, q)
        check_list_of_qualifiers(disc, app, q, qualifiers.get(app, []))
        finals[(disc, app)] = results(disc, 'EVENT', app)
        check_final(disc, app, q, finals[(disc, app)], starts.get(app, ([], [])))
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])
for key in TIES:
    if key not in TABLES:
        err(f'tie break for {key}: no such table')
check_qual_start_lists(listed)
check_medallists(finals)

corrections.finish()
checks.finish()
