"""Finish strokes the writer lifted early.

A free end that is heading down and stops short of the baseline (leg of A/H,
stem of t/4 ...) is run on to the baseline along its own direction. A free end
heading up and stopping short of the cap line (or ascender line) is run up to
it. Everything is drawn with the local stroke radius so the new ink matches the
writer's own thickness.

All masks are bool at the working resolution (y grows downward).
"""
import math

import cv2
import numpy as np

from strokes import _nbrs

COS40 = math.cos(math.radians(40))
MAX_BEND = math.radians(15)


def _walk(sk, e, maxlen):
    """walk back along the skeleton from free end e; stop at a junction or
    after maxlen pixels. Returns the list of pixels, e first."""
    path = [e]
    prev = None
    cur = e
    while len(path) < maxlen:
        nb = [p for p in _nbrs(sk, *cur) if p != prev and p not in path]
        if not nb:
            break
        prev, cur = cur, nb[0]
        path.append(cur)
        if len(_nbrs(sk, *cur)) > 2:  # junction: stop here
            break
    return path


def _blocked(work, own, yc, xc, r):
    """True if foreign ink (not in own) lies within 2px of a disc at (yc,xc)."""
    H, W = work.shape
    R = r + 2
    y0, y1 = max(0, yc - R), min(H, yc + R + 1)
    x0, x1 = max(0, xc - R), min(W, xc + R + 1)
    if y0 >= y1 or x0 >= x1:
        return False
    sub = work[y0:y1, x0:x1] & ~own[y0:y1, x0:x1]
    if not sub.any():
        return False
    yy, xx = np.nonzero(sub)
    d2 = (yy + y0 - yc) ** 2 + (xx + x0 - xc) ** 2
    return bool((d2 <= (r + 2) ** 2).any())


def _extend(work, d, target, bottom, C, gap):
    """run end d along its heading until its ink reaches target.
    Returns (ink mask, centreline mask, pixel count) or None."""
    H, W = work.shape
    ey, ex = d["e"]
    r = d["r"]
    sgn = 1.0 if d["uy"] > 0 else -1.0
    alpha0 = math.atan2(d["ux"], abs(d["uy"]))
    bend = math.copysign(min(abs(alpha0), MAX_BEND), alpha0)

    # the stroke's own pixels near the tip are not obstacles
    own = np.zeros((H, W), np.uint8)
    for py, px in d["path"]:
        own[py, px] = 1
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * (r + 2) + 1,) * 2)
    own = cv2.dilate(own, k) > 0

    est = max(abs(gap), 1.0)
    max_travel = 0.30 * C
    y, x = float(ey), float(ex)
    travel = 0.0
    step = 0.5
    pts = []
    while travel < max_travel:
        frac = min(1.0, travel / est)
        alpha = alpha0 - bend * frac          # bend towards vertical
        dy = sgn * math.cos(alpha)
        dx = math.sin(alpha)
        ny, nx = y + step * dy, x + step * dx
        yc, xc = int(round(ny)), int(round(nx))
        if not (0 <= yc < H and 0 <= xc < W):
            break
        if _blocked(work, own, yc, xc, r):
            break
        y, x = ny, nx
        travel += step
        pts.append((yc, xc))
        if bottom and yc + r >= target:
            break
        if not bottom and yc - r <= target:
            break

    if not pts:
        return None
    ink = np.zeros((H, W), np.uint8)
    line = np.zeros((H, W), np.uint8)
    chain = [(ey, ex)] + pts
    for yc, xc in pts:
        cv2.circle(ink, (xc, yc), r, 1, -1)
    for (ay, ax), (by, bx) in zip(chain, chain[1:]):
        cv2.line(line, (ax, ay), (bx, by), 1, 1)
    ink = ink > 0
    added = int((ink & ~work).sum())
    if added == 0:
        return None
    return ink, line > 0, added


def complete(big, sk, baseline_row, cap_row, xh_row, kind):
    """returns (new_big, new_sk, report). report: list of
    {end:(y,x), target:"baseline"|"cap", added_px:int}."""
    big = np.asarray(big, bool)
    sk = np.asarray(sk, bool)
    work = big.copy()
    new_sk = sk.copy()
    report = []
    C = float(baseline_row - cap_row)
    if C <= 0 or kind not in ("cap", "x", "asc", "desc", "other"):
        return work, new_sk, report

    dist = cv2.distanceTransform(big.astype(np.uint8), cv2.DIST_L2, 5)
    L = max(4, int(round(0.12 * C)))

    ends = []
    for y, x in zip(*np.nonzero(sk)):
        if len(_nbrs(sk, y, x)) != 1:
            continue
        path = _walk(sk, (int(y), int(x)), max(L + 1, int(round(C))))
        if len(path) < 4:
            continue
        k = min(L, len(path) - 1)
        ty = path[0][0] - path[k][0]
        tx = path[0][1] - path[k][1]
        n = math.hypot(ty, tx)
        if n == 0:
            continue
        ends.append({
            "e": path[0],
            "path": path,
            "uy": ty / n,
            "ux": tx / n,
            "r": max(2, int(round(float(dist[path[0]])))),
        })

    def down(d):
        return d["uy"] >= COS40

    def up(d):
        return -d["uy"] >= COS40

    def reaches_base(d):
        return d["e"][0] + d["r"] >= baseline_row - 0.02 * C

    def reaches_cap(d, T):
        return d["e"][0] - d["r"] <= T + 0.02 * C

    jobs = []  # (d, target_row, bottom, gap, label)

    # bottom completion
    if kind in ("cap", "x", "asc"):
        for d in ends:
            if not down(d):
                continue
            ey = d["e"][0]
            if reaches_base(d):          # already lands on the baseline
                continue
            # must be the lowest point of its stroke
            if ey < max(p[0] for p in d["path"]) - 1:
                continue
            gap = baseline_row - ey
            if not (0.04 * C <= gap <= 0.30 * C):
                continue
            others = [o for o in ends if o is not d]
            if any(reaches_base(o) for o in others):
                leg = any(down(o) and reaches_base(o) for o in others)
                if not leg:
                    continue
            jobs.append((d, baseline_row, True, gap, "baseline"))

    # top completion
    if kind in ("cap", "asc"):
        for d in ends:
            if not up(d):
                continue
            ey = d["e"][0]
            others = [o for o in ends if o is not d and up(o)]
            if kind == "asc" and others:
                T = float(np.median([o["e"][0] - o["r"] for o in others]))
            else:
                T = float(cap_row)
            if reaches_cap(d, T):        # already reaches the top line
                continue
            # must be the topmost point of its stroke
            if ey > min(p[0] for p in d["path"]) + 1:
                continue
            gap = ey - T
            if not (0.04 * C <= gap <= 0.20 * C):
                continue
            jobs.append((d, T, False, gap, "cap"))

    for d, target, bottom, gap, label in jobs:
        res = _extend(work, d, target, bottom, C, gap)
        if res is None:
            continue
        ink, line, added = res
        work |= ink
        new_sk |= line
        report.append({"end": (int(d["e"][0]), int(d["e"][1])),
                       "target": label, "added_px": added})

    return work, new_sk, report
