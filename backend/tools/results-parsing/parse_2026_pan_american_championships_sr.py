"""Parse the 2026 Senior Pan American Championships results book into the CSV standard.

Usage:

    python3 -I parse_2026_pan_american_championships_sr.py \\
        data/2026/2026-PAN-AMERICAN-CHAMPIONSHIPS/18533-ResultsbookMedia-PanAms-SR.pdf

Writes PARTICIPANTS, JUDGES, SCORES-C1-*, SCORES-C2-*, SCORES-C3-*, RANKING-QUAL-AA,
RANKING-FINAL-TEAM (Competition I decides the team title), RANKING-FINAL-AA and an IMPORT.json for MAG SR and WAG SR next to the PDF, reading
event metadata from the EVENT.csv already there. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.5).

The book is the same organizer media book as the juniors' (§5.4: sporttech.io results tables), but
every page except the schedule is a scanned image. The pages were read with OCR and checked by eye
into `transcriptions/2026-PAN-AMERICAN-CHAMPIONSHIPS-SR/` (format in the README there); this parser
reads those, and compares every routine with sporttech.io's own export of the competition
(`SPORTTECH`, saved next to the PDF). Where the export differs from the book, the export is taken
and the change logged in the event's CORRECTIONS.csv (applied by `common.Output`). Qualification decides the team title (no team final); the top
24 all-arounders (two per country) go to an all-around final, and the top eight per apparatus to the
finals. Neither discipline has a single-vault list: every vaulter's first vault comes from the
all-around report (no vault rank is published, so `Rank` is blank) and the two-vault list adds the
second vault and the qualification ranking.
"""
import os, re, sys, unicodedata
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common, sporttech
from common import D, split_given_first, split_surname_first

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '2026-PAN-AMERICAN-CHAMPIONSHIPS'
TRANSCRIPTIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transcriptions', f'{EVENT_PREFIX}-SR')
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
# All-around report column order, and the RANKING column order (import-file-model.md).
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
# From the Competition Schedule page (p. 2): qualification Wed 17 Jun, all-around finals Fri 19 Jun,
# apparatus finals Sun 21 Jun.
SESSION_DATE = {'QUAL': '2026-06-17', 'AA': '2026-06-19', 'EVENT': '2026-06-21'}
# sporttech.io's CSV export of the whole competition (every frame of every stage), a text copy of
# the results used to cross-check the transcriptions.
SPORTTECH = os.path.join(OUT, '18533-sporttech-export.csv')
# Licences the entry list prints as "En tramite" (pending), from the FIG athlete database.
LICENCES = {}

def plain(s):
    """Upper case without accents, for comparing the many spellings of a name."""
    return ''.join(c for c in unicodedata.normalize('NFD', s.upper()) if unicodedata.category(c) != 'Mn')

def read(name):
    """A transcription's lines, without comments and blank lines, as (line number, fields)."""
    path = os.path.join(TRANSCRIPTIONS, name)
    rows = []
    for n, l in enumerate(open(path, encoding='utf-8'), 1):
        l = l.rstrip('\n')
        if not l.strip() or l.startswith('#'):
            continue
        if l.startswith('!'):
            err(f'{name}:{n}: unreviewed line {l[:80]!r}')
            l = l[1:]
        rows.append((n, l.split('|')))
    return rows

# ---------------------------------------------------------------- participants
PEOPLE = {}   # bib -> dict(name, noc, year, legal)

def entry_counts():
    """`ENTRY-COUNTS.txt`: the book's "Number of Entries by NOC" (p. 3), NOC|men|women."""
    return {disc: {f[0]: int(f[i]) for _, f in read('ENTRY-COUNTS.txt') if int(f[i])}
            for i, disc in ((1, 'MAG'), (2, 'WAG'))}

def participants(disc):
    rows, counts = [], {}
    for n, f in read(f'{disc}-ENTRIES.txt'):
        noc, legal, name, lic, bib, year = f[0].lstrip('~'), *f[1:]
        counts[noc] = counts.get(noc, 0) + 1
        # Struck through on the entry list: withdrawn. Their pending licence is left blank.
        status = 'WITHDRAWN' if f[0].startswith('~') else 'RESERVE' if name.endswith(' (reserve)') else 'COMPETITOR'
        name = name.removesuffix(' (reserve)')
        if status != 'WITHDRAWN' and lic.isdigit() == (bib in LICENCES):
            err(f'participants {disc}: bib {bib} licence {lic!r} vs LICENCES')
        sur, giv = split_given_first(name)
        if not sur or not giv:
            err(f'participants {disc}: name split {name!r} -> {sur!r}/{giv!r}')
        PEOPLE[bib] = dict(name=name, noc=noc, year=year, legal=legal)
        rows.append({'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE,
                     'Event Start Date': EVENT_START, 'Order': len(rows) + 1, 'NOC Code': noc,
                     'Bib Number': bib, 'FIG License': lic if lic.isdigit() else LICENCES.get(bib, ''), 'Name': name,
                     'Surname': sur, 'Given Name': giv, 'Birth Year': year, 'Birth Date': '', 'Entry Status': status})
    if counts != entry_counts()[disc]:
        err(f'participants {disc}: entries by NOC {counts} != "Number of Entries" {entry_counts()[disc]}')
    out.csv(f'{PREFIX[disc]}-PARTICIPANTS.csv', common.PARTICIPANTS + ['Entry Status'], rows)

def check_identity(ctx, bib, name):
    """Results print `SURNAME Given`, sometimes spelled differently from the entry list; every
    surname word must appear in the entry list's full legal name or short name."""
    p = PEOPLE.get(bib)
    if not p:
        err(f'{ctx}: bib {bib} not in participants'); return
    surname = split_surname_first(name)[0] or name.split()[0]
    known = plain(p['legal'] + ' ' + p['name']).replace('-', ' ').split()
    if not all(w in known for w in plain(surname).replace('-', ' ').split()):
        err(f'{ctx}: bib {bib} {name!r} does not match entry {p["legal"]!r}')

# ---------------------------------------------------------------- judges
JUDGE_FN = {'AS': 'SV', 'SA': 'SV', 'Línea': 'L', 'Línea1': 'L1', 'Línea2': 'L2', 'Tiempo': 'T',
            'Tiempo1': 'T1', 'Tiempo2': 'T2', 'Presidenta': 'President', 'Miembro': 'Member'}

def judge_noc(fed):
    # Supervisors are credited to the continental union: 'UPAG-ECU' -> ECU, plain 'UPAG' -> none.
    # Men's finals line judges lent by the women's panel print 'WAG' -> none.
    return '' if fed in ('UPAG', 'WAG') else fed.removeprefix('UPAG-')

def judges(disc):
    rows = []
    for rnd in ('QUAL', 'AA', 'EVENT'):
        n_rnd = len(rows)
        for n, (app, fn, name, fed) in read(f'{disc}-JUDGES-{rnd}.txt'):
            if disc == 'MAG':   # 'SURNAME, Given' (once printed with a full stop for the comma)
                sur, giv = (s.strip() for s in re.split(r'[,.] ', name, maxsplit=1))
            else:               # 'SURNAME Given'
                sur, giv = split_surname_first(name)
            if not sur or not giv:
                err(f'judges {disc} {rnd}: name split {name!r}')
            if app and app not in APPS[disc]:
                err(f'judges {disc} {rnd}: apparatus {app!r}')
            if fed and not re.fullmatch(r'(UPAG-)?[A-Z]{3}|UPAG', fed) or fed == 'WAG' and disc != 'MAG':
                err(f'judges {disc} {rnd}: federation {fed!r}')
            rows.append({'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE,
                         'Event Start Date': EVENT_START, 'Competition': common.COMPETITION[rnd], 'Apparatus': app,
                         'Function': JUDGE_FN.get(fn, fn), 'Name': name, 'Surname': sur, 'Given Name': giv,
                         'NOC Code': judge_noc(fed)})
        print(f'  judges {disc} {rnd}: {len(rows) - n_rnd}')
    out.csv(f'{PREFIX[disc]}-JUDGES.csv', common.JUDGES, rows)

# ---------------------------------------------------------------- result tables
ONE = r'-?\d\.\d'
SCORE = r'\d+\.\d{3}'

def routine(f, ctx):
    """`APP|D|E|B|Pen|Total`, or `APP|—` (no routine), `APP|DNS`, `APP|0` (a bare zero)."""
    kind = f[1] if len(f) == 2 else 'routine'
    if kind == '—':
        return dict(kind='none')
    if kind == 'DNS':
        return dict(kind='dns')
    if kind == '0':
        return dict(kind='zero', D='', E='', B='', Penalty='', Total='0')
    if len(f) != 6:
        err(f'{ctx}: routine {f}'); return dict(kind='none')
    g = dict(kind='routine', D=f[1], E=f[2], B=f[3], Penalty=f[4], Total=f[5])
    if not (re.fullmatch(ONE, g['D']) and re.fullmatch(SCORE, g['E']) and re.fullmatch(SCORE, g['Total'])
            and re.fullmatch(f'({ONE})?', g['B']) and re.fullmatch(f'({ONE})?', g['Penalty'])
            and not g['B'].startswith('-') and (not g['Penalty'] or g['Penalty'].startswith('-'))):
        err(f'{ctx}: values {f}')
    else:
        checks.check_sum(ctx, g['Total'], g['D'], g['E'], g['B'], g['Penalty'])
    return g

def table(name, apps):
    """A results transcription: per athlete `rank|mark|bib|name|totals…`, then a line per routine."""
    athletes, cur = [], None
    for n, f in read(name):
        ctx = f'{name}:{n}'
        if f[0] in apps:
            if cur is None or f[0] in cur['apps']:
                err(f'{ctx}: routine {f[0]} out of place'); continue
            cur['apps'][f[0]] = routine(f, f'{ctx} bib {cur["bib"]} {f[0]}')
            continue
        if len(f) < 4 or not re.fullmatch(r'\d{3}', f[2]) or not re.fullmatch(r'\d*', f[0]):
            err(f'{ctx}: athlete line {f}'); cur = None; continue
        if not re.fullmatch(r'(Q|[QR]\d)?', f[1]):
            err(f'{ctx}: marker {f[1]!r}')
        cur = dict(rank=f[0], mk=f[1], bib=f[2], name=f[3], totals=f[4:], apps={}, line=n)
        check_identity(ctx, cur['bib'], cur['name'])
        athletes.append(cur)
    bibs = [a['bib'] for a in athletes]
    if len(bibs) != len(set(bibs)):
        err(f'{name}: a bib listed twice')
    return athletes

STATUS = {'routine': 'COMPLETED', 'dns': 'DNS', 'zero': 'COMPLETED'}

def routine_cols(g, suffix='', vault=False):
    if g is None:
        return {f'{c}{suffix}': '' for c in common.ROUTINE}
    status = 'INVALID_VAULT' if vault and g['kind'] == 'zero' else STATUS[g['kind']]
    return {f'Status{suffix}': status, f'D{suffix}': g.get('D', ''), f'E{suffix}': g.get('E', ''),
            f'B{suffix}': g.get('B', ''), f'Penalty{suffix}': g.get('Penalty', ''), f'SJ Penalty{suffix}': '',
            f'Total{suffix}': g.get('Total', '')}

def meta(disc, rnd, app, rank, bib):
    return {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE,
            'Competition Start Date': SESSION_DATE[rnd], 'Competition': common.COMPETITION[rnd], 'Part': '', 'Apparatus': app,
            'Rank': rank, 'Bib': bib, 'Name': PEOPLE[bib]['name'], 'NOC Code': PEOPLE[bib]['noc']}

def same_routine(ctx, a, b):
    keys = ['kind', 'D', 'E', 'B', 'Penalty', 'Total']
    if [a.get(k, '') for k in keys] != [b.get(k, '') for k in keys]:
        err(f'{ctx}: {[a.get(k, "") for k in keys]} != all-around {[b.get(k, "") for k in keys]}')

def check_ranks(ctx, rows, key='Total'):
    """Ranks published as printed: never decreasing, totals never increasing, ties equal, and no rank
    skipped except after a tie."""
    ranked = [r for r in rows if r['Rank']]
    checks.check_rank_order(ctx, [dict(Rank=r['Rank'], Total=r[key], Bib=r['Bib']) for r in ranked])
    for i, r in enumerate(ranked):
        if int(r['Rank']) != i + 1 and (i == 0 or r['Rank'] != ranked[i - 1]['Rank']):
            err(f'{ctx}: rank {r["Rank"]} at position {i + 1} (bib {r["Bib"]})')

def aa_total(a, ctx, n):
    """An all-around row's printed total: the apparatus sum, or DNF/DNS/— when unfinished."""
    if len(a['totals']) != 1:
        err(f'{ctx}: totals {a["totals"]}'); return ''
    total = a['totals'][0]
    done = [g for g in a['apps'].values() if g['kind'] in ('routine', 'zero')]
    if re.fullmatch(SCORE, total):
        if len(a['apps']) != n:
            err(f'{ctx}: {len(a["apps"])} routines with a total')
        if sum(D(g['Total']) for g in done) != D(total):
            err(f'{ctx}: apparatus sum {sum(D(g["Total"]) for g in done)} != {total}')
        return total
    if total not in ('DNF', 'DNS', '—'):
        err(f'{ctx}: total {total!r}')
    return ''

# ---------------------------------------------------------------- all-around and team reports
def aa_report(disc):
    """The qualification all-around report: every routine of the round."""
    name = f'{disc}-QUAL-AA.txt'
    athletes = table(name, APPS[disc])
    for a in athletes:
        ctx = f'{name} bib {a["bib"]}'
        for app in APPS[disc]:
            a['apps'].setdefault(app, dict(kind='none'))
        a['Total'] = aa_total(dict(a, apps={k: g for k, g in a['apps'].items() if g['kind'] != 'none'}), ctx,
                              sum(g['kind'] != 'none' for g in a['apps'].values()))
        if a['mk'] not in ('', 'Q') and not re.fullmatch(r'R\d', a['mk']):
            err(f'{ctx}: marker {a["mk"]!r}')
    check_ranks(f'{disc} QUAL AA', [dict(Rank=a['rank'], Total=a['Total'], Bib=a['bib']) for a in athletes])
    check_markers(f'{disc} QUAL AA', [a for a in athletes if a['rank']], numbered=False)
    return athletes

def summary_aa(disc, athletes, rnd):
    final = rnd == 'AA'
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'Bib', 'Name',
           'NOC Code'] + [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total'] + \
          ([] if final else ['Qualification'])
    rows = []
    for a in athletes:
        if all(g['kind'] == 'none' for g in a['apps'].values()):
            continue          # entered but competed on nothing
        r = {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE, 'Event Start Date': EVENT_START,
             'Competition': common.COMPETITION[rnd], 'Part': '', 'Rank': a['rank'], 'Bib': a['bib'], 'Name': PEOPLE[a['bib']]['name'],
             'NOC Code': PEOPLE[a['bib']]['noc'], 'SJ Penalty': '', 'Total': a['Total']}
        if not final:
            r['Qualification'] = a['mk']
        for app in SUMMARY_APPS[disc]:
            r[f'{app} Total'] = a['apps'][app].get('Total', '')
        rows.append(r)
    out.ranking(PREFIX[disc], 'AA', hdr, rows, EVENTS[PREFIX[disc]])

def team_report(disc, aa):
    """`T|rank|NOC|apparatus totals…|total[|penalty]`, then `M|bib|name|values…` per member: a score,
    `—` (no routine), `DNS`, or blank (a skipped apparatus). The penalty is a deduction from the team
    total (CUB MAG, -1.000), written as the summary's SJ Penalty."""
    name = f'{disc}-QUAL-TEAM.txt'
    n = len(APPS[disc])
    teams = []
    for ln, f in read(name):
        if f[0] == 'T':
            if len(f) not in (n + 4, n + 5):
                err(f'{name}:{ln}: team line {f}'); continue
            teams.append(dict(Rank=f[1], NOC=f[2], totals=f[3:3 + n], Total=f[3 + n],
                              Penalty=f[4 + n] if len(f) == n + 5 else '', athletes={}))
        elif f[0] == 'M' and teams:
            if len(f) != n + 3:
                err(f'{name}:{ln}: member line {f}'); continue
            check_identity(f'{name}:{ln}', f[1], f[2])
            teams[-1]['athletes'][f[1]] = dict(zip(APPS[disc], f[3:]))
        else:
            err(f'{name}:{ln}: line {f}')
    for t in teams:
        c = f'{disc} team {t["NOC"]}'
        for app, total in zip(APPS[disc], t['totals']):
            got = []
            for bib, apps in t['athletes'].items():
                v = apps[app]
                g = aa[bib]['apps'][app] if bib in aa else dict(kind='none')
                want = {'routine': g.get('Total'), 'zero': '0', 'dns': 'DNS', 'none': '—'}[g['kind']]
                if v != want and not (v == '' and g['kind'] in ('none', 'zero')):
                    err(f'{c} bib {bib} {app}: {v!r} != all-around {want!r}')
                if g['kind'] in ('routine', 'zero'):
                    got.append(D(g['Total']))
            best = sum(sorted(got, reverse=True)[:3])
            if best != D(total):
                err(f'{c} {app}: best three {best} != {total}')
        if sum(D(x) for x in t['totals']) + D(t['Penalty']) != D(t['Total']):
            err(f'{c}: apparatus totals != {t["Total"]}')
        if any(PEOPLE[b]['noc'] != t['NOC'] for b in t['athletes'] if b in PEOPLE):
            err(f'{c}: athlete from another NOC')
        if any(b not in aa for b in t['athletes']):
            err(f'{c}: member missing from the all-around report')
    team_nocs = {t['NOC'] for t in teams}
    for a in aa.values():
        noc = PEOPLE[a['bib']]['noc']
        if noc in team_nocs and not any(a['bib'] in t['athletes'] for t in teams if t['NOC'] == noc):
            err(f'{disc} team {noc}: bib {a["bib"]} not listed as a member')
    checks.check_rank_order(f'{disc} team', [dict(Rank=t['Rank'], Total=t['Total'], Bib=t['NOC']) for t in teams])
    hdr = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'NOC Code'] + \
          [f'{a} Total' for a in SUMMARY_APPS[disc]] + ['SJ Penalty', 'Total', 'Qualification']
    rows = []
    for t in teams:
        r = {'Event Name': EVENT_NAME, 'Discipline': disc, 'Age Category': AGE, 'Event Start Date': EVENT_START,
             'Competition': 'C1', 'Part': '', 'Rank': t['Rank'], 'NOC Code': t['NOC'], 'SJ Penalty': t['Penalty'],
             'Total': t['Total'], 'Qualification': ''}
        for app, total in zip(APPS[disc], t['totals']):
            r[f'{app} Total'] = total
        rows.append(r)
    out.ranking(PREFIX[disc], 'TEAM', hdr, rows, EVENTS[PREFIX[disc]])

# ---------------------------------------------------------------- qualification
def qualification(mk):
    # Q1…Q8 number the qualifiers in order; the stored value is Q. Reserves keep R1…R3.
    return 'Q' if mk.startswith('Q') else mk

def check_markers(ctx, ranked, numbered=True):
    """Qualifiers (Q1…Q8, or plain Q on the all-around ranking) then reserves R1…R3, in rank order."""
    qs = [r['mk'] for r in ranked if r['mk'].startswith('Q')]
    rs = [r['mk'] for r in ranked if r['mk'].startswith('R')]
    want_q = [f'Q{i}' for i in range(1, len(qs) + 1)] if numbered else ['Q'] * len(qs)
    if qs != want_q or rs != [f'R{i}' for i in range(1, len(rs) + 1)]:
        err(f'{ctx}: markers out of order {qs} {rs}')
    last_q = max((i for i, r in enumerate(ranked) if r['mk'].startswith('Q')), default=-1)
    if any(r['mk'].startswith('R') for r in ranked[:last_q]):
        err(f'{ctx}: a reserve ranked above a qualifier')
    nocs = {}
    for r in ranked:
        if r['mk'].startswith('Q'):
            noc = PEOPLE[r['bib']]['noc']
            nocs[noc] = nocs.get(noc, 0) + 1
    if any(v > 2 for v in nocs.values()):
        err(f'{ctx}: more than two qualifiers from one NOC {nocs}')

def qual_app(disc, app, aa):
    name = f'{disc}-QUAL-{app}.txt'
    ctx = f'{disc} QUAL {app}'
    bs = table(name, [app])
    rows = []
    for b in bs:
        c = f'{ctx} bib {b["bib"]}'
        if b['totals'] and any(b['totals']):
            err(f'{c}: extra values {b["totals"]}')
        g = b['apps'].get(app)
        if g is None:
            err(f'{c}: no routine'); continue
        same_routine(c, g, aa[b['bib']]['apps'][app] if b['bib'] in aa else dict(kind='none'))
        if g['kind'] == 'none':
            if b['rank'] or b['mk']:
                err(f'{c}: ranked without a routine')
            continue
        rows.append({**meta(disc, 'QUAL', app, b['rank'], b['bib']), **routine_cols(g),
                     'Qualification': qualification(b['mk']), 'Qualification Rank': b['rank']})
    aa_bibs = {bib for bib, a in aa.items() if a['apps'][app]['kind'] != 'none'}
    if {r['Bib'] for r in rows} != aa_bibs:
        err(f'{ctx}: athletes differ from the all-around report: {sorted({r["Bib"] for r in rows} ^ aa_bibs)}')
    check_ranks(ctx, rows)
    check_markers(ctx, [b for b in bs if b['rank']])
    out.csv(f'{PREFIX[disc]}-SCORES-C1-{app}.csv', common.score_header(False, True), rows)
    return {r['Bib']: r['Qualification'] for r in rows if r['Qualification']}

def vault_totals(f, ctx):
    """A vault line's trailing values: [VB] Total (WAG prints its vault bonus in its own column)."""
    if len(f) == 2 and re.fullmatch(f'({ONE})?', f[0]):
        return f[0], f[1]
    if len(f) == 1:
        return '', f[0]
    err(f'{ctx}: totals {f}')
    return '', ''

def qual_vault(disc, aa):
    name = f'{disc}-QUAL-VT.txt'
    ctx = f'{disc} QUAL VT'
    double = {}
    bs = table(name, ['VT1', 'VT2'])
    for b in bs:
        c = f'{ctx} bib {b["bib"]}'
        v1, v2 = b['apps'].get('VT1'), b['apps'].get('VT2')
        if not v1 or not v2:
            err(f'{c}: two vaults expected'); continue
        same_routine(c + ' vault 1', v1, aa[b['bib']]['apps']['VT'])
        bonus, total = vault_totals(b['totals'], c)
        checks.check_vault_average(c, v1['Total'], v2['Total'], bonus, total)
        double[b['bib']] = dict(b=b, v2=v2, bonus=bonus, Total=total)
    # sporttech.io ranks every vaulter, a single vault counting half, but lists only the two-vault
    # athletes: the ranks skip the one-vault athletes between them (MAG 14-16), so only the order is checked.
    checks.check_rank_order(ctx, [dict(Rank=d['b']['rank'], Total=d['Total'], Bib=bib) for bib, d in double.items()
                                  if d['b']['rank']])
    check_markers(ctx, [b for b in bs if b['rank']])
    rows = []
    for a in aa.values():
        g = a['apps']['VT']
        if g['kind'] == 'none':
            continue
        r = {**meta(disc, 'QUAL', 'VT', '', a['bib']), **routine_cols(g, '1', vault=True), **routine_cols(None, '2'),
             'Combined Bonus': '', 'Total': g.get('Total', ''), 'Qualification': '', 'Qualification Rank': ''}
        if a['bib'] in double:
            d = double[a['bib']]
            r.update(routine_cols(d['v2'], '2', vault=True))
            r.update({'Combined Bonus': d['bonus'], 'Total': d['Total'], 'Qualification Rank': d['b']['rank'],
                      'Qualification': qualification(d['b']['mk'])})
        rows.append(r)
    if not set(double) <= {r['Bib'] for r in rows}:
        err(f'{ctx}: two-vault athletes missing from the all-around report')
    out.csv(f'{PREFIX[disc]}-SCORES-C1-VT.csv', common.score_header(True, True), rows)
    return {r['Bib']: r['Qualification'] for r in rows if r['Qualification']}

# ---------------------------------------------------------------- all-around final
def aa_final(disc, qual_aa):
    name = f'{disc}-AA.txt'
    athletes = table(name, APPS[disc])
    marks = {a['bib']: a['mk'] for a in qual_aa}
    for a in athletes:
        ctx = f'{name} bib {a["bib"]}'
        for app in APPS[disc]:
            a['apps'].setdefault(app, dict(kind='none'))
        a['Total'] = aa_total(dict(a, apps={k: g for k, g in a['apps'].items() if g['kind'] != 'none'}), ctx,
                              len(APPS[disc]))
        if a['mk']:
            err(f'{ctx}: marker {a["mk"]!r} in a final')
        if a['bib'] not in marks:
            err(f'{ctx}: not in the qualification all-around ranking')
    # The all-around ranking prints no reserve markers, so a replacement is any finalist without a Q.
    finalists = {a['bib'] for a in athletes}
    absent = sorted(b for b, m in marks.items() if m == 'Q' and b not in finalists)
    replacements = sorted(b for b in finalists if marks.get(b) == '')
    if absent or replacements:
        print(f'  {disc} AA final: qualifiers {absent} absent; {replacements} competed without a Q')
    check_ranks(f'{disc} AA final', [dict(Rank=a['rank'], Total=a['Total'], Bib=a['bib']) for a in athletes])
    for app in APPS[disc]:
        vault = False      # all-around final vault is a single attempt
        rows = [{**meta(disc, 'AA', app, '', a['bib']), **routine_cols(a['apps'][app], vault=app == 'VT')}
                for a in athletes if a['apps'][app]['kind'] != 'none']
        out.csv(f'{PREFIX[disc]}-SCORES-C2-{app}.csv', common.score_header(vault, False), rows)
    summary_aa(disc, athletes, 'AA')

# ---------------------------------------------------------------- finals
def final(disc, app, marks):
    name = f'{disc}-EVENT-{app}.txt'
    ctx = f'{disc} EVENT {app}'
    vault = app == 'VT'
    q = {b for b, m in marks.items() if m == 'Q'}
    r_ = {b for b, m in marks.items() if m.startswith('R')}
    rows = []
    for b in table(name, ['VT1', 'VT2'] if vault else [app]):
        c = f'{ctx} bib {b["bib"]}'
        if b['bib'] not in q | r_:
            err(f'{c}: not a qualifier or reserve')
        if vault:
            g1, g2 = b['apps'].get('VT1'), b['apps'].get('VT2')
            if not g1 or not g2:
                err(f'{c}: two vaults expected'); continue
            bonus, total = vault_totals(b['totals'], c)
            checks.check_vault_average(c, g1['Total'], g2['Total'], bonus, total)
            r = {**meta(disc, 'EVENT', app, b['rank'], b['bib']), **routine_cols(g1, '1', True),
                 **routine_cols(g2, '2', True), 'Combined Bonus': bonus, 'Total': total}
        else:
            g = b['apps'].get(app)
            if not g:
                err(f'{c}: no routine'); continue
            if b['totals'] != [g.get('Total', '')]:
                err(f'{c}: final total {b["totals"]} != routine {g.get("Total")}')
            r = {**meta(disc, 'EVENT', app, b['rank'], b['bib']), **routine_cols(g)}
        rows.append(r)
    finalists = {r['Bib'] for r in rows}
    if len(rows) != 8:
        err(f'{ctx}: {len(rows)} finalists')
    if len(q - finalists) != len(finalists & r_):
        err(f'{ctx}: qualifiers absent {sorted(q - finalists)}, reserves in {sorted(finalists & r_)}')
    elif q - finalists:
        print(f'  {ctx}: qualifiers {sorted(q - finalists)} replaced by reserves {sorted(finalists & r_)}')
    check_ranks(ctx, rows)
    out.csv(f'{PREFIX[disc]}-SCORES-C3-{app}.csv', common.score_header(vault, False), rows)

# ---------------------------------------------------------------- sporttech.io cross-check
EXPORT_TITLE = {'MAG': 'SENIOR - Men', 'WAG': 'SENIOR - Women'}
ROUND_OF_DATE = {'2026-06-17': 'QUAL', '2026-06-18': 'QUAL', '2026-06-19': 'AA', '2026-06-21': 'EVENT'}

def noc_of(bib):
    return PEOPLE[bib]['noc'] if bib in PEOPLE else None

# ---------------------------------------------------------------- main
for disc in ('MAG', 'WAG'):
    participants(disc)
    judges(disc)
    athletes = aa_report(disc)
    aa = {a['bib']: a for a in athletes}
    summary_aa(disc, athletes, 'QUAL')
    team_report(disc, aa)
    for app in APPS[disc]:
        marks = qual_vault(disc, aa) if app == 'VT' else qual_app(disc, app, aa)
        final(disc, app, marks)
    aa_final(disc, athletes)
    sporttech.crosscheck(OUT, PREFIX[disc], SPORTTECH, EXPORT_TITLE[disc], ROUND_OF_DATE, noc_of, err)
    out.manifest(PREFIX[disc], EVENTS[PREFIX[disc]])

corrections.finish()
checks.finish()
