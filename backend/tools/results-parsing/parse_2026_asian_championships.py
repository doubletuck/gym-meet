"""Parse the 2026 Asian Championships results books (senior and junior) into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_asian_championships.py data/2026/2026-ASIAN-CHAMPIONSHIPS/1856[5-8]-*.pdf

One book per discipline and age category (18565 MAG SR, 18566 MAG JR, 18567 WAG SR, 18568 WAG JR),
each recognised by its title band. Writes PARTICIPANTS, JUDGES, SCORES-QUAL-*, SCORES-EVENT-*,
SUMMARY-QUAL-{TEAM,AA}, SUMMARY-FINAL-{TEAM,AA} and an IMPORT.json per book next to the PDFs,
reading event metadata from the EVENT.csv already there. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.16).

Media books in the FIG layout, printed by Starting Future (footer codes like GAM103900_73I: G,
M/W, a 3-digit unit -- x01 team, x02 all-around, x03.. apparatus, x 1 for seniors, 3 for MAG
juniors, 2 for WAG juniors -- a 3-digit phase -- 900 qualification, 100 final -- and the report
suffix).

One competition is the qualification, the Team Final and the All-Around Final at once. The book
prints the qualification rankings (every team and athlete, with Q/R/NR) and, from the same
routines, Team Final and All-Around Final rankings (the qualifiers only, re-ranked). The finals'
rankings are written as SUMMARY-FINAL-* files whose `Scores Round` is QUAL: the TEAM and AA
sessions hold no routines of their own (§4.9).

Australia is "an invited country and does not enter any ranking": its rows print `*` for a rank
and are kept unranked, its athletes entered as HORS_CONCOURS.
"""
import os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first as split_name

OUT = os.path.dirname(os.path.abspath(sys.argv[1]))
EVENT_PREFIX = '2026-ASIAN-CHAMPIONSHIPS'
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
out = common.Output(OUT, common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR', 'MAG-JR', 'WAG-JR'], err))
# The book being parsed: they're parsed one at a time, so its age category is held here
AGE = None
AGE_WORD = {'SR': 'Senior', 'JR': 'Junior'}

G = {'MAG': 'M', 'WAG': 'W'}
GENDER = {'MAG': "Men's", 'WAG': "Women's"}
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
APP_NAME = {'FX': 'Floor Exercise', 'PH': 'Pommel Horse', 'SR': 'Rings', 'VT': 'Vault', 'PB': 'Parallel Bars',
            'HB': 'Horizontal Bar', 'UB': 'Uneven Bars', 'BB': 'Balance Beam'}
# From each book's Competition Schedule page (never from report footers, §4.4). TEAM and AA are
# rankings of the qualification's routines, competed the same day.
SESSION_DATE = {
    ('MAG', 'SR'): {'QUAL': '2026-06-18',
                    'EVENT': {'FX': '2026-06-20', 'PH': '2026-06-20', 'SR': '2026-06-20',
                              'VT': '2026-06-21', 'PB': '2026-06-21', 'HB': '2026-06-21'}},
    ('MAG', 'JR'): {'QUAL': '2026-06-19',
                    'EVENT': {'PH': '2026-06-20', 'SR': '2026-06-20', 'FX': '2026-06-20',
                              'PB': '2026-06-21', 'HB': '2026-06-21', 'VT': '2026-06-21'}},
    ('WAG', 'SR'): {'QUAL': '2026-06-25',
                    'EVENT': {'VT': '2026-06-27', 'UB': '2026-06-27', 'BB': '2026-06-28', 'FX': '2026-06-28'}},
    ('WAG', 'JR'): {'QUAL': '2026-06-26',
                    'EVENT': {'UB': '2026-06-27', 'VT': '2026-06-27', 'FX': '2026-06-28', 'BB': '2026-06-28'}},
}
# Invited countries print `*` for a rank: they enter no ranking
INVITED = {'AUS'}
MARKERS = ('Q', 'R1', 'R2', 'R3', 'R4', 'NR')

# ---------------------------------------------------------------- page lookup
PAGES = {}

def footer(page):
    for l in reversed(page.split('\n')):
        if re.search(r'Page \d+/\d+', l):
            return l.split()[0]
    return None

def find(disc, code, title=None, optional=False):
    """0-based page indexes whose footer code matches the pattern `code` and whose title block has
    the line `title`."""
    pages = PAGES[disc]
    idx = [i for i, p in enumerate(pages) if re.fullmatch(code, footer(p) or '')]
    if title:
        idx = [i for i in idx if any(l.strip() == title for l in pages[i].split('\n')[:10])]
    if not idx and not optional:
        raise SystemExit(f'{disc}: no pages for {code} / {title}')
    return idx

def lines(disc, idx):
    return [l for i in idx for l in PAGES[disc][i].split('\n')]

def title(disc, what):
    return f'{AGE_WORD[AGE]} {GENDER[disc]} {what}'

def book(path):
    """(discipline, age category) of a book, from its title band."""
    for l in common.pdf_pages(path)[1].split('\n')[:6]:
        m = re.search(r"(SENIOR|JUNIOR) (MEN|WOMEN)'S ARTISTIC GYMNASTICS ASIAN CHAMPIONSHIPS", l)
        if m:
            return ('MAG' if m.group(2) == 'MEN' else 'WAG'), m.group(1)[0] + 'R'
    raise SystemExit(f'{path}: no title band')

# ---------------------------------------------------------------- participants
MONTHS = {m: i + 1 for i, m in enumerate('JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split())}
NAMES = {}

def participants(disc, ev):
    rows, noc = [], None
    for l in lines(disc, find(disc, 'GA0000000_32A')):
        m = re.match(r'^\s+([A-Z]{3})\s+- \S', l)
        if m:
            noc = m.group(1); continue
        m = re.match(r"^\s+(\S.*?)\s{2,}(\d+)?\s+(\d{3})\s+(\d{1,2}) ([A-Z]{3}) (\d{4})\s*$", l)
        if not m:
            if re.search(r'\s\d{3}\s+\d{1,2} [A-Z]{3} \d{4}\s*$', l):
                err(f'{disc} participants: unparsed {l!r}')
            continue
        name, lic, bib, d, mon, y = m.groups()
        sur, giv = split_name(name)
        if not sur or not giv:
            err(f'{disc} participants: name split {name!r} -> {sur!r}/{giv!r}')
        if bib in NAMES:
            err(f'{disc} participants: duplicate bib {bib}')
        NAMES[bib] = (name, noc)
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': AGE,
                     'Event Start Date': ev['Start Date'], 'Order': len(rows) + 1, 'NOC Code': noc,
                     'Bib Number': bib, 'FIG License': lic or '', 'Name': name, 'Surname': sur,
                     'Given Name': giv, 'Birth Year': y, 'Birth Date': f'{y}-{MONTHS[mon]:02d}-{int(d):02d}',
                     'Entry Status': 'HORS_CONCOURS' if noc in INVITED else ''})
    print(f'  {disc} participants: {len(rows)}')
    out.csv(f'{prefix(disc)}-PARTICIPANTS.csv', common.PARTICIPANTS + ['Entry Status'], rows)
    # Results rows carry the name as corrected
    for r in rows:
        NAMES[r['Bib Number']] = (r['Name'], r['NOC Code'])

def check_name(ctx, bib, noc):
    """The participant's full name for a results row, after checking the bib and NOC."""
    if bib not in NAMES:
        err(f'{ctx}: bib {bib} not in participants'); return ''
    full, pnoc = NAMES[bib]
    if pnoc != noc:
        err(f'{ctx}: bib {bib} NOC {noc} != participants {pnoc}')
    return full

def check_rank(ctx, rank, noc, bib=''):
    """`*` marks an invited country's row, and only theirs; the stored rank is then blank."""
    if (rank == '*') != (noc in INVITED):
        err(f'{ctx} {bib or noc}: rank {rank!r} for {noc}')
    return '' if rank == '*' else common.rank_number(rank.lstrip('='))

# ---------------------------------------------------------------- judges
# Panel order in the grid follows the icon legend; the panels confirm it (beam's two time
# judges, vault's single line judge, floor's time and line judges).
GRID = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}

def judge_fn(f):
    m = re.fullmatch(r'(Time|Line) Judge(?: (\d))?', f)
    if m:
        return ('T' if m.group(1) == 'Time' else 'L') + (m.group(2) or '')
    return 'SV' if f == 'AS' else f

def judge_noc(noc):
    # The Asian Gymnastics Union, credited like any continental union (§4.7)
    return '' if noc == 'AGU' else noc

def judges(disc, ev):
    rows = []
    def add(rnd, app, fn, name, noc):
        sur, giv = split_name(name)
        if not sur or not giv:
            err(f'{disc} judges: name split {name!r}')
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': AGE,
                     'Event Start Date': ev['Start Date'], 'Round': rnd, 'Apparatus': app, 'Function': fn,
                     'Name': name, 'Surname': sur, 'Given Name': giv, 'NOC Code': judge_noc(noc)})
    sfx = '57A' if disc == 'MAG' else '57B'
    for rnd, code in (('QUAL', f'GA{G[disc]}000900_{sfx}'), ('EVENT', f'GA{G[disc]}000100_{sfx}')):
        n0, block, split_at, in_res = len(rows), -1, None, False
        pages = find(disc, code, optional=True)
        if not pages:
            # The MAG junior book prints no qualification judges
            print(f'  {disc} {AGE} judges {rnd}: no sheet')
            continue
        for l in lines(disc, pages):
            m = re.match(r'^\s+[MW]AG AGU President:?\s+(\S.*?)\s*$', l)
            if m:
                add(rnd, '', 'President', m.group(1), ''); continue
            if re.match(r'^\s+Function\s+Name\s+(?:(?:NOC|Code)\s+)?Function\s+Name', l):
                block += 1
                split_at = l.index('Function', l.index('Name'))
                continue
            if l.strip() == 'Reserves':
                in_res = True; continue
            if l.startswith('Legend:'):
                break
            if in_res:
                m = re.match(r'^\s+R(\d)\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', l)
                if m:
                    add(rnd, '', f'R{m.group(1)}', m.group(2), m.group(3))
                continue
            if block >= 0 and split_at:
                for side, part in ((0, l[:split_at]), (1, l[split_at:])):
                    m = re.match(r'^\s*(AS|D\d|E\d|(?:Time|Line) Judge(?: \d)?)\s+(\S.*?)\s{2,}([A-Z]{3})\s*$', part)
                    if m:
                        add(rnd, GRID[disc][block * 2 + side], judge_fn(m.group(1)), m.group(2), m.group(3))
                    elif part.strip() and part.strip() not in ('NOC', 'Code', 'NOC Code'):
                        err(f'{disc} judges {rnd}: unparsed {part!r}')
        if block + 1 != len(GRID[disc]) // 2:
            err(f'{disc} judges {rnd}: {block + 1} panel rows')
        for app in GRID[disc]:
            fns = [r['Function'] for r in rows[n0:] if r['Apparatus'] == app]
            if not {'SV', 'D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5'} <= set(fns) or len(fns) != len(set(fns)):
                err(f'{disc} judges {rnd} {app}: functions {fns}')
        print(f'  {disc} judges {rnd}: {len(rows) - n0}')
    out.csv(f'{prefix(disc)}-JUDGES.csv', common.JUDGES, rows)

# ---------------------------------------------------------------- apparatus tables
def prefix(disc):
    return f'{EVENT_PREFIX}-{disc}-{AGE}'

def meta(disc, rnd, app):
    date = SESSION_DATE[(disc, AGE)][rnd]
    if isinstance(date, dict):
        date = date[app]
    return {'Event Name': EVENTS[prefix(disc)]['Title'], 'Discipline': disc, 'Age Category': AGE,
            'Session Start Date': date, 'Round': rnd, 'Part': '', 'Apparatus': app}

def split_bp(vals, ctx):
    """Pen. and Bonus: signed, one decimal; the sign tells them apart. A bonus is written unsigned."""
    b = p = ''
    for v in vals:
        if not re.fullmatch(r'[-+]\d+\.\d+', v):
            err(f'{ctx}: unexpected token {v!r}'); continue
        if v.startswith('-'):
            if p: err(f'{ctx}: two penalties')
            p = v
        else:
            if b: err(f'{ctx}: two bonuses')
            b = v[1:]
    return b, p

RANK = r'(=?\d+|\*)'
ROW_RE = re.compile(r'^\s*' + RANK + r'\s+(\d{3})\s+(.+?)\s{2,}([A-Z]{3})\s+(\d+\.\d)\s+(\d+\.\d{3})'
                    r'((?:\s+[-+]\d+\.\d+)*)\s+(\d+\.\d{3})(?:\s+(Q|R\d|NR))?(?:\s+(\d+)\s+(\d+))?\s*$')
DNS_RE = re.compile(r'^\s*(\*\s+)?(\d{3})\s+(.+?)\s{2,}([A-Z]{3})\s+DNS(?:\s+(\d+)\s+(\d+))?\s*$')

def single_table(disc, idx, ctx, final):
    rows = []
    for l in lines(disc, idx):
        m = ROW_RE.match(l)
        if m:
            rank, bib, name, noc, d, e, bp, tot, q, qrank, order = m.groups()
            if final != (qrank is not None):
                err(f'{ctx} bib {bib}: qualification rank / start order columns {qrank} {order}')
            b, p = split_bp(bp.split(), f'{ctx} bib {bib}')
            checks.check_sum(f'{ctx} bib {bib}', tot, d, e, b, p)
            rows.append(dict(Rank=check_rank(ctx, rank, noc, bib), Bib=bib, NOC=noc, Status='COMPLETED', D=d, E=e,
                             B=b, Penalty=p, Total=tot, Q=q or ''))
            continue
        m = DNS_RE.match(l)
        if m:
            star, bib, name, noc, qrank, order = m.groups()
            if star:
                check_rank(ctx, '*', noc, bib)
            if final != (qrank is not None):
                err(f'{ctx} bib {bib}: qualification rank / start order columns {qrank} {order}')
            rows.append(dict(Rank='', Bib=bib, NOC=noc, Status='DNS', D='', E='', B='', Penalty='', Total='', Q=''))
            continue
        if re.match(r'^\s*(=?\d+|\*)\s+\d{3}\s', l) or re.search(r'\bDN[SF]\s*$', l):
            err(f'{ctx}: unparsed {l!r}')
    n = sum(1 for l in lines(disc, idx) if re.match(r'^\s*(=?\d+|\*)?\s+\d{3}\s+\S', l))
    if n != len(rows):
        err(f'{ctx}: parsed {len(rows)} rows, counted {n}')
    checks.check_rank_order(ctx, rows)
    return rows

QUAL = defaultdict(dict)    # disc -> (app, bib) -> routine dict, for cross-checking team/AA reports
TABLES = defaultdict(dict)  # disc -> (rnd, app) -> rows, for the tie-break and qualifier lists

def app_pages(disc, rnd, app, sfx):
    phase = '900' if rnd == 'QUAL' else '100'
    what = 'Qualification' if rnd == 'QUAL' else 'Final'
    unit = APPS[disc].index(app) + 3
    return find(disc, rf'GA{G[disc]}\d0{unit}{phase}_{sfx}', title(disc, f'{APP_NAME[app]} {what}'))

def single_app(disc, rnd, app):
    ctx = f'{disc} {rnd} {app}'
    rows = single_table(disc, app_pages(disc, rnd, app, '73I'), ctx, rnd == 'EVENT')
    if app == 'VT':
        return rows
    TABLES[disc][(rnd, app)] = rows
    out_rows = []
    for r in rows:
        row = meta(disc, rnd, app) | {'Rank': r['Rank'], 'Bib': r['Bib'], 'Name': check_name(ctx, r['Bib'], r['NOC']),
                                      'NOC Code': r['NOC'], 'Status': r['Status'], 'D': r['D'], 'E': r['E'],
                                      'B': r['B'], 'Penalty': r['Penalty'], 'SJ Penalty': '', 'Total': r['Total']}
        if rnd == 'QUAL':
            QUAL[disc][(app, r['Bib'])] = r
            row |= {'Qualification': r['Q'], 'Qualification Rank': r['Rank']}
        out_rows.append(row)
    out.csv(f'{prefix(disc)}-SCORES-{rnd}-{app}.csv', common.score_header(False, rnd == 'QUAL'), out_rows)

def vault_attempt(tokens, ctx):
    """D E [pen/bonus...] VaultScore -> routine dict, remaining tokens."""
    if tokens[0] == 'DNS':
        return dict(Status='DNS', D='', E='', B='', Penalty='', Total=''), tokens[1:]
    d, e, i = tokens[0], tokens[1], 2
    while i < len(tokens) and not re.fullmatch(r'\d+\.\d{3}', tokens[i]):
        i += 1
    if i == len(tokens):
        err(f'{ctx}: no vault score in {tokens}')
        return dict(Status='DNS', D='', E='', B='', Penalty='', Total=''), []
    b, p = split_bp(tokens[2:i], ctx)
    tot = tokens[i]
    checks.check_sum(ctx, tot, d, e, b, p)
    status = 'INVALID_VAULT' if D(tot) == 0 else 'COMPLETED'
    return dict(Status=status, D=d, E=e, B=b, Penalty=p, Total=tot), tokens[i + 1:]

def double_table(disc, rnd):
    ctx = f'{disc} {rnd} VT double'
    ls = lines(disc, app_pages(disc, rnd, 'VT', '73J'))
    rows, cur = [], None
    for l in ls:
        m = re.match(r'^\s*' + RANK + r'?\s+(\d{3})\s+(.+?)\s{2,}([A-Z]{3})\s+1\s+(.*)$', l)
        if m:
            rank, bib, name, noc, rest = m.groups()
            t = rest.split()
            if rnd == 'EVENT':
                if not (re.fullmatch(r'\d+', t[-1]) and re.fullmatch(r'\d+', t[-2])):
                    err(f'{ctx} bib {bib}: no qualification rank / start order')
                t = t[:-2]
            q = t.pop() if t[-1] in MARKERS else ''
            v1, t = vault_attempt(t, f'{ctx} bib {bib} v1')
            bonus = ''
            if len(t) == 2:   # WAG: the combined +0.2 between vault 1's score and the result
                bonus = t.pop(0)
                if not re.fullmatch(r'\+\d\.\d', bonus):
                    err(f'{ctx} bib {bib}: bad combined bonus {bonus}')
                bonus = bonus[1:]
            if len(t) != 1:
                err(f'{ctx} bib {bib}: leftover {t}'); t = ['']
            cur = dict(Rank=check_rank(ctx, rank or '', noc, bib) if rank else '', Bib=bib, NOC=noc, v1=v1,
                       Bonus=bonus, Total=t[0], Q=q)
            rows.append(cur)
            continue
        m = re.match(r'^\s+2\s+(.*)$', l)
        if m and cur is not None and 'v2' not in cur:
            v2, t = vault_attempt(m.group(1).split(), f'{ctx} bib {cur["Bib"]} v2')
            if t: err(f'{ctx} bib {cur["Bib"]}: leftover v2 {t}')
            cur['v2'] = v2
            if cur['Total'] not in ('DNF', 'DNS'):
                checks.check_vault_average(f'{ctx} bib {cur["Bib"]}', cur['v1']['Total'], v2['Total'],
                                           cur['Bonus'], cur['Total'])
            continue
        if re.match(r'^\s*(=?\d+|\*)\s+\d{3}\s', l):
            err(f'{ctx}: unparsed {l!r}')
    if any('v2' not in r for r in rows):
        err(f'{ctx}: missing vault 2 line')
    n = sum(1 for l in ls if re.match(r'^\s*(=?\d+|\*)?\s+\d{3}\s+\S.*\s1\s', l))
    if n != len(rows):
        err(f'{ctx}: parsed {len(rows)} rows, counted {n}')
    checks.check_rank_order(ctx, [dict(r, Total='' if r['Total'] in ('DNS', 'DNF') else r['Total'])
                                  for r in rows])
    return rows

def vault_cols(n, v):
    return {f'Status{n}': v['Status'], f'D{n}': v['D'], f'E{n}': v['E'], f'B{n}': v['B'],
            f'Penalty{n}': v['Penalty'], f'SJ Penalty{n}': '', f'Total{n}': v['Total']}

BLANK_V = dict(Status='', D='', E='', B='', Penalty='', Total='')

def vault(disc, rnd):
    ctx = f'{disc} {rnd} VT'
    double = double_table(disc, rnd)
    rows = []
    if rnd == 'QUAL':
        single = single_app(disc, 'QUAL', 'VT')
        dbl = {r['Bib']: r for r in double}
        for s in single:
            v1 = {k: s[k] for k in ('Status', 'D', 'E', 'B', 'Penalty', 'Total')}
            if v1['Status'] == 'COMPLETED' and D(v1['Total']) == 0:
                v1['Status'] = 'INVALID_VAULT'
            QUAL[disc][('VT', s['Bib'])] = s
            r = dbl.pop(s['Bib'], None)
            if r is None:
                v2, bonus, total, q, qrank = BLANK_V, '', s['Total'], '', ''
            else:
                # The double list prints D to one decimal, as the single list does
                if r['v1'] != v1 and not (r['v1']['Status'] == v1['Status'] == 'DNS'):
                    err(f'{ctx} bib {s["Bib"]}: single/double vault 1 differ {v1} vs {r["v1"]}')
                v2 = r['v2'] if r['v2']['Status'] != 'DNS' else dict(BLANK_V, Status='DNS')
                bonus, q, qrank = r['Bonus'], r['Q'], r['Rank']
                total = '' if r['Total'] in ('DNF', 'DNS') else r['Total']
            row = meta(disc, rnd, 'VT') | {'Rank': s['Rank'], 'Bib': s['Bib'],
                                           'Name': check_name(ctx, s['Bib'], s['NOC']), 'NOC Code': s['NOC']}
            row |= vault_cols(1, v1) | vault_cols(2, v2) | {'Combined Bonus': bonus, 'Total': total,
                                                             'Qualification': q, 'Qualification Rank': qrank}
            rows.append(row)
        if dbl:
            err(f'{ctx}: double-list bibs not on the single list: {list(dbl)}')
    else:
        for r in double:
            row = meta(disc, rnd, 'VT') | {'Rank': r['Rank'], 'Bib': r['Bib'],
                                           'Name': check_name(ctx, r['Bib'], r['NOC']), 'NOC Code': r['NOC']}
            row |= vault_cols(1, r['v1']) | vault_cols(2, r['v2']) | {'Combined Bonus': r['Bonus'],
                                                                       'Total': r['Total']}
            rows.append(row)
    # For the qualifier lists: the double list's ranking decides the vault final
    TABLES[disc][(rnd, 'VT')] = [dict(Rank=r['Rank'], Bib=r['Bib'], Total=r['Total'], Q=r['Q']) for r in double]
    out.csv(f'{prefix(disc)}-SCORES-{rnd}-VT.csv', common.score_header(True, rnd == 'QUAL'), rows)

# ---------------------------------------------------------------- team / all-around reports
ITEM = re.compile(r'(\d+\.\d{3})\s+(\d+\.\d{3})(?:\s+\((\d+)\))?|DNS')

def e_line(line, items, ctx):
    """The E line under a D line: one E per routine, left to right, each followed by its
    signed penalty/bonus. A long name can wrap onto it ahead of the `E`."""
    m = re.match(r'^\s*(?:\S.*?\s{2,})?E(\s|$)', line)
    if not m:
        err(f'{ctx}: expected E line, got {line!r}'); return
    done = [it for it in items if it['D'] is not None]
    k = -1
    for v in line[m.end():].split():
        if re.fullmatch(r'\d+\.\d{3}', v):
            k += 1
            if k >= len(done):
                err(f'{ctx}: more E values than routines'); return
            done[k]['E'] = v
        elif k >= 0 and re.fullmatch(r'[-+]\d+\.\d+', v):
            key = 'Penalty' if v.startswith('-') else 'B'
            if done[k][key]: err(f'{ctx}: two {key}')
            done[k][key] = v.lstrip('+')
        else:
            err(f'{ctx}: unexpected E-line token {v!r}')
    if k + 1 != len(done):
        err(f'{ctx}: {k + 1} E values for {len(done)} routines')

def routine(it, ctx):
    if it['D'] is None:
        return dict(Status='DNS', D='', E='', B='', Penalty='', Total='', Rank='')
    checks.check_sum(ctx, it['S'], it['D'], it['E'], it['B'], it['Penalty'])
    return dict(Status='COMPLETED', D=it['D'], E=it['E'], B=it['B'], Penalty=it['Penalty'], Total=it['S'],
                Rank=it['Rk'] or '')

def aa_report(disc, rnd):
    """All-Around Qualification (rnd QUAL) or All-Around Final (rnd AA) ranking."""
    sfx = '73G' if disc == 'MAG' else '73H'
    what = 'All-Around Qualification' if rnd == 'QUAL' else 'All-Around Final'
    ls = lines(disc, find(disc, rf'GA{G[disc]}\d02900_{sfx}', title(disc, what)))
    n, ctx0, athletes = len(APPS[disc]), f'{disc} {rnd} AA', []
    for i, l in enumerate(ls):
        m = re.match(r'^\s*' + RANK + r'?\s+(\d{3})\s+(.+?)\s{2,}([A-Z]{3})\s+D\s(.*)$', l)
        if not m:
            if re.match(r'^\s*(=?\d+|\*)\s+\d{3}\s', l): err(f'{ctx0}: unparsed {l!r}')
            continue
        rank, bib, name, noc, rest = m.groups()
        ctx = f'{ctx0} bib {bib}'
        items, end = [], 0
        for it in ITEM.finditer(rest):
            if len(items) == n: break
            end = it.end()
            items.append(dict(D=None) if it.group(0) == 'DNS' else
                         dict(D=it.group(1), S=it.group(2), Rk=it.group(3), E='', B='', Penalty=''))
        tail = rest[end:].split()
        if len(items) != n or not tail:
            err(f'{ctx}: {len(items)} apparatus items, tail {tail}'); continue
        e_line(ls[i + 1], items, ctx)
        apps = {app: routine(it, f'{ctx} {app}') for app, it in zip(APPS[disc], items)}
        total, q = tail[0], (tail[1] if len(tail) > 1 else '')
        if len(tail) > 2 or (q and q not in MARKERS):
            err(f'{ctx}: tail {tail}')
        if total not in ('DNF', 'DNS'):
            s = sum(D(v['Total']) for v in apps.values())
            if s != D(total): err(f'{ctx}: apparatus sum {s} != {total}')
        athletes.append(dict(Rank=check_rank(ctx0, rank or '', noc, bib) if rank else '', Bib=bib, NOC=noc,
                             apps=apps, Total='' if total in ('DNF', 'DNS') else total, Q=q))
    n_id = sum(1 for l in ls if re.match(r'^\s*(=?\d+|\*)?\s+\d{3}\s+\S.*?\s+D\s', l))
    if n_id != len(athletes): err(f'{ctx0}: parsed {len(athletes)} of {n_id}')
    checks.check_rank_order(ctx0, athletes)
    return athletes

def team_report(disc, rnd):
    """Team Qualification (rnd QUAL) or Team Final (rnd TEAM) ranking."""
    sfx = '73C' if disc == 'MAG' else '73D'
    what = 'Team Qualification' if rnd == 'QUAL' else 'Team Final'
    ls = lines(disc, find(disc, rf'GA{G[disc]}\d01900_{sfx}', title(disc, what)))
    n, ctx0 = len(APPS[disc]), f'{disc} {rnd} team'
    teams, team = [], None
    for i, l in enumerate(ls):
        m = re.match(r'^\s*(\d+|\*)\s+([A-Z]{3}) - (.+?)\s{2,}(\d.*)$', l)
        if m:
            rank, noc, _, rest = m.groups()
            base = m.start(4)
            # A total with a penalty taken off it is starred, the penalty noted on the next line
            cols = [(base + x.end(1), x.group(1), x.group(3), bool(x.group(2))) for x in
                    re.finditer(r'(\d+\.\d{3})(?:\s+(\*)?\((\d+)\))?', rest)]
            tail = rest.split()
            q = tail.pop() if tail[-1] in MARKERS else ''
            starred = tail[-1].startswith('*')
            pen = re.match(r'^\s+\* Penalty (-\d+\.\d+)\s*$', ls[i + 1])
            if (any(c[3] for c in cols) or starred) != bool(pen):
                err(f'{ctx0} {noc}: starred totals {[c[1] for c in cols if c[3]]} and penalty note {ls[i + 1]!r}')
            if len(cols) != n + 1:
                err(f'{ctx0} {noc}: {len(cols) - 1} apparatus totals'); continue
            if (noc in INVITED) == any(c[2] for c in cols[:n]):
                err(f'{ctx0} {noc}: apparatus ranks printed {[c[2] for c in cols[:n]]}')
            team = dict(Rank=check_rank(ctx0, rank, noc), NOC=noc, cols=[c[0] for c in cols[:n]],
                        totals=[c[1] for c in cols[:n]], ranks=[c[2] or '' for c in cols[:n]],
                        Total=cols[n][1], Q=q, athletes=[], raw=[],
                        starred=[c[3] for c in cols[:n]], Penalty=pen.group(1) if pen else '')
            teams.append(team)
            continue
        m = re.match(r'^\s+(\d{3}) (.+?)\s{2,}D(\s.*)?$', l)
        if m and team is not None:
            base = m.start(3) if m.group(3) else len(l)
            items = [(base + it.end(), dict(D=None) if it.group(0) == 'DNS' else
                      dict(D=it.group(1), S=it.group(2), Rk=None, E='', B='', Penalty=''))
                     for it in ITEM.finditer(m.group(3) or '')]
            team['raw'].append((m.group(1), i, items))
    for team in teams:
        # Header and athlete lines can sit a column apart on a page, so the apparatus columns are
        # where the team's own all-arounders' routines end (a DNS is right-aligned the same way)
        full = [items for _, _, items in team['raw'] if len(items) == n]
        cols = [sorted(items[k][0] for items in full)[len(full) // 2] for k in range(n)] if full else team['cols']
        if not full:
            print(f'  {ctx0} {team["NOC"]}: no all-arounder, columns from the header')
        for bib, i, raw in team['raw']:
            ctx = f'{ctx0} {team["NOC"]} bib {bib}'
            items = {}
            for pos, it in raw:
                a = min(range(n), key=lambda k: abs(cols[k] - pos))
                if abs(cols[a] - pos) > 3: err(f'{ctx}: routine ending at {pos} under no column {cols}')
                if a in items: err(f'{ctx}: two routines in column {a}')
                items[a] = it
            ordered = [items[a] for a in sorted(items)]
            if ordered:
                e_line(ls[i + 1], ordered, ctx)
            apps = {APPS[disc][a]: routine(it, f'{ctx} {APPS[disc][a]}') for a, it in sorted(items.items())}
            team['athletes'].append(dict(Bib=bib, NOC=team['NOC'], apps=apps))
    for t in teams:
        best = []
        for a, app in enumerate(APPS[disc]):
            sc = sorted((D(x['apps'][app]['Total']) for x in t['athletes']
                         if app in x['apps'] and x['apps'][app]['Total']), reverse=True)
            best.append(sum(sc[:3]))
            # A starred apparatus total has part of the team's penalty taken off it
            if sum(sc[:3]) != D(t['totals'][a]) and not t['starred'][a]:
                err(f'{ctx0} {t["NOC"]} {app}: best three {sum(sc[:3])} != {t["totals"][a]}')
        if sum(best) + D(t['Penalty']) != D(t['Total']):
            err(f'{ctx0} {t["NOC"]}: best threes {sum(best)} and penalty {t["Penalty"] or 0} != {t["Total"]}')
    checks.check_rank_order(ctx0, [dict(t, Bib=t['NOC']) for t in teams])
    return teams

def cross_check_qual(disc, athletes, ctx):
    """Every routine in a team/AA report equals the apparatus table's."""
    for a in athletes:
        for app, x in a['apps'].items():
            q = QUAL[disc].get((app, a['Bib']))
            if q is None:
                err(f'{ctx} bib {a["Bib"]} {app}: not in the apparatus table'); continue
            if x['Status'] != q['Status']:
                err(f'{ctx} bib {a["Bib"]} {app}: {x["Status"]} vs apparatus table {q["Status"]}'); continue
            # The apparatus tables print D to one decimal, the team and AA reports to three
            for k in ('D', 'E', 'B', 'Penalty', 'Total'):
                if (D(x[k]) if x[k] else x[k]) != (D(q[k]) if q[k] else q[k]):
                    err(f'{ctx} bib {a["Bib"]} {app} {k}: {x[k]!r} vs apparatus table {q[k]!r}')

def summary_meta(disc, rnd):
    ev = EVENTS[prefix(disc)]
    return {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': AGE, 'Event Start Date': ev['Start Date'],
            'Round': rnd, 'Part': ''}

SUMMARY_HEAD = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part']

def summary_team(disc, rnd, teams):
    hdr = SUMMARY_HEAD + ['Rank', 'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total']
    hdr += ['Qualification'] if rnd == 'QUAL' else ['Scores Round']
    rows = []
    for t in teams:
        r = summary_meta(disc, rnd) | {'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': t['Penalty'],
                                       'Total': t['Total'], 'Qualification': t['Q'], 'Scores Round': 'QUAL'}
        for a, app in enumerate(APPS[disc]):
            r[f'{app} Total'] = t['totals'][a]
        rows.append(r)
    out.csv(f'{prefix(disc)}-SUMMARY-{"QUAL" if rnd == "QUAL" else "FINAL"}-TEAM.csv', hdr, rows)

def summary_aa(disc, rnd, athletes):
    hdr = SUMMARY_HEAD + ['Rank', 'Bib', 'Name', 'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + \
          ['SJ Penalty', 'Total']
    hdr += ['Qualification'] if rnd == 'QUAL' else ['Scores Round']
    rows = []
    for a in athletes:
        r = summary_meta(disc, rnd) | {'Rank': a['Rank'], 'Bib': a['Bib'],
                                       'Name': check_name(f'{disc} {rnd} AA', a['Bib'], a['NOC']),
                                       'NOC Code': a['NOC'], 'SJ Penalty': '', 'Total': a['Total'],
                                       'Qualification': a['Q'], 'Scores Round': 'QUAL'}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = a['apps'][app]['Total']
        rows.append(r)
    out.csv(f'{prefix(disc)}-SUMMARY-{"QUAL" if rnd == "QUAL" else "FINAL"}-AA.csv', hdr, rows)

def check_final_ranking(ctx, qual, final, key, two_per_country):
    """A finals ranking re-ranks the qualification's `Q` rows, unchanged, in the same order."""
    qualified = [r for r in qual if r['Q'] == 'Q']
    if [r[key] for r in qualified] != [r[key] for r in final]:
        err(f'{ctx}: finalists {[r[key] for r in final]} != qualifiers {[r[key] for r in qualified]}')
    for q, f in zip(qualified, final):
        if q['Total'] != f['Total']:
            err(f'{ctx} {f[key]}: total {f["Total"]} != qualification {q["Total"]}')
    if [r['Rank'] for r in final] != [str(i) for i in range(1, len(final) + 1)]:
        err(f'{ctx}: ranks {[r["Rank"] for r in final]}')
    if two_per_country:
        per = defaultdict(int)
        for r in final:
            per[r['NOC']] += 1
        if max(per.values()) > 2:
            err(f'{ctx}: more than two per country')
    if any(r['Q'] for r in final):
        err(f'{ctx}: qualification markers on a final')

# ---------------------------------------------------------------- cross-checks
def tie_breaks(disc):
    """Tie-break reports list the tied athletes with the ranks the tables print."""
    for i, page in enumerate(PAGES[disc]):
        code = footer(page) or ''
        if not re.fullmatch(r'GA[MW]\d{6}_77[A-C]', code):
            continue
        head = [l.strip() for l in page.split('\n')[:10]]
        what = next((h for h in head if h.startswith(AGE_WORD[AGE] + ' ')), '')
        unit, phase = int(code[4:6]), code[6:9]
        if unit == 2:
            # The all-around tie-break is titled "All-Around Final" but ranks the qualification
            table = {r['Bib']: r['Rank'] for r in AA_QUAL[disc]}
        else:
            app = APPS[disc][unit - 3]
            rnd = 'QUAL' if phase == '900' else 'EVENT'
            table = {r['Bib']: r['Rank'] for r in TABLES[disc][(rnd, app)]}
        # A rank the report shares (equal E and D) but the table splits is written shared and logged
        corrected = {(c['Key'], c['Corrected']) for c in out.corrections.rows
                     if c['File'].startswith(f'{disc}-{AGE}-SCORES-') and c['Field'] == 'Rank'}
        n = 0
        for l in page.split('\n'):
            m = re.match(r'^\s*(=?\d+)\s+(\d{3})\s+\S', l)
            if m:
                n += 1
                rank, bib = m.group(1).lstrip('='), m.group(2)
                if table.get(bib) != rank and not (m.group(1).startswith('=') and (bib, rank) in corrected):
                    err(f'{disc} tie-break p{i + 1} ({what}): bib {m.group(2)} rank {m.group(1)} '
                        f'vs table {table.get(m.group(2))}')
        if not n:
            err(f'{disc} tie-break p{i + 1}: no rows')

def qualifier_lists(disc):
    """The List of Qualifiers and the finals start list name the same Q/R/NR as the tables, and each
    final's athletes are its qualifiers; a reserve or compatriot who replaced one is reported."""
    code = f'GA{G[disc]}000100_{"53B" if disc == "MAG" else "53C"}'
    ls = lines(disc, find(disc, code))
    # Two lists side by side, in the panel order of the icon legend; split at the second heading
    blocks, cur = [], None
    for l in ls:
        if re.match(r'^\s*Qualifying\s+NOC', l):
            split_at = l.index('Qualifying', 10)
            cur = ([], [])
            blocks.append(cur)
            continue
        if cur is None:
            continue
        for side, part in ((0, l[:split_at]), (1, l[split_at:])):
            m = re.match(r'^\s*(\d+|R\d|NR)\s+(\d{3})\s+\S.*?\s([A-Z]{3})\s+(\d+\.\d{3})\s*$', part)
            if m:
                cur[side].append(m.groups())
    lists = [side for b in blocks for side in b]
    if len(lists) != len(APPS[disc]):
        err(f'{disc} qualifiers: {len(lists)} lists'); return
    for app, lst in zip(APPS[disc], lists):
        table = TABLES[disc][('QUAL', app)]
        want = [(r['Q'], r['Bib']) for r in table if r['Q']]
        got = [('Q' if mark.isdigit() else mark, bib) for mark, bib, _, _ in lst]
        if sorted(want) != sorted(got):
            err(f'{disc} qualifiers {app}: list {got} vs table {want}')
        qualifiers = {bib for mark, bib in want if mark == 'Q'}
        finalists = {r['Bib'] for r in TABLES[disc][('EVENT', app)]}
        if finalists != qualifiers:
            print(f'  {disc} {app} final: qualifiers absent {sorted(qualifiers - finalists)}, '
                  f'in their place {sorted(finalists - qualifiers)}')
            for bib in finalists - qualifiers:
                if not any(b == bib for _, b in want):
                    err(f'{disc} {app} final: bib {bib} is neither a qualifier nor a reserve')

def medallists(disc):
    """Medallists by Event: the top three of each final, as ranked."""
    ls = lines(disc, find(disc, 'GA0000000_93'))
    medals, event = defaultdict(list), None
    for l in ls:
        m = re.match(r'^((?:Senior|Junior) \S+ [A-Za-z -]+?)\s{2,}\S{3} \d{2} [A-Z]{3}\s+(GOLD|SILVER|BRONZE)\s+(.+?)\s{2,}([A-Z]{3})\s*$', l)
        if m:
            event = m.group(1).split(' ', 2)[2]
            medals[event].append((m.group(2), m.group(3), m.group(4)))
            continue
        m = re.match(r'^\s+(GOLD|SILVER|BRONZE)\s+(.+?)\s{2,}([A-Z]{3})\s*$', l)
        if m and event:
            medals[event].append(m.groups())
    want = {'Team': [('', t['NOC']) for t in TEAM_FINAL[disc][:3]],
            'All-Around': [(r['Bib'], r['NOC']) for r in AA_FINAL[disc][:3]]}
    for app in APPS[disc]:
        rows = [r for r in TABLES[disc][('EVENT', app)] if r['Rank'] in ('1', '2', '3')]
        want[APP_NAME[app]] = [(r['Bib'], r.get('NOC', '')) for r in rows]
    for event, rows in want.items():
        got = medals.get(event, [])
        if [noc for _, noc in rows] != [noc for _, _, noc in got]:
            err(f'{disc} medallists {event}: {got} vs results {rows}')
        for (bib, _), (_, name, _) in zip(rows, got):
            if bib and NAMES[bib][0] != name:
                err(f'{disc} medallists {event}: {name} vs bib {bib} {NAMES[bib][0]}')

# ---------------------------------------------------------------- run
AA_QUAL, AA_FINAL, TEAM_FINAL = {}, {}, {}

for path in sys.argv[1:]:
    disc, AGE = book(path)
    print(f'===== {disc} {AGE}')
    PAGES[disc] = common.pdf_pages(path)
    QUAL[disc].clear(); TABLES[disc].clear()
    ev = EVENTS[prefix(disc)]
    participants(disc, ev)
    judges(disc, ev)
    for app in APPS[disc]:
        if app == 'VT':
            vault(disc, 'QUAL'); vault(disc, 'EVENT')
        else:
            single_app(disc, 'QUAL', app); single_app(disc, 'EVENT', app)

    tq = team_report(disc, 'QUAL')
    cross_check_qual(disc, [x for t in tq for x in t['athletes']], f'{disc} team qual')
    summary_team(disc, 'QUAL', tq)
    tf = team_report(disc, 'TEAM')
    cross_check_qual(disc, [x for t in tf for x in t['athletes']], f'{disc} team final')
    check_final_ranking(f'{disc} team final', tq, tf, 'NOC', False)
    for q, f in zip([t for t in tq if t['Q'] == 'Q'], tf):
        if (q['totals'], q['ranks'], q['Rank']) != (f['totals'], f['ranks'], f['Rank']):
            err(f'{disc} team final {f["NOC"]}: differs from its qualification row')
    summary_team(disc, 'TEAM', tf)
    TEAM_FINAL[disc] = tf

    AA_QUAL[disc] = aaq = aa_report(disc, 'QUAL')
    cross_check_qual(disc, aaq, f'{disc} AA qual')
    summary_aa(disc, 'QUAL', aaq)
    AA_FINAL[disc] = aaf = aa_report(disc, 'AA')
    cross_check_qual(disc, aaf, f'{disc} AA final')
    check_final_ranking(f'{disc} AA final', aaq, aaf, 'Bib', True)
    summary_aa(disc, 'AA', aaf)

    # Vault double list rows carry their NOC for the medal check
    for r in TABLES[disc][('EVENT', 'VT')]:
        r['NOC'] = NAMES[r['Bib']][1]
    tie_breaks(disc)
    qualifier_lists(disc)
    medallists(disc)

    NAMES.clear()
    out.manifest(prefix(disc), ev)

out.corrections.finish()
checks.finish()
