"""Parse the 2026 South American Games (Santa Fe) artistic gymnastics results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_south_american_games.py data/2026/2026-SOUTH-AMERICAN-GAMES/18708-ResultsbookMedia.pdf

Writes PARTICIPANTS, JUDGES, SCORES-{QUAL,EVENT}-<APP>, SUMMARY-FINAL-TEAM and SUMMARY-FINAL-AA, and an
IMPORT.json, per discipline next to the PDF, reading event metadata from the EVENT.csv already there.
Exits non-zero if any check fails (docs/instructions-results-parsing.md §3; this source format is
§5.22).

The book is the Games' media book: rhythmic (pp. 2-77), trampoline (pp. 79-133), then artistic
(pp. 136-249), the only part read. Every artistic page has text and a footer code like
`C73A.GARM1APFX-------------QUAL--------.ENG` (report family, then the event); headers are Spanish
over English. "Competition I: Qualification" (MAG 13, WAG 14 September) is followed by apparatus
finals (15-16 September), so it is QUAL. The schedule's "Competition II: Final" (team and
all-around) shares qualification's time block, and its reports, titled Final, rank the
qualification's routines: the team final (four of five up counting) and the all-around final (two
per NOC ranked, the others printed unranked). So TEAM and AA hold only a SUMMARY-FINAL-TEAM /
SUMMARY-FINAL-AA with `Scores Round` QUAL (§4.9, as at the Asian Games).

Sources: the apparatus tables give every qualification and final routine, except vault, whose
qualification table lists only the two-vault athletes. WAG prints a First Vault list (every first
vault, ranked over the field); MAG doesn't, so its other first vaults come from the team report
(team members) and the all-around report (individuals), with `Rank` blank (§4.5). The team report
also prints `DNS` for two entered routines the rings table leaves out (MAG AGÜERO and CHIAPPONI) and
a vault DNS (LEON); they are written as DNS rows. Everything the team and all-around reports print
is checked against the tables. The results print their own bibs, not the entry list's (agreed with
the user: the results' bibs are written, each entry matched to one by name and NOC). The entry list
by NOC, the start lists, lists of qualifiers, tie-break reports and the medallists by event are
cross-checks.
"""
import os, re, sys
from collections import Counter, defaultdict
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_surname_first

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-SOUTH-AMERICAN-GAMES'
PAGES = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err
out = common.Output(OUT, common.Corrections(OUT, EVENT_PREFIX, ['MAG-SR', 'WAG-SR'], err))

PREFIX = {d: f'{EVENT_PREFIX}-{d}-SR' for d in ('MAG', 'WAG')}
G = {'MAG': 'M', 'WAG': 'W'}
# The team and all-around reports' icon columns are in this order (legend), proven by the values
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
APP_NAME = {'Floor Exercise': 'FX', 'Pommel Horse': 'PH', 'Still Rings': 'SR', 'Rings': 'SR', 'Vault': 'VT',
            'Parallel Bars': 'PB', 'Horizontal Bar': 'HB', 'Uneven Bars': 'UB', 'Balance Beam': 'BB'}
# From the Competition Schedule page (§4.4); the medallists by event print each final's date
# (checked). The team and all-around finals are the qualification's rankings, the same day.
FINALS_DAY = {'2026-09-15': {'MAG': ['FX', 'PH', 'SR'], 'WAG': ['VT', 'UB']},
              '2026-09-16': {'MAG': ['VT', 'PB', 'HB'], 'WAG': ['BB', 'FX']}}
SESSION_DATE = {'MAG': {'QUAL': '2026-09-13', 'TEAM': '2026-09-13', 'AA': '2026-09-13'},
                'WAG': {'QUAL': '2026-09-14', 'TEAM': '2026-09-14', 'AA': '2026-09-14'}}
for day, by_disc in FINALS_DAY.items():
    for disc, apps in by_disc.items():
        for app in apps:
            SESSION_DATE[disc][('EVENT', app)] = day
TEAM_COUNTING = 4
AA_PER_NOC = 2
SCORE = r'\d+\.\d{3}'
ROUTINE_KEYS = ['Status', 'D', 'E', 'B', 'Penalty', 'SJ Penalty', 'Total']
# A finalist who wasn't a qualifier, and the qualifier they replaced (no NR is printed, so the
# compatriot's Qualification stays blank, §4.6): MAG parallel bars ZABALA (Q, 1st) out, BARAJAS
# (3rd, COL's third) in; WAG floor LIDE (Q) out, GUTIERREZ (12th, PAN's third) in
REPLACEMENTS = {('MAG', 'PB'): ({'65'}, {'61'}), ('WAG', 'FX'): ({'26'}, {'24'})}
# A vault final line 2 printed blank, with the result printed as half of vault 1 and ranked (MAG
# ROSTAGNO). Read as DNS (§4.3); written INVALID_VAULT 0.000 through CORRECTIONS.csv (agreed with
# the user)
VAULT2_BLANK_HALVED = {('MAG', '76')}
# The team report prints no E for a 0.000 the tables and the all-around report print with E `0.000`
# (WAG ORTIZ's bars, no D)
NO_E = {('WAG', '10', 'UB')}
# A bare `0` in the team report's bonus line (MAG BRAJAO, under vault's D): no bonus
ZERO_BONUS = {('MAG', '53')}
# Unsigned penalties on the tables and reports; `0.0` is none (written blank)
def penalty(v):
    return '' if not v or D(v) == 0 else '-' + v

# ---------------------------------------------------------------- page lookup
def footer_code(page):
    """`C73A.GARM1APFX-------------QUAL--------.ENG  Report Created …` -> `C73A.GARM1APFXQUAL`."""
    m = re.search(r'^\s*(C\d+[A-Z]?)\.(GAR[\w-]*?)\.ENG\s+Report Created', page, re.M)
    return f'{m.group(1)}.{m.group(2).replace("-", "")}' if m else ''

CODES = [footer_code(p) for p in PAGES]

def find(pattern, copies=1):
    """The pages whose footer code matches, in one run (or `copies` identical runs: the first)."""
    idx = [i for i, c in enumerate(CODES) if re.fullmatch(pattern, c)]
    if not idx:
        raise SystemExit(f'no pages with code {pattern}')
    runs = [[idx[0]]]
    for i in idx[1:]:
        if i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    if len(runs) != copies:
        err(f'{pattern}: pages {[i + 1 for i in idx]} in {len(runs)} runs, expected {copies}')
    for run in runs[1:]:
        if [PAGES[i] for i in run] != [PAGES[i] for i in runs[0]]:
            err(f'{pattern}: the copy at pages {[i + 1 for i in run]} differs from the first')
    return runs[0]

def body(i):
    """A page's lines, up to its legend."""
    lines = PAGES[i].split('\n')
    for j, l in enumerate(lines):
        if re.match(r'^\s*(Legend:|Note:|Pos\. Position)', l):
            return lines[:j]
    return lines

# ---------------------------------------------------------------- routines
def empty_routine():
    return dict.fromkeys(ROUTINE_KEYS, '')

def routine(d, e, b, pen, total, status='COMPLETED'):
    return dict(empty_routine(), Status=status, D=d, E=e, B=b, Penalty=penalty(pen), Total=total)

def dns():
    return dict(empty_routine(), Status='DNS')

def check_routine(ctx, r):
    """D + E + B - penalty = the score, which never goes below zero (§4.3)."""
    if r['Status'] == 'DNS':
        return
    s = D(r['D']) + D(r['E']) + D(r['B']) + D(r['Penalty'])
    if s != D(r['Total']) and not (s < 0 and D(r['Total']) == 0):
        err(f'{ctx}: {r["D"]} + {r["E"]} + {r["B"] or 0} {r["Penalty"] or "- 0"} != {r["Total"]}')

def check_average(ctx, t1, t2, bonus, total):
    """A two-vault result: the average of the vaults, rounded to 3 decimals (not truncated: MAG final
    CHICA 13.375 and 13.350 print 13.363), plus any combined bonus. Halves print either way
    (13.5375 -> 13.537), so 0.0005 either side is allowed."""
    avg = (D(t1) + D(t2)) / 2 + D(bonus)
    if abs(avg - D(total)) > Decimal('0.0005'):
        err(f'{ctx}: average {avg} != printed {total}')

def same(ctx, got, want, keys=ROUTINE_KEYS):
    """Two prints of one routine agree (numerically: the reports print `0.100`, the tables `0.1`)."""
    for k in keys:
        a, b = got.get(k, ''), want.get(k, '')
        if (a == '') != (b == '') or (a and a not in ('DNS',) and b not in ('DNS',) and k != 'Status'
                                      and D(a) != D(b)) or (k == 'Status' and a != b):
            err(f'{ctx} {k}: {a!r} != {b!r}')

# ---------------------------------------------------------------- tables
def label_edges(lines, names):
    """Right edge of each column label, read from the header lines (labels may sit on the line above
    or below, e.g. `Vault`/`Score`)."""
    edges = {}
    for l in lines:
        for m in re.finditer(r'\S+', l):
            if m.group() in names and m.group() not in edges:
                edges[m.group()] = m.end()
    if set(edges) != set(names):
        raise SystemExit(f'header labels {sorted(edges)} != {sorted(names)}')
    return edges

def place(ctx, line, start, edges, total=False):
    """Values right-aligned under their labels: each token goes to the label whose right edge is
    nearest (within 3), one token per label (§2.6). `Total` isn't aligned with its label: with
    `total`, a row's last value, if it has three decimals, is the total."""
    vals = {}
    found = list(re.finditer(r'\S+', line[start:]))
    if total and found and re.fullmatch(SCORE, found[-1].group()):
        vals['Total'] = found.pop().group()
    edges = {k: v for k, v in edges.items() if k != 'Total'}
    for m in found:
        end = start + m.end()
        label, edge = min(edges.items(), key=lambda kv: abs(kv[1] - end))
        if abs(edge - end) > 3 or label in vals:
            err(f'{ctx}: cannot place {m.group()!r} at {end} in {line.strip()!r}')
            continue
        vals[label] = m.group()
    return vals

ROW = re.compile(r'^\s*(\d+|--)\s+(\d+)\s+(\S.*?)\s{2,}([A-Z]{3})(?=\s)(.*?)(?:\s+(Q|R\d))?\s*$')

def table_pages(disc, rnd, app):
    if rnd == 'QUAL':
        return find(rf'C73[AB]\.GAR{G[disc]}1AP{app}QUAL')
    return find(rf'C73[AIJ]\.GAR{G[disc]}1AP{app}FNL')

def header_lines(lines):
    k = next(j for j, l in enumerate(lines) if re.match(r'^\s*Rank\s+Bib\s+Name', l))
    return k, lines[k - 1:k + 2]

def single_table(ctx, lines):
    """`Rank Bib Name NOC D E B Pen. Total [Q|R1]` -> rows; `--  bib name NOC DNS` is DNS."""
    k, hdr = header_lines(lines)
    edges = label_edges(hdr, ['D', 'E', 'B', 'Pen.', 'Total'])
    rows = []
    for l in lines[k + 1:]:
        m = ROW.match(l)
        if not m:
            continue
        rank, bib, name, noc, rest, marker = m.groups()
        r = {'Rank': '' if rank == '--' else rank, 'Bib': bib, 'Name': name, 'NOC': noc, 'Q': marker or ''}
        if rest.strip() == 'DNS':
            if rank != '--':
                err(f'{ctx}: ranked DNS bib {bib}')
            r.update(dns())
        else:
            v = place(f'{ctx} bib {bib}', l[:m.end(5)], m.start(5), edges, total=True)
            r.update(routine(v.get('D', ''), v.get('E', ''), v.get('B', ''), v.get('Pen.', ''), v.get('Total', '')))
            check_routine(f'{ctx} bib {bib}', r)
        rows.append(r)
    n = sum(1 for l in lines[k + 1:] if re.match(r'^\s*(\d+|--)\s+\d+\s+[A-ZÁÉÍÓÚÑÜ]', l))
    if n != len(rows) or not rows:
        err(f'{ctx}: {len(rows)} rows parsed, {n} counted')
    return rows

def vault_table(ctx, disc, lines):
    """Two-vault table: `rank bib name NOC 1 D E [Pen.] Score Total [Q|R1]`, then `2 D E Pen. Score [B]`.
    MAG's B on a line is that vault's bonus (inside its score); WAG's is the combined bonus (§4.5)."""
    k, hdr = header_lines(lines)
    edges = label_edges(hdr, ['D', 'E', 'Pen.', 'Score', 'B', 'Total'])
    rows = []
    for j in range(k + 1, len(lines)):
        m = re.match(r'^\s*(\d+)\s+(\d+)\s+(\S.*?)\s{2,}([A-Z]{3})\s+1(?=\s)(.*?)(?:\s+(Q|R\d))?\s*$', lines[j])
        if not m:
            continue
        rank, bib, name, noc, _, marker = m.groups()
        c = f'{ctx} bib {bib}'
        v1 = place(c, lines[j][:m.end(5)], m.start(5), edges, total=True)
        m2 = re.match(r'^\s+2(?=\s|$)', lines[j + 1])
        if not m2:
            err(f'{c}: no vault 2 line'); continue
        v2 = place(c, lines[j + 1], m2.end(), edges)
        r = {'Rank': rank, 'Bib': bib, 'Name': name, 'NOC': noc, 'Q': marker or '', 'Total': v1.pop('Total', ''),
             'Combined Bonus': ''}
        for n, v in (('1', v1), ('2', v2)):
            b = v.get('B', '')
            if b and disc == 'WAG':
                if n == '1':
                    err(f'{c}: combined bonus on vault 1')
                r['Combined Bonus'], b = b, ''
            if not v:
                r[n] = dns()
            else:
                x = routine(v.get('D', ''), v.get('E', ''), b, v.get('Pen.', ''), v.get('Score', ''))
                if not x['Total'] and not x['E']:
                    # WAG CARVAJAL: vault 1 prints only its penalty; the First Vault list gives E and
                    # score 0.000 (an invalid vault)
                    x['_blank'] = True
                elif D(x['Total']) == 0:
                    x['Status'] = 'INVALID_VAULT'
                r[n] = x
                if not x.get('_blank'):
                    check_routine(f'{c} vault {n}', x)
        if r['2']['Status'] == 'DNS':
            if (disc, bib) not in VAULT2_BLANK_HALVED:
                err(f'{c}: vault 2 blank')
            check_average(c, r['1']['Total'], '0', '', r['Total'])
        else:
            check_average(c, r['1']['Total'], r['2']['Total'], r['Combined Bonus'], r['Total'])
        rows.append(r)
    n = sum(1 for l in lines[k + 1:] if re.match(r'^\s*\d+\s+\d+\s+[A-ZÁÉÍÓÚÑÜ]', l))
    if n != len(rows) or not rows:
        err(f'{ctx}: {len(rows)} rows parsed, {n} counted')
    return rows

def first_vault_list(disc):
    """WAG First Vault list (`Primer Salto`, the second page of the qualification vault report):
    every first vault, ranked over the field."""
    idx = [i for i in find(rf'C73B\.GARW1APVTQUAL') if 'First Vault' in PAGES[i]]
    if len(idx) != 1:
        err(f'{disc} first vault list: pages {idx}')
    lines = body(idx[0])
    k, hdr = header_lines(lines)
    edges = label_edges(hdr, ['D', 'E', 'Pen.', 'Total'])
    rows = []
    for l in lines[k + 1:]:
        m = ROW.match(l)
        if not m:
            continue
        rank, bib, name, noc, rest, _ = m.groups()
        v = place(f'{disc} first vault bib {bib}', l[:m.end(5)], m.start(5), edges, total=True)
        r = {'Rank': rank, 'Bib': bib, 'Name': name, 'NOC': noc,
             **routine(v.get('D', ''), v.get('E', ''), '', v.get('Pen.', ''), v.get('Total', ''))}
        if D(r['Total']) == 0:
            r['Status'] = 'INVALID_VAULT'
        check_routine(f'{disc} first vault bib {bib}', r)
        rows.append(r)
    common_rank_check(f'{disc} first vault list', rows)
    return rows

def common_rank_check(ctx, rows):
    checks.check_rank_order(ctx, [r for r in rows if r['Rank']])

def tables(disc, rnd, app):
    ctx = f'{disc} {rnd} {app}'
    idx = table_pages(disc, rnd, app)
    if app == 'VT':
        idx = [i for i in idx if 'First Vault' not in PAGES[i]]
        rows = vault_table(ctx, disc, [l for i in idx for l in body(i)])
        common_rank_check(ctx, [{'Rank': r['Rank'], 'Total': r['Total'], 'Bib': r['Bib']} for r in rows])
    else:
        rows = single_table(ctx, [l for i in idx for l in body(i)])
        common_rank_check(ctx, rows)
    return rows

# ---------------------------------------------------------------- team and all-around reports
def tokens(line):
    """Numbers, `(rank)`s and `DNS` with their end columns; the rest is text (a wrapped name, a NOC)."""
    toks, text = [], line
    for m in re.finditer(r'\(\d+\)|(?<!\S)(?:\d+\.\d+|0|DNS)(?!\S)', line):
        toks.append((m.group(), m.end()))
        text = text[:m.start()] + ' ' * (m.end() - m.start()) + text[m.end():]
    return toks, ' '.join(text.split())

def resolve(ctx, disc, bib, performed, e_line, c_line, known, no_e=()):
    """A report's E line (each routine's E, then its penalty if any) and rank line (each routine's
    bonus if any, under the next column's D, then its rank) for the routines line A printed:
    `performed` is [(app, D, score)]. Routines the tables give are checked against them; a first
    vault no table gives (MAG) is worked out: the penalty is what D + E exceeds the score by, a bonus
    what it falls short. Returns {app: routine}."""
    e = [t for t, _ in e_line if not t.startswith('(')]
    if any(t.startswith('(') for t, _ in e_line):
        err(f'{ctx}: rank on the E line')
    got, want_c = {}, []
    for app, d, score in performed:
        c = f'{ctx} {app}'
        if not e:
            err(f'{c}: E line short'); return got
        k = known(app, bib)
        x = routine(d, k['E'] if (disc, bib, app) in no_e else e.pop(0), '', '', score)
        if k:
            if k['Penalty']:
                x['Penalty'] = '-' + e.pop(0) if e else ''
            x['B'] = k['B']
            if k['Status'] == 'INVALID_VAULT' or (D(score) == 0 and app == 'VT'):
                x['Status'] = 'INVALID_VAULT'
            same(c, x, k)
        else:
            r = D(d) + D(x['E']) - D(score)
            if r > 0:
                pen = e.pop(0)
                x['Penalty'], b = '-' + pen, D(pen) - r
                x['B'] = str(b) if b else ''
            elif r < 0:
                x['B'] = f'{-r:.1f}'
            if D(score) == 0:
                x['Status'] = 'INVALID_VAULT'
        check_routine(c, x)
        got[app] = x
        if x['B']:
            want_c.append(x['B'])
        rank = known_rank(app, bib)
        if rank:
            want_c.append(f'({rank})')
    if e:
        err(f'{ctx}: E line has {e} left over')
    c_toks = [t for t, _ in c_line]
    if c_toks.count('0'):
        if (disc, bib) not in ZERO_BONUS:
            err(f'{ctx}: bare 0 on the rank line')
        c_toks = [t for t in c_toks if t != '0']
    norm = lambda ts: [t if t.startswith('(') else D(t) for t in ts]
    if norm(c_toks) != norm(want_c):
        err(f'{ctx}: rank line {c_toks} != {want_c}')
    return got

def team_report(disc, known):
    """`rank  NOC - Country  <app totals>  total`, then per member: `bib NAME  [D Score | DNS] …` (a
    column per apparatus, a member's blank where they weren't up), an E line and a rank line.
    Values on line A are placed by the header's `Score` columns."""
    ctx0 = f'{disc} team report'
    napps = len(APPS[disc])
    teams = []
    for i in find(rf'C73[CD]\.GAR{G[disc]}TEAMFNL'):
        lines = body(i)
        k = next(j for j, l in enumerate(lines) if re.search(r'\bD\s+Score\s+D\s+Score', l))
        edges = [m.end() for m in re.finditer(r'Score', lines[k])]
        if len(edges) != napps:
            err(f'{ctx0} p. {i + 1}: {len(edges)} columns')
        blocks = []  # (kind, line, following lines)
        for l in lines[k + 3:]:
            if not l.strip():
                continue
            if re.match(r'^\s*\d+\s+[A-Z]{3} - ', l) or re.match(r'^\s+\d+ [A-ZÁÉÍÓÚÑÜ]', l):
                blocks.append([l, []])
            elif blocks:
                blocks[-1][1].append(l)
            else:
                err(f'{ctx0} p. {i + 1}: stray line {l.strip()!r}')
        for l, rest in blocks:
            t = re.match(r'^\s*(\d+)\s+([A-Z]{3}) - \S.*?\s{2,}((?:' + SCORE + r'\s*)+)$', l)
            if t:
                vals = re.findall(SCORE, t.group(3))
                if len(vals) != napps + 1 or rest:
                    err(f'{ctx0}: team line {l.strip()!r}')
                teams.append({'Rank': t.group(1), 'NOC': t.group(2), 'totals': dict(zip(APPS[disc], vals[:-1])),
                              'Total': vals[-1], 'members': []})
                continue
            m = re.match(r'^\s+(\d+) ([A-ZÁÉÍÓÚÑÜ][^\d(]*?)(?:\s{2,}|$)', l)
            bib, name = m.group(1), m.group(2).strip()
            ctx = f'{ctx0} {teams[-1]["NOC"]} bib {bib}'
            cols = defaultdict(list)
            for tok, end in tokens(l[m.end():])[0]:
                end += m.end()
                col = next((a for a, e in enumerate(edges) if end <= e + 2), None)
                if col is None:
                    err(f'{ctx}: {tok} at {end} past the last column'); continue
                cols[APPS[disc][col]].append(tok)
            apps, performed = {}, []
            for app in APPS[disc]:
                v = cols.get(app)
                if not v:
                    continue
                if v == ['DNS']:
                    apps[app] = dns()
                elif len(v) in (1, 2) and 'DNS' not in v:
                    performed.append((app, v[0] if len(v) == 2 else '', v[-1]))
                else:
                    err(f'{ctx} {app}: {v}')
            e_line = tokens(rest[0])[0] if rest else []
            c_line = tokens(rest[1])[0] if len(rest) > 1 else []
            if len(rest) > 2:
                err(f'{ctx}: extra lines {rest[2:]}')
            apps.update(resolve(ctx, disc, bib, performed, e_line, c_line, known, NO_E))
            teams[-1]['members'].append({'Bib': bib, 'Name': name, 'apps': apps})
    for t in teams:
        ctx = f'{ctx0} {t["NOC"]}'
        for app in APPS[disc]:
            scores = sorted((D(x['apps'][app]['Total']) for x in t['members']
                             if app in x['apps'] and x['apps'][app]['Status'] != 'DNS'), reverse=True)
            if sum(scores[:TEAM_COUNTING]) != D(t['totals'][app]):
                err(f'{ctx} {app}: best {TEAM_COUNTING} of {scores} != {t["totals"][app]}')
        if sum(D(v) for v in t['totals'].values()) != D(t['Total']):
            err(f'{ctx}: apparatus totals != {t["Total"]}')
    checks.check_rank_order(ctx0, [{'Rank': t['Rank'], 'Total': t['Total'], 'Bib': t['NOC']} for t in teams])
    if [t['Rank'] for t in teams] != [str(n + 1) for n in range(len(teams))]:
        err(f'{ctx0}: ranks {[t["Rank"] for t in teams]}')
    return teams

def aa_report(disc, known):
    """`[rank] bib NAME  D Score …  total` (every apparatus; D blank where not printed), then an E line
    and a rank line; a long name wraps onto them, before the `NOC - Country` (itself wrapped at
    times). Values are read in order, the tables saying where a D is blank."""
    ctx0 = f'{disc} all-around report'
    lines = [l for i in find(rf'C73[GH]\.GAR{G[disc]}1AAFNL') for l in body(i)]
    head = re.compile(r'^\s*(?:(\d+)\s+)?(\d+)\s+([A-ZÁÉÍÓÚÑÜ][^\d(]*?)\s+(' + SCORE + r'(?:\s+' + SCORE + r')*)\s*$')
    starts = [j for j, l in enumerate(lines) if head.match(l)]
    athletes = []
    for n, j in enumerate(starts):
        rank, bib, name, vals = head.match(lines[j]).groups()
        ctx = f'{ctx0} bib {bib}'
        rest = [l for l in lines[j + 1:starts[n + 1] if n + 1 < len(starts) else len(lines)] if l.strip()]
        parts, text = [], [name]
        for l in rest:
            toks, t = tokens(l)
            if t:
                text.append(t)
            if toks:
                parts.append(toks)
        full = ' '.join(' '.join(text).split())
        mm = re.fullmatch(r'(.+?) ([A-Z]{3}) - \S.*', full)
        if not mm:
            err(f'{ctx}: no NOC in {full!r}'); continue
        vals = vals.split()
        performed = []
        for app in APPS[disc]:
            k = known(app, bib)
            if k and k['Status'] == 'DNS':
                err(f'{ctx} {app}: DNS in the all-around'); continue
            take = 2 if not k or k['D'] else 1
            if len(vals) < take + 1:
                err(f'{ctx}: too few values'); break
            got = vals[:take]
            vals = vals[take:]
            performed.append((app, got[0] if take == 2 else '', got[-1]))
        if len(vals) != 1:
            err(f'{ctx}: values left {vals}')
        total = vals[-1]
        if len(parts) != 2:
            err(f'{ctx}: {len(parts)} value lines'); continue
        apps = resolve(ctx, disc, bib, performed, parts[0], parts[1], known)
        if sum(D(x['Total']) for x in apps.values()) != D(total):
            err(f'{ctx}: apparatus scores != {total}')
        athletes.append({'Rank': rank or '', 'Bib': bib, 'Name': mm.group(1), 'NOC': mm.group(2), 'apps': apps,
                         'Total': total})
    if len(athletes) != len(starts):
        err(f'{ctx0}: {len(athletes)} of {len(starts)} athletes read')
    return athletes

# ---------------------------------------------------------------- entries
def entries(disc):
    """Entry List by NOC (printed twice: in the front matter and the discipline's section):
    `NOC - Country (n)`, then `SURNAME Given  licence  bib  year`. Its bibs aren't the results'."""
    rows, counts, noc = [], {}, None
    for l in [l for i in find(rf'C32A\.GAR{G[disc]}', copies=2) for l in body(i)]:
        h = re.match(r'^\s*([A-Z]{3}) - .+?\((\d+)\)\s*$', l)
        if h:
            noc = h.group(1)
            counts[noc] = int(h.group(2))
            continue
        m = re.match(r'^\s+(\S.*?)\s{2,}(\d+)\s+(\d+)\s+(\d{4})\s*$', l)
        if m and noc:
            rows.append({'NOC': noc, 'Name': m.group(1), 'Licence': m.group(2), 'Entry Bib': m.group(3),
                         'Year': m.group(4)})
    got = Counter(r['NOC'] for r in rows)
    if got != counts:
        err(f'{disc} entries: {dict(got)} != headings {counts}')
    # Number of Entries by NOC
    col = 0 if disc == 'MAG' else 1
    printed = {}
    for l in [l for i in find(r'C30\.GAR') for l in body(i)]:
        m = re.match(r'^\s*([A-Z]{3}) \S.*?\s{2,}(\d+)\s+(\d+)\s+(\d+)\s*$', l)
        if m:
            printed[m.group(1)] = int(m.group(2 + col))
            if int(m.group(2)) + int(m.group(3)) != int(m.group(4)):
                err(f'entries by NOC {m.group(1)}: total')
    if {k: v for k, v in printed.items() if v} != dict(got):
        err(f'{disc} entries: {dict(got)} != entries by NOC {printed}')
    return rows

NAMES = {}   # disc -> bib -> (name, noc)

def participants(disc, ents, seen):
    """PARTICIPANTS with the results' bibs: each entry is matched to the one bib the results print
    its name and NOC with. `seen` maps bib -> {(name, noc)} from every results table."""
    ev = EVENTS[PREFIX[disc]]
    by_name = defaultdict(set)
    for bib, names in seen.items():
        if len(names) != 1:
            err(f'{disc} bib {bib}: printed as {sorted(names)}')
        for nn in names:
            by_name[nn].add(bib)
    rows, NAMES[disc] = [], {}
    for n, e in enumerate(ents, 1):
        bibs = by_name.get((e['Name'], e['NOC']), set())
        if len(bibs) != 1:
            err(f'{disc} entry {e["Name"]} ({e["NOC"]}): results bibs {sorted(bibs)}'); continue
        bib = bibs.pop()
        sur, giv = split_surname_first(e['Name'])
        if not sur or not giv:
            err(f'{disc} entry {e["Name"]}: split {sur!r} / {giv!r}')
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                     'Event Start Date': ev['Start Date'], 'Order': str(n), 'NOC Code': e['NOC'], 'Bib Number': bib,
                     'FIG License': e['Licence'], 'Name': e['Name'], 'Surname': sur, 'Given Name': giv,
                     'Birth Year': e['Year'], 'Birth Date': ''})
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)
    for r in rows:
        NAMES[disc][r['Bib Number']] = (r['Name'], r['NOC Code'])
    unmatched = set(seen) - set(NAMES[disc])
    if unmatched:
        err(f'{disc}: results bibs {sorted(unmatched)} on no entry')

def check_name(disc, ctx, bib, name, noc):
    want = NAMES[disc].get(bib)
    if want != (' '.join(name.split()), noc):
        err(f'{ctx}: bib {bib} {name} ({noc}), the entry is {want}')

def start_lists(disc):
    """Every start list row's bib, name and NOC agree with the entries."""
    n = 0
    for i, c in enumerate(CODES):
        if re.fullmatch(rf'C51[A-Z]?\.GAR{G[disc]}(QUAL|FNL)', c):
            for l in body(i):
                for m in re.finditer(r'(?<!\S)\d+\s+(\d+)\s+([A-ZÁÉÍÓÚÑÜ][^\d]*?)\s{2,}([A-Z]{3})(?!\S)', l):
                    check_name(disc, f'{disc} start list p. {i + 1}', m.group(1), m.group(2), m.group(3))
                    n += 1
    print(f'  {disc}: {n} start list rows checked')

# ---------------------------------------------------------------- judges
def judge_function(f, panel):
    """PR is the President; a function printed twice on a panel is numbered (beam's two `T`), and an
    unnumbered `L` beside an `L2` is `L1` (§4.7)."""
    if f == 'PR':
        return 'President'
    if f in ('T', 'L'):
        if panel.count(f) == 2:
            return None  # numbered by the caller, in order
        if f + '2' in panel:
            return f + '1'
    return f

def judge_page(i, rnd, disc):
    """Two panels side by side under apparatus headings; the Superior Jury (`PR`) is centred above,
    under `Superior Jury` (WAG finals: one per pair of apparatus, `Superior Jury - Vault & Uneven
    Bars`). Returns [(apparatus or None, function, name, noc)]."""
    panels = defaultdict(list)  # apparatus or ('SJ', apps) -> [(fn, name, noc)]
    sj_apps, left, right = (), None, None
    for l in body(i):
        sj = re.match(r'^\s*Superior Jury\s*-?\s*(.*?)\s*$', l)
        if sj:
            names = [n.strip() for n in sj.group(1).split('&')] if sj.group(1) else []
            sj_apps = tuple(APP_NAME[n] for n in names)
            left = right = None
            continue
        heads = [(m.start(), APP_NAME[m.group()]) for m in re.finditer('|'.join(sorted(APP_NAME, key=len, reverse=True)), l)]
        if heads and not re.search(r'\d', l):
            if len(heads) != 2:
                err(f'judges p. {i + 1}: headings {l.strip()!r}')
            left, right = heads[0][1], heads[1][1]
            continue
        for m in re.finditer(r'(?<!\S)(\d+)\s+(PR|AS|D\d|E\d|L\d?|T\d?|R\d?)\s+(\S.*?)\s{2,}([A-Z]{3}(?:-[A-Z]+)?)(?!\S)', l):
            fn, name, noc = m.group(2), m.group(3), m.group(4)
            if left is None:
                if fn != 'PR':
                    err(f'judges p. {i + 1}: {fn} {name} outside a panel')
                panels[('SJ', sj_apps)].append((fn, name, noc))
            else:
                panels[left if m.start() < 70 else right].append((fn, name, noc))
    rows = []
    for key, members in panels.items():
        fns = [f for f, _, _ in members]
        seen = Counter()
        for fn, name, noc in members:
            f = judge_function(fn, fns)
            if f is None:
                seen[fn] += 1
                f = f'{fn}{seen[fn]}'
            if isinstance(key, tuple):
                for app in key[1] or (None,):
                    rows.append((app, f, name, noc))
            else:
                rows.append((key, f, name, noc))
        if not isinstance(key, tuple):
            want = {'D1', 'D2'} | {f'E{n}' for n in range(1, 4)}
            if not want <= {f for a, f, _, _ in rows if a == key}:
                err(f'{disc} {rnd} judges {key}: panel {fns}')
    return rows

def judges(disc):
    ev = EVENTS[PREFIX[disc]]
    rows = []
    for rnd, pat in (('QUAL', rf'C57[AB]\.GAR{G[disc]}QUAL'), ('EVENT', rf'C57D\.GAR{G[disc]}FNL')):
        got = [x for i in find(pat) for x in judge_page(i, rnd, disc)]
        apps = {a for a, *_ in got if a}
        if apps != set(APPS[disc]):
            err(f'{disc} {rnd} judges: panels {sorted(apps)}')
        for app, f, name, noc in got:
            sur, giv = split_surname_first(name)
            rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR',
                         'Event Start Date': ev['Start Date'], 'Round': rnd, 'Apparatus': app or '', 'Function': f,
                         'Name': name, 'Surname': sur, 'Given Name': giv, 'NOC Code': noc})
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, rows)
    for r in rows:
        if not re.fullmatch(r'[A-Z]{3}', r['NOC Code']):
            err(f'{disc} judges: {r["Name"]} NOC {r["NOC Code"]!r}')

# ---------------------------------------------------------------- writing scores
def meta(disc, rnd, app, rank, bib):
    ev = EVENTS[PREFIX[disc]]
    name, noc = NAMES[disc][bib]
    date = SESSION_DATE[disc][('EVENT', app)] if rnd == 'EVENT' else SESSION_DATE[disc][rnd]
    return {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Session Start Date': date,
            'Round': rnd, 'Part': '', 'Apparatus': app, 'Rank': rank, 'Bib': bib, 'Name': name, 'NOC Code': noc}

def routine_cols(r, n=''):
    return {f'{k}{n}': r[k] for k in ROUTINE_KEYS}

def vault_row(disc, rnd, rank, bib, v1, v2=None, bonus='', total=None, q='', qrank=''):
    row = meta(disc, rnd, 'VT', rank, bib)
    row.update(routine_cols(v1, '1'))
    row.update(routine_cols(v2, '2') if v2 else {f'{k}2': '' for k in ROUTINE_KEYS})
    row['Combined Bonus'] = bonus
    row['Total'] = (v1['Total'] if v1['Status'] != 'DNS' else '') if total is None else total
    if rnd == 'QUAL':
        row['Qualification'], row['Qualification Rank'] = q, qrank
    return row

# ---------------------------------------------------------------- finals checks
def lists_of_qualifiers(disc):
    """List of Qualifiers per apparatus: `Pos. Bib Name Score NOC`, Pos. the qualification rank of a
    qualifier or the reserve's `R1`/`R2`."""
    got = {}
    for i, c in enumerate(CODES):
        m = re.fullmatch(rf'C53[BC]\.GAR{G[disc]}1AP(\w\w)(QUAL|FNL)', c)
        if m:
            got[m.group(1)] = [re.match(r'^\s*(\d+|R\d)\s+(\d+)\s+(\S.*?)\s{2,}(' + SCORE + r')\s+([A-Z]{3})\s*$', l).groups()
                               for l in body(i) if re.match(r'^\s*(\d+|R\d)\s+\d+\s+[A-ZÁÉÍÓÚÑÜ]', l)]
    if set(got) != set(APPS[disc]):
        err(f'{disc} lists of qualifiers: {sorted(got)}')
    return got

def check_qualifiers(disc, app, rows, listed):
    ctx = f'{disc} {app} list of qualifiers'
    marked = sorted((r for r in rows if r['Qualification']), key=lambda r: int(r['Qualification Rank']))
    want = [(r['Qualification Rank'] if r['Qualification'] == 'Q' else r['Qualification'], r['Bib'], r['Total'],
             r['NOC Code']) for r in marked]
    got = [(p, b, s, n) for p, b, _, s, n in listed]
    if got != want:
        err(f'{ctx}: {got} != {want}')
    for p, b, name, s, n in listed:
        check_name(disc, ctx, b, name, n)

def finals_start_lists(disc):
    """The apparatus finals start lists, one page per final in the order of APPS (MAG FX…HB, WAG
    VT…FX); floor's lists its two reserves after the eight."""
    idx = find(rf'C51G?\.GAR{G[disc]}FNL')
    if len(idx) != len(APPS[disc]):
        err(f'{disc} finals start lists: {len(idx)} pages')
    got = {}
    for app, i in zip(APPS[disc], idx):
        got[app] = [re.match(r'^\s*(\d+)\s+(\d+)\s', l).group(2) for l in body(i)
                    if re.match(r'^\s*\d+\s+\d+\s+[A-ZÁÉÍÓÚÑÜ]', l)]
    return got

def check_final(disc, app, qual_rows, final_rows, start_list):
    ctx = f'{disc} EVENT {app}'
    qualified = {r['Bib'] for r in qual_rows if r['Qualification'] == 'Q'}
    competed = {r['Bib'] for r in final_rows}
    out_, in_ = REPLACEMENTS.get((disc, app), (set(), set()))
    if competed != (qualified - out_) | in_ or not out_ <= qualified or in_ & qualified:
        err(f'{ctx}: finalists {sorted(competed)}, qualifiers {sorted(qualified)}')
    if not competed <= set(start_list[:8]) or len(start_list) not in (8, 10):
        err(f'{ctx}: start list {start_list}, finalists {sorted(competed)}')
    if start_list[8:]:
        reserves = [r['Bib'] for r in sorted((r for r in qual_rows if r['Qualification'].startswith('R')),
                                             key=lambda r: r['Qualification'])]
        if start_list[8:] != reserves:
            err(f'{ctx}: start list reserves {start_list[8:]} != {reserves}')
    if [r['Rank'] for r in final_rows] != [str(n + 1) for n in range(len(final_rows))]:
        err(f'{ctx}: ranks {[r["Rank"] for r in final_rows]}')

def check_tie_breaks(disc, results):
    """Tie-Break Output pages reprint tied athletes' rows from a table: rank, bib and total agree.
    `results` maps (round, apparatus) to bib -> (rank, total)."""
    n = 0
    for i, c in enumerate(CODES):
        m = re.fullmatch(rf'C77[AB]\.GAR{G[disc]}1AP(\w\w)(QUAL|FNL)', c)
        if not m:
            continue
        key = ('QUAL' if m.group(2) == 'QUAL' else 'EVENT', m.group(1))
        rows = 0
        for l in body(i):
            t = re.match(r'^\s*(\d+)\s+(\d+)\s+\S.*?\s{2,}[A-Z]{3}\s+(?:1\s+)?.*?(' + SCORE + r')(?:\s+(?:Q|R\d))?\s*$', l)
            if t:
                rows += 1
                rank, bib, total = t.groups()
                if results[key].get(bib) != (rank, total):
                    err(f'{disc} {key} tie break: bib {bib} {rank} {total}, the table {results[key].get(bib)}')
        if not rows:
            err(f'{disc} {key} tie break p. {i + 1}: no rows')
        n += 1
    print(f'  {disc}: {n} tie-break reports checked')

def check_medallists(disc, podiums):
    """Medallists by Event (a summary page, §3.9), and each final's date, against the results."""
    got, event = defaultdict(set), None
    for l in [l for i in find(rf'C93\.GAR{G[disc]}') for l in body(i)]:
        m = re.match(r"^\s*(Team|All-Around|(?:Men|Women)'s - (\w\w) - Final\s+(\d+)-Sep-26)\s", l)
        if m:
            event = 'TEAM' if m.group(1) == 'Team' else 'AA' if m.group(1) == 'All-Around' else m.group(2)
            if m.group(3) and SESSION_DATE[disc][('EVENT', event)] != f'2026-09-{m.group(3)}':
                err(f'{disc} medallists {event}: dated {m.group(3)} Sep')
        m = re.search(r'(Gold|Silver|Bronze)\s+(\S.*?)\s{2,}([A-Z]{3}) - ', l)
        if m and event:
            got[event].add((m.group(1), m.group(3), None if event == 'TEAM' else m.group(2)))
    for k, want in podiums.items():
        if got.get(k) != want:
            err(f'{disc} medallists {k}: page {sorted(got.get(k, ()))}, results {sorted(want)}')
    if set(got) != set(podiums):
        err(f'{disc} medallists: events {sorted(set(got) ^ set(podiums))}')

def podium(rows, team=False):
    medal = {'1': 'Gold', '2': 'Silver', '3': 'Bronze'}
    return {(medal[r['Rank']], r['NOC Code'], None if team else r['Name']) for r in rows if r['Rank'] in medal}

# ---------------------------------------------------------------- summaries
def summary_team(disc, teams):
    ev = EVENTS[PREFIX[disc]]
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part', 'Rank', 'NOC Code'] + \
          [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Scores Round']
    rows = []
    for t in teams:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Round': 'TEAM', 'Part': '', 'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': '',
             'Total': t['Total'], 'Scores Round': 'QUAL'}
        r.update({f'{a} Total': t['totals'][a] for a in SUMMARY_APPS[disc]})
        rows.append(r)
    out.csv(f'{PREFIX[disc]}-SUMMARY-FINAL-TEAM.csv', hdr, rows)
    return rows

def summary_aa(disc, athletes):
    ev = EVENTS[PREFIX[disc]]
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Round', 'Part', 'Rank', 'Bib', 'Name',
           'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Scores Round']
    rows = []
    for a in athletes:
        r = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': 'SR', 'Event Start Date': ev['Start Date'],
             'Round': 'AA', 'Part': '', 'Rank': a['Rank'], 'Bib': a['Bib'], 'Name': NAMES[disc][a['Bib']][0],
             'NOC Code': a['NOC'], 'SJ Penalty': '', 'Total': a['Total'], 'Scores Round': 'QUAL'}
        r.update({f'{x} Total': a['apps'][x]['Total'] for x in SUMMARY_APPS[disc]})
        rows.append(r)
    out.csv(f'{PREFIX[disc]}-SUMMARY-FINAL-AA.csv', hdr, rows)
    # As written (after corrections): two per NOC ranked, in order, 1..n with shared ranks only on
    # equal totals; the others unranked
    per_noc, n = Counter(), 0
    for r in rows:
        per_noc[r['NOC Code']] += 1
        if (per_noc[r['NOC Code']] <= AA_PER_NOC) != bool(r['Rank']):
            err(f'{disc} AA final: bib {r["Bib"]} rank {r["Rank"]!r}, {per_noc[r["NOC Code"]]} of its NOC')
    ranked = [r for r in rows if r['Rank']]
    checks.check_rank_order(f'{disc} AA final', ranked)
    for k, r in enumerate(ranked):
        if r['Rank'] != str(k + 1) and not (k and r['Rank'] == ranked[k - 1]['Rank']):
            err(f'{disc} AA final: rank {r["Rank"]} at place {k + 1}')
    totals = [D(r['Total']) for r in rows]
    if totals != sorted(totals, reverse=True):
        err(f'{disc} AA final: totals out of order')
    return rows

# ---------------------------------------------------------------- run
def run(disc):
    print(f'===== {disc}')
    ents = entries(disc)
    qual = {app: tables(disc, 'QUAL', app) for app in APPS[disc]}
    final = {app: tables(disc, 'EVENT', app) for app in APPS[disc]}
    fv = {r['Bib']: r for r in first_vault_list(disc)} if disc == 'WAG' else {}
    two = {r['Bib']: r for r in qual['VT']}
    vault1 = {}   # bib -> first vault routine, from the most direct source
    for bib, r in fv.items():
        vault1[bib] = r
    for bib, r in two.items():
        if bib in fv:
            # WAG CARVAJAL: the two-vault table prints only vault 1's penalty
            same(f'{disc} QUAL VT bib {bib} vault 1', r['1'] if not r['1'].get('_blank') else
                 dict(r['1'], E=fv[bib]['E'], Total=fv[bib]['Total'], Status=fv[bib]['Status']), fv[bib])
        else:
            vault1[bib] = r['1']
    by_app = {app: {r['Bib']: r for r in qual[app]} for app in APPS[disc] if app != 'VT'}
    def known(app, bib):
        if app == 'VT':
            return vault1.get(bib)
        return by_app[app].get(bib)
    global known_rank
    def known_rank(app, bib):
        if app == 'VT':
            return two[bib]['Rank'] if bib in two else ''
        r = by_app[app].get(bib)
        return r['Rank'] if r else ''
    teams = team_report(disc, known)
    for t in teams:
        for x in t['members']:
            for app, r in x['apps'].items():
                if app == 'VT' and x['Bib'] not in vault1 and r['Status'] != 'DNS':
                    vault1[x['Bib']] = r
    aa = aa_report(disc, known)
    for a in aa:
        if a['Bib'] not in vault1:
            vault1[a['Bib']] = a['apps']['VT']
    # Identity: every bib the results print, with its name and NOC
    seen = defaultdict(set)
    for rows in list(qual.values()) + list(final.values()) + [list(fv.values())]:
        for r in rows:
            seen[r['Bib']].add((r['Name'], r['NOC']))
    participants(disc, ents, seen)
    for t in teams:
        for x in t['members']:
            check_name(disc, f'{disc} team report', x['Bib'], x['Name'], t['NOC'])
    for a in aa:
        check_name(disc, f'{disc} all-around report', a['Bib'], a['Name'], a['NOC'])
    start_lists(disc)
    # Team members with an entered routine the table leaves out (printed DNS in the team report)
    extra_dns = defaultdict(list)
    for t in teams:
        if set(x['Bib'] for x in t['members']) != {b for b, (_, n) in NAMES[disc].items() if n == t['NOC']}:
            err(f'{disc} team {t["NOC"]}: members are not its entries')
        for x in t['members']:
            for app, r in x['apps'].items():
                if r['Status'] == 'DNS':
                    tabled = by_app[app].get(x['Bib']) if app != 'VT' else None
                    if tabled is None:
                        extra_dns[app].append(x['Bib'])
                    elif tabled['Status'] != 'DNS':
                        err(f'{disc} team {t["NOC"]} bib {x["Bib"]} {app}: DNS, the table {tabled["Total"]}')
    for app, bibs in extra_dns.items():
        print(f'  {disc} QUAL {app}: DNS from the team report only: {bibs}')
    # The all-arounders are those with a routine on every apparatus
    full = {b for b in NAMES[disc] if all(b in by_app[a] and by_app[a][b]['Status'] != 'DNS'
                                          for a in by_app)} & set(vault1)
    if {a['Bib'] for a in aa} != full:
        err(f'{disc} all-around: report {sorted(a["Bib"] for a in aa)}, every apparatus {sorted(full)}')
    no_vault = sorted(b for b in NAMES[disc] if all(b in by_app[a] for a in by_app) and b not in vault1
                      and b not in extra_dns.get('VT', []))
    if no_vault:
        print(f'  {disc}: on every other apparatus, no vault printed: {no_vault}')

    qualifiers = lists_of_qualifiers(disc)
    starts = finals_start_lists(disc)
    results, podiums = defaultdict(dict), {}
    for app in APPS[disc]:
        if app == 'VT':
            rows = []
            order = list(fv) if disc == 'WAG' else list(two) + [b for b in vault1 if b not in two]
            for bib in order:
                t = two.get(bib)
                v1 = fv[bib] if bib in fv else vault1[bib]
                rank = fv[bib]['Rank'] if bib in fv else ''
                if t:
                    rows.append(vault_row(disc, 'QUAL', rank, bib, v1, t['2'], t['Combined Bonus'], t['Total'], t['Q'],
                                          t['Rank']))
                else:
                    rows.append(vault_row(disc, 'QUAL', rank, bib, v1))
            for bib in extra_dns.get('VT', []):
                rows.append(vault_row(disc, 'QUAL', '', bib, dns()))
            for r in rows:
                for k in list(r):
                    if k.startswith('_'):
                        del r[k]
            out.csv(f'{PREFIX[disc]}-SCORES-QUAL-VT.csv', common.score_header(True, True), rows)
            results[('QUAL', 'VT')] = {r['Bib']: (r['Qualification Rank'], r['Total']) for r in rows if r['Qualification Rank']}
            if disc == 'WAG' and len(rows) != len(fv):
                err(f'{disc} QUAL VT: {len(rows)} rows, {len(fv)} first vaults')
            f_rows = []
            for t in final[app]:
                f_rows.append(vault_row(disc, 'EVENT', t['Rank'], t['Bib'], t['1'], t['2'], t['Combined Bonus'],
                                        t['Total']))
            for r in f_rows:
                for k in list(r):
                    if k.startswith('_'):
                        del r[k]
            out.csv(f'{PREFIX[disc]}-SCORES-EVENT-VT.csv', common.score_header(True, False), f_rows)
        else:
            rows = []
            for t in qual[app]:
                row = meta(disc, 'QUAL', app, t['Rank'], t['Bib'])
                row.update(routine_cols(t))
                row['Qualification'], row['Qualification Rank'] = t['Q'], t['Rank']
                rows.append(row)
            for bib in extra_dns.get(app, []):
                row = meta(disc, 'QUAL', app, '', bib)
                row.update(routine_cols(dns()))
                row['Qualification'] = row['Qualification Rank'] = ''
                rows.append(row)
            out.csv(f'{PREFIX[disc]}-SCORES-QUAL-{app}.csv', common.score_header(False, True), rows)
            results[('QUAL', app)] = {r['Bib']: (r['Rank'], r['Total']) for r in rows}
            f_rows = []
            for t in final[app]:
                row = meta(disc, 'EVENT', app, t['Rank'], t['Bib'])
                row.update(routine_cols(t))
                f_rows.append(row)
            out.csv(f'{PREFIX[disc]}-SCORES-EVENT-{app}.csv', common.score_header(False, False), f_rows)
        results[('EVENT', app)] = {r['Bib']: (r['Rank'], r['Total']) for r in f_rows}
        for r in rows + f_rows:
            if r['Name'] != NAMES[disc][r['Bib']][0]:
                err(f'{disc} {app}: name')
        for t in qual[app] + final[app]:
            check_name(disc, f'{disc} {app} table', t['Bib'], t['Name'], t['NOC'])
        check_qualifiers(disc, app, rows, qualifiers[app])
        check_final(disc, app, rows, f_rows, starts[app])
        podiums[app] = podium(f_rows)
    check_tie_breaks(disc, results)
    judges(disc)
    t_rows = summary_team(disc, teams)
    a_rows = summary_aa(disc, aa)
    podiums['TEAM'] = podium(t_rows, team=True)
    podiums['AA'] = podium(a_rows)
    check_medallists(disc, podiums)
    competed = {r for rows in results.values() for r in rows} | set(vault1)
    print(f'  {disc}: {len(competed & set(NAMES[disc]))} of {len(NAMES[disc])} entries have results; '
          f'none: {sorted(set(NAMES[disc]) - competed)}')
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])

for disc in ('MAG', 'WAG'):
    run(disc)
out.corrections.finish()
checks.finish()
