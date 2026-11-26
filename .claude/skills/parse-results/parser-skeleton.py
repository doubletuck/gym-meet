"""Parse the <YEAR> <COMPETITION> results into the CSV standard.

Usage (needs poppler's pdftotext on PATH):

    python3 -I parse_<year>_<event>.py data/<year>/<EVENT>/<EVENT>-ALL-RESULTS.pdf

Writes <list the files> and an IMPORT.json per discipline/level next to the PDF, reading
event metadata from the EVENT.csv already there. Exits non-zero if any check fails
(docs/instructions-results-parsing.md §3; this source format is §5.<n>).

<What the source is, which reports are used, and anything inferred rather than read.>
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from common import D

PDF = sys.argv[1]
OUT = os.path.dirname(os.path.abspath(PDF))
EVENT_PREFIX = '<YEAR>-<EVENT>'
PAGES = common.pdf_pages(PDF)
EVENTS = common.read_events(OUT, EVENT_PREFIX)
out = common.Output(OUT)
checks = common.Checks()
err = checks.err

APPS = {'MAG': ['FX', 'PH', 'SR', 'VT', 'PB', 'HB'], 'WAG': ['VT', 'UB', 'BB', 'FX']}
# Competition dates: from the Competition Schedule page (§4.4). Say where they came from.
COMPETITION_DATE = {}

def participants(disc):
    """Entry list -> PARTICIPANTS rows (split names with common.split_surname_first or
    split_given_first, check the count against the source's own total)."""
    ...

def scores(disc, rnd, app):
    """One results table -> SCORES rows, with 'Competition': common.COMPETITION[rnd] (`rnd` is the
    book's name for the report: QUAL, AA, EVENT, TEAM; a meet's only competition is 'C1'). For every
    row: checks.check_sum(...); for vault: checks.check_vault_average(...); then
    checks.check_rank_order(...), a count check, and identity against PARTICIPANTS."""
    ...

def standings(disc, kind):
    """Team or all-around standings -> rows without Purpose or Rank Status, each naming the
    competition whose routines it ranks ('Competition', 'Part'). out.ranking() names the file and sets
    the purpose from the event's format, the rank statuses by rule (instructions §4.2)."""
    ...

for disc in ('MAG', 'WAG'):
    prefix = f'{EVENT_PREFIX}-{disc}-SR'
    ev = EVENTS[prefix]
    # out.csv(f'{prefix}-PARTICIPANTS.csv', common.PARTICIPANTS, rows)
    # out.csv(f'{prefix}-SCORES-{common.COMPETITION[rnd]}-FX.csv', common.score_header(vault=False, qual=True), rows)
    # out.ranking(prefix, 'AA', header, rows, ev)       # after PARTICIPANTS: hors concours entries
    # out.csv(f'{prefix}-JUDGES.csv', common.JUDGES, rows)
    out.manifest(prefix, ev)   # needs the EVENT.csv formats: Team Format, AA Format, Apparatus Format

checks.finish()
