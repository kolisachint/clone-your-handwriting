import math

import cv2
import numpy as np

from complete import complete
from strokes import skeleton

H = W = 400
CAP, BASE, XH = 100, 300, 180
C = BASE - CAP
PEN = 14


def _mask(draw):
    img = np.zeros((H, W), np.uint8)
    draw(img)
    return img > 0


def _line(img, p, q):
    cv2.line(img, p, q, 255, PEN)  # (x, y) order


def _run(mask, kind):
    sk = skeleton(mask)
    return mask, complete(mask, sk, BASE, CAP, XH, kind)


def test_a_cap_A_right_leg_extended():
    def draw(img):
        _line(img, (200, 100), (110, 300))   # left leg (x, y)
        _line(img, (200, 100), (282, 255))   # right leg stops 45px short
        _line(img, (155, 200), (235, 200))   # crossbar
    big, (nb, nsk, rep) = _run(_mask(draw), "cap")

    right = nb.copy()
    right[:, :240] = False
    right[:250] = False
    ys = np.nonzero(right)[0]
    assert 296 <= ys.max() <= 302, ys.max()

    # left leg unchanged
    assert np.array_equal(nb[:, :160], big[:, :160])

    grown = (nb.sum() - big.sum()) / big.sum()
    assert 0 < grown < 0.12, grown
    assert any(r["target"] == "baseline" for r in rep)
    assert nsk.sum() > skeleton(big).sum()


def test_b_H_right_leg_extended_to_baseline():
    def draw(img):
        _line(img, (130, 100), (130, 300))   # left leg
        _line(img, (270, 100), (270, 285))   # right leg ends at 285
        _line(img, (130, 190), (270, 190))   # crossbar
    big, (nb, nsk, rep) = _run(_mask(draw), "cap")
    right = nb.copy()
    right[:, :200] = False
    ys = np.nonzero(right)[0]
    assert 296 <= ys.max() <= 302, ys.max()
    assert len(rep) == 1 and rep[0]["end"][1] > 200
    # left leg untouched
    assert np.array_equal(nb[:, :200], big[:, :200])


def test_c_correct_L_unchanged():
    def draw(img):
        _line(img, (150, 100), (150, 300))   # stem, top on cap, bottom on baseline
        _line(img, (150, 300), (260, 300))   # foot
    big, (nb, nsk, rep) = _run(_mask(draw), "cap")
    assert rep == []
    assert np.array_equal(nb, big)


def test_d_ring_unchanged():
    def draw(img):
        cv2.circle(img, (200, 200), 80, 255, PEN)
    big, (nb, nsk, rep) = _run(_mask(draw), "x")
    assert rep == []
    assert np.array_equal(nb, big)


def test_e_c_curl_not_extended():
    # arc from upper right, round the left side, lower end curls up and right
    cx, cy, rx, ry = 200, 190, 80, 80
    phis = np.radians(np.linspace(60, 285, 200))
    pts = [(int(round(cx + rx * math.cos(p))), int(round(cy - ry * math.sin(p))))
           for p in phis]

    def draw(img):
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, a, b, 255, PEN)
    big, (nb, nsk, rep) = _run(_mask(draw), "x")
    end = pts[-1]
    assert end[1] > 255 and end[1] < 285  # lower end sits low, around y=270
    assert rep == []
    assert np.array_equal(nb, big)
