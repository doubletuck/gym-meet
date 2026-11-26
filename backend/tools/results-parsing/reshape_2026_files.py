#!/usr/bin/env python3
"""Reshape the 2026 import files to the decisions of competition-models.md (rollout step 3).

    python3 -I backend/tools/results-parsing/reshape_2026_files.py <folder>...

Run after convert_file_standard.py, on folders whose manifests carry their formats. For each
manifest:

- **A title Competition I decided is a final ranking.** Where the team or all-around format is
  `C1` and the ranking is `RANKING-QUAL-<X>`, it becomes `RANKING-FINAL-<X>` with Purpose
  `FINAL`, and its `Qualification` column is dropped: it qualified no one. Where the folder
  also has that title's `RANKING-FINAL-<X>` over the same routines (2026 Asian Championships),
  only the final one is kept, and the teams or athletes it leaves out are added to it unranked,
  with their qualifying totals.
- **Every blank rank gets its Rank Status**, by rule, in this order:
  - an hors concours entry (`Entry Status` `HORS_CONCOURS`; a team all of whose entries are):
    `HORS_CONCOURS`;
  - marked `NR` by the qualifying ranking it came from: `NOC_LIMIT`;
  - a partial all-around (one with no apparatus at all included), or a team missing an
    apparatus total: `INCOMPLETE`;
  - a split competition's part row: `UNPLACED` (US Championships print no day-2 places);
  - in a final ranking, an athlete outside its printed places: `NOC_LIMIT` when two
    compatriots are ranked and the total beats the lowest ranked total (the two-per-country
    limit cost a place), otherwise `UNPLACED`; a team outside them: `UNPLACED`.

A row no rule covers, or a Q/R marker on a ranking becoming final, stops the script. Running
it again changes nothing. A one-off, removed once the parsers write these files themselves.
"""
import collections
import csv
import glob
import io
import json
import os
import sys

APPARATUS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT']}
FORMAT_KEYS = {'TEAM': 'teamFormat', 'AA': 'aaFormat'}


def read(path):
    with open(path, encoding='utf-8', newline='') as f:
        raw = f.read()
    ending = '\r\n' if raw.split('\n')[0].endswith('\r') else '\n'
    rows = list(csv.reader(io.StringIO(raw)))
    return rows[0], [dict(zip(rows[0], r)) for r in rows[1:]], ending


def write(path, header, rows, ending):
    out = io.StringIO()
    w = csv.writer(out, lineterminator=ending)
    w.writerow(header)
    for r in rows:
        w.writerow([r.get(h, '') for h in header])
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(out.getvalue())


def ranking_type(name):
    return name.rsplit('-', 1)[1][:-len('.csv')]


class Manifest:

    def __init__(self, folder, path):
        self.folder = folder
        self.path = path
        with open(path, encoding='utf-8') as f:
            self.data = json.load(f)
        self.prefix = os.path.basename(path)[:-len('-IMPORT.json')]
        self.hors_concours, self.noc_entries = set(), collections.defaultdict(set)
        for name in self.data['participants']:
            _, rows, _ = read(os.path.join(folder, name))
            for r in rows:
                self.noc_entries[r['NOC Code']].add(r['Bib Number'])
                if r.get('Entry Status') == 'HORS_CONCOURS':
                    self.hors_concours.add(r['Bib Number'])
        # NOC codes print only on a country's first entry in some lists; carried down there
        self.hors_concours_nocs = {noc for noc, bibs in self.noc_entries.items()
                                   if noc and bibs and bibs <= self.hors_concours}
        self.counts = collections.Counter()

    def file(self, name):
        return os.path.join(self.folder, name)

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, separators=(',', ' : '))
            f.write('\n')


def title_rankings_become_final(m):
    """RANKING-QUAL-<X> of a title Competition I decided becomes its final ranking."""
    rankings = m.data['rankings']
    for name in list(rankings):
        if '-RANKING-QUAL-' not in name:
            continue
        kind = ranking_type(name)
        if kind not in FORMAT_KEYS or m.data['event'][FORMAT_KEYS[kind]] != 'C1':
            continue
        header, rows, ending = read(m.file(name))
        markers = {r.get('Qualification') for r in rows} - {'', None}
        final_name = name.replace('-RANKING-QUAL-', '-RANKING-FINAL-')
        if final_name in rankings:
            add_left_out(m, final_name, rows, kind)
        else:
            if markers - {'NR'}:
                raise SystemExit(f'{name}: markers {sorted(markers)} on a ranking becoming final; look at it')
            for r in rows:
                r['Purpose'] = 'FINAL'
                if r.get('Qualification') == 'NR':
                    if r['Rank']:
                        raise SystemExit(f'{name}: {r.get("Bib") or r["NOC Code"]} is ranked and marked NR; '
                                         'look at it')
                    r['Rank Status'] = 'NOC_LIMIT'
            if 'Qualification' in header:
                header.remove('Qualification')
            write(m.file(final_name), header, rows, ending)
            rankings.append(final_name)
            m.counts['qualifying rankings made final'] += 1
        os.remove(m.file(name))
        rankings.remove(name)
    m.data['rankings'] = sorted(rankings)


def add_left_out(m, final_name, qualifying_rows, kind):
    """The final ranking keeps the whole field: those it leaves out are added unranked."""
    header, rows, ending = read(m.file(final_name))
    key = 'NOC Code' if kind == 'TEAM' else 'Bib'
    present = {r[key] for r in rows}
    for q in qualifying_rows:
        if q[key] in present:
            continue
        r = {h: q.get(h, '') for h in header}
        r['Purpose'], r['Rank'], r['Rank Status'] = 'FINAL', '', ''
        if q.get('Qualification') == 'NR':
            r['Rank Status'] = 'NOC_LIMIT'
        rows.append(r)
        m.counts['left-out rows added to a final ranking'] += 1
    write(m.file(final_name), header, rows, ending)
    m.counts['qualifying rankings dropped (a final ranking of the same routines exists)'] += 1


def rank_statuses(m):
    discipline = m.data['event']['disciplines']
    for name in m.data['rankings']:
        header, rows, ending = read(m.file(name))
        kind = ranking_type(name)
        ranked = [r for r in rows if r['Rank']]
        lowest = min((float(r['Total']) for r in ranked if r['Total']), default=None)
        ranked_by_noc = collections.Counter(r['NOC Code'] for r in ranked)
        changed = False
        for r in rows:
            if r['Rank'] or r['Rank Status']:
                continue
            status = status_for(m, r, kind, discipline, ranked_by_noc, lowest)
            if status is None:
                raise SystemExit(f'{name}: no rule gives a rank status for {r.get("Bib") or r["NOC Code"]} '
                                 f'{r.get("Name", "")}; look at it')
            r['Rank Status'] = status
            m.counts[f'rank status {status}'] += 1
            changed = True
        if changed:
            write(m.file(name), header, rows, ending)


def status_for(m, r, kind, discipline, ranked_by_noc, lowest):
    if kind == 'TEAM' and r['NOC Code'] in m.hors_concours_nocs or r.get('Bib') in m.hors_concours:
        return 'HORS_CONCOURS'
    totals = [r.get(a + ' Total', '') for a in APPARATUS[discipline]] if kind in ('TEAM', 'AA') else []
    # Started none at all (DNS on every apparatus) is the extreme of a partial all-around; a split
    # competition's combined row prints a total but no apparatus totals
    if totals and not all(totals) and (any(totals) or not r['Total']):
        return 'INCOMPLETE'
    if r['Part']:
        return 'UNPLACED'
    if r['Purpose'] != 'FINAL':
        return None
    if kind == 'TEAM':
        return 'UNPLACED'
    if kind == 'AA' and ranked_by_noc[r['NOC Code']] >= 2 and lowest is not None and r['Total'] \
            and float(r['Total']) > lowest:
        return 'NOC_LIMIT'
    return 'UNPLACED'


def main(folders):
    if not folders:
        raise SystemExit(__doc__)
    for folder in folders:
        for path in sorted(glob.glob(os.path.join(folder, '*-IMPORT.json'))):
            m = Manifest(folder, path)
            title_rankings_become_final(m)
            rank_statuses(m)
            m.save()
            print(f'{m.prefix}: ' + (', '.join(f'{k} {v}' for k, v in sorted(m.counts.items())) or 'no changes'))


if __name__ == '__main__':
    main(sys.argv[1:])
