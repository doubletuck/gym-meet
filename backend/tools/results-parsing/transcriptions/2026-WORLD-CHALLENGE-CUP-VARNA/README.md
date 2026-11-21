# Varna 2026 transcriptions

The results tables in `18226-ResultsbookMedia.pdf` have text, but the judging assignments and the
start lists are images. They were read by eye at 110-250 dpi and transcribed here, values exactly as
printed. The parser (`../../parse_2026_world_challenge_cup_varna.py`) reads them, checks every name
against the entry list, and compares the start lists with the results.

- `<DISC>-JUDGES-<ROUND>.txt`: `apparatus|function|SURNAME Given|noc`, function as printed; the
  Technical Delegate and round reserves have apparatus `-`. There is no MAG finals page.
- `<DISC>-START-QUAL.txt`: `apparatus|group|noc|bib|Competitor` (`Surname Given`, `(HC)` kept).
- `FINALS-START-LISTS.txt`: `discipline|apparatus|starters|reserves`, bibs in printed order.
