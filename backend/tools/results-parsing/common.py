"""Shared helpers for the per-meet results parsers in this folder.

Each meet gets its own `parse_<year>_<event>.py` (source layouts differ too much to share a
parser), but they all write the same CSV standard (docs/import-file-model.md) and run the
same kinds of checks (docs/instructions-results-parsing.md §3). Those parts live here.

Parsers run with `python3 -I`, which leaves the script's folder off sys.path, so import this as:

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import common
"""
import collections, csv, json, os, re, subprocess, sys
from decimal import Decimal

# ---------------------------------------------------------------- sources
def pdf_pages(path):
    """`pdftotext -layout` output split into physical pages (index 0 = page 1)."""
    return subprocess.run(['pdftotext', '-layout', path, '-'], check=True, capture_output=True,
                          text=True).stdout.split('\f')

def read_events(out_dir, event_prefix):
    """Rows of `<event_prefix>-EVENT.csv`, keyed by their Prefix column."""
    with open(os.path.join(out_dir, f'{event_prefix}-EVENT.csv'), encoding='utf-8') as f:
        return {r['Prefix']: r for r in csv.DictReader(f)}

# ---------------------------------------------------------------- values
def D(s):
    """A printed score as a Decimal; blank counts as zero."""
    return Decimal(s) if s else Decimal(0)

def rank_number(v):
    """Tie markers vary by source (1T, 45=, 2*); the stored rank is the number alone."""
    return re.sub(r'[T=*]$', '', v)

# ---------------------------------------------------------------- names
PARTICLES = {'Mc', 'van', 'der', 'den', 'de', 'le', 'la', 'du', 'da', 'di', 'von', 'dos', 'del'}

def surname_word(w):
    return re.fullmatch(r"(Mc|Mac)?[^a-z]*[A-Z][^a-z]*", w) is not None

def split_surname_first(name):
    """'SURNAME Given' (FIG results books) -> (surname, given). The surname is the leading run of
    upper-case words, including lowercase particles (`van POL`) and `McDONALD`-style prefixes."""
    words = name.split(' ')
    i = 0
    while i < len(words) and (surname_word(words[i]) or words[i] in PARTICLES):
        i += 1
    return ' '.join(words[:i]), ' '.join(words[i:])

def split_given_first(name):
    """'Given SURNAME' (organizer books) -> (surname, given). The surname is the trailing run of
    upper-case words (`Kilan VAN DER AA`)."""
    words = name.split(' ')
    i = len(words)
    while i > 0 and surname_word(words[i - 1]):
        i -= 1
    return ' '.join(words[i:]), ' '.join(words[:i])

# ---------------------------------------------------------------- column sets (docs/import-file-model.md)
# The competition code written for each of a book's reports, by the name the books give them:
# Competition I (qualification), the all-around final, the apparatus finals, the team final. A meet
# whose only competition is Competition I (Oceania, US Championships) writes C1 for it whatever
# its book calls it.
COMPETITION = {'QUAL': 'C1', 'AA': 'C2', 'EVENT': 'C3', 'TEAM': 'C4'}

SCORE_META = ['Event Name', 'Discipline', 'Age Category', 'Competition Start Date', 'Competition', 'Part',
              'Apparatus', 'Rank', 'Bib', 'Name', 'NOC Code']
ROUTINE = ['Status', 'D', 'E', 'B', 'Penalty', 'SJ Penalty', 'Total']
VAULT = [f'{c}{n}' for n in (1, 2) for c in ROUTINE] + ['Combined Bonus', 'Total']
QUALIFICATION = ['Qualification', 'Qualification Rank']
PARTICIPANTS = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Order', 'NOC Code', 'Bib Number',
                'FIG License', 'Name', 'Surname', 'Given Name', 'Birth Year', 'Birth Date']
JUDGES = ['Event Name', 'Discipline', 'Age Category', 'Event Start Date', 'Competition', 'Apparatus', 'Function',
          'Name', 'Surname', 'Given Name', 'NOC Code']
APPARATUS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['FX', 'BB', 'UB', 'VT'],
             # A mixed team's apparatus, each named with its discipline (both have floor)
             'MIX': ['MAG FX', 'MAG PB', 'MAG HB', 'WAG UB', 'WAG BB', 'WAG FX']}
# A ranking's format column in EVENT.csv, by what it ranks (an apparatus code: the apparatus titles)
FORMAT_COLUMNS = {'TEAM': 'Team Format', 'AA': 'AA Format'}

def with_round(header):
    """A header with `Round` after `Competition`: a competition held in elimination rounds (the Youth
    Olympic Games' mixed team final)."""
    i = header.index('Competition') + 1
    return header[:i] + ['Round'] + header[i:]

def mixed_judges_header():
    """JUDGES header for a mixed slice: `Round` (blank: every round), and `Panel`, the discipline of the
    panel the judge sat on, since both disciplines have a floor panel."""
    header = with_round(JUDGES)
    return header[:header.index('Apparatus')] + ['Panel'] + header[header.index('Apparatus'):]

def score_header(vault, qual, combined_sj_penalty=False, team_role=False, rounds=False):
    """SCORES-* header: single-routine or two-attempt vault shape, with or without qualification columns.
    The vault shape's optional `Combined SJ Penalty` follows `Combined Bonus`; the optional `Team Role`
    comes last; `rounds` adds `Round`."""
    cols = VAULT if vault else ROUTINE
    if vault and combined_sj_penalty:
        cols = VAULT[:-1] + ['Combined SJ Penalty', 'Total']
    header = SCORE_META + cols + (QUALIFICATION if qual else []) + (['Team Role'] if team_role else [])
    return with_round(header) if rounds else header

# ---------------------------------------------------------------- corrections
CORRECTIONS = ['File', 'Key', 'Field', 'Printed', 'Corrected', 'Category', 'Source', 'Note']

def row_key(name, row):
    """How a CORRECTIONS row names the row it corrects: the bib, a team ranking's NOC, or a judge's
    `Competition Apparatus Function` (apparatus `-` when blank). A judge correction can instead name
    the judge as printed, for every row with that name."""
    if 'JUDGES' in name:
        panel = f'{row["Panel"]} ' if row.get('Panel') else ''
        return f'{row["Competition"]} {panel}{row["Apparatus"] or "-"} {row["Function"]}'
    return row.get('Bib') or row.get('Bib Number') or row['NOC Code']

class Corrections:
    """`<event>-CORRECTIONS.csv`: the values written differently from the results book, and why
    (docs/import-file-model.md). Applied as each file is written; a correction whose printed value
    isn't the row's, or that never applies, is an error, so the log can't drift from the files.
    A folder's parsers share the file; each takes the rows for the prefixes it writes (`MAG-SR`, …)."""

    def __init__(self, out_dir, event_prefix, scopes, err):
        self.prefix, self.err = event_prefix, err
        path = os.path.join(out_dir, f'{event_prefix}-CORRECTIONS.csv')
        self.rows = []
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if reader.fieldnames != CORRECTIONS:
                    raise SystemExit(f'{path}: header {reader.fieldnames} != {CORRECTIONS}')
                self.rows = [dict(r, used=False) for r in reader
                             if any(r['File'].startswith(s + '-') for s in scopes)]

    def apply(self, name, header, rows):
        label = name.removeprefix(self.prefix + '-').removesuffix('.csv')
        # Rows are found by their printed key and name, whatever corrections apply first
        keys = [(row_key(name, r), r.get('Name')) for r in rows]
        for c in self.rows:
            if c['File'] != label:
                continue
            c['used'] = True
            if c['Field'] not in header:
                self.err(f'correction {label} {c["Key"]}: no column {c["Field"]!r}'); continue
            hits = [r for r, (key, _) in zip(rows, keys) if key == c['Key']]
            if not hits and 'JUDGES' in name:
                # A judge's printed name corrects every panel they sat on
                hits = [r for r, (_, printed) in zip(rows, keys) if printed == c['Key']]
            elif len(hits) > 1:
                hits = []
            if not hits:
                self.err(f'correction {label} {c["Key"]}: no single row matches'); continue
            for hit in hits:
                if str(hit[c['Field']]) != c['Printed']:
                    self.err(f'correction {label} {c["Key"]} {c["Field"]}: printed {c["Printed"]!r}, '
                             f'the row has {hit[c["Field"]]!r}')
                else:
                    hit[c['Field']] = c['Corrected']

    def finish(self):
        for c in self.rows:
            if not c['used']:
                self.err(f'correction {c["File"]} {c["Key"]} {c["Field"]}: no such file written')
        if self.rows:
            print(f'{len(self.rows)} corrections applied')

# ---------------------------------------------------------------- output
class Output:
    """Writes CSVs and the IMPORT.json manifest into one event folder, applying any corrections."""

    def __init__(self, out_dir, corrections=None):
        self.dir = out_dir
        self.corrections = corrections
        self.participants = {}  # rows of each PARTICIPANTS file written, by prefix
        self.rankings = set()

    def csv(self, name, header, rows, correct=True):
        if correct and self.corrections:
            self.corrections.apply(name, header, rows)
        if name.endswith('-PARTICIPANTS.csv'):
            self.participants[name.removesuffix('-PARTICIPANTS.csv')] = rows
        with open(os.path.join(self.dir, name), 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f, lineterminator='\n')
            w.writerow(header)
            for r in rows:
                missing = [h for h in header if h not in r]
                if missing:
                    raise SystemExit(f'{name}: row missing {missing}: {r}')
                w.writerow([r[h] for h in header])
        print(f'{name}: {len(rows)} rows')

    def ranking(self, prefix, kind, header, rows, event, left_out_from=None, last_round=None):
        """`<prefix>-RANKING-{QUAL,FINAL}-<kind>.csv` (kind `TEAM`, `AA` or an apparatus code): standings
        whose rows each name the competition they rank (`Competition`, `Part`). The parser's header has
        neither `Purpose` nor `Rank Status`; they're added here.

        - Purpose follows the event's format (EVENT.csv): a ranking of C1 for a title its own final
          decided is `QUALIFYING`; a split competition's part rows `INFORMATIONAL`; otherwise `FINAL`.
          A final ranking qualifies no one: its `Qualification` column is dropped, an `NR` becoming
          the `NOC_LIMIT` rank status, and any other marker is an error.
        - `left_out_from`: the rows of a qualifying ranking printed over the same routines for a
          title Competition I decided (2026 Asian Championships). Only the final ranking is written,
          with the teams or athletes it leaves out added unranked, as the qualifying ranking has them.
        - `last_round`: for a competition held in elimination rounds, the deciding one; a row of an
          earlier round (its `Round` column) is `QUALIFYING`.
        - Corrections apply next, then every blank rank gets its Rank Status (`rank_status`)."""
        header = list(header)
        header.insert(header.index('Part') + 1, 'Purpose')
        header.insert(header.index('Rank') + 1, 'Rank Status')
        title_format = event[FORMAT_COLUMNS.get(kind, 'Apparatus Format')]
        if not title_format:
            raise SystemExit(f'{prefix}: EVENT.csv has no {FORMAT_COLUMNS.get(kind, "Apparatus Format")}')
        for r in rows:
            r['Purpose'] = ('INFORMATIONAL' if r['Part'] else
                            'QUALIFYING' if r['Competition'] == 'C1' and title_format == 'FINAL' else
                            'QUALIFYING' if r.get('Round') and int(r['Round']) < last_round else 'FINAL')
            r.setdefault('Rank Status', '')
        purposes = {r['Purpose'] for r in rows if not r['Part']}
        if len(purposes) != 1:
            raise SystemExit(f'{prefix} {kind}: rows of purposes {sorted(purposes)} in one ranking')
        final = purposes == {'FINAL'}
        name = f'{prefix}-RANKING-{"FINAL" if final else "QUAL"}-{kind}.csv'
        if name in self.rankings:
            raise SystemExit(f'{name}: written twice; a title has one ranking per purpose')
        self.rankings.add(name)
        if left_out_from:
            key = 'NOC Code' if kind == 'TEAM' else 'Bib'
            present = {r[key] for r in rows}
            for q in left_out_from:
                if q[key] not in present:
                    rows.append({**{h: q.get(h, '') for h in header}, 'Competition': rows[0]['Competition'],
                                 'Purpose': 'FINAL', 'Rank': '',
                                 'Rank Status': 'NOC_LIMIT' if q.get('Qualification') == 'NR' else ''})
        if self.corrections:
            self.corrections.apply(name, header, rows)
        if final and 'Qualification' in header:
            for r in rows:
                if r['Qualification'] not in ('', 'NR'):
                    raise SystemExit(f'{name}: {r.get("Bib") or r["NOC Code"]} marked {r["Qualification"]} on a '
                                     'final ranking; look at it')
                if r['Qualification'] == 'NR':
                    if r['Rank']:
                        raise SystemExit(f'{name}: {r.get("Bib") or r["NOC Code"]} is ranked and marked NR')
                    r['Rank Status'] = 'NOC_LIMIT'
            header.remove('Qualification')
        participants = self.participants_of(prefix)
        for r in rows:
            if not r['Rank'] and not r['Rank Status']:
                r['Rank Status'] = rank_status(r, kind, event['Disciplines'], rows, participants)
                if not r['Rank Status']:
                    raise SystemExit(f'{name}: no rule gives a rank status for {r.get("Bib") or r["NOC Code"]} '
                                     f'{r.get("Name", "")}; look at it')
        self.csv(name, header, rows, correct=False)

    def participants_of(self, prefix):
        """The PARTICIPANTS rows written for the prefix, or the file already in the folder. A mixed slice
        has no entry list of its own: its gymnasts are the men's and women's."""
        if '-MIX-' in prefix:
            return self.participants_of(prefix.replace('-MIX-', '-MAG-')) + \
                self.participants_of(prefix.replace('-MIX-', '-WAG-'))
        if prefix not in self.participants:
            path = os.path.join(self.dir, f'{prefix}-PARTICIPANTS.csv')
            with open(path, encoding='utf-8') as f:
                self.participants[prefix] = list(csv.DictReader(f))
        return self.participants[prefix]

    def manifest(self, prefix, event):
        """`<prefix>-IMPORT.json`: the EVENT.csv row, its formats included, plus every file written for
        this prefix."""
        files = sorted(os.listdir(self.dir))
        formats = {key: event.get(column, '') for key, column in
                   (('teamFormat', 'Team Format'), ('aaFormat', 'AA Format'), ('apparatusFormat', 'Apparatus Format'))}
        if not all(formats.values()):
            raise SystemExit(f'{prefix}: EVENT.csv needs Team Format, AA Format and Apparatus Format')
        # An optional Slug names the event's address, for a folder holding several events
        slug = {'slug': event['Slug']} if event.get('Slug') else {}
        manifest = {
            'event': {**slug, 'title': event['Title'], 'shortName': event['Short Name'],
                      'disciplines': event['Disciplines'],
                      'ageCategory': event['Age Category'], 'level': event['Level'],
                      'startDate': event['Start Date'], 'endDate': event['End Date'], 'city': event['City'],
                      'country': event['Country'], 'figEventNumber': event['FIG Event Number'],
                      'venue': event['Venue'], 'apparatusSuppliers': event['Apparatus Suppliers'], **formats},
            'participants': [f for f in files if f.startswith(prefix + '-PARTICIPANTS')],
            'judges': [f for f in files if f.startswith(prefix + '-JUDGES')],
            'scores': [f for f in files if f.startswith(prefix + '-SCORES-')],
            'rankings': [f for f in files if f.startswith(prefix + '-RANKING-')],
        }
        with open(os.path.join(self.dir, f'{prefix}-IMPORT.json'), 'w') as f:
            json.dump(manifest, f, indent=4, separators=(',', ' : '))
            f.write('\n')


def rank_status(row, kind, discipline, rows, participants):
    """Why a ranking row has no rank (import-file-model.md, Rank Status), by rule, in order:

    - an hors concours entry (`Entry Status`; a team all of whose entries are): `HORS_CONCOURS`;
    - a partial all-around, an entry who started no apparatus included, or a team missing an
      apparatus total: `INCOMPLETE`;
    - a split competition's part row: `UNPLACED` (US Championships print no day-2 places);
    - in a final ranking, an athlete outside its printed places: `NOC_LIMIT` when two compatriots
      are ranked and the total beats the lowest ranked total (the two-per-country limit cost a
      place), otherwise `UNPLACED`; a team outside them: `UNPLACED`.

    None where no rule applies (a full all-around unranked in a qualifying ranking)."""
    hors_concours = {p['Bib Number'] for p in participants if p.get('Entry Status') == 'HORS_CONCOURS'}
    entries = collections.defaultdict(set)
    for p in participants:
        entries[p['NOC Code']].add(p['Bib Number'])
    hors_concours_nocs = {noc for noc, bibs in entries.items() if noc and bibs and bibs <= hors_concours}
    if kind == 'TEAM' and row['NOC Code'] in hors_concours_nocs or row.get('Bib') in hors_concours:
        return 'HORS_CONCOURS'
    totals = [row.get(a + ' Total', '') for a in APPARATUS[discipline]] if kind in ('TEAM', 'AA') else []
    # A split competition's combined row prints a total but no apparatus totals
    if totals and not all(totals) and (any(totals) or not row['Total']):
        return 'INCOMPLETE'
    if row['Part']:
        return 'UNPLACED'
    if row['Purpose'] != 'FINAL':
        return None
    if kind == 'AA':
        ranked = [r for r in rows if r['Rank']]
        lowest = min((D(r['Total']) for r in ranked if r['Total']), default=None)
        compatriots = sum(1 for r in ranked if r['NOC Code'] == row['NOC Code'])
        if compatriots >= 2 and lowest is not None and row['Total'] and D(row['Total']) > lowest:
            return 'NOC_LIMIT'
    return 'UNPLACED'

# ---------------------------------------------------------------- checks
class Checks:
    """Collects check failures; `finish()` prints them and exits non-zero if there were any."""

    def __init__(self):
        self.errors = []

    def err(self, msg):
        self.errors.append(msg)

    def check_sum(self, ctx, total, *parts):
        """Routine components (D, E, bonus, penalty, …) must add up to the printed score."""
        if sum((D(p) for p in parts), Decimal(0)) != D(total):
            self.err(f'{ctx}: {" + ".join(p or "0" for p in parts)} != {total}')

    def check_vault_average(self, ctx, first, second, combined_bonus, published):
        """A two-vault result is the average of the attempts, truncated to 3 decimals, plus any
        combined bonus."""
        avg = (D(first) + D(second)) / 2 + D(combined_bonus)
        if not Decimal(0) <= avg - D(published) < Decimal('0.001'):
            self.err(f'{ctx}: average {avg} != published {published}')

    def check_rank_order(self, ctx, rows):
        """Ranked rows: ranks never decrease, totals never increase, tied ranks have equal totals."""
        ranked = [r for r in rows if r['Rank']]
        for a, b in zip(ranked, ranked[1:]):
            if int(b['Rank']) < int(a['Rank']) or D(b['Total']) > D(a['Total']):
                self.err(f'{ctx}: rank order broken at bib {b["Bib"]}')
            if int(b['Rank']) == int(a['Rank']) and D(b['Total']) != D(a['Total']):
                self.err(f'{ctx}: tied rank with different totals at bib {b["Bib"]}')

    def finish(self):
        print(f'\n{len(self.errors)} errors')
        for e in self.errors:
            print(' ', e)
        sys.exit(1 if self.errors else 0)
