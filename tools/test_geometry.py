import math
import os
import pickle

import cv2
import numpy as np
import pytest

from geometry import deskew, shear, slant

SAMPLES = "/tmp/hf_samples.pkl"


def _pca_angle_deg(mask):
    ys, xs = np.nonzero(mask)
    pts = np.stack([xs, ys], 1).astype(np.float64)
    pts -= pts.mean(0)
    cov = pts.T @ pts / len(pts)
    vals, vecs = np.linalg.eigh(cov)
    vx, vy = vecs[:, np.argmax(vals)]
    if vx < 0:
        vx, vy = -vx, -vy
    return math.degrees(math.atan2(vy, vx))  # + = row goes down to the right


def _sample(mask, base, slope, top=0, x=0):
    h, w = mask.shape
    return dict(char="L", mask=mask, line=np.zeros_like(mask),
                bstar=np.full(mask.shape, 128, np.uint8),
                norm=np.full(mask.shape, 255, np.float32),
                top=top, bottom=top + h, x=x, base=base, slope=slope, cap=50.0)


def _bar(h=240, w=240, x0=100, y0=40, y1=200, bw=20):
    m = np.zeros((h, w), bool)
    m[y0:y1, x0:x0 + bw] = True
    return m


def _lean(mask, deg, base):
    """Lean the mask right by deg about row base (test-side, independent of shear())."""
    t = -math.tan(math.radians(deg))  # x' = x + t*(y - base): top moves right
    M = np.array([[1, t, -t * base], [0, 1, 0]], np.float64)
    out = cv2.warpAffine(mask.astype(np.float32), M, (mask.shape[1], mask.shape[0]),
                         flags=cv2.INTER_LINEAR)
    return out > 0.5


# (a) deskew flattens the foot of an L -------------------------------------

def test_deskew_flattens_foot():
    h, w = 240, 240
    canvas = np.zeros((h, w), np.float32)
    canvas[40:200, 100:120] = 1       # bar
    canvas[180:200, 100:180] = 1      # foot, bottom edge at row 200
    base = 200.0
    # cv2 angle -3 about (110, 200) gives a baseline with slope +tan(3 deg)
    M = cv2.getRotationMatrix2D((110.0, base), -3.0, 1.0)
    tilted = cv2.warpAffine(canvas, M, (w, h), flags=cv2.INTER_LINEAR) > 0.5
    slope = math.tan(math.radians(3.0))
    s = _sample(tilted, base=base, slope=slope)

    before = _pca_angle_deg(_foot_pixels(tilted))
    out = deskew(s)
    after = _pca_angle_deg(_foot_pixels(out["mask"]))
    assert abs(before - 3.0) < 1.0, before
    assert abs(after) < 0.5, after
    # input must not be mutated
    assert s["mask"] is tilted and s["top"] == 0 and s["x"] == 0


def _foot_pixels(mask):
    """Ink of the foot: columns that are only ~20 px tall (the bar is ~160 px),
    keeping the 20 rows above each column's lowest ink pixel."""
    fm = np.zeros_like(mask)
    for c in range(mask.shape[1]):
        rows = np.flatnonzero(mask[:, c])
        if rows.size == 0 or rows[-1] - rows[0] > 30:
            continue
        lo = rows[-1]
        fm[lo - 19: lo + 1, c] = mask[lo - 19: lo + 1, c]
    return fm


# (b) slant() ----------------------------------------------------------------

def test_slant_leaning_and_upright():
    lean12 = _lean(_bar(), 12.0, base=200.0)
    assert abs(slant(lean12) - 12.0) <= 3.0, slant(lean12)
    assert abs(slant(_bar())) <= 3.0, slant(_bar())
    assert slant(np.zeros((20, 20), bool)) == 0.0


# (c) shear by measured slant straightens it ---------------------------------

def test_shear_straightens():
    lean = _lean(_bar(), 12.0, base=200.0)
    measured = slant(lean)
    sheared, x_shift = shear(lean, measured, baseline_row=200.0)
    assert x_shift > 0
    assert abs(slant(sheared)) <= 3.0, slant(sheared)
    assert sheared.dtype == bool


def test_shear_float_and_bool_dtypes():
    m = _bar()
    f = m.astype(np.float32)
    sf, xs_f = shear(f, 10.0, baseline_row=200)
    sb, xs_b = shear(m, 10.0, baseline_row=200)
    assert sf.dtype == np.float32 and sb.dtype == bool
    assert xs_f == xs_b
    assert sf.shape == sb.shape
    assert abs(sf.sum() - m.sum()) < 0.02 * m.sum() + 1  # ink conserved


# (d) real samples -----------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(SAMPLES), reason="no samples pickle")
def test_deskew_all_real_samples():
    with open(SAMPLES, "rb") as f:
        samples = pickle.load(f)
    assert len(samples) > 0
    for s in samples:
        before = int(np.asarray(s["mask"]).sum())
        out = deskew(s)
        after = int(out["mask"].sum())
        assert out["mask"].shape == out["line"].shape == out["bstar"].shape == out["norm"].shape
        assert out["bottom"] - out["top"] == out["mask"].shape[0]
        assert out["base"] == s["base"]  # page row unchanged by design
        assert out["slope"] == s["slope"]
        assert abs(after - before) / before < 0.15, (s["char"], before, after)


@pytest.mark.skipif(not os.path.exists(SAMPLES), reason="no samples pickle")
def test_slant_distribution_real_samples():
    with open(SAMPLES, "rb") as f:
        samples = pickle.load(f)
    vals = np.array([slant(s["mask"]) for s in samples])
    print(f"\nslant raw: n={vals.size} median={np.median(vals):.2f} "
          f"p10={np.percentile(vals, 10):.2f} p90={np.percentile(vals, 90):.2f}")
    assert np.all(np.abs(vals) <= 35.0)


if __name__ == "__main__":
    import geometry
    geometry._report(SAMPLES)
