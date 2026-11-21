---
name: parse-results
description: Parse an artistic gymnastics competition results PDF (FIG results book, national championship printout, World Cup book, scanned or text) into the gym-meet import CSVs and IMPORT.json under data/<year>/<event>/. Use when the user adds a new results PDF, asks to parse/convert/import meet results, or asks to re-check existing parsed results.
---

# Parse competition results

Turn a results PDF into the import files for one competition. The standard and
the accumulated knowledge live in the repo — read them, don't work from memory:

- `backend/docs/import-file-model.md` — every file, column and database mapping (the target).
- `backend/docs/instructions-results-parsing.md` — techniques (§2), required checks (§3),
  conventions (§4), and notes per source format (§5). Read §5's matching section in full.
- `backend/docs/data-model.md` — entities, especially `Session` and `Score`.
- `backend/tools/results-parsing/` — `common.py` (shared helpers), `contact_sheet.py`
  (map a scanned book), `ocr_pages.swift` + `ocr_draft.py` (OCR drafts of scanned tables,
  macOS), and one existing parser per source format to start from.

The user is the authority on gymnastics rules and on what the data should mean. Ask when
something is ambiguous; never guess a value, a date or a mapping silently.

## 1. Survey the source

1. Confirm the inputs: the PDF(s) in `data/<year>/<EVENT>/` and `<EVENT>-EVENT.csv`
   (one row per discipline and age category: Prefix, Slug, Title, Disciplines, Age Category,
   Level, dates, City, IOC country code, Venue, FIG event number, Apparatus Suppliers).
   **If the rows for this PDF don't exist, draft them** from the book (title page, schedule,
   sponsor logos), the FIG event page, the meets tracker (`data/<year>/*-MEETS.csv`)
   and any sibling rows (another age category of the same meet); follow the existing rows'
   conventions for Title, Slug and Level. Show the user the drafted rows and ask for any
   field you couldn't find or had to infer (venue, level) before relying on them.
2. `pdfinfo`, then `pdftotext -layout` split on form feed. List every physical page's report
   identity and collapse runs; find pages with no text (scanned) and map them with
   `python3 -I backend/tools/results-parsing/contact_sheet.py <pdf> <scratch>.png`.
3. **Stop and tell the user** if the PDF isn't the expected competition, discipline (artistic
   MAG/WAG only) or level, if pages are missing (e.g. a start list shows more athletes than
   the results), or if a supplementary source would be needed.

## 2. Map the competition onto the model

Identify the structure (parsing doc §4.9): which rounds, whether a round is split into parts,
whether qualification is per apparatus, the vault shape per round, which summaries exist.
Work out every session's date (§4.4) — from a Competition Schedule page, never footer
timestamps; if there is none, propose an inference and confirm it.

**Ask before writing any code** if the meet needs anything the model or the CSV standard
doesn't have yet (a new enum value, a new column, a new session shape, a 4-character code,
an unknown judge function). Explain the options and recommend one; make the change (code,
tests, docs) only once the user agrees.

## 3. Write the parser

- Create `backend/tools/results-parsing/parse_<year>_<event_snake>.py`, starting from the
  closest existing parser and `parser-skeleton.py` in this skill's folder. Use `common.py`
  for sources, names, column sets, output, the manifest and checks; keep only what is
  specific to this source in the new file.
- Scanned pages: render at ~110 dpi, read them, and transcribe into
  `backend/tools/results-parsing/transcriptions/<EVENT>/` (format in an existing README there),
  copying values exactly as printed. Prefer a text copy of the same results when one exists
  (sporttech.io results can be exported as CSV; ask the user, and compare with
  `sporttech.py`). For many pages, draft with
  `ocr_pages.swift` and `ocr_draft.py` in the scratchpad (parsing doc §2.3), then correct
  every `!` line and check markers against the image; the drafts are not a source until reviewed.
- Follow the conventions in parsing doc §4 (names, ranks, status, vault, Q markers, judges,
  countries) and the column rules in `import-file-model.md`.
- Transcriptions copy the book as printed. Any value written differently (a tie-break, a status
  or score from a text copy such as a sporttech.io export, a judge's spelling) goes in the event's
  `<EVENT>-CORRECTIONS.csv`, applied through `common.Corrections`; see `import-file-model.md`.
- Write each prefix's `<PREFIX>-IMPORT.json` with `out.manifest(prefix, event_row)` after its
  CSVs: it copies the EVENT.csv row and lists every file written for that prefix.

## 4. Check

Implement every check in parsing doc §3 that applies — arithmetic, aggregates, rank order,
counts, cross-source agreement, identity against the entry list, finals vs qualifiers. The
parser must exit non-zero on any failure. Then:

1. Run it against a **scratch copy** of the event folder (the session's scratchpad), not the
   real one.
2. Plant one wrong value (in a source or transcription) and confirm a check catches it;
   restore it.
3. If files already exist for the event, compare old and new value by value and explain
   every difference.
4. Run it in place and confirm a second run produces identical files.
5. If any Java code changed, run `mvn -q test` in `backend/` — all tests must pass.

## 5. Report and document

- Summarize what was produced (files per discipline/level, row counts) and list every oddity
  that affects the file or database structures, each with a recommendation.
- Update `instructions-results-parsing.md` with what this source taught: extend the matching
  §5 section (or add one for a new format), add any new convention to §4, and keep §6 open
  items current. Update `import-file-model.md` / `data-model.md` if columns or meanings changed.
- If the meets tracker (`data/<year>/*-MEETS.csv`) lists this meet, set its Status to
  `Parsed`.
- Don't commit unless the user asks.
