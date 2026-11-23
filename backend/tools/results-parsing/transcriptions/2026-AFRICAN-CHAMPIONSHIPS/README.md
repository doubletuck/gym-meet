# 2026 Senior African Championships transcriptions

`18377-ResultsbookMedia.pdf` was laid out in CorelDRAW: the schedule, entry counts and entry list have
text, which the parser reads from the PDF, but every results page is text converted to outlines and
the judges' pages are photographs, so they have no text layer. The pages were rendered at 220 dpi
and read with OCR (macOS Vision, the fast and accurate recognizers merged: `ocr_pages.swift --fast`,
`ocr_draft.py merge`), then every value the parser's checks flagged, every rank, `Q`/`R` mark, bold
team score and RK column was checked by eye against the page. The parser
(`../../parse_2026_african_championships.py`) reads only these files and checks every report against
the others: each routine's arithmetic, every apparatus table against the all-around report (values
and RK), the team pages against both, the tie-break pages and the finals start lists.

Pipe-separated, `#` starts a comment (`# p17` gives the book page). A line starting with `!` is an
unreviewed draft line and fails the parser. Values are copied as printed: penalties unsigned, ties
broken as printed, names as each report prints them (the files take names from the entry list).

- `<DISC>-JUDGES-<ROUND>.txt` (`QUAL`, `EVENT` for the finals): `APP|function|SURNAME|Given|NOC`. MAG's
  Competition Jury has no apparatus (`|TD|…`). The WAG sheets' two Superior Jury lines print a given
  name only: `SUPERIOR JURY 2` (Rawan) is transcribed with the surname blank, supplied by a correction;
  `SUPERIOR JURY 1` (Debbie) is not transcribed (see the comments there).
- `<DISC>-QUAL-TEAM.txt`: `T|rank|Country|total`, then `M|bib|Given SURNAME|values…` per member in the
  book's apparatus order (MAG FX PH SR VT PB HB, WAG VT UB BB FX); `*` before a score printed in bold
  (counting), blank where the member has no routine.
- `<DISC>-QUAL-AA.txt`: the all-around report, every routine of qualification:
  `rank|bib|SURNAME Given|NOC|total` (`<partial> DNF` for an incomplete all-around, no rank), then
  `APP|D|E|P|Total|RK` per routine. The report prints no bonus and `0.000` for no penalty.
- `<DISC>-QUAL-<APP>.txt`, `<DISC>-EVENT-<APP>.txt` (non-vault):
  `rank|bib|SURNAME Given|NOC|D|E|PEN|BONUS|Total|mark`. Pommel horse and every WAG table print no
  BONUS column (blank). Marks: `Q`, `R` as printed (the WAG uneven bars final prints `Q` on every row).
- `<DISC>-QUAL-VT.txt`, `<DISC>-EVENT-VT.txt`: `rank|bib|SURNAME Given|NOC|D|E|PEN|Score|Total|mark`
  for vault 1, then `V2|D|E|PEN|Score|Bonus` or `V2|DNS`. Total is the two-vault result, `DNF`, or blank
  for an athlete with one vault (listed unranked after the two-vault ranking).
- `<DISC>-TIE-BREAKS.txt`: `APP|rank|bib|SURNAME Given|NOC|Total|E|D`, vault
  `VT|rank|bib|SURNAME Given|NOC|Total|highest vault|E|D`; each page prints only the deciding value.
- `<DISC>-FINALS-START.txt`: the Apparatus Finals Start List, `APP|#|bib|Given SURNAME|NOC`, `#` 1-8,
  `R1`, `R2`.
