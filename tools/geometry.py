"""Geometry helpers for handwriting letter samples: deskew, slant, shear.

Conventions
-----------
* Image coordinates: rows (y) grow downwards, columns (x) grow rightwards.
* Slope is dy/dx of the writing baseline on the page (positive = row goes
  down to the right).
* Slant is in degrees, positive = stroke leans right (top to the right).
* cv2.getRotationMatrix2D angle: +theta maps direction (1, s) to horizontal
  when theta = atan(s), so deskew passes degrees(atan(slope)) to cv2.
"""

import math
import pickle

import cv2
import numpy as np
from skimage.morphology import skeletonize


# ---------------------------------------------------------------- deskew

def deskew(sample):
    """Return a new sample with the writing baseline made horizontal.

    The input dict is not mutated. mask/line/bstar/norm are rotated about the
    point (crop centre column, baseline row) by atan(slope), then re-cropped
    tightly to the rotated mask ink. top/bottom/x are updated to the new crop
    frame; base is a page-row value and stays unchanged (the rotation pivots
    on the baseline, so the baseline keeps its page row at the centre column).
    All other keys are copied as-is (including slope).
    """
    out = dict(sample)
    mask = np.asarray(sample["mask"], dtype=bool)
    h, w = mask.shape
    slope = float(sample["slope"])
    top = int(sample["top"])
    x0 = int(sample["x"])
    base_local = float(sample["base"]) - top

    pad = int(math.ceil(math.hypot(h, w))) + 2
    ang = math.degrees(math.atan(slope))
    cx, cy = w / 2.0 + pad, base_local + pad
    M = cv2.getRotationMatrix2D((cx, cy), ang, 1.0)
    out_size = (w + 2 * pad, h + 2 * pad)

    def rot_bool(a):
        p = np.pad(np.asarray(a, dtype=bool).astype(np.uint8), pad, constant_values=0)
        r = cv2.warpAffine(p, M, out_size, flags=cv2.INTER_NEAREST,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return r > 0

    def rot_lin(a, fill):
        a = np.asarray(a)
        p = np.pad(a.astype(np.float32), pad, constant_values=fill)
        r = cv2.warpAffine(p, M, out_size, flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=float(fill))
        if a.dtype == np.uint8:
            r = np.clip(np.round(r), 0, 255).astype(np.uint8)
        else:
            r = r.astype(a.dtype)
        return r

    rm = rot_bool(mask)
    rl = rot_bool(sample["line"])
    rb = rot_lin(sample["bstar"], 128)
    rn = rot_lin(sample["norm"], 255)

    rows = np.flatnonzero(rm.any(axis=1))
    cols = np.flatnonzero(rm.any(axis=0))
    if rows.size == 0:  # no ink: nothing to re-crop
        out.update(mask=mask.copy(), line=np.asarray(sample["line"], bool).copy(),
                   bstar=np.asarray(sample["bstar"]).copy(),
                   norm=np.asarray(sample["norm"]).copy())
        return out

    r0, r1 = int(rows[0]), int(rows[-1]) + 1
    c0, c1 = int(cols[0]), int(cols[-1]) + 1
    new_h = r1 - r0
    out["mask"] = rm[r0:r1, c0:c1].copy()
    out["line"] = rl[r0:r1, c0:c1].copy()
    out["bstar"] = rb[r0:r1, c0:c1].copy()
    out["norm"] = rn[r0:r1, c0:c1].copy()
    out["top"] = top + r0 - pad
    out["bottom"] = out["top"] + new_h
    out["x"] = x0 + c0 - pad
    out["base"] = float(sample["base"])
    return out


# ---------------------------------------------------------------- slant

def slant(mask, max_dev_deg=35.0, min_linearity=0.8, win=7):
    """Dominant lean of near-vertical strokes, in degrees (+ = leans right).

    Skeletonise, then for every skeleton pixel fit a PCA line to the skeleton
    pixels in a win x win neighbourhood. Keep pixels whose local direction is
    within max_dev_deg of vertical and whose neighbourhood is linear enough
    (drops junctions/blobs). Each kept pixel has weight 1 (= stroke length).
    Returns the weighted median angle, or 0.0 if there are no such strokes.
    """
    m = np.asarray(mask, dtype=bool)
    if not m.any():
        return 0.0
    sk = skeletonize(m).astype(np.float64)
    if sk.sum() < 3:
        return 0.0

    h, w = sk.shape
    Y, X = np.mgrid[0:h, 0:w].astype(np.float64)
    ksize = (win, win)

    def box(a):
        return cv2.boxFilter(a, cv2.CV_64F, ksize, normalize=False,
                             borderType=cv2.BORDER_CONSTANT)

    n = box(sk)
    n_safe = np.maximum(n, 1.0)
    mx = box(sk * X) / n_safe
    my = box(sk * Y) / n_safe
    cxx = box(sk * X * X) / n_safe - mx * mx
    cyy = box(sk * Y * Y) / n_safe - my * my
    cxy = box(sk * X * Y) / n_safe - mx * my

    tr = cxx + cyy
    disc = np.sqrt(((cxx - cyy) / 2.0) ** 2 + cxy ** 2)
    l1 = tr / 2.0 + disc
    l2 = tr / 2.0 - disc
    lin = (l1 - l2) / (l1 + l2 + 1e-12)

    theta = 0.5 * np.arctan2(2.0 * cxy, cxx - cyy)  # major axis, (x, y)
    dx, dy = np.cos(theta), np.sin(theta)
    flip = dy > 0  # orient so the direction points up (dy < 0)
    dx = np.where(flip, -dx, dx)
    dy = np.where(flip, -dy, dy)
    ang = np.degrees(np.arctan2(dx, -dy))  # + = top to the right

    keep = (sk > 0) & (n >= 5) & (lin >= min_linearity) & (np.abs(ang) <= max_dev_deg)
    if not keep.any():
        return 0.0
    a = ang[keep]
    order = np.argsort(a)
    a = a[order]
    cum = np.cumsum(np.ones_like(a))  # weight 1 per skeleton pixel
    idx = int(np.searchsorted(cum, cum[-1] / 2.0))
    return float(a[min(idx, a.size - 1)])


# ---------------------------------------------------------------- shear

def shear(arr, deg, baseline_row, fill=0):
    """Horizontal shear by -deg about baseline_row, widening the canvas.

    A stroke leaning +deg (top to the right) becomes upright. Row y moves by
    tan(deg) * (y - baseline_row) columns. Columns are added on the left as
    needed; the number added is returned as x_shift. Works for bool arrays
    (nearest) and float / uint8 arrays (linear).

    Returns (sheared, x_shift).
    """
    a = np.asarray(arr)
    is_bool = a.dtype == bool
    if is_bool:
        src = a.astype(np.uint8)
        flags = cv2.INTER_NEAREST
        border = 1 if fill else 0
    else:
        if a.dtype == np.uint8:
            src = a
        else:
            src = a.astype(np.float32)
        flags = cv2.INTER_LINEAR
        border = float(fill)

    h, w = a.shape
    k = math.tan(math.radians(deg))
    shifts = k * (np.arange(h, dtype=np.float64) - float(baseline_row))
    x_shift = int(math.ceil(max(0.0, -float(shifts.min()))))
    right = int(math.ceil(max(0.0, float(shifts.max()))))
    new_w = w + x_shift + right

    M = np.array([[1.0, k, x_shift - k * float(baseline_row)],
                  [0.0, 1.0, 0.0]], dtype=np.float64)
    dst = cv2.warpAffine(src, M, (new_w, h), flags=flags,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=border)
    if is_bool:
        dst = dst > 0
    elif a.dtype == np.uint8:
        dst = np.clip(np.round(dst), 0, 255).astype(np.uint8)
    else:
        dst = dst.astype(a.dtype)
    return dst, x_shift


# ---------------------------------------------------------------- report

def _report(path="/tmp/hf_samples.pkl"):
    with open(path, "rb") as f:
        samples = pickle.load(f)
    raw = np.array([slant(s["mask"]) for s in samples])
    des = np.array([slant(deskew(s)["mask"]) for s in samples])
    for name, v in (("raw", raw), ("deskewed", des)):
        print(f"slant {name}: n={v.size} median={np.median(v):.2f} "
              f"p10={np.percentile(v, 10):.2f} p90={np.percentile(v, 90):.2f} "
              f"deg")


if __name__ == "__main__":
    _report()
