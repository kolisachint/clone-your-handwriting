import cv2,numpy as np
from seg import inkmask, rows
def line_groups(mask, y0, y1, x0, x1, pad=40, gap=4):
    """components of ink whose centroid falls in band y0..y1, merged when x-overlapping."""
    Y0=max(0,y0-pad); Y1=min(mask.shape[0],y1+pad)
    sub=mask[Y0:Y1,x0:x1].astype(np.uint8)
    n,lab,st,cen=cv2.connectedComponentsWithStats(sub,8)
    comps=[]
    for i in range(1,n):
        x,y,w,h,a=st[i]; cy=cen[i][1]+Y0
        if a<15: continue
        if not (y0-5<=cy<=y1+5): continue
        comps.append([x,x+w,y,y+h,[i]])
    comps.sort()
    groups=[]
    for c in comps:
        if groups and c[0] < groups[-1][1]-gap and (min(c[1],groups[-1][1])-c[0]) > 0.3*min(c[1]-c[0],groups[-1][1]-groups[-1][0]):
            g=groups[-1]; g[1]=max(g[1],c[1]); g[2]=min(g[2],c[2]); g[3]=max(g[3],c[3]); g[4]+=c[4]
        else: groups.append(c)
    out=[]
    for g in groups:
        m=np.isin(lab,g[4])[g[2]:g[3],g[0]:g[1]]
        out.append(dict(x=g[0]+x0,y=g[2]+Y0,w=g[1]-g[0],h=g[3]-g[2],mask=m))
    return out
def draw(im, groups, labels, path):
    v=im.copy()
    for i,g in enumerate(groups):
        cv2.rectangle(v,(g['x'],g['y']),(g['x']+g['w'],g['y']+g['h']),(0,0,255),2)
        cv2.putText(v,labels[i] if i<len(labels) else '?',(g['x'],g['y']-4),cv2.FONT_HERSHEY_SIMPLEX,1.0,(0,140,0),2)
    cv2.imwrite(path,v)
