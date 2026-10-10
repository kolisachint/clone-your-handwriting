"""Remove ink that is not part of the letter.

Three kinds of stray ink were found reviewing v0.1:
  1. ruled-line stubs left on either side of a stroke (H, 4, k, A, 1, M)
  2. ink blots / pen-pressure pools (A apex, *, u, d)
  3. pen lift flicks at stroke ends
Spurs are removed on the skeleton (short free-ending branches that cross a
ruled line, or are much thinner than the stroke); blots are removed by capping
the local stroke radius.
"""
import numpy as np, cv2
from strokes import skeleton, _nbrs, reconstruct, stroke_width

def _branches(sk):
    ys,xs=np.nonzero(sk)
    ends=[(y,x) for y,x in zip(ys,xs) if len(_nbrs(sk,y,x))==1]
    out=[]
    for e in ends:
        path=[e]; prev=None; cur=e
        while True:
            nb=[p for p in _nbrs(sk,*cur) if p!=prev and p not in path]
            if len(nb)!=1: break
            prev,cur=cur,nb[0]
            if len(_nbrs(sk,*cur))>2: break
            path.append(cur)
        out.append((path, len(_nbrs(sk,*cur))>2))
    return out

PEN_B=108    # Lab b* of the blue pen (median ~99)
LINE_B=114   # ruled lines are paler grey-blue (median ~122)

def remove_spurs(big, linemask_big, bstar_big, cap_px, up, nm=None):
    sk=skeleton(big)
    pen=float(np.percentile(nm[sk],30)) if (nm is not None and sk.any()) else None
    w=stroke_width(big, sk)
    for _ in range(3):
        changed=False
        for path,joins in _branches(sk):
            if not joins: continue
            L=len(path); ys=np.array([p[0] for p in path]); xs=np.array([p[1] for p in path])
            col=float(np.median(bstar_big[ys,xs])) if bstar_big is not None else 0
            online=linemask_big[ys,xs].mean()>0.5 if linemask_big is not None else False
            # line residue: lies on a ruled line and is line-coloured, not pen-coloured
            residue=online and col>LINE_B and L<0.15*cap_px*up
            tiny=L<0.04*cap_px*up
            # short horizontal nub sitting on a ruled line = line stub glued to the stroke
            horiz=(np.ptp(xs)+1)>2.0*(np.ptp(ys)+1)
            # ruled-line mask is only approximate near strokes, so also accept
            # a nub that is merely close to a line row
            near=linemask_big is not None and cv2.dilate(linemask_big.astype(np.uint8),np.ones((15,1)))[ys,xs].mean()>0.3
            nub=(online or near) and horiz and L<0.08*cap_px*up
            pale=True if pen is None else float(np.median(nm[ys,xs]))>max(50,1.35*pen)
            if (residue or nub) and not pale: residue=nub=False
            # pale stub glued to a stroke along a ruled line (any direction; curls too)
            if pen is not None and pale and online and L<0.15*cap_px*up: residue=True
            if residue or tiny or nub:
                sk[ys,xs]=False; changed=True
        if not changed: break
    return sk, w

def clean(mask, linemask, cap_px, up=4, bstar=None, norm=None):
    """mask/linemask/bstar at source resolution -> cleaned mask at up x resolution."""
    m=np.pad(mask,4).astype(np.float32)
    big=cv2.GaussianBlur(cv2.resize(m,None,fx=up,fy=up,interpolation=cv2.INTER_CUBIC),(0,0),up*0.9)>0.45
    lm=bs=None
    if linemask is not None:
        lm=cv2.resize(np.pad(linemask,4).astype(np.uint8),None,fx=up,fy=up,interpolation=cv2.INTER_NEAREST)>0
    if bstar is not None:
        bs=cv2.resize(np.pad(bstar,4,constant_values=128).astype(np.float32),None,fx=up,fy=up,interpolation=cv2.INTER_LINEAR)
    nm=None
    if norm is not None:
        nm=cv2.resize(np.pad(norm,4,constant_values=255).astype(np.float32),None,fx=up,fy=up)
    sk,w=remove_spurs(big, lm, bs, cap_px, up, nm)
    sk=remove_line_bridges(sk, lm, nm, cap_px, up)
    # bridges removed -> new free ends may appear; prune those once more
    sk,_=remove_spurs(reconstruct(big,sk), lm, bs, cap_px, up) if False else (sk,w)
    n,lab,st,_=cv2.connectedComponentsWithStats(sk.astype(np.uint8),8)
    pen=float(np.median(nm[sk])) if (nm is not None and sk.any()) else 0
    keep=[]
    for i in range(1,n):
        sel=lab==i
        small=st[i,4]<0.06*cap_px*up
        pale=nm is not None and float(np.median(nm[sel]))>max(55,1.5*pen)
        if not (small and pale): keep.append(i)
    sk=np.isin(lab,keep)
    # radius cap: blots everywhere at 0.65w; where a ruled line crosses, the
    # line widens the stroke, so cap at the stroke's own half-width there
    dist=cv2.distanceTransform(big.astype(np.uint8),cv2.DIST_L2,5)
    lim=np.full(dist.shape,w*0.65,np.float32)
    if lm is not None: lim[cv2.dilate(lm.astype(np.uint8),np.ones((5,5)))>0]=w*0.5
    out=reconstruct(big, sk, dist=np.minimum(dist,lim))
    out=cv2.GaussianBlur(out.astype(np.float32),(0,0),up*0.5)>0.5
    return out, sk, w

def _segments(sk):
    """all skeleton segments between nodes (junctions/ends) as pixel lists."""
    H,W=sk.shape; deg=np.zeros(sk.shape,np.int32)
    ys,xs=np.nonzero(sk)
    for y,x in zip(ys,xs): deg[y,x]=len(_nbrs(sk,y,x))
    node=(deg!=2)&sk
    seen=np.zeros(sk.shape,bool); segs=[]
    for y,x in zip(*np.nonzero(node)):
        for n in _nbrs(sk,y,x):
            if seen[n] or node[n]:
                continue
            path=[n]; prev=(y,x); cur=n; seen[n]=True
            while not node[cur]:
                nb=[p for p in _nbrs(sk,*cur) if p!=prev and not seen[p] or (node[p] and p!=prev and p!=(y,x))]
                nb=[p for p in nb if p!=prev]
                if not nb: break
                prev,cur=cur,nb[0]
                if node[cur]: break
                seen[cur]=True; path.append(cur)
            segs.append(path)
    return segs

def remove_line_bridges(sk, lm, nm, cap_px, up):
    """drop ruled-line ink fused into a letter (a line through the bowl of o,
    across l, beside H). Such pieces sit on a ruled line, run horizontally, and
    are clearly paler than the pen strokes of the same letter. Real crossbars
    (H, 4, A) are pen-dark and stay."""
    if lm is None or nm is None: return sk
    pen=float(np.percentile(nm[sk],30)) if sk.any() else 40
    deg=np.zeros(sk.shape,np.int32)
    for y,x in zip(*np.nonzero(sk)): deg[y,x]=len(_nbrs(sk,y,x))
    for path in _segments(sk):
        if len(path)<4: continue
        ys=np.array([p[0] for p in path]); xs=np.array([p[1] for p in path])
        # only junction-to-junction pieces; free ends are handled by remove_spurs
        tips=[q for p in (path[0],path[-1]) for q in _nbrs(sk,*p) if q not in path]
        if any(deg[q]==1 for q in tips) or any(deg[p]==1 for p in path): continue
        horiz=(np.ptp(xs)+1)>2.5*(np.ptp(ys)+1)
        tone=float(np.median(nm[ys,xs]))
        # pen strokes only ride a ruled line briefly; long pale horizontal = line
        if horiz and lm[ys,xs].mean()>0.6 and tone>max(55,1.4*pen) and len(path)<0.25*cap_px*up:
            sk[ys,xs]=False
    return sk
