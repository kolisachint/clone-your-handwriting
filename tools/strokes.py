"""Stroke-level cleanup and re-inking for glyph bitmaps.

All functions take/return bool masks (True = ink) at the working resolution.
"""
import numpy as np, cv2
from skimage.morphology import skeletonize

N8=[(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

def smooth(mask, up=4, sigma=0.9):
    m=cv2.resize(mask.astype(np.float32),None,fx=up,fy=up,interpolation=cv2.INTER_CUBIC)
    return cv2.GaussianBlur(m,(0,0),up*sigma)>0.45

def skeleton(mask):
    return skeletonize(mask)

def _nbrs(sk,y,x):
    H,W=sk.shape
    return [(y+dy,x+dx) for dy,dx in N8 if 0<=y+dy<H and 0<=x+dx<W and sk[y+dy,x+dx]]

def prune(sk, minlen):
    """remove skeleton branches that end freely and are shorter than minlen px
    (ink spurs: ruled-line stubs, pen flicks, blot tails). Main strokes stay."""
    sk=sk.copy()
    for _ in range(3):
        changed=False
        ys,xs=np.nonzero(sk)
        ends=[(y,x) for y,x in zip(ys,xs) if len(_nbrs(sk,y,x))==1]
        for e in ends:
            path=[e]; prev=None; cur=e
            while True:
                nb=[p for p in _nbrs(sk,*cur) if p!=prev and p not in path[-3:]]
                if len(nb)!=1 or len(path)>minlen: break
                prev,cur=cur,nb[0]
                if len(_nbrs(sk,*cur))>2: break
                path.append(cur)
            if len(path)<=minlen and len(_nbrs(sk,*cur))>2:
                for p in path: sk[p]=False
                changed=True
        if not changed: break
    return sk

def reconstruct(mask, sk, dist=None, cap=None):
    """medial-axis reconstruction: union of discs on skeleton with local radius.
    Keeps the writer's own stroke width; anything not covered (spurs) is dropped."""
    if dist is None: dist=cv2.distanceTransform(mask.astype(np.uint8),cv2.DIST_L2,5)
    out=np.zeros(mask.shape,np.uint8)
    ys,xs=np.nonzero(sk)
    for y,x in zip(ys,xs):
        r=dist[y,x]
        if cap: r=min(r,cap)
        cv2.circle(out,(int(x),int(y)),max(1,int(round(r))),1,-1)
    # skeletonize shortens each free end by ~one radius; give it back
    for y,x in zip(ys,xs):
        if len(_nbrs(sk,y,x))==1:
            nb=_nbrs(sk,y,x)[0]; dy,dx=y-nb[0],x-nb[1]
            r=dist[y,x] if not cap else min(dist[y,x],cap)
            for t in range(1,int(r)+1):
                yy,xx=int(y+dy*t),int(x+dx*t)
                if 0<=yy<mask.shape[0] and 0<=xx<mask.shape[1] and mask[yy,xx]:
                    cv2.circle(out,(xx,yy),max(1,int(round(r))),1,-1)
    return out>0

def restroke(sk, width):
    """draw the skeleton with a round pen of constant width (px)."""
    k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(max(1,int(width)),)*2)
    return cv2.dilate(sk.astype(np.uint8),k)>0

def stroke_width(mask, sk):
    d=cv2.distanceTransform(mask.astype(np.uint8),cv2.DIST_L2,5)
    v=d[sk]; return float(2*np.median(v)) if len(v) else 1.0

def clean_blobs(mask, sk, width):
    """cap the local radius so ink pools/blots don't render as fat spots."""
    return reconstruct(mask, sk, cap=width*0.75)
