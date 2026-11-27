#!/usr/bin/env python3
"""Keep a local copy of World Gymnastics (FIG) athlete licenses, and check entry lists against it.

    python3 -I fig_athletes.py sync    [--discipline MAG] [--max-age 30]
    python3 -I fig_athletes.py search  --lastname GHADIMI [--given Mehrdad] [--country QAT]
                                       [--license 70193] [--discipline MAG] [--online]
    python3 -I fig_athletes.py check   data/2026/2026-ASIAN-GAMES [--refresh]
    python3 -I fig_athletes.py missing [--refresh]

`sync` downloads every active MAG and WAG license (one request per discipline) and merges it
into `data/athletes/FIG-LICENSES.csv`, keyed by license. A license FIG no longer lists keeps its
row, so an athlete whose license lapses is not lost; `Last Seen` shows when FIG last listed it.
Without `--max-age` it always downloads; with it, only a discipline last synced longer ago.

`search` looks athletes up in that file, or with `--online` asks FIG (and merges what it returns).

`check` compares PARTICIPANTS.csv files (a file, or every one under a folder) with the reference
files: FIG-LICENSES.csv and the hand-curated ATHLETES.csv. It reports licenses FIG doesn't know,
and names, countries and birth dates that differ, and suggests a license for an unlicensed entry
FIG lists under the same name and country. It changes nothing: a value the book has wrong is
corrected through the meet's CORRECTIONS.csv.

`missing` lists the athletes of every PARTICIPANTS.csv under data/ whose full birth date neither
a results book nor a reference file gives, as ATHLETES.csv rows to fill in by hand.

`check` and `missing` sync first when the copy is older than 30 days, or with `--refresh`.

See backend/docs/results-sourcing.md.
"""
import argparse, csv, datetime, glob, json, os, sys, unicodedata, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_events import REPO, SITE, USER_AGENT, read_csv, write_csv

DISCIPLINES = ['MAG', 'WAG']
ATHLETES_DIR = os.path.join(REPO, 'data', 'athletes')
FIG_LICENSES = os.path.join(ATHLETES_DIR, 'FIG-LICENSES.csv')
ATHLETES = os.path.join(ATHLETES_DIR, 'ATHLETES.csv')
FIG_COLUMNS = ['FIG License', 'Gymnast ID', 'Discipline', 'Surname', 'Given Name', 'NOC Code', 'Birth Date',
               'Licensed On', 'Valid To', 'First Seen', 'Last Seen']
ATHLETES_COLUMNS = ['Discipline', 'NOC Code', 'FIG License', 'Surname', 'Given Name', 'Birth Date', 'Source', 'Note']
# FIG record field -> FIG-LICENSES.csv column (First Seen and Last Seen are ours)
FIG_FIELDS = {'idgymnastlicense': 'FIG License', 'gymnastid': 'Gymnast ID', 'discipline': 'Discipline',
              'preferredlastname': 'Surname', 'preferredfirstname': 'Given Name', 'country': 'NOC Code',
              'birth': 'Birth Date', 'licensestatus': 'Licensed On', 'validto': 'Valid To'}
MAX_AGE_DAYS = 30

# ---------------------------------------------------------------- FIG site
def search_licenses(discipline='', country='', license='', lastname=''):
    """FIG's license search, as its athletes page calls it. Every criterion may be empty."""
    params = {'function': 'searchLicenses', 'discipline': discipline, 'country': country,
              'idlicense': license, 'lastname': lastname}
    url = SITE + '/api/athletes.php?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest',
        'Referer': SITE + '/site/athletes/lic_view.php'})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read()
    return parse_records(body)

def parse_records(body):
    try:
        records = json.loads(body)
    except ValueError:
        records = None
    if not isinstance(records, list) or not all(isinstance(r, dict) and FIG_FIELDS.keys() <= r.keys()
                                                for r in records):
        sys.exit('FIG license search returned something other than a list of licenses; '
                 'the endpoint (/api/athletes.php?function=searchLicenses) may have changed')
    return records

# ---------------------------------------------------------------- the reference files
def today():
    return datetime.date.today().isoformat()

def read_rows(path):
    return read_csv(path)[1] if os.path.exists(path) else []

def write_fig_licenses(rows, path=FIG_LICENSES):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows.sort(key=lambda r: (r['Discipline'], name_key(r['Surname']), name_key(r['Given Name']),
                             int(r['FIG License']) if r['FIG License'].isdigit() else 0, r['FIG License']))
    write_csv(path, FIG_COLUMNS, rows)

def merge(rows, records, seen):
    """Merges FIG records into FIG-LICENSES.csv rows by license; returns (added, changed) rows."""
    by_license = {r['FIG License']: r for r in rows}
    added, changed = [], []
    for record in records:
        values = {column: str(record[field] or '').strip() for field, column in FIG_FIELDS.items()}
        row = by_license.get(values['FIG License'])
        if row is None:
            row = {**values, 'First Seen': seen, 'Last Seen': seen}
            by_license[values['FIG License']] = row
            rows.append(row)
            added.append(row)
            continue
        if any(row.get(c) != v for c, v in values.items() if c not in ('Licensed On', 'Valid To')):
            changed.append((dict(row), row))
        row.update(values)
        row['Last Seen'] = max(row.get('Last Seen', ''), seen)
    return added, changed

def last_synced(rows, discipline):
    return max((r['Last Seen'] for r in rows if r['Discipline'] == discipline), default='')

def stale(rows, discipline, max_age):
    synced = last_synced(rows, discipline)
    if not synced:
        return True
    return (datetime.date.today() - datetime.date.fromisoformat(synced)).days > max_age

def sync(disciplines=DISCIPLINES, max_age=None, path=FIG_LICENSES, quiet=False):
    rows = read_rows(path)
    for discipline in disciplines:
        if max_age is not None and not stale(rows, discipline, max_age):
            if not quiet:
                print(f'{discipline}: synced {last_synced(rows, discipline)}, within {max_age} days; not downloaded')
            continue
        before = {r['FIG License'] for r in rows if r['Discipline'] == discipline}
        records = [r for r in search_licenses(discipline=discipline) if r['discipline'] == discipline]
        if not records:
            sys.exit(f'FIG returned no {discipline} licenses; nothing merged')
        seen = today()
        added, changed = merge(rows, records, seen)
        listed = {r['idgymnastlicense'] for r in records}
        lapsed = sorted(before - listed)
        print(f'{discipline}: {len(records)} active licenses; {len(added)} new, {len(changed)} changed, '
              f'{len(lapsed)} no longer listed')
        for old, new in changed:
            diffs = ', '.join(f'{c} {old.get(c)!r} -> {new[c]!r}' for c in FIG_COLUMNS
                              if c not in ('Licensed On', 'Valid To', 'Last Seen') and old.get(c) != new[c])
            print(f'  changed {new["FIG License"]} {new["Surname"]} {new["Given Name"]}: {diffs}')
        write_fig_licenses(rows, path)
    return rows

def fresh_rows(refresh, path=FIG_LICENSES):
    return sync(max_age=-1 if refresh else MAX_AGE_DAYS, path=path, quiet=True)

# ---------------------------------------------------------------- matching
def name_key(name):
    """A name compared without case, accents, punctuation or extra spaces."""
    text = unicodedata.normalize('NFKD', name or '')
    text = ''.join(c if c.isalnum() else ' ' for c in text if not unicodedata.combining(c))
    return ' '.join(text.casefold().split())

def same_name(surname, given, other_surname, other_given):
    """Whether two names can be the same person's: FIG lists preferred names, often shorter than a book's
    ("AJALLA Isabella" for "AJALLA Isabella Ayelen"), sometimes spaced or ordered differently."""
    words = set(name_key(f'{surname} {given}').split())
    other = set(name_key(f'{other_surname} {other_given}').split())
    joined = name_key(surname + given).replace(' ', '') == name_key(other_surname + other_given).replace(' ', '')
    return joined or words <= other or other <= words

# Entry-list NOC codes FIG lists under another federation's: home nations and Crown dependencies, and neutral athletes
# (AIN; WG1/WG2 and AIN1/AIN2 at some meets), who may be from any. None means any federation.
FEDERATIONS = {'ENG': {'GBR'}, 'SCO': {'GBR'}, 'WAL': {'GBR'}, 'NIR': {'GBR', 'IRL'}, 'IOM': {'GBR'},
               'JEY': {'GBR'}, 'GUE': {'GBR'},
               'AIN': None, 'AIN1': None, 'AIN2': None, 'WG1': None, 'WG2': None}

def same_country(noc, fig_noc):
    federations = FEDERATIONS.get(noc, {noc})
    return federations is None or fig_noc in federations

class Reference:
    """FIG-LICENSES.csv and ATHLETES.csv, indexed by license and by discipline and name."""

    def __init__(self, fig_rows, athletes_rows):
        self.fig_by_license = {r['FIG License']: r for r in fig_rows}
        self.fig_by_name = index(fig_rows)
        self.hand_by_license = {r['FIG License']: r for r in athletes_rows if r.get('FIG License')}
        self.hand_by_name = index(athletes_rows)

    def fig(self, license, discipline, noc, surname, given):
        """The FIG row for a license, or the one FIG row with this name and country; and any others."""
        if license:
            return self.fig_by_license.get(license), []
        found = [r for r in self.fig_by_name.get((discipline, name_key(surname), name_key(given)), [])
                 if same_country(noc, r['NOC Code'])]
        return (found[0], []) if len(found) == 1 else (None, found)

    def hand(self, license, discipline, noc, surname, given):
        if license and license in self.hand_by_license:
            return self.hand_by_license[license]
        found = [r for r in self.hand_by_name.get((discipline, name_key(surname), name_key(given)), [])
                 if r['NOC Code'] == noc]
        return found[0] if len(found) == 1 else None

def index(rows):
    found = {}
    for r in rows:
        found.setdefault((r['Discipline'], name_key(r['Surname']), name_key(r['Given Name'])), []).append(r)
    return found

def participants(row_source):
    """PARTICIPANTS.csv rows as (file, line, row), the NOC carried down as the importer does."""
    for path in row_source:
        noc = ''
        with open(path, encoding='utf-8-sig', newline='') as f:
            for line, row in enumerate(csv.DictReader(f), start=2):
                noc = row.get('NOC Code') or noc
                yield path, line, {**row, 'NOC Code': noc}

def participant_files(paths):
    files = []
    for path in paths:
        if os.path.isdir(path):
            files += glob.glob(os.path.join(path, '**', '*-PARTICIPANTS.csv'), recursive=True)
        else:
            files.append(path)
    return sorted(files)

def compare(row, ref):
    """What differs between an entry-list row and the reference files."""
    lic = row.get('FIG License', '').strip()
    discipline, noc = row['Discipline'], row['NOC Code']
    surname, given = row['Surname'], row['Given Name']
    dob, year = row.get('Birth Date', '').strip(), row.get('Birth Year', '').strip()
    issues = []
    fig, others = ref.fig(lic, discipline, noc, surname, given)
    if lic and fig is None:
        issues.append(f'FIG lists no license {lic} (lapsed, or misprinted)')
    elif not lic and fig is not None:
        issues.append(f'no license printed; FIG lists {fig["FIG License"]} for this name and country, '
                      f'born {fig["Birth Date"]}')
    elif not lic and others:
        issues.append('no license printed; FIG lists ' + ', '.join(o['FIG License'] for o in others)
                      + ' for this name and country')
    if fig is not None and lic:
        if fig['Discipline'] != discipline:
            issues.append(f'FIG license {lic} is {fig["Discipline"]}')
        if not same_name(surname, given, fig['Surname'], fig['Given Name']):
            issues.append(f'FIG names license {lic} {fig["Surname"]} {fig["Given Name"]}')
        if not same_country(noc, fig['NOC Code']):
            issues.append(f'FIG lists license {lic} under {fig["NOC Code"]}')
    for source, other in (('FIG', fig), ('ATHLETES.csv', ref.hand(lic, discipline, noc, surname, given))):
        if other is None or not other.get('Birth Date'):
            continue
        if dob and other['Birth Date'] != dob:
            issues.append(f'{source} has born {other["Birth Date"]}, not {dob}')
        elif not dob and year and other['Birth Date'][:4] != year:
            issues.append(f'{source} has born {other["Birth Date"]}, not in {year}')
    return issues

def check(paths, ref, out=sys.stdout):
    count = 0
    for path, line, row in participants(participant_files(paths)):
        for issue in compare(row, ref):
            count += 1
            print(f'{os.path.relpath(path, REPO)} line {line} bib {row.get("Bib Number", "")} '
                  f'{row["Surname"]} {row["Given Name"]} ({row["NOC Code"]}): {issue}', file=out)
    print(f'{count} differences', file=out)
    return count

def missing(paths, ref):
    """ATHLETES.csv rows for athletes with no full birth date from a book or a reference file."""
    athletes = {}
    for _, _, row in participants(participant_files(paths)):
        key = (row['Discipline'], name_key(row['Surname']), name_key(row['Given Name']))
        a = athletes.setdefault(key, {'rows': [], 'dated': False})
        a['rows'].append(row)
        a['dated'] = a['dated'] or bool(row.get('Birth Date', '').strip())
    result = []
    for a in athletes.values():
        if a['dated']:
            continue
        dated = False
        for row in a['rows']:
            lic = row.get('FIG License', '').strip()
            args = (lic, row['Discipline'], row['NOC Code'], row['Surname'], row['Given Name'])
            fig, _ = ref.fig(*args)
            hand = ref.hand(*args)
            dated = dated or (fig is not None and bool(fig['Birth Date'])) or (hand is not None and bool(hand['Birth Date']))
        if not dated:
            last = a['rows'][-1]
            lic = next((r['FIG License'] for r in reversed(a['rows']) if r.get('FIG License', '').strip()), '')
            years = sorted({r['Birth Year'] for r in a['rows'] if r.get('Birth Year', '').strip()})
            result.append({'Discipline': last['Discipline'], 'NOC Code': last['NOC Code'], 'FIG License': lic,
                           'Surname': last['Surname'], 'Given Name': last['Given Name'], 'Birth Date': '',
                           'Source': '', 'Note': ('born ' + '/'.join(years)) if years else ''})
    result.sort(key=lambda r: (r['Discipline'], r['NOC Code'], name_key(r['Surname']), name_key(r['Given Name'])))
    return result

# ---------------------------------------------------------------- commands
def cmd_sync(args):
    sync(args.discipline or DISCIPLINES, args.max_age)

def cmd_search(args):
    disciplines = [args.discipline] if args.discipline else DISCIPLINES
    if args.online:
        records = [r for d in disciplines for r in search_licenses(d, args.country or '', args.license or '',
                                                                   args.lastname or '')]
        rows = read_rows(FIG_LICENSES)
        added, _ = merge(rows, records, today())
        write_fig_licenses(rows)
        print(f'FIG returned {len(records)} licenses ({len(added)} new to FIG-LICENSES.csv)')
    rows = [r for r in read_rows(FIG_LICENSES)
            if r['Discipline'] in disciplines
            and (not args.license or r['FIG License'] == args.license)
            and (not args.country or r['NOC Code'] == args.country.upper())
            and (not args.lastname or name_key(args.lastname) in name_key(r['Surname']))
            and (not args.given or name_key(args.given) in name_key(r['Given Name']))]
    w = csv.writer(sys.stdout, lineterminator='\n')
    w.writerow(FIG_COLUMNS)
    w.writerows([r.get(c, '') for c in FIG_COLUMNS] for r in rows)

def cmd_check(args):
    ref = Reference(fresh_rows(args.refresh), read_rows(ATHLETES))
    check(args.paths, ref)

def cmd_missing(args):
    ref = Reference(fresh_rows(args.refresh), read_rows(ATHLETES))
    rows = missing([os.path.join(REPO, 'data')], ref)
    w = csv.writer(sys.stdout, lineterminator='\n')
    w.writerow(ATHLETES_COLUMNS)
    w.writerows([r[c] for c in ATHLETES_COLUMNS] for r in rows)
    print(f'{len(rows)} athletes with no full birth date', file=sys.stderr)

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('sync', help='download active licenses into data/athletes/FIG-LICENSES.csv')
    s.add_argument('--discipline', choices=DISCIPLINES, action='append')
    s.add_argument('--max-age', type=int, metavar='DAYS', help='skip a discipline synced within this many days')
    q = sub.add_parser('search', help='look athletes up in FIG-LICENSES.csv, or with --online on the FIG site')
    q.add_argument('--lastname')
    q.add_argument('--given', help='given name (FIG-LICENSES.csv only; FIG cannot search by it)')
    q.add_argument('--country', help='NOC code')
    q.add_argument('--license')
    q.add_argument('--discipline', choices=DISCIPLINES)
    q.add_argument('--online', action='store_true', help='ask FIG, and merge what it returns')
    c = sub.add_parser('check', help='compare PARTICIPANTS.csv files with the reference files')
    c.add_argument('paths', nargs='+', help='PARTICIPANTS.csv files, or folders searched for them')
    c.add_argument('--refresh', action='store_true', help='sync first, however recent the copy')
    m = sub.add_parser('missing', help='list athletes with no full birth date, as ATHLETES.csv rows')
    m.add_argument('--refresh', action='store_true', help='sync first, however recent the copy')
    args = p.parse_args(argv)
    if args.command == 'search' and not any((args.lastname, args.given, args.country, args.license)):
        p.error('search needs at least one of --lastname, --given, --country, --license')
    {'sync': cmd_sync, 'search': cmd_search, 'check': cmd_check, 'missing': cmd_missing}[args.command](args)

if __name__ == '__main__':
    main()
