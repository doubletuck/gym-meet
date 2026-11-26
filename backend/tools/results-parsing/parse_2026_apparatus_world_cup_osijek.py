"""Parse the 2026 Apparatus World Cup Osijek results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_apparatus_world_cup_osijek.py \\
        data/2026/2026-APPARATUS-WORLD-CUP-OSIJEK/17937-ResultsbookMedia.pdf

Writes PARTICIPANTS / JUDGES / SCORES-C1-<APP> / SCORES-C3-<APP> CSVs and an IMPORT.json
per discipline next to the PDF, reading event metadata from the EVENT.csv already there and
applying the event's CORRECTIONS.csv. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.10).

The Croatian Federation's media book, printed whole by Elevien: every page has text. Its reports
carry no codes; each starts with a printed title (`Qualification Results — Floor`) and runs on
until the next, so pages are found by title within each discipline's part of the book.
"""
import os, re, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_given_first

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-APPARATUS-WORLD-CUP-OSIJEK'
PREFIX = {disc: f'{EVENT_PREFIX}-{disc}-SR' for disc in ('MAG', 'WAG')}

BOOK = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err)
out = common.Output(OUT, corrections)

APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
# Competition Schedule (p. 3): qualification day 1 MAG FX-PH-SR / WAG VT-UB, day 2 the rest;
# finals on Saturday MAG FX-PH-SR / WAG VT-UB, Sunday the rest (the finals start lists agree).
DAY = {'MAG': {'FX': 1, 'PH': 1, 'SR': 1, 'VT': 2, 'PB': 2, 'HB': 2},
       'WAG': {'VT': 1, 'UB': 1, 'BB': 2, 'FX': 2}}
DATES = {'QUAL': {1: '2026-04-09', 2: '2026-04-10'}, 'EVENT': {1: '2026-04-11', 2: '2026-04-12'}}
WEEKDAY = {'2026-04-09': 'Thursday, 9 April 2026', '2026-04-10': 'Friday, 10 April 2026',
           '2026-04-11': 'Saturday, 11 April 2026', '2026-04-12': 'Sunday, 12 April 2026'}
APP_TITLE = {'FX': 'Floor', 'PH': 'Pommel Horse', 'SR': 'Still Rings', 'VT': 'Vault', 'PB': 'Parallel Bars',
             'HB': 'Horizontal Bar', 'UB': 'Uneven Bars', 'BB': 'Balance Beam'}
TITLE_APP = {v: k for k, v in APP_TITLE.items()} | {'Floor Exercise': 'FX', 'Floor (M)': 'FX', 'Floor (W)': 'FX',
                                                     'Vault (M)': 'VT', 'Vault (W)': 'VT'}
ENTRY_COUNTS_PAGE = 4
MEDALLISTS_PAGE = 5
# On a qualification start list but with no result and no DNS row in the book.
NO_RESULT = {}

NUM = r'\d+\.\d{3}'

def page(n):
    return BOOK[n - 1]

def penalty(s):
    """Neutral deductions (`ND`) are printed unsigned; written negative, as deducted."""
    return '-' + s if s else ''

# ---------------------------------------------------------------- finding reports
TITLE = re.compile(r'^ {2,6}(Entry List by NOC|Entry List by BIB|Starting Lists — Qualifications Day \d \((?:MAG|WAG)\)'
                   r'|Judges Assignment — (?:Qualifications|Finals)|Qualification Results — .+|List of Qualifiers to Finals'
                   r'|Finals Starting Lists|Finals Results — .+|Medalists by Apparatus — (?:MAG|WAG))\s*$', re.M)

def find_reports():
    """disc -> report title -> its physical pages. Each discipline's part of the book starts at its
    cover page (`(MAG)` / `(WAG)`); a page without a title continues the report before it."""
    reports, disc, title = defaultdict(lambda: defaultdict(list)), None, None
    for n in range(1, len(BOOK) + 1):
        if m := re.search(r'^\s*\((MAG|WAG)\)\s*$', page(n), re.M):
            disc, title = m.group(1), None
            continue
        if disc is None:
            continue
        titles = TITLE.findall(page(n))
        if len(titles) > 1:
            err(f'p. {n}: two reports {titles}')
        if titles:
            title = titles[0].strip()
        if title is None:
            err(f'p. {n}: no report')
        else:
            reports[disc][title].append(n)
    return reports

REPORTS = find_reports()

def report(disc, title):
    pages = REPORTS[disc].get(title)
    if not pages:
        err(f'{disc}: no report {title!r}')
        return []
    return pages

# ---------------------------------------------------------------- participants
PARTICIPANTS = {}   # disc -> bib -> participant row, as written (corrections applied)

def participants(disc):
    """Entry List by NOC: a `NOC - Country` line, then `Given SURNAME bib licence` per athlete.
    Neutral athletes come under two `AIN` headings, both printed `AIN` (kept, §4.8)."""
    ev = EVENTS[PREFIX[disc]]
    rows, noc = [], None
    for n in report(disc, 'Entry List by NOC'):
        for l in page(n).split('\n'):
            if m := re.match(r'^\s+([A-Z]{3})\s+- \S', l):
                noc = m.group(1)
                continue
            m = re.match(r'^\s+(\S.*?)\s{2,}(\d{3})\s+(\d+)\s*$', l)
            if not m:
                if re.search(r'\s\d{3}\s+\d+\s*$', l):
                    err(f'{disc} participants p. {n}: unparsed {l!r}')
                continue
            name, bib, licence = m.groups()
            surname, given = split_given_first(name)
            rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                         'Event Start Date': ev['Start Date'], 'Order': len(rows) + 1, 'NOC Code': noc,
                         'Bib Number': bib, 'FIG License': licence, 'Name': name, 'Surname': surname,
                         'Given Name': given, 'Birth Year': '', 'Birth Date': ''})
    printed = {}
    for n in report(disc, 'Entry List by BIB'):
        for m in re.finditer(r'(?:^|\s)(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', page(n), re.M):
            printed[m.group(1)] = (m.group(2), m.group(3))
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)
    by_bib = {}
    for r in rows:
        bib = r['Bib Number']
        if bib in by_bib:
            err(f'{disc} participants: bib {bib} twice')
        if not r['Surname'] or not r['Given Name']:
            err(f'{disc} participants: bib {bib} name {r["Name"]!r} doesn\'t split')
        if printed.get(bib) != (r['Name'], r['NOC Code']):
            err(f'{disc} participants: bib {bib} {r["Name"]} {r["NOC Code"]}, by BIB {printed.get(bib)}')
        by_bib[bib] = r
    if printed.keys() != by_bib.keys():
        err(f'{disc} participants: by BIB {sorted(printed.keys() ^ by_bib.keys())} differ')
    PARTICIPANTS[disc] = by_bib

def check_entry_counts():
    """Number of Entries by NOC (p. 4): men and women per country (`-` for none), against the
    entry lists. The two neutral groups have a row each, both `AIN`."""
    printed, total = defaultdict(Counter), None
    for l in page(ENTRY_COUNTS_PAGE).split('\n'):
        if m := re.match(r'^\s*([A-Z]{3}) - .*?\s(\d+|-)\s+(\d+|-)\s+(\d+)\s*$', l):
            noc, men, women, both = m.groups()
            men, women = (0 if v == '-' else int(v) for v in (men, women))
            if men + women != int(both):
                err(f'entries by NOC: {l.strip()!r} doesn\'t add up')
            printed['MAG'][noc] += men
            printed['WAG'][noc] += women
        if m := re.match(r'^\s*TOTAL \(\d+ NOCs\)\s+(\d+)\s+(\d+)\s+(\d+)\s*$', l):
            total = {'MAG': int(m.group(1)), 'WAG': int(m.group(2))}
    for disc in ('MAG', 'WAG'):
        counted = Counter(p['NOC Code'] for p in PARTICIPANTS[disc].values())
        book = +printed[disc]
        if counted != book or total is None or sum(counted.values()) != total[disc]:
            err(f'{disc} entries by NOC: list {dict(sorted(counted.items()))} != p. 4 {dict(book)}, total {total}')

def identify(disc, ctx, bib, name, noc):
    """A row's printed `Given SURNAME` and NOC against the entry list."""
    p = PARTICIPANTS[disc].get(bib)
    if p is None:
        err(f'{ctx}: bib {bib} not on the entry list'); return None
    if name != p['Name'] or noc != p['NOC Code']:
        err(f'{ctx}: bib {bib} printed {name} {noc}, entered {p["Name"]} {p["NOC Code"]}')
    return p

# ---------------------------------------------------------------- results tables
ROW = re.compile(r'^\s*(?:(\d{1,2})\s+)?(\d{3})\s{2,}(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)(.*)$')
ATTEMPT = re.compile(r'^\s+(V[12])(\s.*)$')
TIE = re.compile(r'^\s*(\d+)\s+(\d{3})\s{2,}(\S.*?)\s{2,}([A-Z]{3})\s+(' + NUM + r')\s+(' + NUM + r')\s*$')
MEDAL = re.compile(r'^\s*(🥇|🥈|🥉)\s+(\S.*?)\s{2,}([A-Z]{3})\s*$')
COLUMNS = {'D': 'D', 'E': 'E', 'ND': 'ND', 'Bonus': 'B', 'SB': 'B', 'VB': 'B', 'Total': 'Total', 'Average': 'Average'}

def by_position(header, values, ctx):
    """Values are right-aligned under their heading; ND and the bonus columns are often empty."""
    cols = [(m.end(), COLUMNS[m.group()]) for m in re.finditer(r'\S+', header) if m.group() in COLUMNS]
    got = {}
    for end, value in values:
        x, col = min(cols, key=lambda c: abs(c[0] - end))
        if col in got or abs(x - end) > 3:
            err(f'{ctx}: value {value} not under a column ({header.strip()!r})'); return None
        got[col] = value
    return got

def vault_attempt_line(words, wag, ctx):
    """`V1|V2 D E [ND] [bonus] Score`. The ND and bonus columns drift against their headings from
    page to page (and continued pages print none), so a lone value is placed by its sign: ND is
    deducted from D + E; MAG's SB is added; WAG's VB isn't in the attempt's score at all."""
    if not 3 <= len(words) <= 5:
        err(f'{ctx}: {words}'); return None
    d, e, *extra, score = words
    if len(extra) == 2:
        return dict(D=d, E=e, ND=extra[0], B=extra[1], Total=score)
    if not extra:
        return dict(D=d, E=e, Total=score)
    x = extra[0]
    if D(d) + D(e) - D(x) == D(score):
        return dict(D=d, E=e, ND=x, Total=score)
    if D(d) + D(e) + (0 if wag else D(x)) == D(score):
        return dict(D=d, E=e, B=x, Total=score)
    err(f'{ctx}: {x} is neither ND nor bonus'); return None

def tokens(text, offset):
    return [(m.end() + offset, m.group()) for m in re.finditer(r'\S+', text)]

def read_section(disc, title):
    """A results report -> (rows, tie-break rows, medallists). The table comes first; a
    `Tie-break — <app>` section (only some qualification tables print one) and, on a final, a
    `Medalists — <app>` block follow, both possibly carrying onto the next page."""
    app = TITLE_APP[title.split(' — ')[1]]
    ctx = f'{disc} {title}'
    rows, ties, medals = [], [], []
    header, mode, pending = None, 'table', None
    pages = report(disc, title)
    for n in pages:
        for l in page(n).split('\n'):
            s = l.strip()
            if s.startswith('Rank') and ' D ' in f' {s} ':
                header, mode = l, 'table'
                continue
            if s.startswith('Tie-break —'):
                if s != f'Tie-break — {APP_TITLE[app]}':
                    err(f'{ctx}: {s!r}')
                mode = 'tie'
                continue
            if s.startswith('Medalists —'):
                if s != f'Medalists — {APP_TITLE[app]}':
                    err(f'{ctx}: {s!r}')
                mode = 'medals'
                continue
            if mode == 'tie':
                if m := TIE.match(l):
                    ties.append(dict(zip(('Rank', 'Bib', 'Name', 'NOC', 'Total', 'first'), m.groups())))
                elif re.match(r'^\s*\d+\s+\d{3}\s', l):
                    err(f'{ctx} tie break p. {n}: unparsed {l!r}')
                continue
            if mode == 'medals':
                if m := MEDAL.match(l):
                    medals.append((m.group(2), m.group(3)))
                continue
            if app == 'VT' and (m := ATTEMPT.match(l)):
                words = m.group(2).split()
                attempt = 'DNS' if words == ['DNS'] else vault_attempt_line(words, disc == 'WAG', f'{ctx} p. {n} {s!r}')
                if m.group(1) == 'V1':
                    if pending is not None:
                        err(f'{ctx} p. {n}: two V1 lines')
                    pending = attempt
                elif not rows or 'v2' in rows[-1] or rows[-1]['v1'] is None:
                    err(f'{ctx} p. {n}: V2 out of place')
                else:
                    rows[-1]['v2'] = attempt
                continue
            m = ROW.match(l)
            if not m:
                if re.match(r'^\s*(?:\d+\s+)?\d{3}\s', l):
                    err(f'{ctx} p. {n}: unparsed {l!r}')
                continue
            rank, bib, name, noc, rest = m.groups()
            q = re.search(r'\s(Q|R\d)\s*$', rest)
            if q:
                rest = rest[:q.start()]
            row = dict(Rank=rank or '', Bib=bib, Name=name, NOC=noc, Q=q.group(1) if q else '')
            vals = tokens(rest, m.start(5))
            words = [v for _, v in vals]
            if app == 'VT':
                # The average on the name's line, the attempts above (V1) and below (V2) it. DNS: no
                # attempts; DNF: vault 1 done, `V2 ... DNS`.
                row['v1'], pending = pending, None
                if words == ['DNS'] and row['v1'] is None:
                    row |= dict(v1='DNS', v2='DNS', Total='')
                elif words == ['DNF'] and row['v1'] not in (None, 'DNS'):
                    row['Total'] = 'DNF'
                elif len(words) == 1 and re.fullmatch(NUM, words[0]) and row['v1'] not in (None, 'DNS'):
                    row['Total'] = words[0]
                else:
                    err(f'{ctx} p. {n}: bib {bib}: {words}'); continue
            elif words == ['DNS']:
                row |= dict(Status='DNS', D='', E='', B='', ND='', Total='')
            else:
                got = by_position(header, vals, f'{ctx} p. {n} bib {bib}')
                if got is None or not {'D', 'E', 'Total'} <= got.keys() or 'Average' in got:
                    err(f'{ctx} p. {n}: bib {bib}: values {words}'); continue
                row |= dict(Status='COMPLETED', B='', ND='') | got
            rows.append(row)
    if pending is not None:
        err(f'{ctx}: a V1 line without its athlete')
    for r in rows:
        if app == 'VT':
            if r['Total'] == 'DNF':
                if r.get('v2') != 'DNS':
                    err(f'{ctx}: bib {r["Bib"]} DNF with a second vault')
                r['Total'] = ''
            elif r['v1'] != 'DNS' and not isinstance(r.get('v2'), dict):
                err(f'{ctx}: bib {r["Bib"]} without a second vault')
    # Ranked rows, and unranked (DNS, DNF) with the bib at the margin; the tie-break rows look alike
    n_ids = sum(len(re.findall(r'^\s*(?:\d+\s+)?\d{3}\s+[A-Z]', page(n), re.M)) for n in pages) - len(ties)
    if n_ids != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_ids} rows')
    return app, rows, ties, medals

def check_rows(ctx, rows, app, wag):
    for r in rows:
        c = f'{ctx} bib {r["Bib"]}'
        if app != 'VT':
            if r['Status'] != 'DNS':
                checks.check_sum(c, r['Total'], r['D'], r['E'], r['B'], penalty(r['ND']))
            continue
        if r['v1'] == 'DNS':
            if r['Rank'] or r['Total']:
                err(f'{c}: a DNS vault row with values')
            continue
        for n in (1, 2):
            v = r[f'v{n}']
            if v == 'DNS':
                continue
            if not {'D', 'E', 'Total'} <= v.keys() or 'Average' in v:
                err(f'{c} vault {n}: {v}'); continue
            # MAG's SB is inside the attempt's score; WAG's VB isn't (it's the vault score's)
            checks.check_sum(f'{c} vault {n}', v['Total'], v['D'], v['E'], '' if wag else v.get('B', ''),
                             penalty(v.get('ND', '')))
        if r['v2'] == 'DNS':
            if r['Rank'] or r['Total']:
                err(f'{c}: a DNF vault row with a rank or total')
            continue
        if wag and r['v1'].get('B'):
            err(f'{c}: a vault bonus on vault 1')
        checks.check_vault_average(c, r['v1']['Total'], r['v2']['Total'], r['v2'].get('B', '') if wag else '',
                                   r['Total'])
    checks.check_rank_order(ctx, rows)

def tie_key(r, app):
    """Equal totals are ranked on E, then D (WAG floor qualification: SHAMAY over ZLOBEC); vault on
    the higher vault."""
    return (max(D(r['v1']['Total']), D(r['v2']['Total'])),) if app == 'VT' else (D(r['E']), D(r['D']))

# Tie-break sections whose ranks aren't the table's: WAG uneven bars qualification prints ranks
# 12-38 for the table's 17-44 and leaves out two of its tied pairs (KUNDRAT / SHAMAY,
# ARTAMONOVA / AJALLA). Its totals and E scores are the table's; the table wins (§3).
STALE_TIE_BREAK = {'WAG QUAL UB'}

def check_ties(ctx, rows, ties, app):
    """Equal totals are ordered by the tie-break key, and equal on all of it share a rank. Where
    the table prints a tie-break section it lists every tied athlete, as on the table."""
    by_bib = {r['Bib']: r for r in rows}
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
    stale = ctx in STALE_TIE_BREAK
    tied = {r['Bib'] for g in groups.values() if len(g) > 1 for r in g}
    listed = [t['Bib'] for t in ties]
    if listed != [r['Bib'] for r in rows if r['Bib'] in tied] and not (stale and set(listed) < tied):
        err(f'{ctx} tie break: lists {listed}, tied {sorted(tied)}')
    for t in ties:
        r = by_bib.get(t['Bib'])
        if r and ((t['Name'], t['NOC'], t['Total']) != (r['Name'], r['NOC'], r['Total'])
                  or D(t['first']) != tie_key(r, app)[0] or (t['Rank'] != r['Rank']) != stale):
            err(f'{ctx} tie break: bib {t["Bib"]} {t} differs from the table')
    if stale:
        print(f'  {ctx} tie break: ranks {[t["Rank"] for t in ties]}, table {[by_bib[b]["Rank"] for b in listed]}; '
              f'not listed {sorted(tied - set(listed))}')

def vault_attempt(n, v, wag):
    if v == 'DNS':
        return {f'Status{n}': 'DNS', f'D{n}': '', f'E{n}': '', f'B{n}': '', f'Penalty{n}': '',
                f'SJ Penalty{n}': '', f'Total{n}': ''}
    invalid = D(v['Total']) == 0
    return {f'Status{n}': 'INVALID_VAULT' if invalid else 'COMPLETED', f'D{n}': v['D'], f'E{n}': v['E'],
            f'B{n}': '' if wag else v.get('B', ''), f'Penalty{n}': penalty(v.get('ND', '')), f'SJ Penalty{n}': '',
            f'Total{n}': v['Total']}

COMPETED = defaultdict(set)   # (disc, app) -> bibs with a qualification routine
DNS = defaultdict(set)        # (disc, app) -> bibs with a qualification DNS row
MEDALS = {}                   # (disc, app) -> the final's medallists block

def results(disc, rnd, app):
    title = f'{"Qualification" if rnd == "QUAL" else "Finals"} Results — {APP_TITLE[app]}'
    ctx = f'{disc} {rnd} {app}'
    wag = disc == 'WAG'
    _, rows, ties, medals = read_section(disc, title)
    check_rows(ctx, rows, app, wag)
    check_ties(ctx, rows, ties, app)
    qual = rnd == 'QUAL'
    if qual and medals or not qual and len(medals) != 3:
        err(f'{ctx}: medallists {medals}')
    MEDALS[(disc, app)] = medals
    written = []
    for r in rows:
        p = identify(disc, ctx, r['Bib'], r['Name'], r['NOC'])
        if p is None:
            continue
        if r['Q'] and not qual:
            err(f'{ctx}: bib {r["Bib"]} marker {r["Q"]} on a final')
        if qual:
            dns = r.get('Status') == 'DNS' or r.get('v1') == 'DNS'
            (DNS if dns else COMPETED)[(disc, app)].add(r['Bib'])
        row = {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
               'Competition Start Date': DATES[rnd][DAY[disc][app]], 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app,
               'Rank': r['Rank'], 'Bib': r['Bib'], 'Name': p['Name'], 'NOC Code': p['NOC Code']}
        if app == 'VT':
            row |= vault_attempt(1, r['v1'], wag) | vault_attempt(2, r['v2'], wag)
            row |= {'Combined Bonus': r['v2'].get('B', '') if wag and r['v2'] != 'DNS' else '', 'Total': r['Total']}
        else:
            row |= {'Status': r['Status'], 'D': r['D'], 'E': r['E'], 'B': r['B'], 'Penalty': penalty(r['ND']),
                    'SJ Penalty': '', 'Total': r['Total']}
        if qual:
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        written.append(row)
    out.csv(f'{PREFIX[disc]}-SCORES-{common.COMPETITION[rnd]}-{app}.csv', common.score_header(app == 'VT', qual), written)
    return written

# ---------------------------------------------------------------- qualifiers, finals, start lists
def check_qualifiers(disc, app, rows):
    """Q on the top eight, at most two per country (no `NR` printed), then three reserves,
    numbered by rank: a tie shares a number and runs past the third (MAG pommel horse: R1, then
    three tied R2)."""
    expected, per_noc, q, reserves, last = {}, Counter(), 0, 0, None
    for r in rows:
        if not r['Rank'] or per_noc[r['NOC Code']] >= 2 and q < 8:
            continue
        if q < 8:
            expected[r['Bib']] = 'Q'
            per_noc[r['NOC Code']] += 1
            q += 1
            continue
        if last and last[0] == r['Rank']:
            number = last[1]
        elif reserves < 3:
            number = (last[1] if last else 0) + 1
        else:
            break
        expected[r['Bib']] = f'R{number}'
        reserves += 1
        last = (r['Rank'], number)
    printed = {r['Bib']: r['Qualification'] for r in rows if r['Qualification']}
    if printed != expected:
        err(f'{disc} QUAL {app}: markers {printed}, expected {expected}')

def qualifiers_list(disc):
    """List of Qualifiers to Finals: per apparatus (two blocks side by side under their names),
    `# BIB NOC Given SURNAME marker`."""
    lists, block = defaultdict(list), None
    for n in report(disc, 'List of Qualifiers to Finals'):
        for l in page(n).split('\n'):
            heads = re.findall(r'\S+(?: \S+)*', l)
            if heads and all(h in TITLE_APP for h in heads):
                block = [TITLE_APP[h] for h in heads]
                continue
            for m in re.finditer(r'(\d+)\s+(\d{3})\s+([A-Z]{3})\s+(\S.*?)\s{2,}(Q|R\d)(?=\s|$)', l):
                # A block's column may run longer than its neighbour (a tie at the last reserve)
                side = 0 if m.start() < 60 else 1
                if block is None or side >= len(block):
                    err(f'{disc} qualifiers: line {l!r}'); continue
                lists[block[side]].append(m.groups())
    return lists

def check_qualifiers_list(disc, app, rows, listed):
    by_bib = {r['Bib']: r for r in rows}
    marked = [r for r in rows if r['Qualification']]
    got = [(b, noc, name, mark) for _, b, noc, name, mark in listed]
    want = [(r['Bib'], r['NOC Code'], r['Name'], r['Qualification']) for r in marked]
    if got != want or any(by_bib[b]['Rank'] != str(i) and by_bib[b]['Qualification'] == 'Q'
                          for i, b, *_ in listed if b in by_bib):
        err(f'{disc} QUAL {app}: qualifiers list {got} != table {want}')

def finals_start_lists(disc):
    """Finals Starting Lists: per apparatus (two side by side), `#. BIB Given SURNAME NOC` for the
    eight starters, then the reserves without a number, in order. Each pair is dated."""
    lists, block = defaultdict(lambda: dict(start=[], reserves=[], date=None)), None
    for n in report(disc, 'Finals Starting Lists'):
        for l in page(n).split('\n'):
            heads = re.findall(r'\S+(?: \S+)*', l)
            if heads and all(h in TITLE_APP for h in heads):
                block = [TITLE_APP[h] for h in heads]
                continue
            if block and (dates := re.findall(r'\w+day, \d+ April 2026', l)):
                for app, d in zip(block, dates):
                    lists[app]['date'] = d
                continue
            for m in re.finditer(r'(?:(\d)\.\s+)?(\d{3})\s{2,}(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', l):
                side = 0 if m.start() < 60 else 1
                if block is None or side >= len(block):
                    err(f'{disc} finals start list: line {l!r}'); continue
                lists[block[side]]['start' if m.group(1) else 'reserves'].append(m.group(2))
    return lists

def check_final(disc, app, qual_rows, final_rows, starters):
    """The final's athletes are its start list's eight, and its reserves the R-marked athletes in
    order. A qualifier missing from the final was replaced by the reserves in order."""
    marks = {r['Bib']: r['Qualification'] for r in qual_rows}
    finalists = {r['Bib'] for r in final_rows}
    if WEEKDAY[DATES['EVENT'][DAY[disc][app]]] != starters['date']:
        err(f'{disc} EVENT {app}: start list dated {starters["date"]}')
    if finalists != set(starters['start']) or len(finalists) != 8:
        err(f'{disc} EVENT {app}: finalists {sorted(finalists)} != start list {sorted(starters["start"])}')
    reserves = [r['Bib'] for r in qual_rows if r['Qualification'].startswith('R')]
    if starters['reserves'] != reserves:
        err(f'{disc} EVENT {app}: start list reserves {starters["reserves"]}, marked {reserves}')
    absent = sorted(b for b, m in marks.items() if m == 'Q' and b not in finalists)
    came_in = [b for b in reserves if b in finalists]
    if absent or any(m != 'Q' for b, m in marks.items() if b in finalists and b not in came_in):
        print(f'  {disc} EVENT {app}: qualifiers {absent} replaced by {came_in}')
        if came_in != reserves[:len(absent)]:
            err(f'{disc} EVENT {app}: qualifiers {absent} replaced by {came_in}')

def check_qual_start_lists(disc):
    """Every qualification routine is on the day's start list for that apparatus, and those listed
    without a result are the known NO_RESULT athletes. A DNS row's athlete may be missing from it
    (MAG LINDPOINTNER on vault, FEDERICI on parallel bars, THORPE on high bar): reported. Groups print one column per apparatus,
    under the apparatus names at the top of the day's first page; a continued group has no
    heading, so its columns are placed by the nearest heading."""
    listed = defaultdict(set)
    for day in (1, 2):
        apps = [a for a in APPS[disc] if DAY[disc][a] == day]
        pages = report(disc, f'Starting Lists — Qualifications Day {day} ({disc})')
        if pages and WEEKDAY[DATES['QUAL'][day]] not in page(pages[0]):
            err(f'{disc} start list day {day}: not dated {WEEKDAY[DATES["QUAL"][day]]}')
        heads = None
        for n in pages:
            columns = None
            for l in page(n).split('\n'):
                names = re.findall(r'\S+(?: \S+)*', l)
                if names and all(h in TITLE_APP for h in names):
                    heads = [TITLE_APP[h] for h in names]
                    if heads != apps:
                        err(f'{disc} start list day {day}: apparatus {heads}')
                    continue
                if re.match(r'^\s*#\s+BIB', l):
                    columns = [m.start() for m in re.finditer('#', l)]
                    if len(columns) != len(apps):
                        err(f'{disc} start list day {day} p. {n}: {len(columns)} columns')
                    continue
                for m in re.finditer(r'(\d+)\.\s+(\d{3})\s+(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', l):
                    if columns is None:
                        # A group carried onto a new page: place by the next heading on the page
                        nxt = re.search(r'^\s*#\s+BIB.*$', page(n)[page(n).find(l):], re.M)
                        columns = [c.start() for c in re.finditer('#', nxt.group())]
                    col = max(i for i in range(len(columns)) if columns[i] <= m.start() + 1)
                    app = apps[col]
                    identify(disc, f'{disc} start list day {day}', m.group(2), m.group(3), m.group(4))
                    if m.group(2) in listed[app]:
                        err(f'{disc} start list {app}: bib {m.group(2)} twice')
                    listed[app].add(m.group(2))
    for app in APPS[disc]:
        missing = COMPETED[(disc, app)] - listed[app]
        extra = listed[app] - COMPETED[(disc, app)] - DNS[(disc, app)]
        if missing or extra != NO_RESULT.get((disc, app), set()):
            err(f'{disc} QUAL {app} start list: not listed {sorted(missing)}, listed without a result {sorted(extra)}')
        if DNS[(disc, app)] - listed[app]:
            print(f'  {disc} QUAL {app}: DNS rows not on the start list {sorted(DNS[(disc, app)] - listed[app])}')

def check_medallists(finals):
    """Medallists are printed three times: Medalists by Event (p. 5), each final's own block, and
    Medalists by Apparatus at the end of each discipline. All three against the final's ranks."""
    by_event = {}
    disc = None
    for l in page(MEDALLISTS_PAGE).split('\n'):
        if m := re.search(r'Medalists by Event — (MAG|WAG)', l):
            disc = m.group(1)
            continue
        m = re.match(r'^\s*(Floor|Pommel Horse|Still Rings|Vault|Parallel Bars|Horizontal Bar|Uneven Bars|Balance Beam)'
                     r'\s{2,}(.*)$', l)
        if m and disc:
            by_event[(disc, TITLE_APP[m.group(1)])] = re.findall(r'(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', m.group(2))
    by_apparatus = {}
    for d in ('MAG', 'WAG'):
        for n in report(d, f'Medalists by Apparatus — {d}'):
            for l in page(n).split('\n'):
                m = re.match(r'^\s*(Floor|Pommel Horse|Still Rings|Vault|Parallel Bars|Horizontal Bar|Uneven Bars|'
                             r'Balance Beam)\s{2,}(.*)$', l)
                if m:
                    by_apparatus[(d, TITLE_APP[m.group(1)])] = re.findall(r'(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)', m.group(2))
    for key, rows in finals.items():
        podium = [(r['Name'], r['NOC Code']) for r in sorted(rows, key=lambda r: int(r['Rank'] or 99))
                  if r['Rank'] in ('1', '2', '3')]
        for source, printed in (('p. 5', by_event.get(key)), ('final', MEDALS.get(key)),
                                ('by apparatus', by_apparatus.get(key))):
            if [tuple(p) for p in printed or []] != podium:
                print(f'  medallists {key} ({source}): printed {printed}, final {podium}')

# ---------------------------------------------------------------- judges
JUDGE = re.compile(r'(?:^|\s{2,})(D\d|E\d|S|T\d?|L\d?|R\d)\s{2,}(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)')

def judges(disc, rnd):
    """Judges Assignment: `Technical Delegate: SURNAME Given (NOC)`, then panels two to a row under
    the apparatus names, `Function Given SURNAME NOC`. `S` is the panel's supervisor, written `SV`;
    MAG's `R1`-`R3` under the last panel are the round's reserves (apparatus blank)."""
    ev = EVENTS[PREFIX[disc]]
    title = f'Judges Assignment — {"Qualifications" if rnd == "QUAL" else "Finals"}'
    base = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
            'Competition': common.COMPETITION[rnd]}
    rows, block, panels = [], None, defaultdict(list)
    for n in report(disc, title):
        for l in page(n).split('\n'):
            if m := re.match(r'^\s*Technical Delegate: (\S.*?) \(([A-Z]{3})\)\s*$', l):
                surname, given = common.split_surname_first(m.group(1))
                rows.append(base | {'Apparatus': '', 'Function': 'TD', 'Name': m.group(1), 'Surname': surname,
                                    'Given Name': given, 'NOC Code': m.group(2)})
                continue
            heads = re.findall(r'\S+(?: \S+)*', l)
            if heads and all(h in TITLE_APP for h in heads):
                block = [TITLE_APP[h] for h in heads]
                continue
            for m in JUDGE.finditer(l):
                func, name, noc = m.groups()
                side = 0 if m.start(1) < 70 else 1
                if block is None or side >= len(block):
                    err(f'{disc} {rnd} judges: line {l!r}'); continue
                panels[block[side]].append((func, name, noc))
    for app in APPS[disc]:
        funcs = [f for f, _, _ in panels[app]]
        reserves = [j for j in panels[app] if j[0].startswith('R')]
        if funcs[:8] != ['D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5', 'S'] or len(set(funcs)) != len(funcs) \
                or reserves and (disc, app) != ('MAG', 'PB'):
            err(f'{disc} {rnd} {app}: panel {funcs}')
        for func, name, noc in panels[app]:
            surname, given = split_given_first(name)
            reserve = func.startswith('R')
            rows.append(base | {'Apparatus': '' if reserve else app, 'Function': 'SV' if func == 'S' else func,
                                'Name': name, 'Surname': surname, 'Given Name': given, 'NOC Code': noc})
    if [r['Function'] for r in rows].count('TD') != 1:
        err(f'{disc} {rnd} judges: technical delegate')
    if set(panels) != set(APPS[disc]):
        err(f'{disc} {rnd} judges: panels {sorted(panels)}')
    for r in rows:
        if not r['Surname'] or not r['Given Name']:
            err(f'{disc} {rnd} judges: {r["Name"]!r} doesn\'t split')
    # Rows run TD, then the panels in apparatus order, then the round's reserves
    return [r for r in rows if r['Apparatus'] or r['Function'] == 'TD'] + \
           [r for r in rows if not r['Apparatus'] and r['Function'] != 'TD']

# ---------------------------------------------------------------- run
finals = {}
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    participants(disc)
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, judges(disc, 'QUAL') + judges(disc, 'EVENT'))
    listed = qualifiers_list(disc)
    starts = finals_start_lists(disc)
    for app in APPS[disc]:
        q = results(disc, 'QUAL', app)
        check_qualifiers(disc, app, q)
        check_qualifiers_list(disc, app, q, listed[app])
        finals[(disc, app)] = results(disc, 'EVENT', app)
        check_final(disc, app, q, finals[(disc, app)], starts[app])
    check_qual_start_lists(disc)
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])
check_entry_counts()
check_medallists(finals)

corrections.finish()
checks.finish()
