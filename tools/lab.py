import cv2,numpy as np
from seg import inkmask, rows
from groups import line_groups
def fit(groups, n):
    gs=[g for g in groups]
    if gs:
        med=np.median([g['mask'].sum() for g in gs])
        while len(gs)>n:
            # drop tiny junk first, else merge closest neighbours
            small=[i for i,g in enumerate(gs) if g['mask'].sum()<0.12*med]
            if small: gs.pop(small[0]); continue
            gaps=[gs[i+1]['x']-(gs[i]['x']+gs[i]['w']) for i in range(len(gs)-1)]
            i=int(np.argmin(gaps)); gs[i:i+2]=[merge(gs[i],gs[i+1])]
    return gs
def merge(a,b):
    x=min(a['x'],b['x']); y=min(a['y'],b['y']); X=max(a['x']+a['w'],b['x']+b['w']); Y=max(a['y']+a['h'],b['y']+b['h'])
    m=np.zeros((Y-y,X-x),bool)
    for g in (a,b): m[g['y']-y:g['y']-y+g['h'], g['x']-x:g['x']-x+g['w']] |= g['mask']
    return dict(x=x,y=y,w=X-x,h=Y-y,mask=m)
def split(g, k):
    """split one group into k pieces at the lowest-ink columns."""
    prof=g['mask'].sum(0).astype(float); w=len(prof); cuts=[]
    for j in range(1,k):
        c=int(w*j/k); lo,hi=max(1,c-w//(3*k)),min(w-1,c+w//(3*k))
        cuts.append(lo+int(np.argmin(prof[lo:hi])))
    out=[];xs=[0]+cuts+[w]
    for a,b in zip(xs,xs[1:]):
        m=g['mask'][:,a:b]; ys=np.where(m.any(1))[0]
        out.append(dict(x=g['x']+a,y=g['y']+ys[0],w=b-a,h=ys[-1]-ys[0]+1,mask=m[ys[0]:ys[-1]+1]))
    return out
def label_row(mask,y0,y1,x0,x1,text,splits=None,drop=()):
    gs=line_groups(mask,y0,y1,x0,x1)
    gs=[g for i,g in enumerate(gs) if i not in drop]
    if splits:
        for i,k in sorted(splits.items(),reverse=True): gs[i:i+1]=split(gs[i],k)
    gs=fit(gs,len(text))
    if len(gs)!=len(text): return []
    return [(c,g) for c,g in zip(text,gs) if c!=' ']
