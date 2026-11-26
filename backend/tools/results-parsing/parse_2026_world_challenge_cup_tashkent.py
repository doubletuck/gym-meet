"""Parse the 2026 World Challenge Cup Tashkent results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_world_challenge_cup_tashkent.py \\
        data/2026/2026-WORLD-CHALLENGE-CUP-TASHKENT/18291-ResultsbookMedia.pdf

Writes PARTICIPANTS / JUDGES / SCORES-C1-<APP> / SCORES-C3-<APP> CSVs and an IMPORT.json
per discipline next to the PDF, reading event metadata from the EVENT.csv already there and
applying the event's CORRECTIONS.csv. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.18).

The Uzbek Federation's media book: every page has text except the cover, no report codes. A
schedule (pp. 2-4), entry counts by NOC (p. 5), medallists (p. 6), medal standings (p. 7), the
entry list (`Number of Athletes`, pp. 8-10), then per discipline the qualification start lists
(MAG one page per apparatus and subdivision, WAG one page per apparatus), the qualification
judges, per apparatus the results (`Apparatus Results`) and any `Tie-Break Report` on the next
page, the finals start lists (one page per day), the finals judges and the finals.

The MAG rings final prints totals only; its D, E and bonus come from a screenshot of the
Elevien app in the event folder, logged as corrections.
"""
import os, re, sys, unicodedata
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-WORLD-CHALLENGE-CUP-TASHKENT'
PREFIX = {disc: f'{EVENT_PREFIX}-{disc}-SR' for disc in ('MAG', 'WAG')}

# NFKC folds the ligatures some start lists print (`Soﬁa`)
BOOK = [unicodedata.normalize('NFKC', p) for p in common.pdf_pages(PDF)]
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err)
out = common.Output(OUT, corrections)

APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
APP_NAMES = {'Floor Exercise': 'FX', 'Pommel Horse': 'PH', 'Rings': 'SR', 'Vault': 'VT', 'Parallel Bars': 'PB',
             'Horizontal Bar': 'HB', 'Uneven Bars': 'UB', 'Balance Beam': 'BB'}
APP_TITLE = {v: k for k, v in APP_NAMES.items()}
# The schedule's names for the apparatus
SCHEDULE_NAMES = {'FLOOR': 'FX', 'POMMEL HORSE': 'PH', 'RINGS': 'SR', 'VAULT': 'VT', 'PARALLEL BARS': 'PB',
                  'HORIZONTAL BAR': 'HB', 'UNEVEN BARS': 'UB', 'BALANCE BEAM': 'BB'}
# Judges panels: icon grid, left to right then top to bottom (rendered pages; MAG's time and line
# judges sit on FX and VT, WAG's legend names the icons)
GRID = {'MAG': [('FX', 'VT'), ('PH', 'PB'), ('SR', 'HB')], 'WAG': [('VT', 'UB'), ('BB', 'FX')]}
PANEL_EXTRA = {'MAG': {'FX': ['T', 'L1', 'L2'], 'VT': ['L']},
               'WAG': {'VT': ['L'], 'UB': ['T'], 'BB': ['T1', 'T2'], 'FX': ['T', 'L1', 'L2']}}

# Hors concours athletes: on the qualification start lists, marked `(HC)`, but not on the entry
# list and with no result anywhere. They are not written.
HORS_CONCOURS = {'MAG': {'135', '136', '137', '138'}, 'WAG': {'225', '226', '227'}}
# MAG floor qualification, subdivision IV (p. 14), prints the three bibs against the wrong names
# (`104 VU Tien Anh`, `131 ONOSHIMA`, `145 TARRAB`): printed bib -> the bib of the athlete named.
START_LIST_BIBS = {('MAG', 'FX'): {'104': '145', '131': '104', '145': '131'}}
# On a qualification start list with no row (not even `DNS`): MAG SITCHINAVA on vault. Elevien has
# him `DNS`; the parser adds his row, blank, and the CORRECTIONS log sets both vaults' status.
MISSING_ROWS = {('MAG', 'VT'): ['112']}
# Number of Entries by NOC (p. 5) prints these countries' men and women wrongly (HUN, IND and ISL
# swapped; GEO 3 men for 4, VIE 3 for 4); its totals agree with the entry list.
ENTRY_COUNT_MISPRINTS = {'GEO', 'HUN', 'IND', 'ISL', 'VIE'}
# Tables with equal totals and no Tie-Break Report page; the rank order is still checked on E, D
# (the rings final's from the Elevien values)
NO_TIE_PAGE = {('MAG', 'EVENT', 'SR'), ('WAG', 'EVENT', 'VT')}

def page(n):
    return BOOK[n - 1]

def lines_of(n):
    return page(n).split('\n')

def heads(n):
    """The page's heading lines, above any table."""
    hs = []
    for l in lines_of(n):
        if re.match(r'^\s*(Rank|№|NF\b|Function|SUPERIOR JURY|Superior Jury)', l):
            break
        if l.strip():
            hs.append(re.sub(r'\s+', ' ', l.strip()))
    return hs

def pages_where(test):
    return [n for n in range(1, len(BOOK) + 1) if test(heads(n))]

def iso(dmy):
    d, m, y = dmy.split('.')
    return f'{y}-{m}-{d}'

# ---------------------------------------------------------------- schedule
MONTHS = {'May': 5}

def read_schedule():
    """Schedule (pp. 2-4): `May 21 - Thursday` opens a day, `Qualification, Day 1` or `Apparatus
    Finals` a competition; then rotations `MAG: Floor / Pommel Horse`, `WAG: Vault` or finals
    `MAG FLOOR`. Award ceremonies and training lines name apparatus too and are skipped.
    -> (disc, round, app) -> date; (disc, date) -> the finals in schedule order."""
    sessions, order, day, rnd = {}, defaultdict(list), None, None
    for n in (2, 3, 4):
        for l in lines_of(n):
            if m := re.match(r'^\s*(May) (\d+) - \w+day\s*$', l):
                day, rnd = f'2026-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}', None
            elif re.match(r'^\s*Qualification, Day \d\s*$', l):
                rnd = 'QUAL'
            elif l.strip() == 'Apparatus Finals':
                rnd = 'EVENT'
            elif rnd and not re.search(r'AWARD|training|Judges|Marching', l, re.I):
                for m in re.finditer(r'\b(MAG|WAG):? ([A-Za-z /]+?)(?=\s{2,}|\s*$)', l):
                    for name in m.group(2).split('/'):
                        app = SCHEDULE_NAMES.get(name.strip().upper())
                        if app is None:
                            err(f'schedule p. {n}: {name!r}'); continue
                        key = (m.group(1), rnd, app)
                        if sessions.setdefault(key, day) != day:
                            err(f'schedule: {key} on {sessions[key]} and {day}')
                        if rnd == 'EVENT':
                            order[(m.group(1), day)].append(app)
    if len(sessions) != 20:
        err(f'schedule: {len(sessions)} sessions')
    return sessions, order

DATES, FINALS_ORDER = read_schedule()

# ---------------------------------------------------------------- participants
PARTICIPANTS = {}   # disc -> bib -> participant row
ENTRY = re.compile(r'^(.*?)\s*\b(\d{3})\s+(\d{3,5})\s+(\d{4})\s*$')
COUNTRY = re.compile(r'^\s*([A-Z]{3})\s*[-–]\s+\S.*$')

def split_names(text):
    """A country's names run together (the entry list wraps them, sometimes onto another
    athlete's line: `GOBADZE Ani MOTTEN` / `Dorien`): a name starts at an upper-case word that
    follows a given name."""
    names = []
    for w in text.split():
        if names and common.surname_word(w) and not common.surname_word(names[-1][-1]):
            names.append([w])
        elif names:
            names[-1].append(w)
        else:
            names.append([w])
    return [' '.join(n) for n in names]

def participants():
    """Entry list (`Number of Athletes`, pp. 8-10): under `NOC – Country` headings, each athlete
    `SURNAME Given  Bib  Licence  Year`; names wrap and drift a line from their numbers, so each
    country's names are read in order and paired with its numbers in order. MAG bibs are 1xx."""
    pages = pages_where(lambda h: 'Number of Athletes' in h)
    if pages != [8, 9, 10]:
        err(f'entry list: pages {pages}')
    countries, noc = [], None
    for n in pages:
        started = False
        for l in lines_of(n):
            if not started:
                started = 'Number of Athletes' in l
                continue
            if m := COUNTRY.match(l):
                noc = m.group(1)
                countries.append((noc, [], []))
                continue
            if not l.strip() or re.match(r'^\s*(NF\s|Number$)', l.strip()) or noc is None:
                continue
            m = ENTRY.match(l)
            text = m.group(1) if m else l
            if m:
                countries[-1][2].append(m.groups()[1:])
            if text.strip():
                countries[-1][1].append(text.strip())
    rows = {'MAG': [], 'WAG': []}
    for noc, texts, numbers in countries:
        names = split_names(' '.join(texts))
        if len(names) != len(numbers):
            err(f'entry list {noc}: names {names}, numbers {numbers}'); continue
        for name, (b, licence, year) in zip(names, numbers):
            disc = 'MAG' if b.startswith('1') else 'WAG'
            ev = EVENTS[PREFIX[disc]]
            surname, given = common.split_surname_first(name)
            rows[disc].append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                               'Event Start Date': ev['Start Date'], 'Order': len(rows[disc]) + 1,
                               'NOC Code': noc, 'Bib Number': b, 'FIG License': licence, 'Name': name,
                               'Surname': surname, 'Given Name': given, 'Birth Year': year, 'Birth Date': ''})
    n_numbers = sum(len(re.findall(r'\b\d{3}\s+\d{3,5}\s+\d{4}\s*$', page(n), re.M)) for n in pages)
    for disc in APPS:
        out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows[disc])
        by_bib = {}
        for r in rows[disc]:
            # Checked as written, after corrections
            if r['Bib Number'] in by_bib:
                err(f'{disc} participants: bib {r["Bib Number"]} twice')
            if not r['Surname'] or not r['Given Name'] or (r['Surname'], r['Given Name']) != \
                    common.split_surname_first(r['Name']):
                err(f'{disc} participants: {r["Name"]!r} doesn\'t split')
            by_bib[r['Bib Number']] = r
        PARTICIPANTS[disc] = by_bib
    if n_numbers != sum(len(v) for v in PARTICIPANTS.values()):
        err(f'entry list: {n_numbers} numbered lines, {sum(len(v) for v in PARTICIPANTS.values())} entries')

def check_entry_counts():
    """Number of Entries by NOC (p. 5): `NOC  men  women  total`, a blank for none; each number
    under the `Men` / `Women` / `Total` heading it starts nearest to (§2.6)."""
    if 'Number of Entries by NOC' not in heads(5):
        err('p. 5 is not Number of Entries by NOC'); return
    starts, printed, total = None, {}, None
    for l in lines_of(5):
        if re.fullmatch(r'\s*Men\s+Women\s+Total\s*', l):
            starts = {m.group(): m.start() for m in re.finditer(r'\S+', l)}
            continue
        m = re.match(r'^\s*(?:([A-Z]{3})|Total NFs: (\d+))\s+(\d.*?)\s*$', l)
        if not m or starts is None:
            continue
        values = {}
        for v in re.finditer(r'\d+', l[m.start(3):]):
            pos = m.start(3) + v.start()
            col = min(starts, key=lambda c: abs(starts[c] - pos))
            if abs(starts[col] - pos) > 3 or col in values:
                err(f'entries by NOC: {l.strip()!r}'); break
            values[col] = int(v.group())
        men, women = values.get('Men', 0), values.get('Women', 0)
        if m.group(2):
            total = (men, women, values.get('Total'), int(m.group(2)))
        else:
            printed[m.group(1)] = (men, women, values.get('Total'))
    listed = defaultdict(lambda: [0, 0])
    for i, disc in enumerate(APPS):
        for p in PARTICIPANTS[disc].values():
            listed[p['NOC Code']][i] += 1
    wrong = {noc for noc in set(printed) | set(listed)
             if printed.get(noc, (0, 0))[:2] != tuple(listed[noc])}
    if wrong != ENTRY_COUNT_MISPRINTS:
        err(f'entries by NOC: differ for {sorted(wrong)}, known misprints {sorted(ENTRY_COUNT_MISPRINTS)}')
    for noc, (men, women, tot) in printed.items():
        if tot != sum(listed[noc]):
            print(f'  entries by NOC: {noc} total {tot}, entry list {sum(listed[noc])}')
    men, women = len(PARTICIPANTS['MAG']), len(PARTICIPANTS['WAG'])
    if total != (men, women, men + women, len(listed)):
        err(f'entries by NOC: totals {total}, entry list {(men, women, men + women, len(listed))}')

def identify(disc, ctx, b, name, noc):
    """A row's printed name and NOC against the entry list."""
    p = PARTICIPANTS[disc].get(b)
    if p is None:
        err(f'{ctx}: bib {b} not on the entry list'); return None
    if noc != p['NOC Code'] or name != p['Name']:
        err(f'{ctx}: bib {b} printed {name!r} {noc}, entered {p["Name"]} {p["NOC Code"]}')
    return p

# ---------------------------------------------------------------- results tables
def report(disc, rnd, app, tie=False):
    """The pages of one results table or tie-break report, by its heading lines."""
    want = f'{disc} {"Qualification" if rnd == "QUAL" else "Final"}'
    return pages_where(lambda h: 'Apparatus Results' in h and want in h and APP_TITLE[app] in h
                       and ('Tie-Break Report' in h) == tie)

ROW = re.compile(r'^\s*(?:(\d+)\s+)?(\d{3})\s+([A-Z]\S*(?: \S+)*?)\s{2,}([A-Z]{3})(?:\s+(.*?))?\s*$')
SCORE = r'\d+\.\d{3}'
MARK = re.compile(r'^(Q|R\d)$')

def penalty(v):
    """`Pen` prints unsigned, `0.00` for none."""
    return '' if D(v) == 0 else f'-{v}'

def bonus(v):
    """`B` prints `0.0` for none."""
    return '' if D(v) == 0 else v

def routine(ctx, tokens, has_b):
    """`D E [B] Pen Score` -> routine dict, or None."""
    n = 5 if has_b else 4
    vals = tokens[:n]
    if len(vals) != n or not all(re.fullmatch(SCORE, v) for v in (vals[0], vals[1], vals[-1])) \
            or has_b and not re.fullmatch(r'\d\.\d', vals[2]) or not re.fullmatch(r'\d\.\d\d', vals[-2]):
        err(f'{ctx}: values {tokens}')
        return None
    return dict(Status='INVALID_VAULT' if D(vals[-1]) == 0 else 'COMPLETED', D=vals[0], E=vals[1],
                B=bonus(vals[2]) if has_b else '', Penalty=penalty(vals[-2]), Total=vals[-1])

DNS = dict(Status='DNS', D='', E='', B='', Penalty='', Total='')

def read_table(ctx, n, vault):
    """One results page -> rows. The header row says which columns print: `B` (MAG, not pommel
    horse), or `Total` alone (MAG rings final). Vault: `1` and vault 1, the score and the vault
    total on the athlete's line; then (WAG qualification: the birth year) `2` and vault 2, and
    `(+0.2)` where WAG's bonus was added."""
    ls = lines_of(n)
    header = next((l for l in ls if l.strip().startswith('Rank')), '')
    cols = header.split()
    has_b, totals_only = 'B' in cols, 'D' not in cols
    rows, years = [], {}
    n_ids = sum(1 for l in ls if re.match(r'^\s*(?:\d+\s+)?\d{3}\s+[A-Z]', l))
    for i, l in enumerate(ls):
        m = ROW.match(l)
        if not m:
            continue
        rank, b, name, noc, rest = m.groups()
        tokens = (rest or '').split()
        row = dict(Rank=rank or '', Bib=b, Name=name, NOC=noc, Q='')
        c = f'{ctx} bib {b}'
        if tokens and MARK.match(tokens[-1]):
            row['Q'] = tokens.pop()
        if vault:
            m2 = re.match(r'^\s*(?:(\d{4})\s+)?2\s+(\S.*?)\s*$', ls[i + 1] if i + 1 < len(ls) else '')
            if tokens[:1] != ['1'] or not m2:
                err(f'{c}: vault lines {tokens}'); continue
            if m2.group(1):
                years[b] = m2.group(1)
            v1 = routine(f'{c} vault 1', tokens[1:], has_b)
            t2 = m2.group(2).split()
            combined = ''
            if t2 and t2[-1] == '(+0.2)':
                combined = '0.2'
                t2.pop()
            v2 = DNS if t2 == ['DNS'] else routine(f'{c} vault 2', t2, has_b)
            left = tokens[1 + (5 if has_b else 4):]
            if v1 is None or v2 is None or len(left) != 1 or len(t2) not in (1, 5 if has_b else 4):
                err(f'{c}: vault values {tokens} / {t2}'); continue
            total = left[0]
            if total == 'DNF':
                # Vault 1 done, vault 2 not: no vault score, no rank
                if rank or v2 is not DNS or combined:
                    err(f'{c}: DNF row')
                total = ''
            elif not re.fullmatch(SCORE, total):
                err(f'{c}: vault total {total!r}'); continue
            row |= dict(v1=v1, v2=v2, Bonus=combined, Total=total)
        elif tokens == ['DNS']:
            row |= DNS
        elif totals_only:
            if len(tokens) != 1 or not re.fullmatch(SCORE, tokens[0]):
                err(f'{c}: values {tokens}'); continue
            row |= dict(DNS, Status='COMPLETED', Total=tokens[0])
        else:
            a = routine(c, tokens, has_b)
            if a is None or len(tokens) != (5 if has_b else 4):
                err(f'{c}: values {tokens}'); continue
            row |= a
        rows.append(row)
    if n_ids != len(rows):
        err(f'{ctx}: parsed {len(rows)} rows of {n_ids}')
    return rows, years, totals_only

TIE = re.compile(rf'^\s*(\d+)\s+(\d{{3}})\s+(\S.*?)\s{{2,}}([A-Z]{{3}})\s+({SCORE})\s+({SCORE})(?:\s+({SCORE}))?\s*$')

def read_ties(disc, rnd, app):
    """Tie-Break Report: `Rank Bib Name NOC Total` and the first value that differs (E; vault:
    the highest vault), then the next where that is equal too."""
    ties = []
    for n in report(disc, rnd, app, tie=True):
        for l in lines_of(n):
            if t := TIE.match(l):
                ties.append(dict(zip(('Rank', 'Bib', 'Name', 'NOC', 'Total', 'First', 'Second'), t.groups())))
            elif re.match(r'^\s*\d+\s+\d{3}\s+[A-Z]', l):
                err(f'{disc} {rnd} {app} tie break p. {n}: unparsed {l!r}')
    return ties

def tie_key(r, app):
    """The printed rules: E, then D; vault: the highest vault, then the highest E, then D."""
    if app == 'VT':
        return (max(D(r['Total1']), D(r['Total2'])), max(D(r['E1']), D(r['E2'])), max(D(r['D1']), D(r['D2'])))
    return (D(r['E']), D(r['D']))

def check_ties(ctx, key, rows, app):
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
    listed = read_ties(*key)
    if not listed and tied and key in NO_TIE_PAGE:
        return
    if [t['Bib'] for t in listed] != tied or key in NO_TIE_PAGE:
        err(f'{ctx} tie break: lists {[t["Bib"] for t in listed]}, tied {tied}')
    by_bib = {r['Bib']: r for r in rows}
    for t in listed:
        r = by_bib.get(t['Bib'])
        if r is None:
            continue
        k = tie_key(r, app)
        group = [tie_key(x, app) for x in groups[r['Total']]]
        # The second value prints only where the first is equal across the group
        second = k[1] if len({g[0] for g in group}) == 1 else None
        if (t['Rank'], t['Name'], t['NOC'], t['Total']) != (r['Rank'], r['Name'], r['NOC Code'], r['Total']) \
                or D(t['First']) != k[0] or (D(t['Second']) if t['Second'] else None) != second:
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

COMPETED = defaultdict(set)   # (disc, app) -> bibs with a qualification row
VAULT_YEARS = {}              # WAG bib -> birth year printed on the vault qualification table

def results(disc, rnd, app):
    """A results table -> SCORES rows."""
    ctx = f'{disc} {rnd} {app}'
    vault, qual = app == 'VT', rnd == 'QUAL'
    pages = report(disc, rnd, app)
    if len(pages) != 1:
        err(f'{ctx}: pages {pages}'); return []
    rows, years, totals_only = read_table(ctx, pages[0], vault)
    if totals_only != ((disc, rnd, app) == ('MAG', 'EVENT', 'SR')):
        err(f'{ctx}: columns')
    if years and (disc, rnd, app) != ('WAG', 'QUAL', 'VT'):
        err(f'{ctx}: birth years printed')
    VAULT_YEARS.update(years)
    written = []
    for r in rows:
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
            if disc == 'MAG' and r['Bonus'] or disc == 'WAG' and (r['v1']['B'] or r['v2']['B']):
                err(f'{c}: bonus in the wrong place')
            row |= attempt_columns(1, r['v1']) | attempt_columns(2, r['v2']) | \
                {'Combined Bonus': r['Bonus'], 'Total': r['Total']}
        else:
            if (disc == 'WAG' or app == 'PH') and r['B']:
                err(f'{c}: a bonus on {disc} {app}')
            row |= {k: r[k] for k in ('Status', 'D', 'E', 'B', 'Penalty')} | {'SJ Penalty': '', 'Total': r['Total']}
        if qual:
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        elif r['Q']:
            err(f'{c}: marker on a final')
        if bool(row['Total']) != bool(r['Rank']):
            err(f'{c}: rank {r["Rank"]!r} with total {row["Total"]!r}')
        written.append(row)
    for b in MISSING_ROWS.get((disc, app), []) if qual else []:
        # A start-list athlete the table leaves out: blank here, its status from CORRECTIONS
        p = PARTICIPANTS[disc][b]
        if b in COMPETED[(disc, app)]:
            err(f'{ctx}: bib {b} printed after all')
        COMPETED[(disc, app)].add(b)
        blank = dict(DNS, Status='')
        row = {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
               'Competition Start Date': DATES[(disc, rnd, app)], 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app,
               'Rank': '', 'Bib': b, 'Name': p['Name'], 'NOC Code': p['NOC Code']}
        if vault:
            row |= attempt_columns(1, blank) | attempt_columns(2, blank) | {'Combined Bonus': '', 'Total': ''}
        else:
            row |= {k: blank[k] for k in ('Status', 'D', 'E', 'B', 'Penalty')} | {'SJ Penalty': '', 'Total': ''}
        written.append(row | {'Qualification': '', 'Qualification Rank': ''})
    ranked = [int(r['Rank']) for r in written if r['Rank']]
    if ranked != list(range(1, len(ranked) + 1)):
        # Every tie in this book is broken; a shared rank would need a look
        err(f'{ctx}: ranks {ranked}')
    out.csv(f'{PREFIX[disc]}-SCORES-{common.COMPETITION[rnd]}-{app}.csv', common.score_header(vault, qual), written)
    # The rows as written: the rings final's D and E come from corrections
    check_written(ctx, written, app)
    checks.check_rank_order(ctx, written)
    check_ties(ctx, (disc, rnd, app), written, app)
    return written

def check_birth_years():
    """The WAG vault qualification table prints each vaulter's birth year: the entry list's, as
    written (two are corrected from it)."""
    for b, year in VAULT_YEARS.items():
        p = PARTICIPANTS['WAG'].get(b)
        if p is None or p['Birth Year'] != year:
            err(f'WAG vault birth year: bib {b} {year}, entry list {p and p["Birth Year"]}')
    if len(VAULT_YEARS) != len(COMPETED[('WAG', 'VT')]):
        err(f'WAG vault birth years: {len(VAULT_YEARS)} for {len(COMPETED[("WAG", "VT")])} vaulters')

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

START = re.compile(r'(?<!\S)(\d{3})\s+([A-Z]\S*(?: \S+)*?)\s{2,}([A-Z]{3})(?:\s+(2VT|R[1-3]))?(?=\s|$)')

def finals_start_lists():
    """Finals start lists, one page per discipline and day (`START LIST dd.mm.yyyy` / `MAG
    Finals`): eight starters then `RESERVE` R1-R3 per final, in columns left, right, then a centred
    one (MAG's third final); the columns are that day's finals in schedule order. Vaulters print
    `2VT`. -> (disc, app) -> (starters, reserves)."""
    lists = {}
    for disc in APPS:
        pages = pages_where(lambda h: f'{disc} Finals' in h and any(x.startswith('START LIST') for x in h))
        if len(pages) != 2:
            err(f'{disc} finals start lists: pages {pages}')
        for n in pages:
            day = iso(re.search(r'START LIST (\d\d\.\d\d\.\d{4})', page(n)).group(1))
            apps = FINALS_ORDER[(disc, day)]
            for app in apps:
                lists[(disc, app)] = ([], [])
            for l in lines_of(n):
                found = list(START.finditer(l))
                for m in found:
                    pos = m.start()
                    col = 0 if pos < 12 else 2 if pos < 40 and len(found) == 1 else 1
                    if col >= len(apps):
                        err(f'{disc} finals start list p. {n}: column {col} {l!r}'); continue
                    app = apps[col]
                    b, name, noc, mark = m.groups()
                    ctx = f'{disc} finals start list {app}'
                    identify(disc, ctx, b, name, noc)
                    starters, reserves = lists[(disc, app)]
                    if mark and mark.startswith('R'):
                        if mark != f'R{len(reserves) + 1}':
                            err(f'{ctx}: {mark} out of order')
                        reserves.append(b)
                    else:
                        if (mark == '2VT') != (app == 'VT') or reserves:
                            err(f'{ctx}: bib {b} marked {mark}')
                        starters.append(b)
                if not found and re.search(r'\s[A-Z]{3}(\s|$)', l) and re.match(r'^\s*\d{3}\s', l):
                    err(f'{disc} finals start list p. {n}: unparsed {l!r}')
    return lists

def check_final(disc, app, qual_rows, final_rows, start_list):
    """The final's athletes are the start list's eight starters and the eight qualifiers; the start
    list's reserves are the R-marked athletes, in order."""
    starters, reserves = start_list
    finalists = {r['Bib'] for r in final_rows}
    qualified = {r['Bib'] for r in qual_rows if r['Qualification'] == 'Q'}
    if finalists != set(starters) or finalists != qualified or len(starters) != 8:
        err(f'{disc} EVENT {app}: finalists {sorted(finalists)}, start list {sorted(starters)}, qualified {sorted(qualified)}')
    marked = [r['Bib'] for r in qual_rows if r['Qualification'].startswith('R')]
    if reserves != marked:
        err(f'{disc} EVENT {app}: start list reserves {reserves}, marked {marked}')

QUAL_START = re.compile(r'(?<!\S)(\d{3})\s+([A-Z]\S*(?: \S+)*?)(?: \(HC\))?\s{2,}([A-Z]{3})(?:\s+(2VT))?(?=\s|$)')

def qual_start_lists():
    """Qualification start lists: MAG a page per apparatus and subdivision (`MAG Qualification FX`,
    `Bib Name NOC order`), WAG a page per apparatus in group columns (`WAG AQ VT`, `WAG
    Qualification BB`; vaulters `2VT`). Hors concours print `(HC)`. Checked as sets."""
    for disc in APPS:
        for app in APPS[disc]:
            pages = pages_where(lambda h: any(x.startswith('START LIST') for x in h)
                                and any(re.fullmatch(rf'{disc} (Qualification|AQ) {app}', x) for x in h))
            date = {DATES[(disc, 'QUAL', app)]} if pages else set()
            listed, hc = set(), set()
            for n in pages:
                date.add(iso(re.search(r'START LIST (\d\d\.\d\d\.\d{4})', page(n)).group(1)))
                for l in lines_of(n):
                    found = list(QUAL_START.finditer(l))
                    for m in found:
                        b, name, noc, mark = m.groups()
                        if '(HC)' in m.group(0):
                            hc.add(b); continue
                        if (mark == '2VT') != (disc == 'WAG' and app == 'VT'):
                            err(f'{disc} start list {app}: bib {b} marked {mark}')
                        b = START_LIST_BIBS.get((disc, app), {}).get(b, b)
                        identify(disc, f'{disc} start list {app} p. {n}', b, name, noc)
                        listed.add(b)
                    if not found and re.match(r'^\s*\d{3}\s+[A-Z]', l):
                        err(f'{disc} start list {app} p. {n}: unparsed {l!r}')
            if not pages or len(date) != 1:
                err(f'{disc} start list {app}: pages {pages}, dates {date}')
            if hc - HORS_CONCOURS[disc] or hc & set(PARTICIPANTS[disc]):
                err(f'{disc} start list {app}: hors concours {sorted(hc)}')
            if listed != COMPETED[(disc, app)]:
                err(f'{disc} QUAL {app} start list: {sorted(listed ^ COMPETED[(disc, app)])} on one side only')
        on_lists = set().union(*(COMPETED[(disc, app)] for app in APPS[disc]))
        if set(PARTICIPANTS[disc]) - on_lists:
            print(f'  {disc}: entered but on no start list {sorted(set(PARTICIPANTS[disc]) - on_lists)}')

MEDALS = {'GOLD': '1', 'SILVER': '2', 'BRONZE': '3'}

def check_medallists(finals):
    """Medallists By Event (p. 6): `Men’s – FX – App-Final` beside each final's three medallists,
    `MEDAL NOC SURNAME Given`. A cross-check only (§3.9)."""
    medals, labels = [], []
    for l in lines_of(6):
        if m := re.search(r"(Men|Women)[’']s – (\w\w) – App-Final", l):
            labels.append(('MAG' if m.group(1) == 'Men' else 'WAG', m.group(2)))
        if m := re.search(r'\b(GOLD|SILVER|BRONZE)\s+([A-Z]{3})\s+(\S.*?)\s*$', l):
            medals.append(m.groups())
    if len(labels) != 10 or len(medals) != 30:
        err(f'medallists: {len(labels)} finals, {len(medals)} medals'); return
    for i, key in enumerate(labels):
        for medal, noc, name in medals[3 * i:3 * i + 3]:
            rows = [r for r in finals.get(key, []) if r['Rank'] == MEDALS[medal]]
            if len(rows) != 1 or (rows[0]['Name'], rows[0]['NOC Code']) != (name, noc):
                err(f'medallists {key} {medal}: {name} {noc}, final {[(r["Name"], r["NOC Code"]) for r in rows]}')

# ---------------------------------------------------------------- judges
def judge_row(disc, rnd, app, function, surname, given, noc):
    ev = EVENTS[PREFIX[disc]]
    if not surname or not given:
        err(f'{disc} {rnd} judges: {surname!r} {given!r}')
    return {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
            'Competition': common.COMPETITION[rnd], 'Apparatus': app, 'Function': function, 'Name': f'{surname} {given}', 'Surname': surname,
            'Given Name': given, 'NOC Code': noc}

MAG_JUDGE = re.compile(r'(?<!\S)(D[12]|E[1-7]|T|L\d?|R\d)\s+([A-Z][A-Z\'-]*(?: [A-Z][A-Z\'-]*)*)\s{2,}(\S.*?)\s{2,}([A-Z]{3})(?=\s|$)')

def mag_judges(rnd):
    """MAG `JUDGES ASSIGNMENT` / `Apparatus Qualification|Final`: `SUPERIOR JURY : Mr. <name> WG`
    (the Technical Delegate, `TD`, NOC blank), then panels two to a row under icons (GRID), each
    judge `Function SURNAME  Given  NF`. The reserves below the grid (`R1` per column, `R2` blank)
    are left out (agreed with the user)."""
    want = 'Apparatus Qualification' if rnd == 'QUAL' else 'Apparatus Final'
    pages = pages_where(lambda h: any('JUDGES ASSIGNMENT' in x for x in h) and want in h and 'MAG' in h)
    if len(pages) != 1:
        err(f'MAG {rnd} judges: pages {pages}'); return []
    n = pages[0]
    rows, block = [], -1
    for l in lines_of(n):
        if m := re.match(r'^\s*SUPERIOR JURY : Mr\. ([A-Z]+) (\S.*?)\s{2,}WG\s*$', l):
            rows.append(judge_row('MAG', rnd, '', 'TD', m.group(1), m.group(2), '')); continue
        if re.fullmatch(r'\s*JUDGES\s+NF\s+JUDGES\s+NF\s*', l):
            block += 1; continue
        found = list(MAG_JUDGE.finditer(l))
        for m in found:
            f, surname, given, noc = m.groups()
            if f.startswith('R'):
                continue
            side = 0 if m.start() < 40 else 1
            rows.append(judge_row('MAG', rnd, GRID['MAG'][block][side], f, surname, given, noc))
        if not found and re.match(r'^\s*(D[12]|E\d|T|L\d?)\s+\S', l):
            err(f'MAG {rnd} judges p. {n}: unparsed {l!r}')
    if block + 1 != 3:
        err(f'MAG {rnd} judges: {block + 1} panel rows')
    return rows

NOC_CAT = re.compile(r'\s([A-Z]{3})\s+([DELT])\s*$')

def wag_judges(rnd):
    """WAG `Apparatus Qualification|Final` / `WAG`: `Superior Jury: <name> Wgym` (`TD`, NOC blank),
    then panels two to a row under icons (GRID), each judge `Function  Name  NOC  category`.
    Long labels wrap: `Time Judge` / `1`, its number on the next line, where the next judge's name
    sits; a judge's name can sit on the line above their NOC. Each judge is read at their NOC and
    category letter, which must agree with the function. Then reserves `R1`-`R4` (apparatus blank)."""
    want = 'Apparatus Qualification' if rnd == 'QUAL' else 'Apparatus Final'
    pages = pages_where(lambda h: want in h and 'WAG' in h and not any('Results' in x for x in h))
    if len(pages) != 1:
        err(f'WAG {rnd} judges: pages {pages}'); return []
    n = pages[0]
    rows, block, reserves, split, name_col = [], -1, False, None, None
    pending = [None, None]   # per side: [label, name] of a judge not yet closed
    last = [None, None]      # per side: the last judge's row, for a wrapped label number
    sj = re.search(r'^Superior Jury: ([A-Z]+) (\S.*?) Wgym\s*$', page(n), re.M)
    if sj:
        rows.append(judge_row('WAG', rnd, '', 'TD', sj.group(1), sj.group(2), ''))
    else:
        err(f'WAG {rnd} judges: no superior jury')

    def close(side, label, name, noc, cat):
        f = label_function(label)
        if f is None or f[0] != cat:
            err(f'WAG {rnd} judges p. {n}: {label!r} {name!r} category {cat}')
            return
        surname, given = common.split_surname_first(name)
        row = judge_row('WAG', rnd, GRID['WAG'][block][side], f, surname, given, noc)
        row['Name'] = name
        rows.append(row)
        last[side] = (row, label)

    for l in lines_of(n):
        if l.strip() == 'Reserves':
            reserves = True; continue
        if reserves:
            if m := re.match(r'^\s*(R\d)\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', l):
                surname, given = common.split_surname_first(m.group(2))
                rows.append(judge_row('WAG', rnd, '', m.group(1), surname, given, m.group(3)))
            continue
        if len(re.findall(r'\bFunction\b', l)) == 2:
            block += 1
            # A wrapped right-hand label (`Line Judge 2`) starts a column left of its heading
            split = [x.start() for x in re.finditer('Function', l)][1] - 2
            name_col = [x.start() for x in re.finditer('Name', l)]
            continue
        if split is None or re.fullmatch(r'\s*(NOC|Code)(\s+(NOC|Code))?\s*', l) or not l.strip():
            continue
        for side, (a, b) in enumerate(((0, split), (split, len(l)))):
            text = l[a:b]
            if not text.strip():
                continue
            col = name_col[side] - a
            label, rest = text[:col].strip(), text[col:]
            m = NOC_CAT.search(rest)
            name = (rest[:m.start()] if m else rest).strip()
            if re.fullmatch(r'\d', label) and last[side]:
                # A wrapped label's number belongs to the judge above
                row, prev = last[side]
                f = label_function(f'{prev} {label}')
                if f is None:
                    err(f'WAG {rnd} judges p. {n}: {prev!r} {label!r}')
                else:
                    row['Function'] = f
                last[side] = None
                label = ''
            if m:
                pend = pending[side] or ['', '']
                close(side, label or pend[0], name or pend[1], m.group(1), m.group(2))
                pending[side] = None
            elif name or label:
                pending[side] = [label, name]
    if any(pending):
        err(f'WAG {rnd} judges p. {n}: left over {pending}')
    if block + 1 != 2:
        err(f'WAG {rnd} judges: {block + 1} panel rows')
    return rows

def label_function(label):
    """`D1`, `E1`… as printed; `Time Judge`, `Line Judge 1` -> `T`, `L1` (§4.7)."""
    if re.fullmatch(r'D[12]|E[1-7]', label):
        return label
    m = re.fullmatch(r'(Time|Line) Judge(?: (\d))?', label)
    return m.group(1)[0] + (m.group(2) or '') if m else None

def check_panels(disc, rnd, rows):
    """Each panel `D1 D2 E1-E4` plus its time and line judges; one Technical Delegate; no judge
    twice on a panel."""
    for app in APPS[disc]:
        panel = [r['Function'] for r in rows if r['Apparatus'] == app]
        if panel != ['D1', 'D2', 'E1', 'E2', 'E3', 'E4'] + PANEL_EXTRA[disc].get(app, []):
            err(f'{disc} {rnd} {app}: panel {panel}')
        names = [r['Name'] for r in rows if r['Apparatus'] == app]
        if len(set(names)) != len(names):
            err(f'{disc} {rnd} {app}: a judge twice {names}')
    rest = [r['Function'] for r in rows if not r['Apparatus']]
    if rest != ['TD'] + ([f'R{i}' for i in range(1, 5)] if disc == 'WAG' else []):
        err(f'{disc} {rnd} judges: {rest}')

def judges(disc, rnd):
    rows = mag_judges(rnd) if disc == 'MAG' else wag_judges(rnd)
    check_panels(disc, rnd, rows)
    return rows

# ---------------------------------------------------------------- run
participants()
check_entry_counts()
finals = {}
starts = finals_start_lists()
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, judges(disc, 'QUAL') + judges(disc, 'EVENT'))
    for app in APPS[disc]:
        q = results(disc, 'QUAL', app)
        check_qualifiers(disc, app, q)
        finals[(disc, app)] = results(disc, 'EVENT', app)
        check_final(disc, app, q, finals[(disc, app)], starts.get((disc, app), ([], [])))
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])
qual_start_lists()
check_birth_years()
check_medallists(finals)

corrections.finish()
checks.finish()
