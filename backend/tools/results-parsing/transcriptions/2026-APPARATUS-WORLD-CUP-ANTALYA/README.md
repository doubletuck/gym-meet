# Antalya 2026 transcriptions

One results page in `17936-ResultsbookMedia.pdf` has no text layer: MAG rings
qualification (p. 21). It was read by eye at 200 dpi and transcribed here; the parser
(`../../parse_2026_apparatus_world_cup_antalya.py`) reads it like the text pages, checks
every row arithmetically and compares it with the rings tie-break report (p. 22), which
has text.

Pipe-separated, `<DISC>-<ROUND>-<APP>.txt`:
`rank|bib|surname|name|noc|D|E|bonus|penalty|total|q`, values exactly as printed
(decimal commas on D/E/bonus/penalty, a point on the total; penalties unsigned).
