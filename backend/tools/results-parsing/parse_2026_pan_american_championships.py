"""Parse the 2026 Junior Pan American Championships results book into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_pan_american_championships.py \\
        data/2026/2026-PAN-AMERICAN-CHAMPIONSHIPS/18529-ResultsbookMedia-PanAms-JR.pdf

Writes PARTICIPANTS, JUDGES, SCORES-C1-*, SCORES-C3-*, RANKING-FINAL-AA, RANKING-FINAL-TEAM (Competition I decides both titles) and an
IMPORT.json for MAG JR and WAG JR next to the PDF, reading event metadata from the EVENT.csv already
there. Exits non-zero if any check fails (docs/instructions-results-parsing.md §3; this source
format is §5.4).

The book is the organizer's media book: entry lists, start lists, judges and medal pages from the
organizer, and results printed by sporttech.io. Qualification decides the team and all-around titles
(no team or all-around final), so there are no TEAM or AA sessions. Reports are found by page number
(below), each checked against its printed title and legend. Neither discipline has a single-vault
list: every vaulter's first vault comes from the all-around report (no vault rank is published, so
`Rank` is blank) and the two-vault list adds the second vault and the qualification ranking.

Every routine, rank and standing is compared with sporttech.io's export of the competition
(`SPORTTECH`); where the book differs (its tied ranks, which the export breaks), the export's value is
written and logged in the event's CORRECTIONS.csv, applied by `common.Output`.
"""
import os, re, sys, unicodedata
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common, sporttech
from common import D, split_given_first, split_surname_first

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
PAGES = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, '2026-PAN-AMERICAN-CHAMPIONSHIPS')
checks = common.Checks()
err = checks.err
corrections = common.Corrections(OUT, '2026-PAN-AMERICAN-CHAMPIONSHIPS', ['MAG-JR', 'WAG-JR'], err)
out = common.Output(OUT, corrections)
# sporttech.io's CSV export of the competition: every routine written is checked against it, and where
# it differs from the book, the export's value is written and logged in the event's CORRECTIONS.csv.
SPORTTECH = os.path.join(OUT, '18529-sporttech-export.csv')
EXPORT_TITLE = {'MAG': 'JUNIOR - Men', 'WAG': 'JUNIOR - Women'}
ROUND_OF_DATE = {'2026-06-18': 'QUAL', '2026-06-20': 'EVENT'}

PREFIX = {'MAG': '2026-PAN-AMERICAN-CHAMPIONSHIPS-MAG-JR', 'WAG': '2026-PAN-AMERICAN-CHAMPIONSHIPS-WAG-JR'}
EVENT_NAME = EVENTS[PREFIX['MAG']]['Title']
EVENT_START = EVENTS[PREFIX['MAG']]['Start Date']
if any(EVENTS[p]['Title'] != EVENT_NAME or EVENTS[p]['Start Date'] != EVENT_START for p in PREFIX.values()):
    raise SystemExit('MAG and WAG rows in EVENT.csv are expected to share a title and start date')
AGE = 'JR'
# All-around report column order (legend), and the RANKING column order (import-file-model.md).
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
LEGEND = {'Floor': 'FX', 'Pommel Horse': 'PH', 'Rings': 'SR', 'Vault': 'VT', 'Parallel Bars': 'PB',
          'High Bar': 'HB', 'Uneven Bars': 'UB', 'Beam': 'BB'}
FINAL_TITLE = {'floor': 'FX', 'pommel horse': 'PH', 'rings': 'SR', 'vault': 'VT', 'parallel bars': 'PB',
               'high bar': 'HB', 'uneven bars': 'UB', 'beam': 'BB'}
# From the Competition Schedule page (p. 2): qualification Thu 18 Jun, apparatus finals Sat 20 Jun.
SESSION_DATE = {'QUAL': '2026-06-18', 'EVENT': '2026-06-20'}

# Physical pages (1-based, inclusive) of each report.
REPORTS = {
    'MAG': {'entries': (8, 9), 'judges': {'QUAL': 22, 'EVENT': 59}, 'aa': (23, 24), 'team': (26, 29),
            'qual': {'FX': (31, 35), 'PH': (36, 40), 'SR': (41, 45), 'PB': (48, 52), 'HB': (53, 57)},
            'vault': (46, 47), 'finalists': 58,
            'finals': {'FX': 60, 'PH': 61, 'SR': 62, 'VT': 63, 'PB': 64, 'HB': 65}},
    'WAG': {'entries': (72, 74), 'judges': {'QUAL': 83, 'EVENT': 112}, 'aa': (84, 87), 'team': (89, 91),
            'qual': {'UB': (96, 100), 'BB': (101, 105), 'FX': (106, 110)},
            'vault': (93, 95), 'finalists': 111,
            'finals': {'VT': 113, 'UB': 114, 'BB': 115, 'FX': 116}},
}
# The book's WAG uneven bars qualification table stops at rank 50 (p. 99). The athletes it leaves out are
# written from the all-around report with no rank; their ranks are corrections, from sporttech.io.
TRUNCATED = {('WAG', 'UB'): 50}
ENTRY_COUNTS = 3                          # "Number of Entries by NOC"
# Finalists pages: apparatus in the order their blocks appear (left to right, then top to bottom).
FINALIST_GRID = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}

def lines(first, last=None):
    return [l for i in range(first - 1, (last or first)) for l in PAGES[i].split('\n')]

def text(first, last=None):
    return '\n'.join(lines(first, last))

def legend_apps(first, last):
    return [LEGEND[a] for a in re.findall(r'– (Floor|Pommel Horse|Rings|Vault|Parallel Bars|High Bar|Uneven Bars|Beam)\b',
                                         text(first, last))]

def plain(s):
    """Upper case without accents, for comparing the many spellings of a name."""
    return ''.join(c for c in unicodedata.normalize('NFD', s.upper()) if unicodedata.category(c) != 'Mn')

# ---------------------------------------------------------------- participants
PEOPLE = {}   # bib -> dict(name, noc, year, legal)

def entry_counts():
    m = re.search(r'TOTAL:\s+\d+\s+(\d+)\s+(\d+)\s+(\d+)', text(ENTRY_COUNTS))
    return {'MAG': int(m.group(1)), 'WAG': int(m.group(2))}

def participants(disc):
    first, last = REPORTS[disc]['entries']
    rows, noc = [], None
    for l in lines(first, last):
        m = re.match(r'^\s*([A-Z]{3})\s+(?:- )?[A-Z][a-z]', l)
        if m:
            noc = m.group(1)
            continue
        m = re.match(r'^\s{2,}(\S.+?)\s{2,}(\S.+?)\s{2,}(\d+|En tramite)\s+(\d{3})\s+(\d{4})\s*$', l)
        if not m:
            if re.search(r'\s\d{3}\s+\d{4}\s*$', l):
                err(f'participants {disc}: unparsed {l!r}')
            continue
        legal, name, lic, bib, year = m.groups()
        # A pending licence ("En tramite") is written blank; one found since is a correction
        if not lic.isdigit() and lic != 'En tramite':
            err(f'participants {disc}: bib {bib} licence {lic!r}')
        sur, giv = split_given_first(name)
        if not sur or not giv:
            err(f'participants {disc}: name split {name!r} -> {sur!r}/{giv!r}')
        PEOPLE[bib] = dict(name=name, noc=noc, year=year, legal=legal)
        rows.append({'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE,
                     'Event Start Date': EVENT_START, 'Order': len(rows) + 1, 'NOC Code': noc,
                     'Bib Number': bib, 'FIG License': lic if lic.isdigit() else '', 'Name': name,
                     'Surname': sur, 'Given Name': giv, 'Birth Year': year, 'Birth Date': ''})
    if len(rows) != entry_counts()[disc]:
        err(f'participants {disc}: {len(rows)} entries, "Number of Entries" says {entry_counts()[disc]}')
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)

def check_identity(ctx, bib, name, year, noc):
    """Results print `SURNAME Given`, often shortened or spelled differently from the entry list;
    every surname word must appear in the entry list's full legal name."""
    p = PEOPLE.get(bib)
    if not p:
        err(f'{ctx}: bib {bib} not in participants'); return
    if noc and noc != p['noc']:
        err(f'{ctx}: bib {bib} NOC {noc} != participants {p["noc"]}')
    if year and year != p['year']:
        err(f'{ctx}: bib {bib} birth year {year} != participants {p["year"]}')
    surname = split_surname_first(name)[0] or name.split()[0]
    legal = plain(p['legal'] + ' ' + p['name']).split()
    if not all(w in legal for w in plain(surname).split()):
        err(f'{ctx}: bib {bib} {name!r} does not match entry {p["legal"]!r}')

# ---------------------------------------------------------------- judges
JUDGE_FN = {'AS': 'SV', 'SA': 'SV', 'Línea': 'L', 'Línea1': 'L1', 'Línea2': 'L2', 'Tiempo': 'T',
            'Tiempo1': 'T1', 'Tiempo2': 'T2', 'Presidenta': 'President', 'Miembro': 'Member'}
# Panel order in the icon grid, left-to-right then top-to-bottom; confirmed by rendering the pages.
GRID = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}

def judge_noc(fed):
    # Supervisors are credited to the continental union: 'UPAG-ECU' -> ECU, plain 'UPAG' -> none.
    return '' if fed == 'UPAG' else fed.removeprefix('UPAG-')

def judges(disc):
    rows = []
    def add(rnd, app, fn, name, noc):
        if disc == 'MAG':   # 'SURNAME, Given'
            sur, giv = (s.strip() for s in name.split(',', 1))
        else:               # 'SURNAME Given'
            sur, giv = split_surname_first(name)
        if not sur or not giv:
            err(f'judges {disc}: name split {name!r}')
        rows.append({'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE,
                     'Event Start Date': EVENT_START, 'Competition': common.COMPETITION[rnd], 'Apparatus': app, 'Function': fn,
                     'Name': name, 'Surname': sur, 'Given Name': giv, 'NOC Code': judge_noc(noc)})
    for rnd, page in REPORTS[disc]['judges'].items():
        n_rnd, block, split_at, jury = len(rows), -1, None, False
        for l in lines(page):
            if re.search(r'Superior Jury:', l):
                jury = True
                l = l.split(':', 1)[1] if disc == 'MAG' else ''
            if jury and block < 0:
                if disc == 'MAG':     # names only, no function printed
                    m = re.match(r'^\s+([A-ZÁÉÍÓÚÑ][^,]+, \S.*?)\s*$', l)
                    if m:
                        add(rnd, '', 'Member', m.group(1), '')
                else:
                    m = re.match(r'^\s+\d+\s+(.+?)\s{2,}(UPAG\S*)\s+(\S+)\s*$', l)
                    if m:
                        add(rnd, '', JUDGE_FN[m.group(3)], m.group(1), m.group(2))
            if re.match(r'^\s*Función\s+Nombre\s+FED\s+Función', l):
                block += 1
                split_at = l.index('Función', l.index('FED'))
                continue
            if block >= 0 and split_at:
                for side, part in ((0, l[:split_at]), (1, l[split_at:])):
                    if not part.strip():
                        continue
                    m = re.match(r'^\s*([A-Z]\d?|[A-Z]{2}|Línea\d?|Tiempo\d?)\s+(?:\d+\s+|#\s+)?(.+?)\s{2,}(\S+)\s*$', part)
                    if not m or not re.fullmatch(r'(UPAG-)?[A-Z]{3}|UPAG', m.group(3)):
                        err(f'judges {disc} {rnd}: unparsed {part!r}')
                        continue
                    fn, name, noc = m.groups()
                    add(rnd, GRID[disc][block * 2 + side], JUDGE_FN.get(fn, fn), name, noc)
        if block + 1 != len(GRID[disc]) // 2:
            err(f'judges {disc} {rnd}: {block + 1} panel rows')
        print(f'  judges {disc} {rnd}: {len(rows) - n_rnd}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, rows)

# ---------------------------------------------------------------- result tables
ONE = r'-?\d+\.\d'
SCORE = r'\d+\.\d{3}'
IDENT = re.compile(r'^\s*(?P<mk>[QR]\d+)?\s*(?P<rank>\d+)?\.?\s*(?:Q\s*)?(?:\.\s*)?#(?P<bib>\d{3})\s+'
                   r'(?P<name>.+?)\s+(?P<year>\d{4})\s+(?:Not\s+)?(?P<noc>[A-Z]{3})(?:\s+(?P<vals>.*?))?\s*$')

def tokens(s, base):
    return [(base + m.start(), m.group()) for m in re.finditer(r'\S+', s)]

def blocks(first, last, ctx):
    """Athlete blocks of a sporttech.io table: the identity line plus the lines under it (bonus and
    penalty line, a Q/R marker pushed below the rank, a second vault). Stops at the legend."""
    out_, cur, paused = [], None, False
    for l in lines(first, last):
        if l.strip().startswith('Legend'):
            break
        m = IDENT.match(l)
        if m:
            cur = dict(mk=m['mk'] or '', rank=m['rank'] or '', bib=m['bib'], name=m['name'].strip(),
                       year=m['year'], noc=m['noc'], vals=tokens(m['vals'] or '', m.start('vals') if m['vals'] else 0),
                       extra=[])
            out_.append(cur)
            paused = False
            continue
        if 'Generated by' in l:
            paused = True
            continue
        if cur is None or paused or not l.strip():
            continue
        toks = tokens(l, 0)
        if re.fullmatch(r'[QR]\d+', toks[0][1]):
            if cur['mk']:
                err(f'{ctx}: bib {cur["bib"]} has two markers')
            cur['mk'] = toks[0][1]
            toks = toks[1:]
        toks = [t for t in toks if re.fullmatch(f'{ONE}|{SCORE}|0', t[1])]
        if toks:
            cur['extra'].append(toks)
    n = len(re.findall(r'#\d{3}\s', text(first, last).split('Legend')[0]))
    if len(out_) != n:
        err(f'{ctx}: parsed {len(out_)} athletes of {n}')
    for b in out_:
        check_identity(ctx, b['bib'], b['name'], b['year'], b['noc'])
    return out_

def groups(vals, n, ctx):
    """Split a row's values into `n` routines — D E Total, '—' (no routine), '… … DNS', or a bare '0'
    (scored zero) — and return them with whatever is left over (the row's overall totals)."""
    gs, i = [], 0
    v = [t for _, t in vals]
    while len(gs) < n:
        if i >= len(v):
            err(f'{ctx}: {len(gs)} of {n} routines in {v}'); break
        pos = vals[i][0]
        if v[i] == '—':
            gs.append(dict(kind='none', pos=pos)); i += 1
        elif v[i] == '…' and v[i + 1:i + 3] == ['…', 'DNS']:
            gs.append(dict(kind='dns', pos=pos)); i += 3
        elif v[i] == '0':
            gs.append(dict(kind='zero', pos=pos, Total='0')); i += 1
        elif i + 2 < len(v) and re.fullmatch(ONE, v[i]) and re.fullmatch(SCORE, v[i + 1]) and re.fullmatch(SCORE, v[i + 2]):
            gs.append(dict(kind='routine', pos=pos, D=v[i], E=v[i + 1], B='', Penalty='', Total=v[i + 2])); i += 3
        else:
            err(f'{ctx}: unexpected value {v[i]!r} in {v}'); break
    return gs, v[i:]

def place_bp(gs, extra, ctx):
    """Bonus and penalty sit on the line below, under their routine's D and E: assign each by
    position, and by sign (bonus positive, penalty negative)."""
    for toks in extra:
        for pos, t in toks:
            if not re.fullmatch(ONE, t):
                err(f'{ctx}: unexpected {t!r} under the row'); continue
            g = [g for g in gs if g['pos'] <= pos + 3]
            g = g[-1] if g else gs[0]
            if g['kind'] != 'routine':
                err(f'{ctx}: {t} under a {g["kind"]} routine'); continue
            col = 'Penalty' if t.startswith('-') else 'B'
            if g[col]:
                err(f'{ctx}: two values for {col}')
            g[col] = t
    for g in gs:
        if g['kind'] == 'routine':
            checks.check_sum(ctx, g['Total'], g['D'], g['E'], g['B'], g['Penalty'])

def inline_vault(v, ctx):
    """A vault on the two-vault list prints in one line: D [B] E [Pen] Total."""
    if v and v[0] == '0':
        return dict(kind='zero', D='', E='', B='', Penalty='', Total='0'), v[1:]
    try:
        r = dict(kind='routine', D=v.pop(0), B='', Penalty='')
        if re.fullmatch(ONE, v[0]) and not v[0].startswith('-'):
            r['B'] = v.pop(0)
        r['E'] = v.pop(0)
        if re.fullmatch(ONE, v[0]) and v[0].startswith('-'):
            r['Penalty'] = v.pop(0)
        r['Total'] = v.pop(0)
    except IndexError:
        err(f'{ctx}: short vault line'); return None, []
    if not (re.fullmatch(ONE, r['D']) and re.fullmatch(SCORE, r['E']) and re.fullmatch(SCORE, r['Total'])):
        err(f'{ctx}: vault values {r}')
    checks.check_sum(ctx, r['Total'], r['D'], r['E'], r['B'], r['Penalty'])
    return r, v

STATUS = {'routine': 'COMPLETED', 'dns': 'DNS', 'zero': 'COMPLETED'}

def routine_cols(g, suffix='', vault=False):
    if g is None:
        return {f'{c}{suffix}': '' for c in common.ROUTINE}
    status = 'INVALID_VAULT' if vault and g['kind'] == 'zero' else STATUS[g['kind']]
    return {f'Status{suffix}': status, f'D{suffix}': g.get('D', ''), f'E{suffix}': g.get('E', ''),
            f'B{suffix}': g.get('B', ''), f'Penalty{suffix}': g.get('Penalty', ''), f'SJ Penalty{suffix}': '',
            f'Total{suffix}': g.get('Total', '')}

def meta(disc, rnd, app, b):
    return {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE,
            'Competition Start Date': SESSION_DATE[rnd], 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app,
            'Rank': b['rank'], 'Bib': b['bib'], 'Name': PEOPLE[b['bib']]['name'], 'NOC Code': b['noc']}

def same_routine(ctx, a, b):
    keys = ['kind', 'D', 'E', 'B', 'Penalty', 'Total']
    if [a.get(k, '') for k in keys] != [b.get(k, '') for k in keys]:
        err(f'{ctx}: {[a.get(k, "") for k in keys]} != all-around {[b.get(k, "") for k in keys]}')

# ---------------------------------------------------------------- all-around and team reports
def aa_report(disc):
    first, last = REPORTS[disc]['aa']
    ctx = f'{disc} all-around'
    if legend_apps(first, last) != APPS[disc]:
        err(f'{ctx}: legend {legend_apps(first, last)}')
    athletes = []
    for b in blocks(first, last, ctx):
        c = f'{ctx} bib {b["bib"]}'
        gs, rest = groups(b['vals'], len(APPS[disc]), c)
        place_bp(gs, b['extra'], c)
        total = rest[0] if len(rest) == 1 else err(f'{c}: totals {rest}') or ''
        apps = dict(zip(APPS[disc], gs))
        done = [g for g in gs if g['kind'] in ('routine', 'zero')]
        if re.fullmatch(SCORE, total):
            if sum(D(g['Total']) for g in done) != D(total):
                err(f'{c}: apparatus sum != {total}')
        elif total not in ('DNF', 'DNS', '—'):
            err(f'{c}: total {total!r}')
        athletes.append(dict(Rank=b['rank'], Bib=b['bib'], NOC=b['noc'], apps=apps,
                             Total=total if re.fullmatch(SCORE, total) else ''))
    checks.check_rank_order(ctx, [dict(Rank=a['Rank'], Total=a['Total'], Bib=a['Bib']) for a in athletes])
    return athletes

def summary_aa(disc, athletes):
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'Bib', 'Name',
           'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for a in athletes:
        if all(g['kind'] == 'none' for g in a['apps'].values()):
            continue          # entered but competed on nothing (a team's fifth member)
        r = {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE, 'Event Start Date': EVENT_START,
             'Competition': 'C1', 'Part': '', 'Rank': a['Rank'], 'Bib': a['Bib'], 'Name': PEOPLE[a['Bib']]['name'],
             'NOC Code': a['NOC'], 'SJ Penalty': '', 'Total': a['Total'], 'Qualification': ''}
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = a['apps'][app].get('Total', '')
        rows.append(r)
    out.ranking(PREFIX[disc], 'AA', hdr, rows, EVENTS[PREFIX[disc]])

def team_report(disc, aa):
    first, last = REPORTS[disc]['team']
    ctx = f'{disc} team'
    by_bib = {a['Bib']: a for a in aa}
    n = len(APPS[disc])
    teams, team, want_total = [], None, False
    for l in lines(first, last):
        if l.strip().startswith('Legend'):
            break
        m = re.match(r'^\s*(\d+)\.\s*(?:T\d+\s*\.?)?\s+([A-Z]{3})\s+(.*)$', l)
        if m:
            vals = re.findall(SCORE, m.group(3))
            starts = [m.start(3) + x.start() for x in re.finditer(SCORE, m.group(3))]
            team = dict(Rank=m.group(1), NOC=m.group(2), totals=vals[:n], starts=starts[:n],
                        Total=vals[n] if len(vals) > n else '', athletes={})
            want_total = not team['Total']
            teams.append(team)
            continue
        if want_total:
            m = re.search(rf'\s({SCORE})\s*$', l)
            if m:
                team['Total'], want_total = m.group(1), False
                continue
        m = re.match(r'^\s+#(\d{3})\s+.+?\s(\d{4})\s+(.*)$', l)
        if m and team:
            bib = m.group(1)
            vals = list(re.finditer(r'\S+', m.group(3)))
            apps = team['athletes'].setdefault(bib, {})
            if len(vals) == n:
                apps.update(zip(APPS[disc], (x.group() for x in vals)))
                continue
            # A skipped apparatus is left blank: place each value under the nearest team total (§2.6).
            prev = -1
            for x in vals:
                start = m.start(3) + x.start()
                a = min(range(n), key=lambda k: abs(team['starts'][k] - start))
                if abs(team['starts'][a] - start) > 6 or a <= prev:
                    err(f'{ctx} bib {bib}: {x.group()} not under an apparatus')
                apps[APPS[disc][a]], prev = x.group(), a
    for t in teams:
        c = f'{ctx} {t["NOC"]}'
        for app, total in zip(APPS[disc], t['totals']):
            got = []
            for bib, apps in t['athletes'].items():
                v = apps.get(app, '')
                g = by_bib[bib]['apps'][app]
                want = {'routine': g.get('Total'), 'zero': '0', 'dns': 'DNS', 'none': '—'}[g['kind']]
                if v != want and not (v == '' and g['kind'] in ('none', 'zero')):
                    err(f'{c} bib {bib} {app}: {v!r} != all-around {want!r}')
                if g['kind'] in ('routine', 'zero'):
                    got.append(D(g['Total']))
            if sum(sorted(got, reverse=True)[:3]) != D(total):
                err(f'{c} {app}: best three {sum(sorted(got, reverse=True)[:3])} != {total}')
        if sum(D(x) for x in t['totals']) != D(t['Total']):
            err(f'{c}: apparatus totals != {t["Total"]}')
        if any(by_bib[b]['NOC'] != t['NOC'] for b in t['athletes']):
            err(f'{c}: athlete from another NOC')
    checks.check_rank_order(ctx, [dict(Rank=t['Rank'], Total=t['Total'], Bib=t['NOC']) for t in teams])
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'NOC Code'] + \
          [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for t in teams:
        r = {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE, 'Event Start Date': EVENT_START,
             'Competition': 'C1', 'Part': '', 'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': '',
             'Total': t['Total'], 'Qualification': ''}
        for app, total in zip(APPS[disc], t['totals']):
            r[f'{app} Total'] = total
        rows.append(r)
    out.ranking(PREFIX[disc], 'TEAM', hdr, rows, EVENTS[PREFIX[disc]])

# ---------------------------------------------------------------- qualification
def qualification(mk):
    # Q1…Q8 number the qualifiers in order; the stored value is Q. Reserves keep R1…R3.
    return 'Q' if mk.startswith('Q') else mk

def check_markers(ctx, ranked):
    """Q1…Q8 then R1…R3, numbered in rank order."""
    qs = [r['mk'] for r in ranked if r['mk'].startswith('Q')]
    rs = [r['mk'] for r in ranked if r['mk'].startswith('R')]
    if qs != [f'Q{i}' for i in range(1, len(qs) + 1)] or rs != [f'R{i}' for i in range(1, len(rs) + 1)]:
        err(f'{ctx}: markers out of order {qs} {rs}')
    last_q = max((i for i, r in enumerate(ranked) if r['mk'].startswith('Q')), default=-1)
    if any(r['mk'].startswith('R') for r in ranked[:last_q]):
        err(f'{ctx}: a reserve ranked above a qualifier')

def qual_app(disc, app, aa):
    first, last = REPORTS[disc]['qual'][app]
    ctx = f'{disc} QUAL {app}'
    if legend_apps(first, last) != [app]:
        err(f'{ctx}: legend {legend_apps(first, last)}')
    bs = blocks(first, last, ctx)
    rows = []
    for b in bs:
        c = f'{ctx} bib {b["bib"]}'
        gs, rest = groups(b['vals'], 1, c)
        if rest:
            err(f'{c}: extra values {rest}')
        place_bp(gs, b['extra'], c)
        g = gs[0]
        # PB and HB also list team members who competed nothing, whom the all-around report leaves out.
        same_routine(c, g, aa[b['bib']]['apps'][app] if b['bib'] in aa else dict(kind='none'))
        if g['kind'] == 'none':
            if b['rank'] or b['mk']:
                err(f'{c}: ranked without a routine')
            continue
        rows.append({**meta(disc, 'QUAL', app, b), **routine_cols(g), 'Qualification': qualification(b['mk']),
                     'Qualification Rank': b['rank']})
    if (disc, app) in TRUNCATED:
        if max(int(b['rank']) for b in bs if b['rank']) != TRUNCATED[(disc, app)]:
            err(f'{ctx}: the table no longer stops at rank {TRUNCATED[(disc, app)]}')
        listed = {b['bib'] for b in bs}
        for bib, a in aa.items():
            if a['apps'][app]['kind'] != 'none' and bib not in listed:
                rows.append({**meta(disc, 'QUAL', app, dict(rank='', bib=bib, noc=a['NOC'])),
                             **routine_cols(a['apps'][app]), 'Qualification': '', 'Qualification Rank': ''})
    aa_bibs = {bib for bib, a in aa.items() if a['apps'][app]['kind'] != 'none'}
    if {r['Bib'] for r in rows} != aa_bibs:
        err(f'{ctx}: athletes differ from the all-around report: {sorted({r["Bib"] for r in rows} ^ aa_bibs)}')
    checks.check_rank_order(ctx, rows)
    check_markers(ctx, [b for b in bs if b['rank']])
    out.csv(f'{PREFIX[disc]}-SCORES-C1-{app}.csv', common.score_header(False, True), rows)
    return {r['Bib']: r['Qualification'] for r in rows if r['Qualification']}

def qual_vault(disc, aa):
    first, last = REPORTS[disc]['vault']
    ctx = f'{disc} QUAL VT'
    if set(legend_apps(first, last)) != {'VT'}:
        err(f'{ctx}: legend {legend_apps(first, last)}')
    double = {}
    bs = blocks(first, last, ctx)
    for b in bs:
        c = f'{ctx} bib {b["bib"]}'
        v1, rest = inline_vault([t for _, t in b['vals']], c + ' vault 1')
        if len(rest) != 1:
            err(f'{c}: totals {rest}')
        if len(b['extra']) != 1:
            err(f'{c}: {len(b["extra"])} lines for vault 2'); continue
        v2, rest2 = inline_vault([t for _, t in b['extra'][0]], c + ' vault 2')
        if rest2:
            err(f'{c}: extra values {rest2}')
        same_routine(c + ' vault 1', v1, aa[b['bib']]['apps']['VT'])
        checks.check_vault_average(c, v1['Total'], v2['Total'], '', rest[0] if rest else '')
        double[b['bib']] = dict(b=b, v2=v2, Total=rest[0] if rest else '')
    ranked = [b for b in bs if b['rank']]
    for x, y in zip(ranked, ranked[1:]):
        if int(y['rank']) < int(x['rank']) or D(double[y['bib']]['Total']) > D(double[x['bib']]['Total']):
            err(f'{ctx}: two-vault rank order broken at bib {y["bib"]}')
    check_markers(ctx, ranked)
    rows = []
    for a in aa.values():
        g = a['apps']['VT']
        if g['kind'] == 'none':
            continue
        b = dict(rank='', bib=a['Bib'], noc=a['NOC'])
        r = {**meta(disc, 'QUAL', 'VT', b), **routine_cols(g, '1', vault=True), **routine_cols(None, '2'),
             'Combined Bonus': '', 'Total': g.get('Total', ''), 'Qualification': '', 'Qualification Rank': ''}
        if a['Bib'] in double:
            d = double[a['Bib']]
            mk = d['b']['mk']
            r.update(routine_cols(d['v2'], '2', vault=True))
            r.update({'Total': d['Total'], 'Qualification Rank': d['b']['rank'],
                      'Qualification': qualification(mk)})
        rows.append(r)
    if not set(double) <= {r['Bib'] for r in rows}:
        err(f'{ctx}: two-vault athletes missing from the all-around report')
    out.csv(f'{PREFIX[disc]}-SCORES-C1-VT.csv', common.score_header(True, True), rows)
    return {r['Bib']: r['Qualification'] for r in rows if r['Qualification']}

# ---------------------------------------------------------------- finals
def finalists(disc):
    """The finalists (or finals start list) page: per apparatus, the 8 finalists and ordered reserves."""
    page = REPORTS[disc]['finalists']
    grid, per_row = FINALIST_GRID[disc], 3 if disc == 'MAG' else 2
    res = {app: dict(Q=set(), R=[]) for app in grid}
    band = -1
    for l in lines(page):
        if re.match(r'^\s*(RK|#)\s+BIB\s', l):
            band += 1
            continue
        for k, m in enumerate(re.finditer(r'(R\d|\d)\s+(\d{3})\s+(.+?)\s{2,}([A-Z]{3})(?=\s|$)', l)):
            app = grid[band * per_row + k]
            mk, bib = m.group(1), m.group(2)
            if bib not in PEOPLE or PEOPLE[bib]['noc'] != m.group(4):
                err(f'{disc} finalists {app}: bib {bib} {m.group(4)}')
            if mk.startswith('R'):
                res[app]['R'].append(bib)
            else:
                res[app]['Q'].add(bib)
    return res

def check_qualifiers(disc, app, marks, fin):
    q = {b for b, m in marks.items() if m == 'Q'}
    r = sorted((b for b, m in marks.items() if m.startswith('R')), key=lambda b: marks[b])
    if q != fin[app]['Q'] or r != fin[app]['R']:
        err(f'{disc} {app}: Q/R {sorted(q)} {r} != finalists page {sorted(fin[app]["Q"])} {fin[app]["R"]}')

def final(disc, app, fin):
    page = REPORTS[disc]['finals'][app]
    ctx = f'{disc} EVENT {app}'
    m = re.search(r'Event Final \(([a-z ]+)\)', text(page))
    if not m or FINAL_TITLE[m.group(1)] != app:
        err(f'{ctx}: page {page} title {m and m.group(1)}')
    vault = app == 'VT'
    rows = []
    for b in blocks(page, page, ctx):
        c = f'{ctx} bib {b["bib"]}'
        if b['bib'] not in fin[app]['Q'] | set(fin[app]['R']):
            err(f'{c}: not a finalist or reserve')
        gs, rest = groups(b['vals'], 2 if vault else 1, c)
        place_bp(gs, b['extra'], c)
        bonus = rest.pop(0) if len(rest) == 2 and re.fullmatch(ONE, rest[0]) else ''
        if not rest and not vault:
            rest = [gs[0]['Total']]          # the uneven bars final prints no overall Total column
        if len(rest) != 1:
            err(f'{c}: totals {rest}'); continue
        if vault:
            checks.check_vault_average(c, gs[0]['Total'], gs[1]['Total'], bonus, rest[0])
            r = {**meta(disc, 'EVENT', app, b), **routine_cols(gs[0], '1', True), **routine_cols(gs[1], '2', True),
                 'Combined Bonus': bonus, 'Total': rest[0]}
        else:
            if rest[0] != gs[0]['Total']:
                err(f'{c}: final total {rest[0]} != routine {gs[0]["Total"]}')
            r = {**meta(disc, 'EVENT', app, b), **routine_cols(gs[0])}
        rows.append(r)
    if len(rows) != 8:
        err(f'{ctx}: {len(rows)} finalists')
    checks.check_rank_order(ctx, rows)
    out.csv(f'{PREFIX[disc]}-SCORES-C3-{app}.csv', common.score_header(vault, False), rows)

# ---------------------------------------------------------------- main
for disc in ('MAG', 'WAG'):
    participants(disc)
    judges(disc)
    athletes = aa_report(disc)
    aa = {a['Bib']: a for a in athletes}
    summary_aa(disc, athletes)
    team_report(disc, athletes)
    fin = finalists(disc)
    for app in APPS[disc]:
        marks = qual_vault(disc, aa) if app == 'VT' else qual_app(disc, app, aa)
        check_qualifiers(disc, app, marks, fin)
        final(disc, app, fin)
    sporttech.crosscheck(OUT, PREFIX[disc], SPORTTECH, EXPORT_TITLE[disc], ROUND_OF_DATE,
                         lambda bib: PEOPLE[bib]['noc'] if bib in PEOPLE else None, err)
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])

corrections.finish()
checks.finish()
