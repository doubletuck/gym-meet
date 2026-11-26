"""Parse the 2026 Oceania Championships media books (seniors and juniors) into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_oceania_championships.py \\
        data/2026/2026-OCEANIA-CHAMPIONSHIPS/18530-ResultsbookMedia.pdf \\
        data/2026/2026-OCEANIA-CHAMPIONSHIPS/18531-ResultsbookMedia.pdf

Writes PARTICIPANTS, JUDGES, SCORES-C1-*, RANKING-FINAL-AA, RANKING-FINAL-TEAM and an IMPORT.json for
MAG and WAG, SR and JR, next to the PDFs, reading event metadata from the EVENT.csv already there.
Exits non-zero if any check fails (docs/instructions-results-parsing.md §3; this source format is
§5.17).

The Oceania Gymnastics Union's media books, one per age category (18530 seniors, 18531 juniors): per
discipline a cover, the Competition Schedule, entry counts and medallists (text), the entry lists
(text), then scanned Elevien start lists, the judges' sheet, the team results and the all-around
results. The scans were transcribed by eye into `transcriptions/2026-OCEANIA-CHAMPIONSHIPS/` (format
in the README there), along with the team line-ups from the Elevien results site, which the books
don't print. One competition on 9 May decides both titles, which the books call the All-around
Final and the Team Final: it is Competition I (C1), and both final rankings rank its routines (§4.9).
"""
import os, re, sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D, split_given_first

PDFS = sys.argv[1:]
OUT = os.path.dirname(os.path.abspath(PDFS[0]))
EVENT_PREFIX = '2026-OCEANIA-CHAMPIONSHIPS'
TRANSCRIPTIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'transcriptions', EVENT_PREFIX)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
checks = common.Checks()
err = checks.err

AGE_HEADING = {'SR': 'Senior', 'JR': 'Junior'}
DISC_HEADING = {'MAG': 'Men’s Artistic Gymnastics', 'WAG': 'Women’s Artistic Gymnastics'}
# Each book holds one age category, both disciplines; the page headings say which
PAGES = {}
for pdf in PDFS:
    pages = common.pdf_pages(pdf)
    ages = {age for age, word in AGE_HEADING.items() if any(f'Gymnastics - {word}' in p for p in pages)}
    if len(ages) != 1:
        raise SystemExit(f'{pdf}: age categories {ages}')
    PAGES[ages.pop()] = pages
DIVISIONS = [(disc, age) for age in ('SR', 'JR') if age in PAGES for disc in ('MAG', 'WAG')]
PREFIX = {div: f'{EVENT_PREFIX}-{div[0]}-{div[1]}' for div in DIVISIONS}
corrections = common.Corrections(OUT, EVENT_PREFIX, [f'{d}-{a}' for d, a in DIVISIONS], err)
out = common.Output(OUT, corrections)
# The all-around report's column order (icons), and the RANKING column order.
APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
SUMMARY_APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
COUNTRY = {'Australia': 'AUS', 'New Zealand': 'NZL'}
# The competition day, from the Competition Schedules (8 May is podium training); checked below.
SESSION_DATE = '2026-05-09'
# Where the start lists and the results disagree. MAG SR HARDY (103) has a high bar score but is on no
# high bar rotation. WAG SR BAYLES (207) is on the beam start list and WAG JR ATKINSON (212) on bars,
# but their cells are blank: a row with no status, made DNS by a correction. The MAG JR start list
# prints DAVIES (113) twice in five groups.
NOT_ON_START_LIST = {('MAG', 'SR', 'HB', '103')}
BLANK_ON_RESULTS = {('WAG', 'SR', 'BB', '207'), ('WAG', 'JR', 'UB', '212')}
DUPLICATED_ON_START_LIST = {('MAG', 'JR', '113')}
# The team results print totals only ("Team Results 3 + 2": up to five a team, up to four up on an
# apparatus, the best three counting; the fifth competes as an individual, for World Championships
# qualification). Who was up for the team comes from <DISC>-<AGE>-TEAM-SCORES.txt, the Elevien results
# site's team pages (screenshots from the user). A country entering no team (MAG JR New Zealand, though
# the site ranks it) has only individuals.
# Judges' functions as printed, written as JudgeFunction codes (docs §4.7)
FUNCTION = {'AS': 'SV', 'Supervisor': 'SV', 'Line': 'L', 'Line 1': 'L1', 'Line 2': 'L2', 'Time': 'T',
            'Time 1': 'T1', 'Time 2': 'T2', 'Reserve': 'R', 'SJ': 'TD', 'SUPERIOR JURY': 'TD'}
for f in ('D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5'):
    FUNCTION[f] = f
SCORE = r'\d+\.\d{3}'

def label(div):
    return f'{div[0]}-{div[1]}'

def transcription(div, kind):
    return f'{label(div)}-{kind}.txt'

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

def page(div, title):
    """The text of the division's page whose report title is `title`."""
    disc, age = div
    heading = f'{DISC_HEADING[disc]} - {AGE_HEADING[age]}'
    hits = [p for p in PAGES[age] if heading in p and re.search(rf'^{re.escape(title)}\s*$', p, re.M)]
    if len(hits) != 1:
        raise SystemExit(f'{label(div)}: {len(hits)} pages titled {title!r}')
    return hits[0]

def section(text, title, end=None):
    """The lines of a page between a section title and the next title (or the page end)."""
    lines = text.split('\n')
    start = next(i for i, l in enumerate(lines) if l.strip() == title)
    body = []
    for l in lines[start + 1:]:
        if end and l.strip() == end:
            break
        if 'Media Book' in l:
            break
        body.append(l)
    return [l for l in body if l.strip()]

# ---------------------------------------------------------------- the text pages
def schedule(div):
    """The Competition Schedule's competition day, and the entry counts per country."""
    text = page(div, 'Competition Schedule')
    day, days = None, []
    for l in section(text, 'Competition Schedule', 'Entries by NOC'):
        m = re.match(r'\s*(\d+)/(\d+)/(\d{4})\s', l)
        if m:
            day = f'{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}'
        if re.search(r'\sCompetition$', l.strip()):
            days.append(day)
    if days != [SESSION_DATE]:
        err(f'{label(div)} schedule: competition on {days}, expected {SESSION_DATE}')
    counts = {}
    for l in section(text, 'Entries by NOC', 'Medallists by Event')[1:]:
        m = re.fullmatch(r'\s*(.+?)\s+(\d+)\s+(\d+)\s*', l)
        if not m:
            err(f'{label(div)} entries by NOC: unread line {l!r}'); continue
        counts[COUNTRY[m[1]]] = (int(m[2]), int(m[3]))
    return text, counts

def medallists(div, text):
    """Medallists by Event: {'AA': [(name, NOC), …], 'TEAM': [NOC, …]} in medal order."""
    medals, event = {'AA': [], 'TEAM': []}, None
    for l in section(text, 'Medallists by Event', 'Medal Standings')[1:]:
        m = re.fullmatch(r'\s*(All around Final|Team Final)?\s*(.+?)\s+(Gold|Silver|Bronze)\s*', l)
        if not m:
            err(f'{label(div)} medallists: unread line {l!r}'); continue
        if m[1]:
            event = 'AA' if m[1].startswith('All') else 'TEAM'
        if event == 'AA':
            a = re.fullmatch(r'(.+) \((\w{3})\)', m[2])
            medals['AA'].append((a[1], a[2]))
        else:
            medals['TEAM'].append(COUNTRY[m[2]])
    return medals

def participants(div, counts):
    """Entry List (by NF, in printed order) -> PARTICIPANTS rows, checked against the Entry List by
    Bib Number and the entry counts."""
    text = page(div, 'Entry List')
    by_nf, noc = [], None
    for l in section(text, 'Entry List', 'Entry List by Bib Number')[1:]:
        m = re.fullmatch(r'\s*(?:(Australia|New Zealand)\s{2,})?(\S.*?)\s*', l)
        noc = COUNTRY[m[1]] if m[1] else noc
        by_nf.append((noc, m[2]))
    by_bib = {}
    for l in section(text, 'Entry List by Bib Number')[1:]:
        m = re.fullmatch(r'\s*(\d+)\s+(Australia|New Zealand)\s+(\S.*?)\s*', l)
        if not m:
            err(f'{label(div)} entry list by bib: unread line {l!r}'); continue
        by_bib[(COUNTRY[m[2]], m[3])] = m[1]
    if sorted(by_nf) != sorted(by_bib):
        err(f'{label(div)}: the entry lists by NF and by bib differ')
    for noc, (teams, athletes) in counts.items():
        if sum(1 for n, _ in by_nf if n == noc) != athletes:
            err(f'{label(div)} {noc}: {athletes} athletes on the entries by NOC page')
    ev = EVENTS[PREFIX[div]]
    rows = []
    for order, (noc, name) in enumerate(by_nf, 1):
        surname, given = split_given_first(name)
        if not surname or not given:
            err(f'{label(div)} entry {name!r}: no SURNAME Given split')
        rows.append({'Event Name': ev['Title'], 'Discipline': div[0], 'Age Category': div[1],
                     'Event Start Date': ev['Start Date'], 'Order': order, 'NOC Code': noc,
                     'Bib Number': by_bib.get((noc, name), ''), 'FIG License': '', 'Name': name,
                     'Surname': surname, 'Given Name': given, 'Birth Year': '', 'Birth Date': ''})
    return rows

# ---------------------------------------------------------------- the transcriptions
def same_name(printed, entry):
    return printed.casefold() == entry.casefold()

def all_around(div, people):
    """<DIV>-AA.txt -> athletes [{rank, bib, total, routines {APP: fields, or None for DNS}}], checked."""
    disc = div[0]
    name = transcription(div, 'AA')
    athletes, a = [], None
    for n, f in read(name):
        ctx = f'{name}:{n}'
        if f[0] in APPS[disc]:
            if f[0] in a['routines']:
                err(f'{ctx}: {f[0]} twice')
            if f[1:] == ['DNS']:
                a['routines'][f[0]] = None
                continue
            app, d, e, p, s, final = f
            if not (re.fullmatch(r'\d+\.\d', d) and re.fullmatch(SCORE, e) and re.fullmatch(r'\d+\.\d', p)
                    and re.fullmatch(r'(\d+\.\d)?', s) and re.fullmatch(SCORE, final)):
                err(f'{ctx}: unread routine {f}')
            if (s == '') != (disc == 'WAG' or app == 'PH'):
                err(f'{ctx}: an S column where none is printed, or the reverse')
            checks.check_sum(ctx, final, d, e, s, f'-{p}')
            a['routines'][app] = {'D': d, 'E': e, 'P': p, 'S': s, 'Total': final}
        else:
            rank, bib, printed, noc, total = f
            person = people.get(bib)
            if not person:
                err(f'{ctx}: bib {bib} is not on the entry list'); continue
            if not same_name(printed, person['Name']) or noc != person['NOC Code']:
                err(f'{ctx}: {printed} {noc} is {person["Name"]} {person["NOC Code"]} on the entry list')
            a = {'rank': rank, 'bib': bib, 'total': total, 'routines': {}, 'ctx': ctx}
            athletes.append(a)
    for a in athletes:
        checks.check_sum(f'{a["ctx"]} total', a['total'], *[r['Total'] for r in a['routines'].values() if r])
    # The unranked follow the ranking. Not every incomplete all-around is unranked: WAG SR GODWIN, with
    # no floor, is ranked 6th, ahead of SHIELDS's four apparatus.
    if any(not a['rank'] and b['rank'] for a, b in zip(athletes, athletes[1:])):
        err(f'{label(div)} all-around: a ranked athlete follows an unranked one')
    ranked = [{'Rank': a['rank'], 'Total': a['total'], 'Bib': a['bib']} for a in athletes]
    checks.check_rank_order(f'{label(div)} all-around', ranked)
    ranks = [a['rank'] for a in athletes if a['rank']]
    if ranks != [str(i) for i in range(1, len(ranks) + 1)]:
        err(f'{label(div)} all-around: ranks are not 1, 2, 3, …')
    if sorted(a['bib'] for a in athletes) != sorted(people):
        err(f'{label(div)} all-around: the athletes are not the entry list')
    return athletes

def start_lists(div, people, athletes):
    """Each apparatus's start list (all rotations) must be the athletes with a cell on it."""
    name = transcription(div, 'START')
    on = {}
    for n, (rot, app, bib, printed) in read(name):
        if bib not in people or not same_name(printed, people[bib]['Name']):
            err(f'{name}:{n}: {bib} {printed} is not on the entry list')
        if bib in on.setdefault(app, set()) and (*div, bib) not in DUPLICATED_ON_START_LIST:
            err(f'{name}:{n}: {bib} twice on {app}')
        on[app].add(bib)
    for app in APPS[div[0]]:
        cells = {a['bib'] for a in athletes if app in a['routines']}
        expected = (on.get(app, set()) | {b for *d, p, b in NOT_ON_START_LIST if (*d, p) == (*div, app)}) \
            - {b for *d, p, b in BLANK_ON_RESULTS if (*d, p) == (*div, app)}
        if cells != expected:
            err(f'{label(div)} {app}: results {sorted(cells)} != start list {sorted(expected)}')

def team_scores(div, athletes, people, printed):
    """<DIV>-TEAM-SCORES.txt -> ({(bib, APP): role}, {NOC: {APP: total}}), checked against the
    all-around report and the printed team totals."""
    disc = div[0]
    name = transcription(div, 'TEAM-SCORES')
    by_bib = {a['bib']: a for a in athletes}
    roles, totals, noc = {}, {}, None
    for n, f in read(name):
        ctx = f'{name}:{n}'
        if f[0] == 'T':
            noc = COUNTRY[f[2]]
            if (f[1], noc, f[3]) not in printed:
                err(f'{ctx}: {f[1:]} is not on the team results page')
            totals[noc] = {app: Decimal(0) for app in APPS[disc]}
            continue
        _, bib, person, *values = f
        if bib not in by_bib or not same_name(person, people[bib]['Name']) or people[bib]['NOC Code'] != noc:
            err(f'{ctx}: {bib} {person} is not a {noc} athlete'); continue
        if len(values) != len(APPS[disc]):
            err(f'{ctx}: {len(values)} values'); continue
        for app, v in zip(APPS[disc], values):
            if not v:
                continue
            if app not in by_bib[bib]['routines']:
                err(f'{ctx}: {app} {v}, but no {app} cell on the all-around report'); continue
            routine = by_bib[bib]['routines'][app]
            if (routine['Total'] if routine else 'DNS') != v.lstrip('~'):
                err(f'{ctx}: {app} {v} is not the all-around report\'s {routine and routine["Total"]}')
            # A team member who didn't start is out of the total, as a dropped score is
            counting = routine and not v.startswith('~')
            roles[(bib, app)] = 'COUNTING' if counting else 'DROPPED'
            if counting:
                totals[noc][app] += D(routine['Total'])
    for r, noc, total in printed:
        if noc not in totals:
            err(f'{name}: no {noc} team'); continue
        if sum(totals[noc].values()) != D(total):
            err(f'{name}: {noc} counting scores add up to {sum(totals[noc].values())}, not {total}')
        for app in APPS[disc]:
            # Up for the team and performed (AUS WAG SR bars lists a fifth member, BAYLES, who didn't start)
            up = [(b, role) for (b, a), role in roles.items()
                  if a == app and people[b]['NOC Code'] == noc and by_bib[b]['routines'][app]]
            counting = [D(by_bib[b]['routines'][app]['Total']) for b, role in up if role == 'COUNTING']
            dropped = [D(by_bib[b]['routines'][app]['Total']) for b, role in up if role == 'DROPPED']
            if len(up) > 4 or len(counting) > 3 or (dropped and counting and max(dropped) > min(counting)):
                err(f'{name}: {noc} {app}: {len(up)} up, {len(counting)} counting, or a dropped score above '
                    f'a counting one')
    # A country's athlete with a routine where they weren't up for the team was the individual, and
    # so was one on the start list with a blank cell (WAG SR BAYLES's beam: no team score there)
    for a in athletes:
        for app in a['routines']:
            roles.setdefault((a['bib'], app), 'INDIVIDUAL')
    for *d, app, bib in BLANK_ON_RESULTS:
        if tuple(d) == div:
            roles.setdefault((bib, app), 'INDIVIDUAL')
    return roles, totals

def teams(div, athletes, people, counts):
    """<DIV>-TEAM.txt -> ([(rank, NOC, total)], {(bib, APP): role}, {NOC: {APP: total}})."""
    rows = [(rank, COUNTRY[c], total) for _, (rank, c, total) in read(transcription(div, 'TEAM'))]
    checks.check_rank_order(f'{label(div)} team', [{'Rank': r, 'Total': t, 'Bib': noc} for r, noc, t in rows])
    for noc, (n_teams, _) in counts.items():
        if n_teams != sum(1 for _, t, _ in rows if t == noc):
            err(f'{label(div)} {noc}: {n_teams} teams on the entries by NOC page')
    roles, totals = team_scores(div, athletes, people, rows)
    return rows, roles, totals

def judges(div):
    """<DIV>-JUDGES.txt -> JUDGES rows (round AA). MAG prints `Given Surname (NOC)`, WAG `SURNAME
    Given`, and both Superior Juries `Given Surname`. A federation printed with the union
    (`AUS / OGU`, `OGU (AUS)`) is the federation; the union alone (`OGU`) is blank (§4.7)."""
    disc = div[0]
    ev = EVENTS[PREFIX[div]]
    name = transcription(div, 'JUDGES')
    rows, seen = [], set()
    for n, (app, function, printed, noc) in read(name):
        ctx = f'{name}:{n}'
        if function not in FUNCTION:
            err(f'{ctx}: unknown function {function!r}'); continue
        if (app, function) in seen:
            err(f'{ctx}: {app} {function} twice')
        seen.add((app, function))
        if app and app not in APPS[disc] or not app and FUNCTION[function] != 'TD':
            err(f'{ctx}: apparatus {app!r} for {function}')
        m = re.fullmatch(r'(?:(\w{3}) / OGU|OGU \((\w{3})\)|OGU|(\w{3}))', noc)
        if not m:
            err(f'{ctx}: unread federation {noc!r}'); continue
        if disc == 'MAG' or not app:
            given, surname = printed.rsplit(' ', 1)
            surname = surname.upper()
        else:
            surname, given = printed.split(' ', 1)
        rows.append({'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': div[1],
                     'Event Start Date': ev['Start Date'], 'Competition': 'C1', 'Apparatus': app,
                     'Function': FUNCTION[function], 'Name': printed, 'Surname': surname, 'Given Name': given,
                     'NOC Code': m[1] or m[2] or m[3] or ''})
    for app in APPS[disc]:
        missing = {'SV', 'D1', 'D2', 'E1', 'E2', 'E3', 'E4', 'E5'} - {r['Function'] for r in rows
                                                                      if r['Apparatus'] == app}
        if missing:
            err(f'{label(div)} {app} panel: no {sorted(missing)}')
    return rows

# ---------------------------------------------------------------- files
def score_rows(div, app, athletes, people, roles):
    ev = EVENTS[PREFIX[div]]
    rows = []
    for a in athletes:
        if app not in a['routines'] and (*div, app, a['bib']) not in BLANK_ON_RESULTS:
            continue
        r = a['routines'].get(app)
        person = people[a['bib']]
        status = 'COMPLETED' if r else ('DNS' if app in a['routines'] else '')
        rows.append({'Event Name': ev['Title'], 'Discipline': div[0], 'Age Category': div[1],
                     'Competition Start Date': SESSION_DATE, 'Competition': 'C1', 'Part': '', 'Apparatus': app,
                     'Rank': '', 'Bib': a['bib'], 'Name': person['Name'], 'NOC Code': person['NOC Code'],
                     'Status': status, 'D': r['D'] if r else '', 'E': r['E'] if r else '',
                     'B': r['S'] if r and D(r['S']) else '',
                     'Penalty': f'-{r["P"]}' if r and D(r['P']) else '', 'SJ Penalty': '',
                     'Total': r['Total'] if r else '', 'Team Role': roles.get((a['bib'], app), '')})
    return rows

for div in DIVISIONS:
    disc, age = div
    prefix, ev = PREFIX[div], EVENTS[PREFIX[div]]
    text, counts = schedule(div)
    medals = medallists(div, text)
    people_rows = participants(div, counts)
    out.csv(f'{prefix}-PARTICIPANTS.csv', common.PARTICIPANTS, people_rows)
    people = {r['Bib Number']: r for r in people_rows}

    athletes = all_around(div, people)
    start_lists(div, people, athletes)
    team_rows, roles, team_totals = teams(div, athletes, people, counts)

    # Medallists by Event (p. 2) and Medallists (p. 9) list the same medals in another order
    aa_top = [(people[a['bib']]['Name'], people[a['bib']]['NOC Code']) for a in athletes[:3]]
    if medals['AA'] != aa_top or medals['TEAM'] != [noc for _, noc, _ in team_rows[:2]]:
        err(f'{label(div)} medallists {medals} != results {aa_top}, {team_rows[:2]}')
    country_name = {v: k for k, v in COUNTRY.items()}
    expected = [f'All around Final {n} ({c}) {m}' for (n, c), m in zip(medals['AA'], ('Gold', 'Silver', 'Bronze'))]
    expected += [f'Team Final {country_name[c]} {m}' for c, m in zip(medals['TEAM'], ('Gold', 'Silver'))]
    medal_page = section(page(div, 'Medallists'), 'Medallists')[1:]
    if sorted(' '.join(l.split()) for l in medal_page) != sorted(expected):
        err(f'{label(div)}: the Medallists page differs from Medallists by Event')

    for app in APPS[disc]:
        rows = score_rows(div, app, athletes, people, roles)
        out.csv(f'{prefix}-SCORES-C1-{app}.csv', common.score_header(vault=False, qual=False, team_role=True),
                rows)
        for r in rows:
            if r['Status'] not in ('COMPLETED', 'DNS'):
                err(f'{label(div)} {app} bib {r["Bib"]}: status {r["Status"]!r} after corrections')

    meta = {'Event Name': ev['Title'], 'Discipline': disc, 'Age Category': age,
            'Event Start Date': ev['Start Date'], 'Part': ''}
    totals = [f'{app} Total' for app in SUMMARY_APPS[disc]]
    aa_rows = []
    for a in athletes:
        person = people[a['bib']]
        aa_rows.append({**meta, 'Competition': 'C1', 'Rank': a['rank'], 'Bib': a['bib'], 'Name': person['Name'],
                        'NOC Code': person['NOC Code'], 'SJ Penalty': '', 'Total': a['total'],
                        **{f'{app} Total': (a['routines'].get(app) or {}).get('Total', '')
                           for app in SUMMARY_APPS[disc]}})
    out.ranking(prefix, 'AA',
                ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'Bib',
                 'Name', 'NOC Code'] + totals + ['SJ Penalty', 'Total'], aa_rows, ev)
    # The one competition decided the team title too. The books print no team apparatus totals: the sums
    # of the counting scores (team_scores)
    out.ranking(prefix, 'TEAM',
                ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank',
                 'NOC Code'] + totals + ['SJ Penalty', 'Total'],
                [{**meta, 'Competition': 'C1', 'Rank': rank, 'NOC Code': noc,
                  **{f'{app} Total': f'{team_totals[noc][app]:.3f}' for app in SUMMARY_APPS[disc]},
                  'SJ Penalty': '', 'Total': total} for rank, noc, total in team_rows], ev)

    out.csv(f'{prefix}-JUDGES.csv', common.JUDGES, judges(div))
    out.manifest(prefix, ev)

corrections.finish()
checks.finish()
