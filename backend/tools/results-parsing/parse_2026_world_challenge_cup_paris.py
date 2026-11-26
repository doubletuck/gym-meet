"""Parse the 2026 World Challenge Cup Paris results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_world_challenge_cup_paris.py \\
        data/2026/2026-WORLD-CHALLENGE-CUP-PARIS/18305-ResultsbookMedia.pdf

Writes PARTICIPANTS / JUDGES / SCORES-C1-<APP> / SCORES-C3-<APP> CSVs and an IMPORT.json
per discipline next to the PDF, reading event metadata from the EVENT.csv already there and
applying the event's CORRECTIONS.csv if there is one. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.14).

The media book, printed by Swiss Timing in the FIG layout (§5.1): every page has text and a
`GAR…` footer code. A Competition Schedule (p. 2), entries by NOC (p. 3), medallists (pp. 4-5),
then per discipline the entry lists by NOC (`_32A`) and by bib (`_32D`), the qualification judges
(`_57A`/`_57B`), per apparatus a start list (`_51I`), the results (`_73I`; vault `_73J`, one
two-vault ranking) and a Tie Break Report (`_77A`; vault `_77B`), the List of Qualifiers
(`_53B`/`_53C`), the finals start lists (`GARG…FNL-PART1/2_51G`, both disciplines), the finals
judges, and per final a Medallists page (`_92A`), the results and any tie-break report.
"""
import os, re, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-WORLD-CHALLENGE-CUP-PARIS'
PREFIX = {disc: f'{EVENT_PREFIX}-{disc}-SR' for disc in ('MAG', 'WAG')}

BOOK = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err)
out = common.Output(OUT, corrections)

APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
APP_NAMES = {'Floor Exercise': 'FX', 'Pommel Horse': 'PH', 'Rings': 'SR', 'Vault': 'VT', 'Parallel Bars': 'PB',
             'Horizontal Bar': 'HB', 'Uneven Bars': 'UB', 'Balance Beam': 'BB'}
APP_RE = '|'.join(APP_NAMES)
DISC = {"Men's": 'MAG', "Women's": 'WAG', 'M': 'MAG', 'W': 'WAG'}
G = {'MAG': 'M', 'WAG': 'W'}
MONTHS = {m: i + 1 for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split())}
NOC = r'(?:[A-Z]{3}|WG\d)'
# Panels, List of Qualifiers blocks: icon grid, left to right then top to bottom (rendered pages)
GRID = {'MAG': [('FX', 'PH'), ('SR', 'VT'), ('PB', 'HB')], 'WAG': [('VT', 'UB'), ('BB', 'FX')]}

# Six French entries added to the entry list late (bibs after the rest), each first on the start
# list of one or two apparatus, whose results rows print bib, name and NOC only: no rank, score or
# `DNS` (the book prints `DNS` for real non-starters). The book gives no reason; they stay entries
# with no SCORES row.
NO_RESULT = {('MAG', 'FX'): {'77'}, ('MAG', 'PH'): {'80'}, ('MAG', 'SR'): {'78'}, ('MAG', 'PB'): {'80'},
             ('MAG', 'HB'): {'79'}, ('WAG', 'UB'): {'259'}, ('WAG', 'BB'): {'260'}, ('WAG', 'FX'): {'260'}}

def page(n):
    return BOOK[n - 1]

def lines_of(n):
    return page(n).split('\n')

FOOTER = re.compile(r'^(GAR\S+) 1\.0\s+Report Created ([A-Z]{3} \d+ [A-Z]{3} \d{4}) [\d:]+\s+Page (\d+)/(\d+)\s*$', re.M)

def footer(n):
    m = FOOTER.search(page(n))
    return m.groups() if m else (None, None, None, None)

def pages_coded(pattern):
    """Pages whose footer code matches `pattern`, checked to run 1/N … N/N in order."""
    found = [n for n in range(1, len(BOOK) + 1) if footer(n)[0] and re.fullmatch(pattern, footer(n)[0])]
    return found

def title(n):
    """The page's report title: the line after `Paris (FRA), …`."""
    ls = [l.strip() for l in lines_of(n) if l.strip()]
    return ls[2] if len(ls) > 2 else ''

def iso(day, mon, year='2026'):
    return f'{year}-{MONTHS[mon]:02d}-{int(day):02d}'

def page_date(n):
    """The date line under the title: `SAT 26 SEP 2026[ - Start Time hh:mm]`."""
    m = re.search(r'^\s*[A-Z]{3} (\d+) ([A-Z]{3}) 2026\b', page(n), re.M)
    return iso(m.group(1), m.group(2)) if m else None

# ---------------------------------------------------------------- schedule
def read_schedule():
    """Competition Schedule (p. 2): `SAT 26 SEP  Apparatus Qualifications` opens a day, then
    `start finish Men's|Women's <apparatus>`. -> (disc, round, app) -> (date, start time)."""
    sessions, day, rnd = {}, None, None
    if title(2) != 'Competition Schedule':
        err('p. 2 is not the Competition Schedule')
    for l in lines_of(2):
        if m := re.match(r'^\s*[A-Z]{3} (\d+) ([A-Z]{3})\s+Apparatus (Qualifications|Finals)\s*$', l):
            day, rnd = iso(m.group(1), m.group(2)), 'QUAL' if m.group(3) == 'Qualifications' else 'EVENT'
        elif m := re.match(rf"^\s*(\d\d:\d\d)\s+\d\d:\d\d\s+(Men's|Women's) ({APP_RE})\s*$", l):
            key = (DISC[m.group(2)], rnd, APP_NAMES[m.group(3)])
            if key in sessions or day is None:
                err(f'schedule: {key} twice or undated')
            sessions[key] = (day, m.group(1))
        elif re.search(r'\d\d:\d\d', l) and not FOOTER.match(l):
            err(f'schedule: unparsed {l!r}')
    if len(sessions) != 20:
        err(f'schedule: {len(sessions)} sessions')
    return sessions

SCHEDULE = read_schedule()
DATES = {k: v[0] for k, v in SCHEDULE.items()}

# ---------------------------------------------------------------- participants
PARTICIPANTS = {}   # disc -> bib -> participant row
BY_BIB = re.compile(rf'^\s*(\d{{1,3}})\s+(\d+)\s+(\S.*?)\s{{2,}}({NOC})\s+(\d{{1,2}}) ([A-Z]{{3}}) (\d{{4}})\s*$')
BY_NOC = re.compile(r'^\s*(\S.*?)\s{2,}(\d+)\s+(\d{1,3})\s+(\d{1,2}) ([A-Z]{3}) (\d{4})\s*$')

def participants():
    """Entry List by Bib Number (`_32D`): `Bib Licence SURNAME Given NOC d MON yyyy`; checked against
    the Entry List by NOC (`_32A`), which prints the same entries under `NOC - Country` headings."""
    for disc in APPS:
        ev = EVENTS[PREFIX[disc]]
        pages = pages_coded(rf'GAR{G[disc]}-+_32D')
        rows, n_lines = [], 0
        for n in pages:
            n_lines += len(re.findall(r'^\s*\d{1,3}\s+\d+\s+[A-Z]', page(n), re.M))
            for l in lines_of(n):
                m = BY_BIB.match(l)
                if not m:
                    if re.match(r'^\s*\d{1,3}\s+\d+\s+[A-Z]', l):
                        err(f'{disc} participants p. {n}: unparsed {l!r}')
                    continue
                b, licence, name, noc, d, mon, year = m.groups()
                surname, given = common.split_surname_first(name)
                rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                             'Event Start Date': ev['Start Date'], 'Order': len(rows) + 1, 'NOC Code': noc,
                             'Bib Number': b, 'FIG License': licence, 'Name': name, 'Surname': surname,
                             'Given Name': given, 'Birth Year': year, 'Birth Date': iso(d, mon, year)})
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
        # Entry List by NOC: the same entries
        listed, noc = {}, None
        for n in pages_coded(rf'GAR{G[disc]}-+_32A'):
            for l in lines_of(n):
                if m := re.match(rf'^\s*({NOC}) - \S', l):
                    noc = m.group(1)
                elif m := BY_NOC.match(l):
                    name, licence, b, d, mon, year = m.groups()
                    listed[b] = (name, licence, noc, iso(d, mon, year))
        entered = {b: (r['Name'], r['FIG License'], r['NOC Code'], r['Birth Date']) for b, r in by_bib.items()}
        if listed != entered:
            diff = {b for b in set(listed) | set(entered) if listed.get(b) != entered.get(b)}
            err(f'{disc} entry list by NOC differs from by bib: {sorted(diff)}')
        out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)

def check_entry_counts():
    """Number of Entries by NOC (p. 3): `NOC - Country  men women total`, a blank where none; each
    number under the `Men` / `Women` / `Total` heading whose right edge it shares (§2.6)."""
    if title(3) != 'Number of Entries by NOC':
        err('p. 3 is not Number of Entries by NOC'); return
    edges, printed, total = None, {'MAG': Counter(), 'WAG': Counter()}, None
    for l in lines_of(3):
        if re.fullmatch(r'\s*Men\s+Women\s+Total\s*', l):
            edges = {m.group(): m.end() for m in re.finditer(r'\S+', l)}
            continue
        m = re.match(rf'^\s*(?:({NOC}) - .*?|(Total): \d+)\s{{2,}}(\d.*?)\s*$', l)
        if not m or edges is None:
            continue
        values = {}
        for v in re.finditer(r'\d+', l[m.start(3):]):
            end = m.start(3) + v.end()
            col = min(edges, key=lambda c: abs(edges[c] - end))
            if abs(edges[col] - end) > 2 or col in values:
                err(f'entries by NOC: {l.strip()!r}'); break
            values[col] = int(v.group())
        men, women = values.get('Men', 0), values.get('Women', 0)
        if men + women != values.get('Total'):
            err(f'entries by NOC: {l.strip()!r} doesn\'t add up')
        if m.group(2):
            total = {'MAG': men, 'WAG': women}
        else:
            printed['MAG'][m.group(1)] += men
            printed['WAG'][m.group(1)] += women
    for disc in APPS:
        counted = Counter(p['NOC Code'] for p in PARTICIPANTS[disc].values())
        if counted != +printed[disc] or total is None or len(PARTICIPANTS[disc]) != total[disc]:
            err(f'{disc} entries by NOC: list {dict(sorted(counted.items()))} != p. 3 {dict(printed[disc])}, total {total}')

def identify(disc, ctx, b, name, noc):
    """A row's printed name and NOC against the entry list; the row takes the entry list's name."""
    p = PARTICIPANTS[disc].get(b)
    if p is None:
        err(f'{ctx}: bib {b} not on the entry list'); return None
    if noc != p['NOC Code'] or name != p['Name']:
        err(f'{ctx}: bib {b} printed {name!r} {noc}, entered {p["Name"]} {p["NOC Code"]}')
    return p

def by_name(disc, ctx, name, noc):
    """A finals start list reserve, printed without a bib."""
    hits = [b for b, p in PARTICIPANTS[disc].items() if (p['Name'], p['NOC Code']) == (name, noc)]
    if len(hits) != 1:
        err(f'{ctx}: {name} {noc} matches {hits}'); return None
    return hits[0]

# ---------------------------------------------------------------- results tables
def report(disc, rnd, app, suffix, heading):
    """The pages of one report, by footer code and title; checked to be numbered 1/N … N/N and
    dated as the schedule has the round."""
    rc = 'QUAL' if rnd == 'QUAL' else 'FNL'
    pages = pages_coded(rf'GAR{G[disc]}1AP{app}-+{rc}-+_{suffix}')
    pages = [n for n in pages if re.fullmatch(heading, title(n))]
    numbers = [(int(footer(n)[2]), int(footer(n)[3])) for n in pages]
    if numbers != [(i + 1, len(pages)) for i in range(len(pages))]:
        err(f'{disc} {rnd} {app} _{suffix}: pages {pages} numbered {numbers}')
    for n in pages:
        if page_date(n) != DATES[(disc, rnd, app)]:
            err(f'{disc} {rnd} {app} p. {n}: dated {page_date(n)}, schedule {DATES[(disc, rnd, app)]}')
    return pages

def app_title(disc, app):
    return f"{'Men' if disc == 'MAG' else 'Women'}'s {next(k for k, v in APP_NAMES.items() if v == app)}"

ROW = re.compile(rf'^\s*(?:(\d+)\s+)?(\d{{1,3}})\s+([A-Z]\S*(?: \S+)*?)\s{{2,}}({NOC})(?:\s+(.*?))?\s*$')
MARK = re.compile(r'^(Q|R\d)$')
SCORE = re.compile(r'\d+\.\d{3}')

def split_bp(ctx, vals):
    """Pen. and Bonus between E and the score: the sign tells them apart (§2.5)."""
    b = p = ''
    for v in vals:
        if not re.fullmatch(r'-?\d+\.\d', v):
            err(f'{ctx}: unexpected {v!r}')
        elif v.startswith('-'):
            if p:
                err(f'{ctx}: two penalties')
            p = v
        else:
            if b:
                err(f'{ctx}: two bonuses')
            b = v
    return b, p

def attempt(ctx, tokens):
    """`D E [Pen.] [Bonus] score` (a vault, or a whole routine) -> routine dict, remaining tokens."""
    if tokens[:1] == ['DNS']:
        return dict(Status='DNS', D='', E='', B='', Penalty='', Total=''), tokens[1:]
    i = 2
    while i < len(tokens) and not SCORE.fullmatch(tokens[i]):
        i += 1
    if i >= len(tokens) or not re.fullmatch(r'\d+\.\d{3}', tokens[0]) or not SCORE.fullmatch(tokens[1]):
        err(f'{ctx}: values {tokens}')
        return None, []
    b, p = split_bp(ctx, tokens[2:i])
    total = tokens[i]
    return dict(Status='INVALID_VAULT' if D(total) == 0 else 'COMPLETED', D=tokens[0], E=tokens[1], B=b,
                Penalty=p, Total=total), tokens[i + 1:]

def read_rows(ctx, pages, vault, final):
    """A results report -> rows: `[Rank] Bib Name NOC` and the values; vault: `1` and vault 1 on the
    athlete's line, `2` and vault 2 on the next. Finals end each row with Qualification Rank and
    Start Order. Rows printing nothing after the NOC have no result (NO_RESULT)."""
    rows, blank, n_ids = [], set(), 0
    ls = [l for n in pages for l in lines_of(n)]
    n_ids = sum(1 for l in ls if re.match(r'^\s*(?:\d+\s+)?\d{1,3}\s+(?!DNS\b)[A-Z]', l))
    for i, l in enumerate(ls):
        m = ROW.match(l)
        if not m or FOOTER.match(l):
            if re.match(r'^\s*(?:\d+\s+)?\d{1,3}\s+[A-Z]', l) and not (vault and re.fullmatch(r'\s*2\s+DNS\s*', l)):
                err(f'{ctx}: unparsed {l!r}')
            continue
        rank, b, name, noc, rest = m.groups()
        tokens = (rest or '').split()
        if not tokens:
            if rank:
                err(f'{ctx}: bib {b} ranked with no values')
            blank.add(b); continue
        row = dict(Rank=rank or '', Bib=b, Name=name, NOC=noc, Q='', QRank='', Start='')
        c = f'{ctx} bib {b}'
        if final and rank:
            if len(tokens) < 3 or not tokens[-1].isdigit() or not tokens[-2].isdigit():
                err(f'{c}: no qualification rank / start order {tokens}'); continue
            row['QRank'], row['Start'] = tokens[-2], tokens[-1]
            tokens = tokens[:-2]
        if tokens and MARK.match(tokens[-1]):
            row['Q'] = tokens.pop()
        if vault:
            nxt = ls[i + 1] if i + 1 < len(ls) else ''
            m2 = re.match(r'^\s*2\s+(\S.*?)\s*$', nxt)
            if tokens[:1] != ['1'] or not m2:
                err(f'{c}: vault lines {tokens} / {nxt!r}'); continue
            v1, left = attempt(f'{c} vault 1', tokens[1:])
            v2, left2 = attempt(f'{c} vault 2', m2.group(1).split())
            if v1 is None or v2 is None or left2:
                err(f'{c}: vault values {tokens} / {m2.group(1)}'); continue
            bonus = left.pop(0) if len(left) == 2 else ''
            if bonus and not re.fullmatch(r'\d\.\d', bonus) or len(left) != 1:
                err(f'{c}: vault score {left}'); continue
            row |= dict(v1=v1, v2=v2, Bonus=bonus, Total=left[0])
        else:
            if tokens == ['DNS']:
                row |= dict(Status='DNS', D='', E='', B='', Penalty='', Total='')
            else:
                a, left = attempt(c, tokens)
                if a is None or left:
                    err(f'{c}: values {tokens}'); continue
                row |= a
        rows.append(row)
    if n_ids != len(rows) + len(blank):
        err(f'{ctx}: parsed {len(rows)} rows and {len(blank)} blank of {n_ids}')
    return rows, blank

TIE = re.compile(rf'^\s*(\d+)\s+(\d{{1,3}})\s+(\S.*?)\s{{2,}}({NOC})\s+(\d+\.\d{{3}})\s+(\d+\.\d{{3}})(?: \((VT[12])\))?(?:\s+(\d+\.\d{{3}}))?(?:\s+(\d+\.\d{{1,3}}))?\s*$')

def read_ties(disc, rnd, app):
    """Tie Break Report (`_77A`; vault `_77B`): `Rank Bib Name NOC Total` and the first value that
    differs (E; vault: the higher vault and which), then the next where that is equal too."""
    pages = report(disc, rnd, app, '77B' if app == 'VT' else '77A', r'.*(Qualification|Qualifcation|Final)')
    ties = []
    for n in pages:
        for l in lines_of(n):
            if t := TIE.match(l):
                ties.append(dict(zip(('Rank', 'Bib', 'Name', 'NOC', 'Total', 'First', 'Which', 'Second', 'Third'),
                                     t.groups())))
            elif re.match(r'^\s*\d+\s+\d{1,3}\s+[A-Z]', l):
                err(f'{disc} {rnd} {app} tie break p. {n}: unparsed {l!r}')
    return ties

def tie_key(r, app):
    """Equal totals: E, then D; vault: the higher vault, then the higher E of either vault, then D.
    Equal on all, the rank is shared (the reports' printed rules)."""
    if app == 'VT':
        return (max(D(r['Total1']), D(r['Total2'])), max(D(r['E1']), D(r['E2'])), max(D(r['D1']), D(r['D2'])))
    return (D(r['E']), D(r['D']))

def check_ties(ctx, rows, app, listed):
    """Tied totals ordered by the tie-break key, sharing a rank only where the key is equal; the
    report lists exactly the tied athletes, with the table's values."""
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
    if [t['Bib'] for t in listed] != tied:
        err(f'{ctx} tie break: lists {[t["Bib"] for t in listed]}, tied {tied}')
    by_bib = {r['Bib']: r for r in rows}
    for t in listed:
        r = by_bib.get(t['Bib'])
        if r is None:
            continue
        if app == 'VT':
            which = 'VT1' if D(r['Total1']) >= D(r['Total2']) else 'VT2'
            first = (r[f'Total{which[-1]}'], which)
            got = (t['First'], t['Which'])
        else:
            first, got = (r['E'], None), (t['First'], t['Which'])
        if (t['Rank'], t['Name'], t['NOC'], t['Total']) != (r['Rank'], r['Name'], r['NOC Code'], r['Total']) \
                or got != first or t['Second'] or t['Third']:
            err(f'{ctx} tie break: bib {t["Bib"]} {t} differs from the table')

def check_written(ctx, rows, app):
    """Arithmetic on the rows as written, after corrections."""
    for r in rows:
        c = f'{ctx} bib {r["Bib"]}'
        if app != 'VT':
            if r['Status'] != 'DNS':
                checks.check_sum(c, r['Total'], r['D'], r['E'], r['B'], r['Penalty'])
            continue
        for n in (1, 2):
            if r[f'Status{n}'] in ('COMPLETED', 'INVALID_VAULT'):
                checks.check_sum(f'{c} vault {n}', r[f'Total{n}'], r[f'D{n}'], r[f'E{n}'], r[f'B{n}'], r[f'Penalty{n}'])
        if r['Total']:
            checks.check_vault_average(c, r['Total1'], r['Total2'], r['Combined Bonus'], r['Total'])

def attempt_columns(n, a):
    return {f'Status{n}': a['Status'], f'D{n}': a['D'], f'E{n}': a['E'], f'B{n}': a['B'],
            f'Penalty{n}': a['Penalty'], f'SJ Penalty{n}': '', f'Total{n}': a['Total']}

COMPETED = defaultdict(set)   # (disc, app) -> bibs with a qualification row, or a blank one
EXTRA = {}                    # (disc, rnd, app) -> bib -> (qualification rank, start order) on finals

def results(disc, rnd, app):
    """A results report -> SCORES rows."""
    ctx = f'{disc} {rnd} {app}'
    vault, qual = app == 'VT', rnd == 'QUAL'
    heading = rf"{app_title(disc, app)} {'Qualification' if qual else 'Final'}"
    pages = report(disc, rnd, app, '73J' if vault else '73I', heading)
    if not pages:
        err(f'{ctx}: no results'); return []
    rows, blank = read_rows(ctx, pages, vault, not qual)
    if blank != NO_RESULT.get((disc, app), set()) if qual else blank:
        err(f'{ctx}: rows with no result {sorted(blank)}')
    if qual:
        COMPETED[(disc, app)] |= blank
    written, EXTRA[(disc, rnd, app)] = [], {}
    for r in rows:
        p = identify(disc, ctx, r['Bib'], r['Name'], r['NOC'])
        if p is None:
            continue
        if qual:
            COMPETED[(disc, app)].add(r['Bib'])
        else:
            EXTRA[(disc, rnd, app)][r['Bib']] = (r['QRank'], r['Start'])
        row = {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
               'Competition Start Date': DATES[(disc, rnd, app)], 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app,
               'Rank': r['Rank'], 'Bib': r['Bib'], 'Name': p['Name'], 'NOC Code': p['NOC Code']}
        c = f'{ctx} bib {r["Bib"]}'
        if vault:
            v1, v2, total = r['v1'], r['v2'], r['Total']
            if total in ('DNS', 'DNF'):
                # DNS on both vaults: no result; DNF: vault 1 done, vault 2 not
                if r['Rank'] or r['Bonus'] or v2['Status'] != 'DNS' or (total == 'DNS') != (v1['Status'] == 'DNS'):
                    err(f'{c}: {total} row {r}')
                total = ''
            if disc == 'MAG' and r['Bonus'] or disc == 'WAG' and (v1['B'] or v2['B']):
                err(f'{c}: bonus in the wrong place')
            row |= attempt_columns(1, v1) | attempt_columns(2, v2) | {'Combined Bonus': r['Bonus'], 'Total': total}
        else:
            if disc == 'WAG' and r['B'] or app == 'PH' and r['B']:
                err(f'{c}: a bonus on {disc} {app}')
            row |= {k: r[k] for k in ('Status', 'D', 'E', 'B', 'Penalty')} | {'SJ Penalty': '', 'Total': r['Total']}
        if qual:
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        elif r['Q']:
            err(f'{c}: marker on a final')
        if bool(row['Total']) != bool(r['Rank']):
            err(f'{c}: rank {r["Rank"]!r} with total {row["Total"]!r}')
        written.append(row)
    ranked = [int(r['Rank']) for r in written if r['Rank']]
    if ranked != list(range(1, len(ranked) + 1)):
        # Every tie in this book is broken; a shared rank would need a look
        err(f'{ctx}: ranks {ranked}')
    checks.check_rank_order(ctx, written)
    check_ties(ctx, written, app, read_ties(disc, rnd, app))
    out.csv(f'{PREFIX[disc]}-SCORES-{common.COMPETITION[rnd]}-{app}.csv', common.score_header(vault, qual), written)
    check_written(ctx, written, app)
    return written

# ---------------------------------------------------------------- qualifiers, finals, start lists
def check_qualifiers(disc, app, rows):
    """Q on the top eight, at most two per country (no `NR` printed), then three reserves."""
    expected, per_noc, q, reserves = {}, Counter(), 0, 0
    for r in rows:
        if not r['Rank'] or per_noc[r['NOC Code']] >= 2:
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

LISTED = re.compile(rf'(?<!\S)([1-8]|R[1-3])\s*(\d{{1,3}}) ([A-Z]\S*(?: \S+)*?)\s{{2,}}({NOC})\s+(\d+\.\d{{3}})(?=\s|$)')

def list_of_qualifiers(disc):
    """List of Qualifiers (`_53B` MAG, `_53C` WAG): blocks of two lists side by side in the icon
    grid, each `order bib Name NOC score` (WAG prints the order and the bib run together, `1255`),
    orders 1-8 then R1-R3. -> app -> [(order, bib, score)]."""
    pages = pages_coded(rf'GAR{G[disc]}1AP-+FNL-+_53[BC]')
    if len(pages) != 1 or title(pages[0]) != f"{'Men' if disc == 'MAG' else 'Women'}'s Apparatus Finals":
        err(f'{disc} list of qualifiers: pages {pages}'); return {}
    lists, block, split = defaultdict(list), -1, None
    for l in lines_of(pages[0]):
        if l.startswith('Qualifying'):
            block += 1
            split = [m.start() for m in re.finditer('Qualifying', l)][1]
            continue
        if block < 0:
            continue
        for m in LISTED.finditer(l):
            app = GRID[disc][block][0 if m.start() < split - 5 else 1]
            b = m.group(2)
            identify(disc, f'{disc} list of qualifiers {app}', b, m.group(3), m.group(4))
            lists[app].append((m.group(1), b, m.group(5)))
        n = len(re.findall(rf'\s{NOC}\s+\d+\.\d{{3}}', l))
        if n != len(LISTED.findall(l)):
            err(f'{disc} list of qualifiers: unparsed {l!r}')
    if block + 1 != len(GRID[disc]):
        err(f'{disc} list of qualifiers: {block + 1} blocks')
    return lists

def check_list_of_qualifiers(disc, app, rows, listed):
    """The List of Qualifiers names the Q athletes 1-8 in rank order, then R1-R3, with their scores."""
    marked = [r for r in rows if r['Qualification']]
    marked = [(r['Qualification'] if r['Qualification'].startswith('R') else str(i + 1), r['Bib'], r['Total'])
              for i, r in enumerate(marked)]
    if listed != marked:
        err(f'{disc} list of qualifiers {app}: {listed}, table {marked}')

START = re.compile(rf'(?<!\S)(\d{{1,3}}|R[1-3])\s+([A-Z]\S*(?: \S+)*?)\s{{2,}}({NOC})(?=\s|$)')

def finals_start_lists():
    """Start List Part 1 / Part 2 (`GARG1AP…FNL-PART<n>_51G`): blocks headed `Start Time: hh:mm`,
    Men on the left, Women on the right (a block can have Men only); each final's eight starters
    by start order, then R1-R3 printed with no bib. The apparatus comes from the schedule's start
    time for that discipline. -> (disc, app) -> (starters, reserves)."""
    by_time = {(disc, t): app for (disc, rnd, app), (_, t) in SCHEDULE.items() if rnd == 'EVENT'}
    if len(by_time) != 10:
        err(f'finals: two finals share a start time')
    lists = {}
    for part in (1, 2):
        pages = pages_coded(rf'GARG1AP-+FNL-PART{part}-+_51G')
        # Printed in both disciplines' sections, the same pages: read the first copy
        if len(pages) != 4 or pages[2:] != [n for n in pages[2:] if page(n) == page(pages[pages.index(n) - 2])]:
            err(f'finals start list part {part}: pages {pages} not two identical copies')
        pages = pages[:2]
        if any(page_date(n) != '2026-09-27' for n in pages):
            err(f'finals start list part {part}: pages {pages}')
        sides = []
        for l in (l for n in pages for l in lines_of(n)):
            times = [(m.start(), m.group(1)) for m in re.finditer(r'Start Time: (\d\d:\d\d)', l)]
            if times:
                sides = []
                for pos, t in times:
                    disc = 'MAG' if pos < 40 else 'WAG'
                    app = by_time.get((disc, t))
                    if app is None:
                        err(f'finals start list: {disc} {t} not in the schedule'); continue
                    if (disc, app) in lists:
                        err(f'finals start list: {disc} {app} twice')
                    lists[(disc, app)] = ([], [])
                    sides.append((pos, disc, app))
                continue
            for m in START.finditer(l):
                pos, disc, app = [s for s in sides if s[0] <= m.start() + 6][-1]
                order, name, noc = m.groups()
                ctx = f'{disc} finals start list {app}'
                if order.startswith('R'):
                    if f'R{len(lists[(disc, app)][1]) + 1}' != order:
                        err(f'{ctx}: {order} out of order')
                    lists[(disc, app)][1].append(by_name(disc, ctx, name, noc))
                else:
                    identify(disc, ctx, order, name, noc)
                    lists[(disc, app)][0].append(order)
            if re.search(rf'\s{NOC}\s*$', l) and not START.search(l) and l.split() not in (['NOC'], ['NOC', 'NOC']):
                err(f'finals start list: unparsed {l!r}')
    return lists

def check_final(disc, app, qual_rows, final_rows, start_list):
    """The final's athletes are the start list's eight starters and the eight qualifiers, each
    final row's Start Order its place on the start list and its Qualification Rank its rank in
    qualification; the start list's reserves are the R-marked athletes, in order."""
    starters, reserves = start_list
    finalists = {r['Bib'] for r in final_rows}
    qualified = {r['Bib']: r for r in qual_rows if r['Qualification'] == 'Q'}
    if finalists != set(starters) or finalists != set(qualified) or len(starters) != 8:
        err(f'{disc} EVENT {app}: finalists {sorted(finalists)}, start list {sorted(starters)}, qualified {sorted(qualified)}')
    for b, (qrank, start) in EXTRA[(disc, 'EVENT', app)].items():
        if b in qualified and qrank != qualified[b]['Qualification Rank'] or b in starters and starters.index(b) + 1 != int(start):
            err(f'{disc} EVENT {app} bib {b}: qualification rank {qrank}, start order {start}')
    marked = [r['Bib'] for r in qual_rows if r['Qualification'].startswith('R')]
    if reserves != marked:
        err(f'{disc} EVENT {app}: start list reserves {reserves}, marked {marked}')

QUAL_START = re.compile(rf'^\s*(\d{{1,3}})\s+(\S.*?)\s{{2,}}({NOC})(\s+\*)?\s*$')

def qual_start_lists():
    """Qualification start lists (`_51I`): `Bib Name NOC`, `*` on vault (two vaults)."""
    for disc in APPS:
        for app in APPS[disc]:
            pages = report(disc, 'QUAL', app, '51I', rf"{app_title(disc, app)} Qualifications?")
            listed = set()
            for n in pages:
                for l in lines_of(n):
                    s = QUAL_START.match(l)
                    if not s:
                        if re.match(r'^\s*\d{1,3}\s+[A-Z]', l):
                            err(f'{disc} start list {app} p. {n}: unparsed {l!r}')
                        continue
                    b, name, noc, star = s.groups()
                    identify(disc, f'{disc} start list {app}', b, name, noc)
                    if bool(star) != (app == 'VT'):
                        err(f'{disc} start list {app}: bib {b} two-vault marker')
                    listed.add(b)
            if listed != COMPETED[(disc, app)]:
                err(f'{disc} QUAL {app} start list: {sorted(listed ^ COMPETED[(disc, app)])} on one side only')
        on_lists = set().union(*(COMPETED[(disc, app)] for app in APPS[disc]))
        if set(PARTICIPANTS[disc]) - on_lists:
            print(f'  {disc}: entered but on no start list {sorted(set(PARTICIPANTS[disc]) - on_lists)}')

MEDALS = {'GOLD': '1', 'SILVER': '2', 'BRONZE': '3'}

def check_medallists(finals):
    """Medallists by Event (p. 4) and each final's Medallists page (`_92A`) against the finals: a
    cross-check only (§3.9)."""
    key, seen = None, Counter()
    for l in lines_of(4):
        if m := re.match(rf"^(Men's|Women's) ({APP_RE})\s+SUN 27 SEP\b", l):
            key = (DISC[m.group(1)], APP_NAMES[m.group(2)])
        if m := re.search(rf'\b(GOLD|SILVER|BRONZE)\s+(\S.*?)\s{{2,}}({NOC})\s*$', l):
            medal('medallists p. 4', finals, key, MEDALS[m.group(1)], m.group(2), m.group(3))
            seen['p4'] += 1
    for disc in APPS:
        for app in APPS[disc]:
            pages = pages_coded(rf'GAR{G[disc]}1AP{app}-+_92A')
            if len(pages) != 1:
                err(f'{disc} {app} medallists: pages {pages}'); continue
            for l in lines_of(pages[0]):
                if m := re.match(rf'^(GOLD|SILVER|BRONZE)\s+(\S.*?)\s{{2,}}({NOC}) - ', l):
                    medal(f'medallists p. {pages[0]}', finals, (disc, app), MEDALS[m.group(1)], m.group(2), m.group(3))
                    seen[(disc, app)] += 1
    if seen['p4'] != 30 or any(v != 3 for k, v in seen.items() if k != 'p4'):
        err(f'medallists: {dict(seen)}')

def medal(ctx, finals, key, rank, name, noc):
    rows = [r for r in finals.get(key, []) if r['Rank'] == rank]
    if len(rows) != 1 or (rows[0]['Name'], rows[0]['NOC Code']) != (name, noc):
        err(f'{ctx} {key} {rank}: {name} {noc}, final {[(r["Name"], r["NOC Code"]) for r in rows]}')

# ---------------------------------------------------------------- judges
def judge_row(disc, rnd, app, function, name, noc):
    ev = EVENTS[PREFIX[disc]]
    surname, given = common.split_surname_first(name)
    if not surname or not given:
        err(f'{disc} {rnd} judges: {name!r} doesn\'t split')
    return {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
            'Competition': common.COMPETITION[rnd], 'Apparatus': app, 'Function': function, 'Name': name, 'Surname': surname,
            'Given Name': given, 'NOC Code': noc}

SUPERIOR = {'Technical Delegate': 'TD', 'Technical Delegate Assistant': 'TDA'}
JUDGE = re.compile(rf'^\s*(D[12]|E[1-7]|(?:Time|Line) Judge(?: [12])?)\s+(\S.*?)\s{{2,}}({NOC})\s*$')

def judge_function(f):
    m = re.fullmatch(r'(Time|Line) Judge(?: (\d))?', f)
    return (m.group(1)[0] + (m.group(2) or '')) if m else f

def judges(disc, rnd):
    """Judges Assignments (`_57A` MAG, `_57B` WAG): the Superior Jury (`Name  Technical Delegate`,
    `Name  Technical Delegate Assistant`, no NOC), then panels two to a row in the icon grid, each
    judge `Function SURNAME Given NOC`, split where the second `Function` heading starts; then any
    round reserves `R1`… (apparatus blank)."""
    rc = 'QUAL' if rnd == 'QUAL' else 'FNL'
    want = f"{'Men' if disc == 'MAG' else 'Women'}'s Qualifications" if rnd == 'QUAL' else 'Apparatus Finals'
    pages = [n for n in pages_coded(rf'GAR{G[disc]}1AP\w*-+{rc}-+_57[AB]') if title(n) == want]
    if len(pages) != 1:
        err(f'{disc} {rnd} judges: pages {pages}'); return []
    n = pages[0]
    rows, block, split, reserves = [], -1, None, False
    for l in lines_of(n):
        if m := re.match(r'^\s*(?:Superior Jury:)?\s+([A-Z]\S*(?: \S+)*?)\s{2,}(Technical Delegate(?: Assistant)?)\s*$', l):
            rows.append(judge_row(disc, rnd, '', SUPERIOR[m.group(2)], m.group(1), '')); continue
        if len(re.findall(r'\bFunction\b', l)) == 2:
            block += 1
            split = [x.start() for x in re.finditer('Function', l)][1]
            continue
        if l.strip() == 'Reserves':
            reserves = True; continue
        if l.strip().startswith(('Legend:', 'Dx ')) or FOOTER.match(l):
            split = None
        if reserves:
            if m := re.match(rf'^\s*(R\d)\s+(\S.*?)\s{{2,}}({NOC})\s*$', l):
                rows.append(judge_row(disc, rnd, '', m.group(1), m.group(2), m.group(3)))
            continue
        if split is None or not l.strip():
            continue
        for side, text in ((0, l[:split]), (1, l[split:])):
            if not text.strip() or re.fullmatch(r'\s*(Code|NOC|NOC\s+Code)\s*', text):
                continue
            j = JUDGE.match(text)
            if not j:
                err(f'{disc} {rnd} judges p. {n}: unparsed {text.strip()!r}'); continue
            rows.append(judge_row(disc, rnd, GRID[disc][block][side], judge_function(j.group(1)), j.group(2), j.group(3)))
    if block + 1 != len(GRID[disc]):
        err(f'{disc} {rnd} judges: {block + 1} panel rows')
    if [r['Function'] for r in rows if not r['Apparatus'] and not r['Function'].startswith('R')] != ['TD', 'TDA']:
        err(f'{disc} {rnd} judges: superior jury {[r["Name"] for r in rows if not r["Apparatus"]]}')
    n_e = 4 if (disc, rnd) == ('WAG', 'QUAL') else 5
    for app in APPS[disc]:
        panel = [r['Function'] for r in rows if r['Apparatus'] == app]
        if panel[:2 + n_e] != ['D1', 'D2'] + [f'E{i}' for i in range(1, n_e + 1)] or \
                any(not re.fullmatch(r'[TL]\d?', f) for f in panel[2 + n_e:]):
            err(f'{disc} {rnd} {app}: panel {panel}')
    keys = Counter((r['Apparatus'], r['Function']) for r in rows)
    if any(v > 1 for v in keys.values()):
        err(f'{disc} {rnd} judges: a function twice {[k for k, v in keys.items() if v > 1]}')
    return rows

# ---------------------------------------------------------------- run
participants()
check_entry_counts()
finals = {}
starts = finals_start_lists()
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, judges(disc, 'QUAL') + judges(disc, 'EVENT'))
    qualifiers = list_of_qualifiers(disc)
    for app in APPS[disc]:
        q = results(disc, 'QUAL', app)
        check_qualifiers(disc, app, q)
        check_list_of_qualifiers(disc, app, q, qualifiers.get(app, []))
        finals[(disc, app)] = results(disc, 'EVENT', app)
        check_final(disc, app, q, finals[(disc, app)], starts.get((disc, app), ([], [])))
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])
qual_start_lists()
check_medallists(finals)

corrections.finish()
checks.finish()
