"""Parse the 2026 European Championships men's all-around rankings: the juniors' final, and the
seniors' title, decided in Competition I.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_european_championships.py \\
        data/2026/2026-EUROPEAN-CHAMPIONSHIPS/2026-EUROPEAN-CHAMPIONSHIPS-MAG-RESULTS.pdf

The other 2026 Europeans files were written before these parsers existed. Writes, next to the PDF,
in the current standard (docs/import-file-model.md):

- `2026-EUROPEAN-CHAMPIONSHIPS-MAG-JR-RANKING-FINAL-AA.csv`, from the juniors' "All-Around Results"
  of the All-Around Final (the routines, `SCORES-C2-*`, were already written), and the MAG JR
  manifest. FIG/Swiss Timing layout (instructions-results-parsing.md §5.1): each athlete takes three
  lines, the D / Total / Rk of each apparatus above the rank, bib, name and NOC, then E / Pen. / B
  (and the SJ penalty, when there is one) below it, then the all-around total. Checks: each
  apparatus total equals the athlete's C2 score, the apparatus totals and any SJ penalty add up to
  the total, ranks and totals are in order, and every bib is in the entry list.
- `2026-EUROPEAN-CHAMPIONSHIPS-MAG-SR-RANKING-FINAL-AA.csv` and the MAG SR manifest. The senior book
  prints the all-around medallists, dated qualification day, but no ranking. The ranking is derived
  from the `SCORES-C1-*` files: every gymnast with all six apparatus, each apparatus total the C1
  score (the first vault on vault), ranked by their sum. The parser leaves a tie unranked; the
  event's CORRECTIONS.csv breaks it (`TIE_BREAK`). Checks: the medallists are ranks 1-3, every bib
  is in the entry list, and after corrections every row is ranked, in order.
"""
import csv, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D

PDF = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(PDF))
EVENT = '2026-EUROPEAN-CHAMPIONSHIPS'
PREFIX = f'{EVENT}-MAG-JR'
SENIORS = f'{EVENT}-MAG-SR'
APPARATUS = ['FX', 'PH', 'SR', 'VT', 'PB', 'HB']
HEADER = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Rank', 'Bib',
          'Name', 'NOC Code'] + [f'{a} Total' for a in APPARATUS] + ['SJ Penalty', 'Total']

checks = common.Checks()
err = checks.err
events = common.read_events(OUT, EVENT)
event = events[PREFIX]

ATHLETE = re.compile(r'^\s*(\d+)?\s+(\d{2,4})\s+(\S.*?\S)\s{2,}([A-Z][A-Z0-9]{2,3})\s*$')
NUMBER = re.compile(r'^-?\d+\.\d+$')


def report_pages():
    for text in common.pdf_pages(PDF):
        if 'All-Around Results' in text and 'All-Around Final' in text and 'JUNIORS' in text:
            yield text


def apparatus_totals(line, ctx):
    """D / Total / Rk per apparatus: the inquiry marker `!` sits apart from its D score."""
    tokens = line.replace('! ', '!').split()
    if len(tokens) != 3 * len(APPARATUS):
        err(f'{ctx}: expected {3 * len(APPARATUS)} D/Total/Rk values, found {len(tokens)}: {line.strip()}')
        return None
    return [tokens[3 * i + 1] for i in range(len(APPARATUS))]


def sj_penalty(line, ctx):
    """E / Pen. / B per apparatus (pommel horse has no B), then an SJ penalty if one applies."""
    tokens = line.split()
    base = 3 * len(APPARATUS) - 1
    if len(tokens) not in (base, base + 1):
        err(f'{ctx}: expected {base} E/Pen./B values (or one more for an SJ penalty), found {len(tokens)}')
        return ''
    return tokens[base] if len(tokens) > base else ''


rows = []
for text in report_pages():
    lines = [l for l in text.split('\n') if l.strip()]
    for i, line in enumerate(lines):
        m = ATHLETE.match(line)
        if not m or i == 0 or i + 2 >= len(lines):
            continue
        rank, bib, name, noc = m.groups()
        ctx = f'bib {bib}'
        totals = apparatus_totals(lines[i - 1], ctx)
        penalty = sj_penalty(lines[i + 1], ctx)
        total = lines[i + 2].strip()
        if totals is None or not NUMBER.match(total):
            err(f'{ctx}: unreadable row around "{line.strip()}"')
            continue
        row = {'Event Name': event['Title'], 'Discipline': 'MAG', 'Age Category': 'JR',
               'Event Start Date': event['Start Date'], 'Competition': 'C2', 'Part': '',
               'Rank': rank or '', 'Bib': bib, 'Name': name, 'NOC Code': noc,
               'SJ Penalty': penalty if D(penalty) else '', 'Total': total}
        for a, t in zip(APPARATUS, totals):
            row[f'{a} Total'] = t
        rows.append(row)

if not rows:
    err('no All-Around Results rows found')

# Checks against the files already written for this slice
entries = {}
with open(os.path.join(OUT, f'{PREFIX}-PARTICIPANTS.csv'), encoding='utf-8') as f:
    for r in csv.DictReader(f):
        entries[r['Bib Number']] = r
scores = {}
for a in APPARATUS:
    with open(os.path.join(OUT, f'{PREFIX}-SCORES-C2-{a}.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            scores[(r['Bib'], a)] = r['Total']
for r in rows:
    ctx = f'bib {r["Bib"]} {r["Name"]}'
    if r['Bib'] not in entries:
        err(f'{ctx}: not in the entry list')
    elif entries[r['Bib']]['NOC Code'] and entries[r['Bib']]['NOC Code'] != r['NOC Code']:
        err(f'{ctx}: NOC {r["NOC Code"]} differs from the entry list\'s {entries[r["Bib"]]["NOC Code"]}')
    for a in APPARATUS:
        if D(r[f'{a} Total']) != D(scores.get((r['Bib'], a), '')):
            err(f'{ctx}: {a} total {r[f"{a} Total"]} differs from the C2 score {scores.get((r["Bib"], a))}')
    checks.check_sum(f'{ctx} total', r['Total'], *[r[f'{a} Total'] for a in APPARATUS], r['SJ Penalty'])
checks.check_rank_order('MAG JR all-around final', rows)
missing = {bib for bib, _ in scores} - {r['Bib'] for r in rows}
if missing:
    err(f'C2 scores for bibs {sorted(missing)} have no all-around result')


# ---------------------------------------------------------------- seniors' all-around, from the C1 scores
senior_event = events[SENIORS]
senior_entries = {}
with open(os.path.join(OUT, f'{SENIORS}-PARTICIPANTS.csv'), encoding='utf-8') as f:
    for r in csv.DictReader(f):
        senior_entries[r['Bib Number']] = r
c1 = {}  # bib -> {apparatus: total}
names = {}
for a in APPARATUS:
    vault = '1' if a == 'VT' else ''
    with open(os.path.join(OUT, f'{SENIORS}-SCORES-C1-{a}.csv'), encoding='utf-8') as f:
        for r in csv.DictReader(f):
            names[r['Bib']] = (r['Name'], r['NOC Code'])
            if r['Total' + vault]:
                c1.setdefault(r['Bib'], {})[a] = r['Total' + vault]
senior_rows = []
for bib, totals in c1.items():
    if len(totals) != len(APPARATUS):
        continue
    name, noc = names[bib]
    row = {'Event Name': senior_event['Title'], 'Discipline': 'MAG', 'Age Category': 'SR',
           'Event Start Date': senior_event['Start Date'], 'Competition': 'C1', 'Part': '', 'Rank': '',
           'Bib': bib, 'Name': name, 'NOC Code': noc, 'SJ Penalty': '',
           'Total': str(sum((D(totals[a]) for a in APPARATUS), D(0)))}
    for a in APPARATUS:
        row[f'{a} Total'] = totals[a]
    senior_rows.append(row)
    if bib not in senior_entries:
        err(f'MAG SR bib {bib} {name}: not in the entry list')
senior_rows.sort(key=lambda r: (-D(r['Total']), int(r['Bib'])))
for i, r in enumerate(senior_rows):
    tied = [o for o in senior_rows if o['Total'] == r['Total']]
    if len(tied) == 1:
        r['Rank'] = str(i + 1)


def medallists():
    """The "Men's - All-Around" gold, silver and bronze of the seniors' Medallists By Event, with
    its date."""
    for text in common.pdf_pages(PDF):
        if 'Medallists By Event' not in text or 'SENIORS' not in text:
            continue
        lines = [l for l in text.split('\n') if l.strip()]
        for i, line in enumerate(lines):
            m = re.search(r"Men's - All-Around\s+(\d{2})/(\d{2})/(\d{4})\s+GOLD\s+(\S+)\s+(\S.*\S)\s*$", line)
            if not m:
                continue
            month, day, year, noc, name = m.groups()
            medals = [(noc, name)]
            for medal, next_line in zip(('SILVER', 'BRONZE'), lines[i + 1:i + 3]):
                n = re.match(rf'^\s*{medal}\s+(\S+)\s+(\S.*\S)\s*$', next_line)
                if not n:
                    err(f'MAG SR medallists: no {medal} line after the all-around gold')
                    return None, []
                medals.append(n.groups())
            return f'{year}-{month}-{day}', medals
    err('MAG SR medallists: no Men\'s - All-Around entry in a seniors\' Medallists By Event page')
    return None, []


medal_date, medals = medallists()
with open(os.path.join(OUT, f'{SENIORS}-SCORES-C1-FX.csv'), encoding='utf-8') as f:
    c1_date = next(csv.DictReader(f))['Competition Start Date']
if medal_date and medal_date != c1_date:
    err(f'MAG SR all-around medals dated {medal_date}, not the C1 date {c1_date}')
for place, (noc, name) in enumerate(medals, 1):
    row = senior_rows[place - 1] if len(senior_rows) >= place else {}
    if (row.get('Name'), row.get('NOC Code'), row.get('Rank')) != (name, noc, str(place)):
        err(f'MAG SR all-around: medallist {place} is {name} ({noc}), the C1 totals rank '
            f'{row.get("Name")} ({row.get("NOC Code")}) {row.get("Rank") or "unranked"} there')

if checks.errors:
    checks.finish()
corrections = common.Corrections(OUT, EVENT, ['MAG-JR', 'MAG-SR'], err)
out = common.Output(OUT, corrections)
out.ranking(PREFIX, 'AA', HEADER, rows, event)
out.manifest(PREFIX, event)
out.ranking(SENIORS, 'AA', HEADER, senior_rows, senior_event)
out.manifest(SENIORS, senior_event)
# Corrections break the ties the parser left unranked
for r in senior_rows:
    if not r['Rank']:
        err(f'MAG SR all-around: bib {r["Bib"]} {r["Name"]} tied on {r["Total"]}, unranked; break the tie '
            'in CORRECTIONS.csv')
checks.check_rank_order('MAG SR all-around', senior_rows)
ranks = [int(r['Rank']) for r in senior_rows if r['Rank']]
if len(ranks) != len(set(ranks)):
    err('MAG SR all-around: a place is shared after corrections')
corrections.finish()
checks.finish()
