# 2026 Senior Pan American Championships transcriptions

Every page of `18533-ResultsbookMedia-PanAms-SR.pdf` except the schedule is a scanned image. The pages
were rendered at 220 dpi and read with OCR (macOS Vision) into drafts, and every row the drafts or
the parser's checks flagged was corrected by eye against the page. The parser
(`../../parse_2026_pan_american_championships_sr.py`) reads only these files, checks every row
arithmetically and against the other reports, and compares every routine, rank and total with
sporttech.io's own export of the competition (`18533-sporttech-export.csv`, next to the PDF).

Pipe-separated, `#` starts a comment (`# p30` gives the book page). A line starting with `!` is an
unreviewed draft line and fails the parser.

- `ENTRY-COUNTS.txt` (p. 3): `NOC|men|women`.
- `<DISC>-ENTRIES.txt`: `NOC|legal name|short name|licence|bib|year`, as printed. A leading `~` marks
  an entry struck through on the list (withdrawn). `(reserve)` is kept as printed on the short name.
- `<DISC>-JUDGES-<ROUND>.txt`: `apparatus|function|name|FED`, as printed (MAG `SURNAME, Given`, WAG
  `SURNAME Given`); Superior Jury rows have no apparatus.
- Results tables, one file per report: `<DISC>-QUAL-AA` (qualification all-around report: every
  routine), `<DISC>-QUAL-<APP>` (per-apparatus qualification), `<DISC>-QUAL-VT` (two-vault list),
  `<DISC>-AA` (all-around final), `<DISC>-EVENT-<APP>` (finals). Per athlete an athlete line
  `rank|marker|bib|SURNAME Given|totals…`, then one line per routine:
  `APP|D|E|B|Pen|Total`, or `APP|—` (no routine), `APP|DNS`, `APP|0` (a bare zero). Vault lists and
  vault finals use `VT1`/`VT2`, and their totals are `[VB|]Total`. Markers: `Q`, `Q1`…`Q8`,
  `R1`…`R3` as printed.
- `<DISC>-QUAL-TEAM.txt`: `T|rank|NOC|apparatus totals…|total[|penalty]`, then
  `M|bib|SURNAME Given|values…` per member (a score, `—`, `DNS`, or blank for a skipped apparatus).
  Struck-through member scores (not counting) are written as plain values.
