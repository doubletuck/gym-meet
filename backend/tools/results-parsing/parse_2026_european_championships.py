"""Parse the 2026 European Championships junior men's all-around final ranking.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_2026_european_championships.py \\
        data/2026/2026-EUROPEAN-CHAMPIONSHIPS/2026-EUROPEAN-CHAMPIONSHIPS-MAG-RESULTS.pdf

Scoped to one report: the juniors' "All-Around Results" of the All-Around Final. The other
2026 Europeans files were written before these parsers existed; the all-around final's
routines (`SCORES-C2-*`) were among them, but its ranking wasn't. Writes
`2026-EUROPEAN-CHAMPIONSHIPS-MAG-JR-RANKING-FINAL-AA.csv` next to the PDF, in the current
standard (docs/import-file-model.md), and lists it in the MAG JR manifest.

FIG/Swiss Timing layout (instructions-results-parsing.md §5.1): each athlete takes three lines,
the D / Total / Rk of each apparatus above the rank, bib, name and NOC, then E / Pen. / B
(and the SJ penalty, when there is one) below it, then the all-around total. Checks: each
apparatus total equals the athlete's C2 score, the apparatus totals and any SJ penalty add up
to the total, ranks and totals are in order, and every bib is in the entry list.
"""
import csv, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D

PDF = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(PDF))
PREFIX = '2026-EUROPEAN-CHAMPIONSHIPS-MAG-JR'
APPARATUS = ['FX', 'PH', 'SR', 'VT', 'PB', 'HB']
HEADER = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Part', 'Purpose',
          'Rank', 'Rank Status', 'Bib', 'Name', 'NOC Code'] + [f'{a} Total' for a in APPARATUS] + \
         ['SJ Penalty', 'Total']

checks = common.Checks()
err = checks.err
event = common.read_events(OUT, '2026-EUROPEAN-CHAMPIONSHIPS')[PREFIX]

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
               'Event Start Date': event['Start Date'], 'Competition': 'C2', 'Part': '', 'Purpose': 'FINAL',
               'Rank': rank or '', 'Rank Status': '', 'Bib': bib, 'Name': name, 'NOC Code': noc,
               'SJ Penalty': penalty if D(penalty) else '', 'Total': total}
        for a, t in zip(APPARATUS, totals):
            row[f'{a} Total'] = t
        if not row['Rank']:
            row['Rank Status'] = 'INCOMPLETE' if not all(totals) else ''
            if not row['Rank Status']:
                err(f'{ctx}: unranked with a full all-around; say why in Rank Status')
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

if checks.errors:
    checks.finish()
name = f'{PREFIX}-RANKING-FINAL-AA.csv'
common.Output(OUT).csv(name, HEADER, rows)
manifest_path = os.path.join(OUT, f'{PREFIX}-IMPORT.json')
with open(manifest_path, encoding='utf-8') as f:
    manifest = json.load(f)
if name not in manifest['rankings']:
    manifest['rankings'] = sorted(manifest['rankings'] + [name])
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=4, separators=(',', ' : '))
        f.write('\n')
checks.finish()
