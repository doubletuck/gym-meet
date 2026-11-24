# 2026 Oceania Championships transcriptions

Two books, one per age category: `18530-ResultsbookMedia.pdf` (seniors) and `18531-ResultsbookMedia.pdf`
(juniors), laid out the same. Files are named `<DISC>-<AGE>-<report>.txt` (`MAG-SR-AA.txt`, `WAG-JR-START.txt`).
Each book has text for its covers, schedules, entry counts, medallists and entry
lists, which the parser reads from the PDF. The start lists, judges' sheets, team results and
all-around results are scans, most of them rotated a quarter turn. They were rendered at 200-220 dpi,
rotated upright and transcribed by eye (no OCR: about 40 lines a discipline). The parser
(`../../parse_2026_oceania_championships.py`) reads only these files for those reports and checks
them: every routine's arithmetic, every all-around total, the team totals against each apparatus's
best three, the start lists against the results, and the medallists against the rankings.

Pipe-separated, `#` starts a comment (`# p9` gives the PDF page). A line starting with `!` is an
unreviewed draft line and fails the parser. Values are copied as printed: penalties unsigned, `0.0`
where the book prints it, names as each report prints them (the files take names from the entry list).

- `<DISC>-<AGE>-AA.txt`: the all-around report, every routine of the competition: `rank|bib|Given
  Surname|NOC|total` (rank blank where none is printed), then `APP|D|E|P|S|Final` per routine in the
  book's column order (MAG FX PH SR VT PB HB, WAG VT UB BB FX), or `APP|DNS` for a cell printed
  `Final DNS`. `P` is the penalty and `S` the bonus; pommel horse and every WAG cell print no `S`
  (blank). An apparatus with an empty cell has no line.
- `<DISC>-<AGE>-TEAM.txt`: the team results, `rank|Country|total`. The page prints nothing else.
- `<DISC>-<AGE>-START.txt`: the Elevien start lists, `rotation|APP|bib|Given Surname` in printed order
  (the MAG juniors' list prints DAVIES twice in five groups; copied as printed).
- `<DISC>-<AGE>-JUDGES.txt`: `APP|function|name|federation`, each as printed. MAG's sheet is a grid with
  names `Given Surname (NOC)`, its Superior Jury in the title (`SJ Gareth Brettell (OGU)`; the juniors' sheet `(NZL)`); WAG's
  four panels print `SURNAME Given` and a judge number (not transcribed), its Superior Jury
  `Allana Slater OGU (AUS)` at the top. The Superior Jury lines have no apparatus.
- `<DISC>-<AGE>-TEAM-SCORES.txt`: not from the book, which doesn't say who was on each team: the
  Elevien results site's team pages, from screenshots the user supplied (kept in the event folder as
  `<event id>-2026-Oceania-Champs-<DISC>-<AGE>-Team(s).png`). A country's block the book doesn't rank
  (the MAG juniors' New Zealand) is kept as a comment.
  `T|rank|Country|total`, then `M|bib|Given Surname|<one value per apparatus>` per team member in the
  book's apparatus order. A score is one the team was up for on that apparatus; `~` before one printed
  grey (dropped from the team total); blank where the member wasn't up for the team (an athlete of the
  country who competed there was the individual). `DNS` (`~DNS` printed grey) is a team member who
  didn't start.
