"""Cross-check written files against a sporttech.io CSV export of the competition.

sporttech.io's "Export to CSV" has one row per frame (routine) of every stage
(docs/instructions-results-parsing.md §5.5). It is trusted over a printed book for routines,
statuses, ranks and totals: every one written must match it, both ways, after the event's
CORRECTIONS.csv has been applied, so each difference from the book is logged there. Its Q/R markers
are not compared: they contradict who competed in the finals (they look recomputed after the meet),
while the book's agree with the finals.

    import sporttech
    sporttech.crosscheck(out_dir, prefix, export_csv, title, round_of_date, noc_of, err)
"""
import csv, os, re
from decimal import Decimal

EXPORT_APP = {'Floor': 'FX', 'Pommel': 'PH', 'Rings': 'SR', 'Vault': 'VT', 'Vault2': 'VT', 'PBars': 'PB',
              'HBar': 'HB', 'UBars': 'UB', 'Beam': 'BB'}

def frames(export_csv, title, round_of_date, err):
    """{(round, bib, apparatus, attempt): frame} for one competition (`title`, e.g. 'SENIOR - Men').

    The export names no stage: its rows come stage by stage (the group number starting again at 1) and
    athlete by athlete. A performance (one athlete's consecutive rows) takes its round from the days its
    frames started (`round_of_date`), or, when none started, from its stage's."""
    with open(export_csv, encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if r['Competition: Title'] == title]
    if not rows:
        err(f'sporttech: no competition {title!r} in {export_csv}')
    perfs, stage, group = [], 0, 0
    for r in rows:
        if int(r['Group #']) < group:
            stage += 1
        group = int(r['Group #'])
        key = (stage, r['Group #'], r['Performance #'], r['Athlete: Bib'])
        if not perfs or perfs[-1][0] != key:
            perfs.append((key, []))
        perfs[-1][1].append(r)

    def rounds(rs):
        return {round_of_date[r['Frame: LastStartTime_G'][:10]] for r in rs
                if r['Frame: LastStartTime_G'][:10] in round_of_date}
    stage_rounds = {}
    for key, rs in perfs:
        stage_rounds.setdefault(key[0], set()).update(rounds(rs))
    out = {}
    for key, rs in perfs:
        rnd = rounds(rs) or stage_rounds[key[0]]
        if len(rnd) != 1:
            err(f'sporttech {title}: bib {key[3]} performance in rounds {rnd}'); continue
        for r in rs:
            out[(next(iter(rnd)), r['Athlete: Bib'], EXPORT_APP[r['Routine type']],
                 2 if r['Routine type'] == 'Vault2' else 1)] = r
    return out

def routine(r):
    """A frame as the CSV columns: (status, D, E, B, Penalty, Total, combined bonus), or None for a frame
    never started, or scored but never published. A bare zero is 'ZERO'."""
    if r['Frame: State'] == 'FAILED':
        return ('DNS', '', '', '', '', '', '')
    if r['Frame: State'] != 'PUBLISHED':
        return None
    total = r['Frame: TMarkTTT_G']
    if Decimal(total) == 0 and Decimal(r['Frame: DMarkT_G']) == 0:
        return ('ZERO', '', '', '', '', '0', '')
    def value(v, negative):
        return '' if Decimal(v) == 0 else ('-' if negative else '') + v
    return ('COMPLETED', r['Frame: DMarkT_G'], r['Frame: EMarkTTT_G'], value(r['Frame: DBonusT_G'], False),
            value(r['Frame: NPenaltyT_G'], True), total, value(r['Frame: VaultBonusT_G'], False))

# The report names the export's rounds use, by the competition code the files write
ROUND_OF_COMPETITION = {'C1': 'QUAL', 'C2': 'AA', 'C3': 'EVENT', 'C4': 'TEAM'}

def crosscheck(out_dir, prefix, export_csv, title, round_of_date, noc_of, err):
    """Every routine, rank and standing in `<prefix>-SCORES-*` and `-RANKING-*` against the export.
    `noc_of(bib)` gives a participant's NOC, to find a team's frames. The export's rounds are named as
    the books name their reports (`round_of_date`: QUAL, AA, EVENT); a file names the competition."""
    fr = frames(export_csv, title, round_of_date, err)
    seen = set()
    for name in sorted(os.listdir(out_dir)):
        m = re.fullmatch(rf'{prefix}-SCORES-([A-Z0-9]+)-([A-Z]{{2}})\.csv', name)
        if not m:
            continue
        code, app = m.groups()
        rnd = ROUND_OF_COMPETITION[code]
        with open(os.path.join(out_dir, name), encoding='utf-8') as f:
            for row in csv.DictReader(f):
                attempts = ('1', '2') if 'Status1' in row else ('',)
                for n, suffix in enumerate(attempts, 1):
                    if not row[f'Status{suffix}']:
                        continue
                    key = (rnd, row['Bib'], app, n)
                    seen.add(key)
                    status = row[f'Status{suffix}']
                    mine = ('ZERO' if row[f'Total{suffix}'] == '0' else status if status != 'INVALID_VAULT' else '?',
                            *(row[f'{c}{suffix}'] for c in ('D', 'E', 'B', 'Penalty', 'Total')),
                            row.get('Combined Bonus', '') if suffix == '2' else '')
                    theirs = routine(fr[key]) if key in fr else None
                    if mine != theirs:
                        err(f'sporttech {prefix} {rnd} {app} bib {row["Bib"]} attempt {n}: {mine} != export {theirs}')
                # The first attempt's frame carries the ranking: the two-vault list's, for vault
                first = (rnd, row['Bib'], app, 1)
                for col in ('Rank', 'Qualification Rank'):
                    if row.get(col) and first in fr and fr[first]['Routine Rank'] != row[col]:
                        err(f'sporttech {prefix} {rnd} {app} bib {row["Bib"]}: {col} {row[col]} != export '
                            f'{fr[first]["Routine Rank"]}')
    for key, r in fr.items():
        if key not in seen and routine(r) and noc_of(key[1]):
            err(f'sporttech {prefix}: {key} {routine(r)[0]} in the export but not written')
    # All-around and team standings: each frame also carries its performance's totals and ranks
    perf = {(rnd, bib): r for (rnd, bib, _, _), r in fr.items()}
    for name in sorted(os.listdir(out_dir)):
        if not re.fullmatch(rf'{prefix}-RANKING-(QUAL|FINAL)-(AA|TEAM)\.csv', name):
            continue
        with open(os.path.join(out_dir, name), encoding='utf-8') as f:
            for row in csv.DictReader(f):
                rnd = ROUND_OF_COMPETITION[row['Competition']]
                if 'Bib' in row:
                    r = perf.get((rnd, row['Bib']))
                    theirs = r and (r['Performance: Rank_G'] if row['Rank'] else '',
                                    r['Performance: MarkTTT_G'] if row['Total'] else '')
                else:
                    r = next((r for (k, b), r in perf.items() if k == rnd and noc_of(b) == row['NOC Code']
                              and r['Performance: TeamRank_G'] != '99'), None)
                    theirs = r and (r['Performance: TeamRank_G'], r['Performance: TeamMarkTTT_G'])
                if (row['Rank'], row['Total']) != theirs:
                    err(f'sporttech {name} {row.get("Bib") or row["NOC Code"]}: '
                        f'{(row["Rank"], row["Total"])} != export {theirs}')
