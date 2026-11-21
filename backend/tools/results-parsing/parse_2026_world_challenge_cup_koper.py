"""Parse the 2026 World Challenge Cup Koper results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_world_challenge_cup_koper.py \\
        data/2026/2026-WORLD-CHALLENGE-CUP-KOPER/18293-ResultsbookMedia.pdf

Writes PARTICIPANTS / JUDGES / SCORES-QUAL-<APP> / SCORES-EVENT-<APP> CSVs and an IMPORT.json
per discipline next to the PDF, reading event metadata from the EVENT.csv already there and
applying the event's CORRECTIONS.csv. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.12).

The Slovenian Federation's media book: every page has text. A Competition Schedule (p. 2), entry
counts by NOC (p. 3), the entry list (pp. 4-7), medallists (p. 8), Elevien qualification start
lists (pp. 9-22), the judges assignments (WAG p. 23, MAG p. 24), the qualification tables printed
by Imagine (pp. 25-34, whole field, no markers), the tie-break report (pp. 35-37), the same tables
again cut to the finalists and reserves with their `Q`/`R` markers (pp. 38-47), the finals draw
(pp. 48-49), the finals start lists (pp. 50-51), the finals judges (MAG p. 52, WAG p. 53), the
finals (pp. 54-63), a finals tie-break (p. 64) and medallists with scores (p. 65).
"""
import os, re, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-WORLD-CHALLENGE-CUP-KOPER'
PREFIX = {disc: f'{EVENT_PREFIX}-{disc}-SR' for disc in ('MAG', 'WAG')}

BOOK = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
corrections = common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err)
out = common.Output(OUT, corrections)

APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
APP_NAMES = {'FLOOR EXERCISE': 'FX', 'POMMEL HORSE': 'PH', 'RINGS': 'SR', 'VAULT': 'VT', 'PARALLEL BARS': 'PB',
             'HORIZONTAL BAR': 'HB', 'UNEVEN BARS': 'UB', 'BALANCE BEAM': 'BB'}
# Competition Schedule (p. 2): qualification on Thursday 28 May WAG VT, MAG FX, PH, then WAG UB, MAG SR;
# Friday the rest. Finals on Saturday MAG FX, PH, SR and WAG VT, UB; Sunday the rest. The table footers
# are print times (every qualification table is stamped 29 May) and aren't used.
DAY = {'MAG': {'FX': 1, 'PH': 1, 'SR': 1, 'VT': 2, 'PB': 2, 'HB': 2},
       'WAG': {'VT': 1, 'UB': 1, 'BB': 2, 'FX': 2}}
DATES = {'QUAL': {1: '2026-05-28', 2: '2026-05-29'}, 'EVENT': {1: '2026-05-30', 2: '2026-05-31'}}
# Qualification start lists (Elevien): one column per apparatus under icons, two columns for MAG's
# first part of each day. (disc, day, part, side) -> apparatus; proven by matching the results.
START_COLUMNS = {('MAG', 1, 1, 'L'): 'FX', ('MAG', 1, 1, 'R'): 'PH', ('MAG', 1, 2, 'L'): 'SR',
                 ('MAG', 2, 1, 'L'): 'VT', ('MAG', 2, 1, 'R'): 'PB', ('MAG', 2, 2, 'L'): 'HB',
                 ('WAG', 1, 1, 'L'): 'VT', ('WAG', 1, 2, 'L'): 'UB', ('WAG', 2, 1, 'L'): 'BB',
                 ('WAG', 2, 2, 'L'): 'FX'}
# On a qualification start list but with no row in the results and no DNS row. Vault qualification
# ranks only two-vault athletes, so a vaulter here may have done one vault; the book doesn't say.
NO_RESULT = {('MAG', 'FX'): {'38', '66'}, ('MAG', 'PH'): {'66'}, ('MAG', 'SR'): {'66'},
             ('MAG', 'VT'): {'38', '65'}, ('MAG', 'PB'): {'37', '49', '66'}, ('MAG', 'HB'): {'15', '38'},
             ('WAG', 'VT'): {'117', '164'}, ('WAG', 'UB'): {'122', '146'}, ('WAG', 'FX'): {'108', '110', '117'}}
# A qualifier who didn't compete in the final, replaced by the first reserve: WAG floor, PEDRO (Q,
# on the finals start list) for SZILAGYI (R1), who is ranked 8th in the final. The book gives no reason.
REPLACED = {('WAG', 'FX'): ('107', '124')}

# Tie-break report values that differ from the table, where the table's add up: WAG floor
# qualification IORDACHE, E 7,399 for the table's 7,366 (4.80 + 7.366 = 12.166). Reported only.
TIE_MISPRINTS = {('WAG', 'QUAL', 'FX', '140'): {'E': '7.399'}}

ENTRY_COUNTS_PAGE, MEDALLISTS_PAGE, MEDALLISTS_SCORES_PAGE = 3, 8, 65

NUM = r'\d+,\d{2,3}'

def page(n):
    return BOOK[n - 1]

def num(s):
    """Values print with a decimal comma; written with a point, as many decimals as printed."""
    return s.replace(',', '.')

def penalty(s):
    """`Pen.` prints unsigned, `0,00` when none; written negative, or blank."""
    return '' if D(num(s)) == 0 else '-' + num(s)

def bonus(s):
    return '' if D(num(s)) == 0 else num(s)

def bib(s):
    """Results and start lists print the bib with leading zeros (`0012`); the entry list doesn't."""
    return str(int(s))

# ---------------------------------------------------------------- finding reports
def find_tables():
    """Imagine tables: `Final results`, a round line (`... - Qualifications` or not) and an
    apparatus heading. The qualification tables are printed twice, the whole field first and then
    cut to the finalists and reserves with markers. Discipline from the bibs (MAG < 100)."""
    tables = defaultdict(list)
    for n in range(1, len(BOOK) + 1):
        text = page(n)
        if not re.match(r'^\s*Final results\s*$', text.split('\n', 1)[0]):
            continue
        rnd = 'QUAL' if re.search(r'Slovenija 2026 - Qualifications\s*$', text, re.M) else 'EVENT'
        heading = [l.strip() for l in text.split('\n') if l.strip() in APP_NAMES]
        bibs = {int(b) for b in re.findall(r'^\s*\d+ \. (\d{4}) ', text, re.M)}
        disc = {'MAG'} if max(bibs) < 100 else {'WAG'} if min(bibs) >= 100 else bibs
        if len(heading) != 1 or len(disc) != 1:
            err(f'p. {n}: table heading {heading}, discipline {disc}'); continue
        disc, app = disc.pop(), APP_NAMES[heading[0]]
        if app not in APPS[disc]:
            err(f'p. {n}: {app} for {disc}'); continue
        tables[(disc, rnd, app)].append(n)
    for disc in APPS:
        for app in APPS[disc]:
            for rnd, count in (('QUAL', 2), ('EVENT', 1)):
                if len(tables[(disc, rnd, app)]) != count:
                    err(f'{disc} {rnd} {app}: pages {tables[(disc, rnd, app)]}, expected {count}')
    return tables

TABLES = find_tables()

# ---------------------------------------------------------------- participants
PARTICIPANTS = {}   # disc -> bib -> participant row
ENTRY = re.compile(r'^\s*(\d+)\s+([A-Z]{3})\s+(\d+)\s+(\S.*?)\s{2,}(\S.*?)\s{2,}(MAG|WAG) Gymnast'
                   r'( \(Hors Concours\))?\s*$')

def participants():
    """List of competitors with BIB numbers (pp. 4-7): `bib NOC licence SURNAME Given Function`,
    `(Hors Concours)` after the function of an athlete competing out of competition."""
    rows = {'MAG': [], 'WAG': []}
    for n in range(4, 8):
        for l in page(n).split('\n'):
            m = ENTRY.match(l)
            if not m:
                if re.match(r'^\s*\d+\s+[A-Z]{3}\s', l):
                    err(f'participants p. {n}: unparsed {l!r}')
                continue
            b, noc, licence, surname, given, disc, hc = m.groups()
            ev = EVENTS[PREFIX[disc]]
            rows[disc].append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                               'Event Start Date': ev['Start Date'], 'Order': len(rows[disc]) + 1, 'NOC Code': noc,
                               'Bib Number': b, 'FIG License': licence, 'Name': f'{surname} {given}',
                               'Surname': surname, 'Given Name': given, 'Birth Year': '', 'Birth Date': '',
                               'Entry Status': 'HORS_CONCOURS' if hc else ''})
    n_lines = sum(len(re.findall(r'^\s*\d+\s+[A-Z]{3}\s+\d+\s', page(n), re.M)) for n in range(4, 8))
    if n_lines != len(rows['MAG']) + len(rows['WAG']):
        err(f'participants: parsed {len(rows["MAG"]) + len(rows["WAG"])} of {n_lines} entries')
    for disc in APPS:
        out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS + ['Entry Status'], rows[disc])
        by_bib = {}
        for r in rows[disc]:
            if r['Bib Number'] in by_bib:
                err(f'{disc} participants: bib {r["Bib Number"]} twice')
            if (int(r['Bib Number']) < 100) != (disc == 'MAG'):
                err(f'{disc} participants: bib {r["Bib Number"]} out of range')
            by_bib[r['Bib Number']] = r
        PARTICIPANTS[disc] = by_bib

def check_entry_counts():
    """Number of Entries by NOC (p. 3): men and women per country, blank for none, and the totals.
    Hors concours entries aren't counted (SLO: 5 men for 7 entries, 4 women for 5)."""
    text = page(ENTRY_COUNTS_PAGE)
    heading = next(l for l in text.split('\n') if re.search(r'MAG\s+WAG\s+Total', l))
    col = {k: heading.index(k) for k in ('MAG', 'WAG', 'Total')}
    printed, total = {'MAG': Counter(), 'WAG': Counter()}, None
    for l in text.split('\n'):
        m = re.match(r'^\s*([A-Z]{3}|TOTAL)\s+(\d.*)$', l)
        if not m:
            continue
        values = {}
        for v in re.finditer(r'\d+', l):
            # Each count right-aligned under its heading
            key = min(col, key=lambda k: abs(col[k] + len(k) - v.end()))
            values[key] = int(v.group())
        if values.get('MAG', 0) + values.get('WAG', 0) != values.get('Total'):
            err(f'entries by NOC: {l.strip()!r} doesn\'t add up')
        if m.group(1) == 'TOTAL':
            total = values
        else:
            printed['MAG'][m.group(1)] += values.get('MAG', 0)
            printed['WAG'][m.group(1)] += values.get('WAG', 0)
    for disc in APPS:
        counted = Counter(p['NOC Code'] for p in PARTICIPANTS[disc].values() if p['Entry Status'] != 'HORS_CONCOURS')
        if counted != +printed[disc] or total is None or sum(counted.values()) != total[disc]:
            err(f'{disc} entries by NOC: list {dict(sorted(counted.items()))} != p. 3 {dict(printed[disc])}, total {total}')

def identify(disc, ctx, b, name, noc):
    """A row's printed `SURNAME Given` and NOC against the entry list. Case differences (`PAES
    DIOGO`) and accents are reported, not failed; the row takes the entry list's name."""
    p = PARTICIPANTS[disc].get(b)
    if p is None:
        err(f'{ctx}: bib {b} not on the entry list'); return None
    if noc != p['NOC Code'] or name.upper() != p['Name'].upper():
        err(f'{ctx}: bib {b} printed {name} {noc}, entered {p["Name"]} {p["NOC Code"]}')
    elif name != p['Name']:
        print(f'  {ctx}: bib {b} printed {name!r}, entered {p["Name"]!r}')
    return p

# ---------------------------------------------------------------- results tables
ROW = re.compile(r'^\s*(\d+) \. (\d{4}) (\S.*?)\s{2,}([A-Z]{3})((?:\s+' + NUM + r')+)(?:\s+(Q|R\d))?\s*$')
VALUES = re.compile(r'^((?:\s+' + NUM + r')+)\s*$')

def read_table(ctx, n):
    """One table page -> rows `R. Bib Name NOC D E S.b. Pen. Score Comp. [Bon.] Total`, vault with
    vault 2 `D E S.b. Pen. Score` on the line below."""
    rows = []
    for l in page(n).split('\n'):
        if m := ROW.match(l):
            rank, b, name, noc, values, mark = m.groups()
            rows.append(dict(Rank=rank, Bib=bib(b), Name=name, NOC=noc, lines=[num(values).split()], Q=mark or ''))
        elif m := VALUES.match(l):
            if not rows:
                err(f'{ctx}: values before any athlete {l!r}'); continue
            rows[-1]['lines'].append(num(m.group(1)).split())
        elif re.match(r'^\s*\d+ \. ', l):
            err(f'{ctx} p. {n}: unparsed {l!r}')
    n_ids = len(re.findall(r'^\s*\d+ \. \d{4} ', page(n), re.M))
    if n_ids != len(rows):
        err(f'{ctx}: parsed {len(rows)} of {n_ids} rows')
    if not re.search(r'D\s+E\s+S\.b\.\s+Pen\.\s+Score\s+Comp\.\s+(Bon\.\s+)?Total', page(n)):
        err(f'{ctx} p. {n}: unexpected heading')
    return rows

def attempt(ctx, values):
    """`D E S.b. Pen. Score`: the bonus (MAG) is added and the penalty deducted in the score."""
    if len(values) != 5:
        err(f'{ctx}: values {values}'); return None
    d, e, sb, pen, score = values
    return dict(D=d, E=e, B=bonus(sb), Penalty=penalty(pen), Total=score)

def tail(ctx, values, wag_vault):
    """The athlete line's `Comp.`, the unlabelled column (WAG vault: `Bon.`, the +0.2 on the vault
    score) and `Total`. `Comp.` and the unlabelled column are `0,00` on every row."""
    comp, extra, total = values
    if D(comp) != 0 or (D(extra) != 0 and not wag_vault):
        err(f'{ctx}: Comp. {comp}, next column {extra}')
    return bonus(extra), total

TIE_HEAD = re.compile(r'^\s*(FX|PH|SR|VT|PB|HB|UB|BB) \((MAG|WAG)\)\s*$')
TIE = re.compile(r'^\s*(\d+)\s+(\d+)\s+(\S.*?)\s{2,}([A-Z]{3})\s+(' + NUM + r')\s+(' + NUM + r')\s+(' + NUM + r')\s*$')

def read_ties():
    """Tie Break Report - QUALIFICATIONS (pp. 35-37) and - FINALS (p. 64): per apparatus, every
    athlete in a group of equal totals, `Rk BIB Name NOC Total E-score D-score`. A section carries
    onto the next page without a heading."""
    ties, rnd, key = defaultdict(list), None, None
    for n in range(1, len(BOOK) + 1):
        text = page(n)
        if m := re.search(r'Tie Break Report - (QUALIFICATIONS|FINALS)', text):
            rnd = {'QUALIFICATIONS': 'QUAL', 'FINALS': 'EVENT'}[m.group(1)]
        elif rnd is None or re.match(r'^\s*Final results', text):
            rnd = None
            continue
        for l in text.split('\n'):
            if m := TIE_HEAD.match(l):
                key = (m.group(2), rnd, m.group(1))
                if key in ties:
                    err(f'tie break p. {n}: {key} twice')
                ties[key] = []
            elif m := TIE.match(l):
                if key is None:
                    err(f'tie break p. {n}: a row before any heading'); continue
                ties[key].append(dict(zip(('Rank', 'Bib', 'Name', 'NOC', 'Total', 'E', 'D'),
                                          (num(v) for v in m.groups()))))
            elif re.match(r'^\s*\d+\s+\d+\s', l):
                err(f'tie break p. {n}: unparsed {l!r}')
    return ties

TIES = read_ties()

def tie_key(r, app):
    """Equal totals are ranked on E, then D; vault (no tie printed) on the higher vault."""
    if app == 'VT':
        return (max(D(r['Total1']), D(r['Total2'])),)
    return (D(r['E']), D(r['D']))

def check_ties(ctx, key, rows, app):
    """Equal totals are ordered by the tie-break key and never share a rank here; the tie-break
    report lists exactly the tied athletes, with the table's rank, total, E and D."""
    groups = defaultdict(list)
    for r in rows:
        groups[r['Total']].append(r)
    for group in groups.values():
        for a, b in zip(group, group[1:]):
            ka, kb = tie_key(a, app), tie_key(b, app)
            if ka < kb or (ka == kb) != (a['Rank'] == b['Rank']):
                err(f'{ctx}: tie {a["Bib"]} / {b["Bib"]} ranked {a["Rank"]} / {b["Rank"]} on {ka} / {kb}')
    tied = [r['Bib'] for r in rows if len(groups[r['Total']]) > 1]
    ties = TIES.get(key, [])
    if [t['Bib'] for t in ties] != tied:
        err(f'{ctx} tie break: lists {[t["Bib"] for t in ties]}, tied {tied}')
    by_bib = {r['Bib']: r for r in rows}
    for t in ties:
        r = by_bib.get(t['Bib'])
        misprint = TIE_MISPRINTS.get(key + (t['Bib'],), {})
        if r is not None and misprint:
            if any(t[f] != v for f, v in misprint.items()):
                err(f'{ctx} tie break: bib {t["Bib"]} misprint {misprint} not as printed')
            print(f'  {ctx} tie break: bib {t["Bib"]} printed {misprint}, table {({f: r[f] for f in misprint})}')
            t = t | {f: r[f] for f in misprint}
        # The tables print D with two decimals, the tie-break report with three
        if r is None or (t['Rank'], t['NOC'], t['Total'], t['E'], D(t['D'])) != (r['Rank'], r['NOC Code'], r['Total'], r['E'], D(r['D'])):
            err(f'{ctx} tie break: bib {t["Bib"]} {t} differs from the table')
        elif t['Name'].upper() != r['Name'].upper():
            print(f'  {ctx} tie break: bib {t["Bib"]} printed {t["Name"]!r}')

def check_written(ctx, rows, app):
    """Arithmetic on the rows as written, after corrections."""
    for r in rows:
        c = f'{ctx} bib {r["Bib"]}'
        if app != 'VT':
            checks.check_sum(c, r['Total'], r['D'], r['E'], r['B'], r['Penalty'])
            continue
        for n in (1, 2):
            checks.check_sum(f'{c} vault {n}', r[f'Total{n}'], r[f'D{n}'], r[f'E{n}'], r[f'B{n}'], r[f'Penalty{n}'])
        checks.check_vault_average(c, r['Total1'], r['Total2'], r['Combined Bonus'], r['Total'])

COMPETED = defaultdict(set)   # (disc, app) -> bibs with a qualification routine

def results(disc, rnd, app):
    """A round's table -> SCORES rows. Qualification: the whole-field table, with the markers from
    the second printing (which must repeat its rows exactly)."""
    ctx = f'{disc} {rnd} {app}'
    vault, qual = app == 'VT', rnd == 'QUAL'
    pages = TABLES[(disc, rnd, app)]
    if not pages:
        return []
    rows = read_table(ctx, pages[0])
    if any(r['Q'] for r in rows):
        err(f'{ctx}: markers on the whole-field table')
    if qual:
        marked = read_table(f'{ctx} (finalists)', pages[1])
        if [{**r, 'Q': ''} for r in marked] != rows[:len(marked)]:
            err(f'{ctx}: the finalists table differs from the whole-field table')
        for r, m in zip(rows, marked):
            r['Q'] = m['Q']
    written = []
    for r in rows:
        p = identify(disc, ctx, r['Bib'], r['Name'], r['NOC'])
        if p is None:
            continue
        if qual:
            COMPETED[(disc, app)].add(r['Bib'])
        row = {'Event Name': EVENTS[PREFIX[disc]]['Title'], 'Discipline': disc, 'Age Category': 'SR',
               'Session Start Date': DATES[rnd][DAY[disc][app]], 'Round': rnd, 'Part': '', 'Apparatus': app,
               'Rank': r['Rank'], 'Bib': r['Bib'], 'Name': p['Name'], 'NOC Code': p['NOC Code']}
        c = f'{ctx} bib {r["Bib"]}'
        lines = r['lines']
        if vault:
            if len(lines) != 2 or len(lines[0]) != 8:
                err(f'{c}: lines {lines}'); continue
            a1, a2 = attempt(f'{c} vault 1', lines[0][:5]), attempt(f'{c} vault 2', lines[1])
            vb, total = tail(c, lines[0][5:], disc == 'WAG')
            if a1 is None or a2 is None:
                continue
            for n, a in ((1, a1), (2, a2)):
                row |= {f'Status{n}': 'INVALID_VAULT' if D(a['Total']) == 0 else 'COMPLETED', f'D{n}': a['D'],
                        f'E{n}': a['E'], f'B{n}': a['B'], f'Penalty{n}': a['Penalty'], f'SJ Penalty{n}': '',
                        f'Total{n}': a['Total']}
            row |= {'Combined Bonus': vb, 'Total': total}
        else:
            if len(lines) != 1 or len(lines[0]) != 8:
                err(f'{c}: lines {lines}'); continue
            a = attempt(c, lines[0][:5])
            _, total = tail(c, lines[0][5:], False)
            if a is None:
                continue
            if a['Total'] != total:
                err(f'{c}: score {a["Total"]} != total {total}')
            if disc == 'WAG' and a['B']:
                err(f'{c}: a WAG bonus')
            row |= {'Status': 'COMPLETED', 'D': a['D'], 'E': a['E'], 'B': a['B'], 'Penalty': a['Penalty'],
                    'SJ Penalty': '', 'Total': total}
        if qual:
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        written.append(row)
    if [r['Rank'] for r in written] != [str(i) for i in range(1, len(written) + 1)]:
        err(f'{ctx}: ranks {[r["Rank"] for r in written]}')
    checks.check_rank_order(ctx, written)
    check_ties(ctx, (disc, rnd, app), written, app)
    out.csv(f'{PREFIX[disc]}-SCORES-{rnd}-{app}.csv', common.score_header(vault, qual), written)
    check_written(ctx, written, app)
    return written

# ---------------------------------------------------------------- qualifiers, finals, start lists
def check_qualifiers(disc, app, rows):
    """Q on the top eight, at most two per country (no `NR` printed), then two reserves."""
    expected, per_noc, q, reserves = {}, Counter(), 0, 0
    for r in rows:
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

START = re.compile(r'(?:(R\d)\s+)?(\d{4})\s+(\S.*?)\s{2,}([A-Z]{3})\b')

def finals_start_lists():
    """Start list (pp. 50-51): per final, the eight starters then `R1`, `R2`, in two columns under
    apparatus headings. A heading sets its column's apparatus."""
    lists = {}
    for n in range(1, len(BOOK) + 1):
        text = page(n)
        if not re.match(r'^\s*Start list\s*$', text.split('\n', 1)[0]):
            continue
        current = {}
        for l in text.split('\n'):
            for name, app in APP_NAMES.items():
                for m in re.finditer(name, l):
                    current['L' if m.start() < 50 else 'R'] = app
            for m in START.finditer(l):
                side = 'L' if m.start() < 50 else 'R'
                b = bib(m.group(2))
                disc = 'MAG' if int(b) < 100 else 'WAG'
                if side not in current:
                    err(f'finals start list p. {n}: {l!r} under no heading'); continue
                starters, reserves = lists.setdefault((disc, current[side]), ([], []))
                if m.group(1):
                    if m.group(1) != f'R{len(reserves) + 1}':
                        err(f'finals start list {disc} {current[side]}: {m.group(1)} out of order')
                    reserves.append(b)
                else:
                    starters.append(b)
                identify(disc, f'{disc} finals start list {current[side]}', b, m.group(3), m.group(4))
    return lists

def check_final(disc, app, qual_rows, final_rows, start_list):
    """The final's athletes are the start list's eight starters and the eight qualifiers; the start
    list's reserves are the R-marked athletes, in order."""
    starters, reserves = start_list
    finalists = {r['Bib'] for r in final_rows}
    qualified = {r['Bib'] for r in qual_rows if r['Qualification'] == 'Q'}
    if (disc, app) in REPLACED:
        absent, reserve = REPLACED[(disc, app)]
        if absent not in qualified or reserve != reserves[0]:
            err(f'{disc} EVENT {app}: replacement {absent} -> {reserve} doesn\'t fit')
        qualified = qualified - {absent} | {reserve}
        starters = [reserve if b == absent else b for b in starters]
        print(f'  {disc} EVENT {app}: qualifier {absent} didn\'t compete, reserve {reserve} did')
    if finalists != set(starters) or finalists != qualified or len(starters) != 8:
        err(f'{disc} EVENT {app}: finalists {sorted(finalists)}, start list {sorted(starters)}, qualified {sorted(qualified)}')
    marked = [r['Bib'] for r in qual_rows if r['Qualification'].startswith('R')]
    if reserves != marked:
        err(f'{disc} EVENT {app}: start list reserves {reserves}, marked {marked}')

START_ENTRY = re.compile(r'(\d+)\.\s+([A-Z]{3})\s+(\d+)\s+(\S.*?)(?=\s{3,}\d+\.|\s*$)')

def qual_start_lists():
    """Qualifications day N part M (MAG|WAG) (pp. 9-22): groups of `# NOC BIB Competitor` (`Surname
    Given`, `(HC)` marked), one column per apparatus; a page without a title continues the one
    before. -> (disc, app) -> bibs listed."""
    listed, ctx = defaultdict(set), None
    for n in range(1, len(BOOK) + 1):
        text = page(n)
        if 'Starting lists' not in text:
            ctx = None
            continue
        if m := re.search(r'Qualifications day (\d) part (\d) \((MAG|WAG)\)', text):
            ctx = (m.group(3), int(m.group(1)), int(m.group(2)))
        if ctx is None:
            err(f'start list p. {n}: no title'); continue
        disc = ctx[0]
        for l in text.split('\n'):
            for m in START_ENTRY.finditer(l):
                side = 'L' if m.start() < 20 else 'R'
                app = START_COLUMNS.get(ctx + (side,))
                _, noc, b, name = m.groups()
                hc = name.endswith(' (HC)')
                name = name.removesuffix(' (HC)')
                p = PARTICIPANTS[disc].get(b)
                if app is None or p is None or (noc, name.upper()) != (p['NOC Code'], p['Name'].upper()) \
                        or hc != (p['Entry Status'] == 'HORS_CONCOURS'):
                    err(f'{disc} start list p. {n} {app}: bib {b} {noc} {name}, entered {p and p["Name"]}')
                    continue
                listed[(disc, app)].add(b)
    return listed

def check_qual_start_lists(listed):
    """Every qualification routine is on its apparatus's start list; those listed without a result
    are hors concours or the known NO_RESULT athletes."""
    for disc in APPS:
        hors_concours = {b for b, p in PARTICIPANTS[disc].items() if p['Entry Status'] == 'HORS_CONCOURS'}
        for app in APPS[disc]:
            missing = COMPETED[(disc, app)] - listed[(disc, app)]
            extra = listed[(disc, app)] - COMPETED[(disc, app)] - hors_concours
            if missing or extra != NO_RESULT.get((disc, app), set()):
                err(f'{disc} QUAL {app} start list: not listed {sorted(missing)}, listed without a result {sorted(extra)}')
            if listed[(disc, app)] & hors_concours:
                print(f'  {disc} QUAL {app}: hors concours {sorted(listed[(disc, app)] & hors_concours)} on the start '
                      f'list, no result printed')
        entered = {b for b, p in PARTICIPANTS[disc].items()}
        on_lists = set().union(*(listed[(disc, app)] for app in APPS[disc]))
        if entered - on_lists:
            print(f'  {disc}: entered but on no start list {sorted(entered - on_lists)}')

MEDAL = re.compile(r'([123])\s+(\S.*?)\s{2,}([A-Z]{3})(?:\s+(' + NUM + r'))?(?=\s{2,}[123]\s|\s*$)')

def check_medallists(finals):
    """Medallists by event (p. 8, and p. 65 with scores) against the finals: a cross-check only
    (§3.9), differences are printed, not failed."""
    for n in (MEDALLISTS_PAGE, MEDALLISTS_SCORES_PAGE):
        current = {}
        for l in page(n).split('\n'):
            heads = list(re.finditer(r'(FX|PH|SR|VT|PB|HB|UB|BB) \((MAG|WAG)\)', l))
            for m in heads:
                current['L' if m.start() < 40 else 'R'] = (m.group(2), m.group(1))
            if heads:
                continue
            for m in MEDAL.finditer(l):
                key = current.get('L' if m.start() < 35 else 'R')
                rank, name, noc, score = m.groups()
                row = next((r for r in finals.get(key, []) if r['Rank'] == rank), None)
                if row is None:
                    err(f'medallists p. {n}: {m.group()!r} under {key}'); continue
                surname = PARTICIPANTS[key[0]][row['Bib']]['Surname']
                if noc != row['NOC Code'] or surname not in name.upper() or score and num(score) != row['Total']:
                    print(f'  medallists p. {n} {key[0]} {key[1]} {rank}: printed {name} {noc} {score or ""}, '
                          f'final {row["Name"]} {row["NOC Code"]} {row["Total"]}')

# ---------------------------------------------------------------- judges
def judge_row(disc, rnd, app, function, name, surname, given, noc):
    ev = EVENTS[PREFIX[disc]]
    return {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
            'Round': rnd, 'Apparatus': app, 'Function': function, 'Name': name, 'Surname': surname,
            'Given Name': given, 'NOC Code': noc}

MAG_JUDGE = re.compile(r'\b(D[12]|E[1-7]|T|L[12]?)\s+(\d+)\s+(\S+(?: \S+)*)\s{2,}(\S+(?: \S+)*)\s{2,}([A-Z]{3})\b')
MAG_GRID = [('FX', 'PH'), ('SR', 'VT'), ('PB', 'HB')]

def mag_judges(rnd):
    """JUDGES ASSIGNMENT (QUALIFICATION p. 24, FINALES p. 52): `Competition Jury` above the panels
    (`Julio Marcos FIG`: the Technical Delegate, `TD`, no NOC), then three rows of two panels under
    apparatus icons, FX/PH, SR/VT, PB/HB; each judge `function number SURNAME Given NOC`. An empty
    `T` or `R1` label is no judge."""
    title = {'QUAL': 'QUALIFICATION', 'EVENT': 'FINALES'}[rnd]
    n = next((n for n in range(1, len(BOOK) + 1) if 'JUDGES ASSIGNMENT' in page(n)
              and re.search(rf'^\s*{title}\s*$', page(n), re.M)), None)
    if n is None:
        err(f'MAG {rnd}: no judges page'); return []
    lines = page(n).split('\n')
    i = next(i for i, l in enumerate(lines) if l.strip() == 'Competition Jury')
    m = re.fullmatch(r'\s*(\S+) (\S+) FIG\s*', lines[i + 1])
    rows = [judge_row('MAG', rnd, '', 'TD', f'{m.group(1)} {m.group(2)}', m.group(2).upper(), m.group(1), '')]
    block, split = -1, None
    for l in lines[i + 2:]:
        if re.search(r'Number\s+JUDGES\s+Nation\s+Number', l):
            block += 1
            split = [m.start() for m in re.finditer('Number', l)][1]
            continue
        for m in MAG_JUDGE.finditer(l):
            # The right panel's labels start a few columns before its `Number` heading
            app = MAG_GRID[block][0 if m.start() < split - 30 else 1]
            function, _, surname, given, noc = m.groups()
            rows.append(judge_row('MAG', rnd, app, function, f'{surname} {given}', surname, given, noc))
        rest = MAG_JUDGE.sub('', l).strip()
        if rest and not re.fullmatch(r'(T|R1)(\s+R1)?', rest):
            err(f'MAG {rnd} judges p. {n}: unparsed {rest!r}')
    return rows

WAG_FUNCTIONS = {'Line Judge': 'L', 'Time Judge': 'T', 'Line Judge 1': 'L1', 'Line Judge 2': 'L2',
                 'Time Judge 1': 'T1', 'Time Judge 2': 'T2'}
WAG_JUDGE = re.compile(r'(D[12]|E[1-7]|(?:Line|Time) Judge(?: \d)?)\s+(\d+)\s+(\S+(?: \S+)*)\s{2,}([A-Z]{3})\s+[DETL]\b')
WAG_RESERVE = re.compile(r'^\s*(R\d)\s+(\d+)\s+(\S+(?: \S+)*)\s{2,}([A-Z]{3})\s+(VT|UB|BB|FX)\s*$')
WAG_GRID = [('VT', 'UB'), ('BB', 'FX')]

def wag_judges(rnd):
    """Judges Assignments (Women's Qualifications p. 23, Women's Finals p. 53): `Superior Jury:
    LARIO Helena Beatriz Wgym President` (the name wraps; `Wgym` written blank), then two rows of two
    panels under apparatus icons, VT/UB, BB/FX: `Function # SURNAME Given NOC` and a category letter.
    Reserves `R1`-`R4`, each beside an apparatus. A long name pushes its NOC to the next line."""
    title = {'QUAL': "Women's Qualifications", 'EVENT': "Women's Finals"}[rnd]
    n = next((n for n in range(1, len(BOOK) + 1) if 'Judges Assignments' in page(n) and title in page(n)), None)
    if n is None:
        err(f'WAG {rnd}: no judges page'); return []
    lines = page(n).split('\n')
    i = next(i for i, l in enumerate(lines) if 'Superior Jury:' in l)
    m = re.fullmatch(r'\s*Superior Jury:\s+(\S+) (\S+)\s+Wgym\s+President\s*', lines[i])
    more = lines[i + 1].strip()
    surname, given = m.group(1), f'{m.group(2)} {more}'
    rows = [judge_row('WAG', rnd, '', 'President', f'{surname} {given}', surname, given, '')]
    # Rejoin a name whose NOC wrapped onto the next line
    joined = []
    for l in lines[i + 2:]:
        if joined and re.match(r'^\s+[A-Z]{3}\s+[DETL]\s', l) and re.search(r'\s(D[12]|E\d)\s+\d+\s+\S.*[a-z]$', joined[-1]):
            joined[-1] = joined[-1] + '   ' + l.strip()
        else:
            joined.append(l)
    block, split = -1, None
    for l in joined:
        if re.search(r'Function\s+#\s+Name\s+Function', l):
            block += 1
            split = [m.start() for m in re.finditer('Function', l)][1]
            continue
        if m := WAG_RESERVE.match(l):
            r, _, name, noc, app = m.groups()
            surname, given = common.split_surname_first(name)
            rows.append(judge_row('WAG', rnd, app, r, name, surname, given, noc))
            continue
        for m in WAG_JUDGE.finditer(l):
            app = WAG_GRID[block][0 if m.start() < split - 5 else 1]
            function, _, name, noc = m.groups()
            surname, given = common.split_surname_first(name)
            rows.append(judge_row('WAG', rnd, app, WAG_FUNCTIONS.get(function, function), name, surname, given, noc))
        if re.match(r'^\s*(D[12]|E\d|Line|Time|R\d)\b', l) and not WAG_JUDGE.search(l) and not WAG_RESERVE.match(l):
            err(f'WAG {rnd} judges p. {n}: unparsed {l.strip()!r}')
    return rows

def judges(disc):
    rows = []
    for rnd in ('QUAL', 'EVENT'):
        got = (mag_judges if disc == 'MAG' else wag_judges)(rnd)
        for app in APPS[disc]:
            panel = [r['Function'] for r in got if r['Apparatus'] == app and not r['Function'].startswith('R')]
            if panel[:7] != ['D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5']:
                err(f'{disc} {rnd} {app}: panel {panel}')
        if sum(r['Apparatus'] == '' for r in got) != 1:
            err(f'{disc} {rnd} judges: superior jury')
        for r in got:
            if not r['Surname'] or not r['Given Name']:
                err(f'{disc} {rnd} judges: {r["Name"]!r} doesn\'t split')
        rows += got
    return rows

# ---------------------------------------------------------------- run
participants()
check_entry_counts()
starts = finals_start_lists()
listed = qual_start_lists()
finals = {}
for disc in ('MAG', 'WAG'):
    print(f'===== {disc}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, judges(disc))
    for app in APPS[disc]:
        q = results(disc, 'QUAL', app)
        check_qualifiers(disc, app, q)
        finals[(disc, app)] = results(disc, 'EVENT', app)
        check_final(disc, app, q, finals[(disc, app)], starts.get((disc, app), ([], [])))
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])
for key in TIES:
    if key[2] not in APPS[key[0]] or not TABLES.get(key):
        err(f'tie break for {key}: no such table')
check_qual_start_lists(listed)
check_medallists(finals)

corrections.finish()
checks.finish()
