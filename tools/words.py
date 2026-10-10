"""Word/sentence-page samples: letters cut from the free-writing pages.

Only the pages listed in PAGES are used (transcriptions below). For each page
half: rows -> transcript lines -> words -> characters, keeping a word only when
its ink-group count matches its character count exactly. Output has the same
sample dict format as extract.py plus key "src": "words".

    cd tools && /tmp/hfv/bin/python words.py
    -> tools/word_samples.pkl, tools/word_sheet.png
"""
import os, sys, pickle, itertools
from collections import Counter
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from seg import inkmask, rows, linekill, linebands
from groups import line_groups

SRC = os.path.join(HERE, "..", "handwriting", "2026-10-10")
REF_PKL = os.path.join(HERE, "samples.pkl")      # extract.py output (alphabet photos)
OUT_PKL = os.path.join(HERE, "word_samples.pkl")
OUT_SHEET = os.path.join(HERE, "word_sheet.png")

ROT = {}                       # all pages used here are landscape, rot 0
DESC = set("gjpqy,;Q")         # same as extract.py
NOSIT = DESC | set("'\"-~^=*")
TWO = set("ij!?:;")            # chars whose glyph is two ink pieces
XH_CHARS = set("acemnorsuvwxz")
MIN_INK = 300                  # rows with less ink are noise
ROW_JOIN_GAP = 12              # row pieces closer than this are one text line
MIN_ROW_H = 0.5                # row height < this * median row height = noise
MARGIN = 60                    # outer page margin (px)
SPINE_PAD = 15                 # left page stops this far before the spine
RIGHT_PAD = 30                 # right page starts this far after the spine
WORD_SEP = 1.3                 # word gaps must be >= this x the largest within-word gap
SMALL_FRAC = 0.45              # piece is "small" (dot/comma) if h <= frac * x-height
MERGE_VGAP = 0.35              # max vertical gap (x-height units) for a dot merge
MAX_W = 2.1                    # glyph width limit in x-height units (caps reach ~2.0)
MAX_H = 2.6                    # glyph height limit in x-height units (ascender+descender)

# (file, side, transcript lines top->bottom, rows to skip at top)
PAGES = [
 ("IMG_0081.jpg", "L", [
   "The quick brown fox jumps over",
   "the lazy dog. Pack my box with",
   "five dozen liquor jugs",
   "How vexingly quick draft zebras jump!",
   "Sphinx of black quartz, judge my vow.",
   "The five boxing wizards jump quickly"], 5),
 ("IMG_0081.jpg", "R", [
   "The quick brown fox",
   "jumps over the lazy dog",
   "Pack my box with",
   "five dozen liquor jugs"], 0),
 ("IMG_0080.jpg", "L", [
   "QUICK ZEBRAS JUMP. VEXING",
   "FOXES WALK BY.",
   "Call 9876543210 at 10:45",
   "am pm on 28/06/2026 cost Rs 1,299",
   "50% off!",
   "The quick brown fox jumps over the",
   "lazy dog. Pack my box with five",
   "dozen liquor jugs. How vexingly",
   "quick draft zebras jump!",
   "Sphinx of black quartz, judge my",
   "vow! The five boxing wizards",
   "jump quickly."], 0),
 ("IMG_0080.jpg", "R", [
   "Jackdraws love my big sphinx of",
   "quartz. Mother, father, sister,",
   "brother, friend, family home.",
   "Monday, Tuesday, Wednesday,",
   "Thursday, Friday, Saturday, Sunday.",
   "January, August, october, December.",
   "Yes! it is ready. Can you come at",
   "7:30 pm? Email me: hello@mail.com",
   "Hope you are well. Thank you so much.",
   "with love."], 0),
 ("IMG_0079.jpg", "R", [
   "the lakes that you're used to",
   "I'm you're he's it's",
   "better it's oop... - get rich",
   "podcasts? #1 reason",
   "HTTP 5x 10x slower",
   "NEED, SQL, PHP, python,",
   "go, lang, ai Artificial intelligence",
   "font handwriting need to fix"], 0),
 ("IMG_0078.jpg", "L", [
   "the and that have with this",
   "from they want what you want!",
   "ing ion ent tion ough ight ness",
   "ment able ally tte ppy ss ll ee",
   "oo aa st good past am are you",
   "are look great nation ness close",
   "open brave great.",
   "Pack my box with five dozen",
   "liquor jugs!",
   "How vexingly quick draft zebras",
   "Jump!"], 0),
]


def load(f, rot=0):
    from PIL import Image as _I
    im = _I.open(os.path.join(SRC, f)).convert("RGB")
    if rot:
        im = im.rotate(rot, expand=True)
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)


def merge(a, b):
    x = min(a['x'], b['x']); y = min(a['y'], b['y'])
    X = max(a['x'] + a['w'], b['x'] + b['w']); Y = max(a['y'] + a['h'], b['y'] + b['h'])
    m = np.zeros((Y - y, X - x), bool)
    for g in (a, b):
        m[g['y'] - y:g['y'] - y + g['h'], g['x'] - x:g['x'] - x + g['w']] |= g['mask']
    return dict(x=x, y=y, w=X - x, h=Y - y, mask=m)


def page_bounds(im, m):
    """Spine = darkest band of the paper in the middle 40-60%, found on the
    grayscale column profile (the ink profile has no reliable minimum here).
    Returns (left_x1, right_x0)."""
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    H, W = g.shape
    colp = np.percentile(g[::3], 60, axis=0)
    sm = np.convolve(colp, np.ones(15) / 15, 'same')
    lo, hi = int(0.4 * W), int(0.6 * W)
    mn = sm[lo:hi].min(); paper = np.median(sm[lo:hi])
    thr = (mn + paper) / 2
    dark = np.where(sm[lo:hi] < thr)[0] + lo
    left_edge, right_edge = int(dark.min()), int(dark.max())
    return left_edge - SPINE_PAD, right_edge + RIGHT_PAD, (left_edge, right_edge)


def align_rows(cands, n):
    """cands: list of (a,b,ink). Need exactly n. Drop surplus rows (<=2) whose
    removal makes the line spacing most regular; refuse if not clearly unique."""
    if len(cands) == n:
        return cands, "exact"
    k = len(cands) - n
    if k < 0 or k > 2:
        return None, "count %d != %d" % (len(cands), n)
    cen = np.array([(a + b) / 2 for a, b, _ in cands])
    scores = []
    for drop in itertools.combinations(range(len(cands)), k):
        keep = [i for i in range(len(cands)) if i not in drop]
        d = np.diff(cen[keep])
        scores.append((float(np.std(d)), drop))
    scores.sort()
    if len(scores) > 1 and scores[1][0] < 1.5 * scores[0][0] + 1e-6:
        return None, "ambiguous drop (%s vs %s)" % (scores[0][1], scores[1][1])
    drop = set(scores[0][1])
    keep = [c for i, c in enumerate(cands) if i not in drop]
    return keep, "dropped %s (spacing std %.1f)" % ([cands[i][:2] for i in scores[0][1]], scores[0][0])


def split_words(gs, nwords):
    """Split a row's ink groups into nwords clusters.

    Gaps between consecutive groups (x order, running right edge) are ranked.
    Word gaps are the nwords-1 largest; they must be clearly separated
    (smallest word gap >= WORD_SEP x largest remaining gap), otherwise the
    row is ambiguous and returns None. The threshold printed is the midpoint
    between the two gap values. (A fixed 0.55*letter-width threshold split
    every word here: within-word gaps reach ~45 px, word gaps start ~50 px.)"""
    G = sorted(gs, key=lambda q: q['x'])
    if nwords == 1:
        return [G], None, None
    gaps = []; right = None
    for i in range(1, len(G)):
        right = G[i - 1]['x'] + G[i - 1]['w'] if right is None else max(right, G[i - 1]['x'] + G[i - 1]['w'])
        gaps.append((G[i]['x'] - right, i))
    if len(gaps) < nwords - 1:
        return None, None, None
    rank = sorted(gaps, key=lambda q: -q[0])
    top = rank[:nwords - 1]; rest = rank[nwords - 1:]
    lo_top = min(v for v, _ in top)
    hi_rest = max(v for v, _ in rest) if rest else 0.0
    if hi_rest > 0 and lo_top < WORD_SEP * hi_rest:
        return None, None, None
    thr = (lo_top + hi_rest) / 2
    cuts = sorted(i for _, i in top)
    bounds = [0] + cuts + [len(G)]
    clusters = [G[bounds[k]:bounds[k + 1]] for k in range(len(bounds) - 1)]
    return clusters, thr, (lo_top / hi_rest if hi_rest > 0 else float('inf'))


def is_ruled_residue(g, K):
    """True when a group is only ruled-line residue: nothing left once the
    linekill mask (same cleanup extract.py applies) is removed."""
    raw = g['mask']
    km = K[g['y']:g['y'] + g['h'], g['x']:g['x'] + g['w']]
    core = (raw & ~km).astype(np.uint8)
    n_, lb, st, _ = cv2.connectedComponentsWithStats(core, 8)
    big = [i for i in range(1, n_) if st[i, 4] >= 12]
    return len(big) == 0


def take_word(C, w, xh):
    """Return list of (char, group) for word w from ink groups C, or (None, reason)."""
    L = len(w)
    groups = [dict(g) for g in sorted(C, key=lambda q: q['x'])]
    budget = len(groups) - L
    two = sum(1 for ch in w if ch in TWO)
    if budget < 0:
        return None, "joined (%d groups < %d chars)" % (len(groups), L)
    if budget > two:
        return None, "extra pieces (%d groups, %d chars, %d dotted)" % (len(groups), L, two)
    smalls = sorted([g for g in groups if g['h'] <= SMALL_FRAC * xh], key=lambda q: q['x'] + q['w'] / 2)
    done = 0
    for s in smalls:
        if done == budget:
            break
        if s not in groups:
            continue
        cands = []
        for t in groups:
            if t is s:
                continue
            xov = min(s['x'] + s['w'], t['x'] + t['w']) - max(s['x'], t['x'])
            if xov < 0.3 * min(s['w'], t['w']):
                continue
            vgap = max(t['y'] - (s['y'] + s['h']), s['y'] - (t['y'] + t['h']))
            if vgap > MERGE_VGAP * xh:
                continue
            cands.append((vgap, t))
        if not cands:
            continue
        cands.sort(key=lambda q: q[0])
        if len(cands) > 1 and cands[1][0] - cands[0][0] < 2:
            return None, "ambiguous dot merge"
        t = cands[0][1]
        groups[groups.index(t)] = merge(t, s)
        groups.remove(s)
        done += 1
    if done != budget or len(groups) != L:
        return None, "could not reduce %d groups to %d chars" % (len(groups), L)
    # a glyph wider/taller than any real letter is two letters joined (or a
    # ruled-line strip): the count can still match by accident, so reject
    for g in groups:
        if g['w'] > MAX_W * xh or g['h'] > MAX_H * xh:
            return None, "oversize group w%.2f h%.2f x-height" % (g['w'] / xh, g['h'] / xh)
    groups.sort(key=lambda q: q['x'])
    return list(zip(w, groups)), "ok"


def main():
    ref = pickle.load(open(REF_PKL, 'rb'))
    ref_cap = {}
    for f in set(s['file'] for s in ref):
        caps = [s['base'] - s['top'] for s in ref if s['file'] == f and s['char'] in "BDEFHIKLMNPRTUVWXZ"]
        ref_cap[f] = float(np.median(caps))
    ref_xh = [s['base'] - s['top'] for s in ref if s['char'] in XH_CHARS]
    ref_xh = float(np.median(ref_xh))
    cap_alpha = float(np.median(list(ref_cap.values())))
    print("reference caps (alphabet photos):", {k: round(v, 2) for k, v in ref_cap.items()},
          "median %.2f, x-height %.2f" % (cap_alpha, ref_xh))

    photos = sorted(set(p[0] for p in PAGES))
    samples = []
    stats = Counter()
    for f in photos:
        im = load(f, ROT.get(f, 0))
        m = inkmask(im)
        K = linekill(im); LB = linebands(im)
        BS = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)[..., 2]
        _g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        NM = np.clip(_g.astype(np.float32) / np.maximum(cv2.medianBlur(_g, 61).astype(np.float32), 1) * 255, 0, 255)
        left_x1, right_x0, edges = page_bounds(im, m)
        print("\n%s: spine edges %s -> left x-range [%d,%d), right x-range [%d,%d)" % (
            f, edges, MARGIN, left_x1, right_x0, im.shape[1] - MARGIN))
        # pass 1: rows and ink groups for each page of this photo
        plan = []
        for pi, (pf, side, lines, skip) in enumerate(PAGES):
            if pf != f:
                continue
            x0, x1 = (MARGIN, left_x1) if side == "L" else (right_x0, im.shape[1] - MARGIN)
            tag = "%s %s" % (f, side)
            rs = [(a, b, int(m[a:b, x0:x1].sum())) for a, b in rows(m, x0, x1)]
            rs = [r for r in rs if r[2] >= MIN_INK]
            joined = []
            for r in rs:
                if joined and r[0] - joined[-1][1] <= ROW_JOIN_GAP:
                    p = joined[-1]; joined[-1] = (p[0], r[1], p[2] + r[2])
                else:
                    joined.append(r)
            if not joined:
                print(tag, "no rows"); continue
            H = float(np.median([b - a for a, b, _ in joined]))
            cands = [r for r in joined if (r[1] - r[0]) >= MIN_ROW_H * H]
            n_expect = skip + len(lines)
            keep, why = align_rows(cands, n_expect)
            print(tag, "usable rows %d (candidates %d), need %d: %s" % (len(cands), len(joined), n_expect, why))
            if keep is None:
                print(tag, "SKIPPED PAGE"); stats['pages_skipped'] += 1; continue
            keep = keep[skip:]
            for li, ((a, b, _), text) in enumerate(zip(keep, lines)):
                gs = line_groups(m, a, b, x0, x1)
                gs = [g for g in gs if not is_ruled_residue(g, K)]
                if gs:
                    mh = max(g['h'] for g in gs)
                    xh_row = float(np.median([g['h'] for g in gs if g['h'] >= 0.3 * mh]))
                    plan.append(dict(pi=pi, li=li, text=text, a=a, b=b, gs=gs, x0=x0, x1=x1, tag=tag, xh=xh_row))
        if not plan:
            continue
        # one x-height per photo (median over its rows); row-level estimates are
        # inflated by tall glyphs in some rows
        xh_photo = float(np.median([p['xh'] for p in plan]))
        print("%s: photo x-height %.1f px (row medians %s)" % (f, xh_photo, sorted(round(p['xh']) for p in plan)))
        # pass 2: words and characters
        for p in plan:
            pi, li, text, gs, tag = p['pi'], p['li'], p['text'], p['gs'], p['tag']
            xh = xh_photo
            rowid = 100 * pi + li
            words = text.split(" ")
            clusters, thr, sep = split_words(gs, len(words))
            if clusters is None:
                print("  %s line %d %r: word gaps not separable (%d words) -> row skipped" % (
                    tag, li, text, len(words)))
                stats['rows_skipped'] += 1; continue
            stats['rows_matched'] += 1
            print("  %s line %d %r: gap thr %s px, sep x%.2f" % (
                tag, li, text, "-" if thr is None else "%.1f" % thr, 0 if sep is None else sep))
            acc = []  # (char, group)
            for wi, (w, C) in enumerate(zip(words, clusters)):
                res, why = take_word(C, w, xh)
                if res is None:
                    stats['words_skipped'] += 1
                    print("     skip %r: %s" % (w, why))
                    continue
                stats['words_ok'] += 1
                print("     ok   %r" % w)
                acc += res
            if not acc:
                continue
            # baseline fit per row (extract.py method) over accepted non-descender items
            sit = [(g['x'] + g['w'] / 2, g['y'] + g['h']) for c, g in acc if c not in NOSIT]
            xs, ys = np.array(sit).T if len(sit) else (np.array([]), np.array([]))
            if len(sit) >= 4:
                k_, c0 = np.polyfit(xs, ys, 1)
                res_ = ys - (k_ * xs + c0); ok = abs(res_) < max(6, 2.5 * np.median(abs(res_)))
                if ok.sum() >= 4:
                    k_, c0 = np.polyfit(xs[ok], ys[ok], 1)
            else:
                k_, c0 = (0, np.median(ys))
            for c, g in acc:
                cx = g['x'] + g['w'] / 2; base = k_ * cx + c0
                km = K[g['y']:g['y'] + g['h'], g['x']:g['x'] + g['w']]
                raw = g['mask']; core = raw & ~km
                core = cv2.morphologyEx(core.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)) > 0
                cols = np.where(core.sum(0) >= 2)[0]
                cm = raw.copy()
                if len(cols):
                    inside = np.zeros(raw.shape[1], bool); inside[max(0, cols[0] - 2):cols[-1] + 3] = True
                    cm = raw & (~km | inside[None, :])
                n_, lb, st, _ = cv2.connectedComponentsWithStats(cm.astype(np.uint8), 8)
                cm = np.isin(lb, [i for i in range(1, n_) if st[i, 4] >= max(12, 0.01 * cm.sum())])
                ys_, xs_ = np.where(cm); g = dict(g)
                if len(ys_):
                    cm = cm[ys_.min():ys_.max() + 1, xs_.min():xs_.max() + 1]
                    g['y'] += ys_.min(); g['x'] += xs_.min(); g['h'], g['w'] = cm.shape
                samples.append(dict(
                    raw=raw, char=c, file=f, row=rowid, mask=cm,
                    line=LB[g['y']:g['y'] + g['h'], g['x']:g['x'] + g['w']].copy(),
                    bstar=BS[g['y']:g['y'] + g['h'], g['x']:g['x'] + g['w']].copy(),
                    norm=NM[g['y']:g['y'] + g['h'], g['x']:g['x'] + g['w']].copy(),
                    top=g['y'], bottom=g['y'] + g['h'], base=base, x=g['x'],
                    slope=float(k_), src="words"))

    # ---- caps: own photo's cap if it has alphabet rows, else scaled by x-height
    for f in set(s['file'] for s in samples):
        ss = [s for s in samples if s['file'] == f]
        xh_t = float(np.median([s['base'] - s['top'] for s in ss if s['char'] in XH_CHARS]))
        if f in ref_cap:
            ch = ref_cap[f]; how = "own alphabet cap"
        else:
            ch = cap_alpha * xh_t / ref_xh; how = "median alpha cap %.2f x (xh %.1f / %.1f)" % (cap_alpha, xh_t, ref_xh)
        for s in ss:
            s['cap'] = ch
        print("%s: cap %.2f px (%s); word x-height %.1f from %d x-height samples" % (
            f, ch, how, xh_t, sum(1 for s in ss if s['char'] in XH_CHARS)))

    pickle.dump(samples, open(OUT_PKL, 'wb'))
    cnt = Counter(s['char'] for s in samples)
    print("\nrows matched %d, rows skipped %d, pages skipped %d" % (
        stats['rows_matched'], stats['rows_skipped'], stats['pages_skipped']))
    print("words accepted %d, words skipped %d" % (stats['words_ok'], stats['words_skipped']))
    print("%d samples, %d chars" % (len(samples), len(cnt)))
    print("per char:", "  ".join("%s:%d" % (c, cnt[c]) for c in sorted(cnt)))
    draw_sheet(samples)


def draw_sheet(samples):
    s = sorted(samples, key=lambda x: (x['char'], x['file'], x['row']))
    CW, CH = 110, 150; cols = 16; n = len(s); R = -(-n // cols)
    im = Image.new('RGB', (cols * CW, R * CH), 'white'); d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 16)
    except OSError:
        f = ImageFont.load_default()
    for i, x in enumerate(s):
        r, c = divmod(i, cols); ox, oy = c * CW, r * CH
        sc = 60 / x['cap']; m = x['mask'].astype(np.uint8) * 255
        h, w = m.shape; nh, nw = max(1, int(h * sc)), max(1, int(w * sc))
        m = cv2.resize(m, (nw, nh), interpolation=cv2.INTER_AREA)
        by = oy + 100; top = int(by - (x['base'] - x['top']) * sc)
        d.line([ox + 2, by, ox + CW - 4, by], fill=(120, 170, 230))
        d.line([ox + 2, by - 60, ox + CW - 4, by - 60], fill=(220, 220, 220))
        px = ox + (CW - nw) // 2
        im.paste(Image.new('RGB', (nw, nh), (20, 20, 90)), (px, top), Image.fromarray(m))
        d.text((ox + 3, oy + 3), "%s %sr%d" % (x['char'], x['file'][4:8], x['row']), fill=(200, 0, 0), font=f)
        d.rectangle([ox, oy, ox + CW - 1, oy + CH - 1], outline=(230, 230, 230))
    im.save(OUT_SHEET)
    print("wrote", OUT_PKL, "and", OUT_SHEET, im.size)


if __name__ == "__main__":
    main()
