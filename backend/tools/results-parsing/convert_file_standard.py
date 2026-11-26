#!/usr/bin/env python3
"""Convert import files from the old standard to the new one (competition-models.md, step 2).

    python3 -I backend/tools/results-parsing/convert_file_standard.py <folder>...

For every `<PREFIX>-IMPORT.json` in each folder, rewrites the files it lists and the manifest:

- `SCORES-QUAL/AA/EVENT/TEAM-<APP>` become `SCORES-C1/C2/C3/C4-<APP>`, and `SUMMARY-*` become
  `RANKING-*`. A slice with no QUAL scores held a single competition, so its `AA` is `C1`
  (Oceania, US Championships).
- The `Round` column becomes `Competition`, with the codes mapped the same way. On a summary, a
  `Scores Round` names the competition ranked, so it becomes the row's `Competition` and the
  column is dropped.
- `Session Start Date` becomes `Competition Start Date`.
- Rankings gain `Purpose` after `Part` (`QUALIFYING` or `FINAL` from the file name,
  `INFORMATIONAL` on a part's row) and an empty `Rank Status` after `Rank`.
- The manifest's `summaries` become `rankings`. When the folder's EVENT.csv has the format
  columns (`Team Format`, `AA Format`, `Apparatus Format`), the manifest gets them.

Only the mechanical changes: which titles a meet's first competition decided, rank statuses
for blank ranks and corrections keys are left to be made by hand. Running it again changes
nothing. A one-off, removed once the parsers write the new standard themselves.
"""
import csv
import glob
import json
import os
import sys

CODES = {'QUAL': 'C1', 'AA': 'C2', 'EVENT': 'C3', 'TEAM': 'C4'}
NEW_CODES = {'C1', 'C2', 'C3', 'C4'}
FORMAT_COLUMNS = [('Team Format', 'teamFormat'), ('AA Format', 'aaFormat'),
                  ('Apparatus Format', 'apparatusFormat')]


def code_map(score_files):
    """Old round code to competition code for one slice: AA is C1 where no QUAL was held."""
    codes = dict(CODES)
    has_qual = any('-SCORES-QUAL-' in f or '-SCORES-C1-' in f for f in score_files)
    if not has_qual:
        codes['AA'] = 'C1'
    return codes


def competition(value, codes, where):
    if value in NEW_CODES:
        return value
    if value not in codes:
        raise SystemExit(f'{where}: unrecognised round {value!r}')
    return codes[value]


def new_name(name, codes):
    for old in CODES:
        marker = f'-SCORES-{old}-'
        if marker in name:
            return name.replace(marker, f'-SCORES-{codes[old]}-')
    return name.replace('-SUMMARY-', '-RANKING-')


def line_ending(path):
    """The file's own line ending, kept on rewriting (the 2026 Europeans files use CRLF)."""
    with open(path, newline='', encoding='utf-8') as f:
        return '\r\n' if f.readline().endswith('\r\n') else '\n'


def read(path):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, [dict(zip(header, row)) for row in reader]


def write(path, header, rows, ending='\n'):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator=ending)
        w.writerow(header)
        for r in rows:
            w.writerow([r[h] for h in header])


def rename_column(header, rows, old, new):
    if old in header:
        header[header.index(old)] = new
        for r in rows:
            r[new] = r.pop(old)


def insert_after(header, rows, after, column, value):
    if column not in header:
        header.insert(header.index(after) + 1, column)
        for r in rows:
            r[column] = value(r)


def convert_file(path, name, codes):
    header, rows = read(path)
    ranking = '-RANKING-' in name
    if 'Round' in header:
        for i, r in enumerate(rows, start=2):
            where = f'{name} line {i}'
            scores_round = r.pop('Scores Round', '') if ranking else ''
            r['Round'] = competition(scores_round or r['Round'], codes, where)
        if 'Scores Round' in header:
            header.remove('Scores Round')
        rename_column(header, rows, 'Round', 'Competition')
    rename_column(header, rows, 'Session Start Date', 'Competition Start Date')
    if ranking:
        purpose = 'QUALIFYING' if '-RANKING-QUAL-' in name else 'FINAL'
        insert_after(header, rows, 'Part', 'Purpose', lambda r: 'INFORMATIONAL' if r['Part'] else purpose)
        insert_after(header, rows, 'Rank', 'Rank Status', lambda r: '')
    return header, rows


def formats(folder, prefix):
    events = glob.glob(os.path.join(folder, '*-EVENT.csv'))
    for event_file in events:
        _, rows = read(event_file)
        for row in rows:
            if row.get('Prefix') == prefix and all(row.get(column) for column, _ in FORMAT_COLUMNS):
                return {key: row[column] for column, key in FORMAT_COLUMNS}
    return {}


def convert_manifest(folder, manifest_file):
    prefix = os.path.basename(manifest_file)[:-len('-IMPORT.json')]
    with open(manifest_file, encoding='utf-8') as f:
        manifest = json.load(f)
    codes = code_map(manifest.get('scores', []))
    lists = {}
    for key in ('participants', 'judges', 'scores', 'summaries', 'rankings'):
        names = manifest.get(key)
        if names is None:
            continue
        converted = []
        for name in names:
            target = new_name(name, codes)
            source = os.path.join(folder, name)
            ending = line_ending(source)
            header, rows = convert_file(source, target, codes)
            write(os.path.join(folder, target), header, rows, ending)
            if target != name:
                os.remove(os.path.join(folder, name))
            converted.append(target)
        lists['rankings' if key == 'summaries' else key] = sorted(converted)

    event = dict(manifest['event'])
    event.update(formats(folder, prefix))
    result = {'event': event}
    for key in ('participants', 'judges', 'scores', 'rankings'):
        result[key] = lists.get(key, [])
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, separators=(',', ' : '))
        f.write('\n')


def main(folders):
    if not folders:
        raise SystemExit(__doc__)
    for folder in folders:
        manifests = sorted(glob.glob(os.path.join(folder, '*-IMPORT.json')))
        if not manifests:
            print(f'{folder}: no IMPORT.json manifests, skipped')
        for manifest_file in manifests:
            convert_manifest(folder, manifest_file)
            print(f'{os.path.basename(manifest_file)}: converted')


if __name__ == '__main__':
    main(sys.argv[1:])
