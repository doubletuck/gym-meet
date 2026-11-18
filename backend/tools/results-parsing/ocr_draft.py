"""Draft transcriptions of scanned results pages from OCR word boxes (ocr_pages.swift).

Usage:

    python3 -I ocr_draft.py <ocr_dir> layout <first> <last>
    python3 -I ocr_draft.py <ocr_dir> table <first> <last> FX,PH,SR,VT,PB,HB
    python3 -I ocr_draft.py <ocr_dir> vault-list <first> <last>
    python3 -I ocr_draft.py <ocr_dir> team <first> <last> <number of apparatus>
    python3 -I ocr_draft.py <ocr_dir> entries <first> <last>

`<ocr_dir>` holds `p-NNN.png.tsv` per page (from `pdftoppm -r 220 -png <pdf> <dir>/p`). Each mode
prints a draft in the transcription format of the Senior Pan Americans
(transcriptions/2026-PAN-AMERICAN-CHAMPIONSHIPS-SR/README.md):

- layout: the page rebuilt as text lines (y position, then words placed by x), for surveying a book;
- table: sporttech.io results tables, one or more routines per athlete (`D E Total`, with `Pen` and
  `B` on the line below). Columns are learned from the rows that parse completely;
- vault-list: sporttech.io's two-vault list (`D [B] E [Pen] Total` on two lines, then the totals);
- team: sporttech.io's team report, members' values placed under the learned member columns;
- entries: an organizer entry list (NOC, legal name, short name, licence, bib, year).

A drafted line that doesn't parse or add up starts with `!` and carries the raw OCR text; the
parsers reject `!` lines, so every one must be corrected against the page image. Rows that parse are
drafts too: OCR drops lone characters (a bare `0`, a `—`), misreads struck-through numbers and
reads markers poorly, so check markers by eye and compare with a text copy where there is one
(docs/instructions-results-parsing.md §2.3).
"""
import os, re, sys
from collections import Counter
from decimal import Decimal, InvalidOperation

# OCR reads some Latin capitals in names as their Cyrillic look-alikes
LATIN = str.maketrans('ХЕРМАВКТНОСхеромаскт', 'XEPMABKTHOCxepomackt')
BIB = re.compile(r'[#$₩](\d{3})\b')       # '#330', sometimes read as '$' or '₩'

def words(ocr_dir, page):
    out = []
    for l in open(os.path.join(ocr_dir, f'p-{page:03d}.png.tsv'), encoding='utf-8'):
        x0, y0, x1, y1, _, t = l.rstrip('\n').split('\t', 5)
        x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
        out.append(dict(x0=x0, x1=x1, xc=(x0 + x1) / 2, y=(y0 + y1) / 2, t=t.translate(LATIN)))
    return out

def lines(ws, tolerance=12):
    """Words grouped into lines by vertical position, each sorted left to right."""
    rows = []
    for w in sorted(ws, key=lambda w: w['y']):
        if rows and abs(rows[-1]['y'] - w['y']) < tolerance:
            rows[-1]['w'].append(w)
        else:
            rows.append(dict(y=w['y'], w=[w]))
    for r in rows:
        r['w'].sort(key=lambda w: w['x0'])
        r['s'] = ' '.join(w['t'] for w in r['w'])
    return rows

def values(ws):
    """Value words -> [(x, value)], repairing the common OCR slips: ',' for '.', a dropped decimal
    point ('7166'), two values run together ('10.7334.2')."""
    out = []
    for w in ws:
        s = w['t'].replace(',', '.').strip('|()[]:;')
        if s in ('-', '—', '–', '_'):
            out.append((w['xc'], '—'))
        elif s in ('...', '…', '..'):
            out.append((w['xc'], '…'))
        elif s in ('DNS', 'DNF'):
            out.append((w['xc'], s))
        else:
            if re.fullmatch(r'\d{4}', s):
                s = s[0] + '.' + s[1:]
            elif re.fullmatch(r'\d{5}', s):
                s = s[:2] + '.' + s[2:]
            parts = re.findall(r'-?\d+\.\d{3}|-?\d\.\d|\b0\b', s)
            if parts and ''.join(parts).replace('-', '') == re.sub(r'[^0-9.]', '', s.replace('-', '')):
                width = (w['x1'] - w['x0']) / len(parts)
                out += [(w['x0'] + width * (i + 0.5), p) for i, p in enumerate(parts)]
            elif s:
                out.append((w['xc'], '?' + w['t']))
    return out

def adds_up(g):
    if g['k'] != 'r':
        return True
    try:
        return sum(Decimal(x or '0') for x in (g['D'], g['E'], g['B'], g['P'])) == Decimal(g['T'])
    except InvalidOperation:
        return False

def routine_line(app, g):
    return f'{app}|{g["k"]}' if g['k'] != 'r' else f'{app}|{g["D"]}|{g["E"]}|{g["B"]}|{g["P"]}|{g["T"]}'

# ---------------------------------------------------------------- layout
def layout(ocr_dir, first, last):
    for page in range(first, last + 1):
        print(f'# p{page}')
        for r in lines(words(ocr_dir, page)):
            s = ''
            for w in r['w']:
                s += ' ' * max(1 if s else 0, int(w['x0'] / 11) - len(s)) + w['t']
            print(f'{int(r["y"]):5d} | {s}')

# ---------------------------------------------------------------- results tables
def athletes(ocr_dir, first, last):
    """Each athlete's identity line (rank, marker, bib, name, value words) and the words below it."""
    for page in range(first, last + 1):
        rows = lines(words(ocr_dir, page))
        stop = next((r['y'] for r in rows if r['s'].startswith('Legend') or 'Generated by' in r['s']), 1e9)
        rows = [r for r in rows if r['y'] < stop]
        ids = [r for r in rows if BIB.search(r['s'])]
        for k, r in enumerate(ids):
            below_until = ids[k + 1]['y'] if k + 1 < len(ids) else stop
            m = BIB.search(r['s'])
            before = r['s'][:m.start()]
            rank = re.search(r'(\d+)\s*[.,]', before)
            mk = re.search(r'\b([QR]\d)\b', before)
            mk = mk.group(1) if mk else 'Q' if re.search(r'\d\s*\.\s*Q\b', before) else ''
            year = next((w for w in r['w'] if re.fullmatch(r'(19|20)\w\w', w['t'])), None)
            year_x = year['x1'] if year else 0
            bib_x = next(w for w in r['w'] if BIB.search(w['t']))['x0']
            name = ' '.join(w['t'] for w in r['w'] if w['x0'] > bib_x and (not year or w['x1'] <= year['x0']))
            vals = values([w for w in r['w'] if w['x0'] > year_x + 60
                           and (w['t'] in ('DNS', 'DNF', '-', '—', '–') or re.search(r'\d|\.\.', w['t']))])
            below = [w for rr in rows if r['y'] + 8 < rr['y'] < below_until - 8 for w in rr['w']]
            # Q1…R3 print in a margin column, level with the row or a little off it
            for rr in rows:
                if rr is not r and abs(rr['y'] - r['y']) < 40:
                    mk = next((w['t'] for w in rr['w'] if w['x0'] < 160 and re.fullmatch(r'[QR]\d', w['t'])), mk)
            if not mk:   # a plain Q under the rank
                mk = next((w['t'].rstrip('.') for w in below if w['x0'] < 200 and re.fullmatch(r'Q\.?', w['t'])), '')
            yield dict(page=page, y=r['y'], rank=rank.group(1) if rank else '', mk=mk, bib=m.group(1), name=name,
                       vals=vals, sub=[w for w in below if w['x0'] > year_x + 60])

def sequence(vals, n):
    """A row read left to right as n routines — D E Total, '—', '… … DNS' or '0' — and what's left."""
    gs, v, i = [], [x for _, x in vals], 0
    while len(gs) < n and i < len(v):
        if v[i] == '—':
            gs.append(dict(k='—')); i += 1
        elif v[i] in ('…', 'DNS'):
            j = i
            while j < len(v) and v[j] == '…':
                j += 1
            if j == len(v) or v[j] != 'DNS':
                return None, v
            gs.append(dict(k='DNS')); i = j + 1
        elif v[i] == '0':
            gs.append(dict(k='0')); i += 1
        elif i + 2 < len(v) and re.fullmatch(r'\d\.\d', v[i]) and all(re.fullmatch(r'\d+\.\d{3}', x) for x in v[i + 1:i + 3]):
            gs.append(dict(k='r')); i += 3
        else:
            return None, v
    return (gs if len(gs) == n else None), v[i:]

def table(ocr_dir, first, last, apps):
    n = len(apps)
    found = list(athletes(ocr_dir, first, last))
    # Column positions: the median x of each value in the rows that read as a full set of routines
    full = []
    for a in found:
        gs, rest = sequence(a['vals'], n)
        if gs and all(g['k'] == 'r' for g in gs):
            full.append([x for x, _ in a['vals']])
    if not full:
        raise SystemExit('no complete row to learn the columns from')
    width = Counter(len(xs) for xs in full).most_common(1)[0][0]
    cols = [sorted(c)[len(c) // 2] for c in zip(*(xs for xs in full if len(xs) == width))]

    def slot(a):
        cells, whole = [[] for _ in cols], {}
        for x, v in a['vals']:
            if x < cols[0] - 40:
                continue                     # a flag or icon in the country column
            if v in ('—', '…', 'DNS'):       # printed across a whole routine
                k = min(range(n), key=lambda k: min(abs(cols[3 * k + j] - x) for j in range(3)))
                whole.setdefault(k, []).append(v)
                continue
            j = min(range(len(cols)), key=lambda k: abs(cols[k] - x))
            if abs(cols[j] - x) > 45:
                return None, f'value {v}@{int(x)} off-column'
            cells[j].append(v)
        if any(len(c) > 1 for c in cells):
            return None, 'two values in a cell'
        gs = []
        for k in range(n):
            d, e, t = (c[0] if c else '' for c in cells[3 * k:3 * k + 3])
            if k in whole:
                if d or e or t:
                    return None, f'{apps[k]}: {whole[k]} with values'
                gs.append(dict(k='DNS' if 'DNS' in whole[k] else '—'))
            elif not (d or e or t):
                gs.append(dict(k='—' if n == 1 else 'blank'))
            elif t == '0' and not (d or e):
                gs.append(dict(k='0'))
            elif d and e and t:
                gs.append(dict(k='r', D=d, E=e, T=t, B='', P='', xd=cols[3 * k], xe=cols[3 * k + 1]))
            else:
                return None, f'{apps[k]}: partial {d!r} {e!r} {t!r}'
        return gs, [c[0] if c else '' for c in cells[3 * n:]]

    page = None
    for a in found:
        if a['page'] != page:
            print(f'# p{a["page"]}'); page = a['page']
        gs, totals = slot(a)
        if gs is not None:
            # Pen sits under its routine's D, B under its E; the sign tells them apart
            for w in a['sub']:
                for x, p in values([w]):
                    scored = [g for g in gs if g['k'] == 'r']
                    if not re.fullmatch(r'-?\d\.\d', p) or not scored:
                        gs, totals = None, f'below the row: {p}'; break
                    col = 'P' if p.startswith('-') else 'B'
                    g = min(scored, key=lambda g: abs(g['xd' if col == 'P' else 'xe'] - x))
                    if g[col]:
                        gs, totals = None, f'two values for {col}'; break
                    g[col] = p
                if gs is None:
                    break
        head = f'{a["rank"]}|{a["mk"]}|{a["bib"]}|{a["name"]}'
        if gs is None:
            raw = ' '.join(f'{v}@{int(x)}' for x, v in a['vals'])
            print(f'!{head}|ERR {totals} || RAW {raw} || BELOW {" ".join(w["t"] for w in a["sub"])} || y={int(a["y"])}')
            continue
        print(('' if all(adds_up(g) for g in gs) else '!') + head + '|' + '|'.join(totals))
        for app, g in zip(apps, gs):
            if g['k'] != 'blank':
                print(('' if adds_up(g) else '!') + routine_line(app, g))

def vault_list(ocr_dir, first, last):
    def inline(v):
        """One vault on one line: D [B] E [Pen] Total, or a bare 0."""
        if v and v[0] == '0':
            return dict(k='0'), v[1:]
        g = dict(k='r', D='', B='', E='', P='', T='')
        try:
            g['D'] = v.pop(0)
            if re.fullmatch(r'\d\.\d', v[0]):
                g['B'] = v.pop(0)
            g['E'] = v.pop(0)
            if re.fullmatch(r'-\d\.\d', v[0]):
                g['P'] = v.pop(0)
            g['T'] = v.pop(0)
        except IndexError:
            return None, v
        return g, v

    page = None
    for a in athletes(ocr_dir, first, last):
        if a['page'] != page:
            print(f'# p{a["page"]}'); page = a['page']
        v = [x for _, x in a['vals']]
        while len(v) > 4 and (v[0].startswith('?') or v[0] == '—'):
            v.pop(0)                         # the vault icon in the Apparatus column
        v1, totals = inline(v)
        v2, rest = inline([x for _, x in values(sorted(a['sub'], key=lambda w: w['x0']))])
        head = f'{a["rank"]}|{a["mk"]}|{a["bib"]}|{a["name"]}'
        if not (v1 and v2):
            print(f'!{head}|RAW {" ".join(x for _, x in a["vals"])} || BELOW {" ".join(w["t"] for w in a["sub"])}')
            continue
        flag = '' if not rest and v1['k'] == 'r' and adds_up(v1) and adds_up(v2) else '!'
        print(flag + head + '|' + '|'.join(totals))
        print(flag + routine_line('VT1', v1))
        print(flag + routine_line('VT2', v2))

# ---------------------------------------------------------------- team report
def team(ocr_dir, first, last, n):
    pages = {p: lines(words(ocr_dir, p)) for p in range(first, last + 1)}
    # Member columns sit left of the team totals: learn them from members with every value printed
    full = [[w['xc'] for w in r['w'] if re.fullmatch(r'\d+[.,]\d{3}', w['t'])] for rows in pages.values()
            for r in rows if '#' in r['s']]
    cols = [sorted(c)[len(c) // 2] for c in zip(*(xs for xs in full if len(xs) == n))]
    for page, rows in pages.items():
        print(f'# p{page}')
        for r in rows:
            if 'Generated' in r['s'] or 'Legend' in r['s']:
                break
            m = re.search(r'#(\d{3})', r['s'])
            if m:
                cells, bad = [''] * n, ''
                for w in r['w']:
                    if w['x0'] <= cols[0] - 60 or not re.search(r'\d|^[-—–]|DNS', w['t']):
                        continue
                    glued = re.fullmatch(r'(\d+[.,]\d{3})([-—–])', w['t'])     # '12.733-'
                    parts = [glued.group(1), '—'] if glued else re.findall(r'\d+[.,]\d{3}|DNS|^[-—–]$', w['t']) or [w['t']]
                    width = (w['x1'] - w['x0']) / len(parts)
                    for i, p in enumerate(parts):
                        x = w['x0'] + width * (i + 0.5)
                        j = min(range(n), key=lambda k: abs(cols[k] - x))
                        if abs(cols[j] - x) > 50 or cells[j]:
                            bad += f' {p}@{int(x)}'
                        else:
                            cells[j] = '—' if p in ('-', '—', '–') else p.replace(',', '.')
                name = ' '.join(w['t'] for w in r['w'][1:] if w['x0'] < cols[0] - 150
                                and not re.fullmatch(r'(19|20)\d\d|#\d{3}', w['t']))
                print(('!' if bad else '') + f'M|{m.group(1)}|{name}|' + '|'.join(cells) + (f' || {bad}' if bad else ''))
                continue
            nums = [w['t'].replace(',', '.') for w in r['w'] if re.fullmatch(r'\d+[.,]\d{3}', w['t'])]
            rank = re.match(r'\s*(\d+)\s*\.', r['s'])
            noc = re.search(r'\b([A-Z]{3})\b', r['s'])
            if len(nums) >= n:
                ok = rank and noc and len(nums) == n + 1
                print(('' if ok else '!') + f'T|{rank.group(1) if rank else "?"}|{noc.group(1) if noc else "?"}|'
                      + '|'.join(nums) + ('' if ok else f' || {r["s"]}'))

# ---------------------------------------------------------------- entry list
def entries(ocr_dir, first, last):
    for page in range(first, last + 1):
        print(f'# p{page}')
        noc = None
        for r in lines(words(ocr_dir, page)):
            if r['y'] < 500:
                continue                     # page header
            c = dict(noc=[], legal=[], name=[], lic=[], bib=[], year=[])
            for w in r['w']:
                x = w['x0']
                c['noc' if x < 200 else 'legal' if x < 700 else 'name' if x < 1150 else 'lic' if x < 1400
                  else 'bib' if x < 1530 else 'year'].append(w['t'])
            c = {k: ' '.join(v) for k, v in c.items()}
            if re.fullmatch(r'[A-Z]{3}', c['noc'].split(' ')[0]) and not c['bib']:
                noc = c['noc'].split(' ')[0]
            elif c['bib'] or c['year']:
                ok = noc and re.fullmatch(r'\d{3}', c['bib']) and re.fullmatch(r'\d{4}', c['year']) and c['legal']
                print(('' if ok else '!') + f"{noc}|{c['legal']}|{c['name']}|{c['lic']}|{c['bib']}|{c['year']}")
            elif any(c.values()) and 'SPIETH' not in r['s'] and 'GYM' not in r['s']:
                print('!? ' + ' | '.join(f'{k}={v}' for k, v in c.items() if v))

if __name__ == '__main__':
    ocr_dir, mode, first, last = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    if mode == 'layout':
        layout(ocr_dir, first, last)
    elif mode == 'table':
        table(ocr_dir, first, last, sys.argv[5].split(','))
    elif mode == 'vault-list':
        vault_list(ocr_dir, first, last)
    elif mode == 'team':
        team(ocr_dir, first, last, int(sys.argv[5]))
    elif mode == 'entries':
        entries(ocr_dir, first, last)
    else:
        raise SystemExit(f'unknown mode {mode!r}')
