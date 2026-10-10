import cv2,numpy as np,json,os
from PIL import Image
from seg import inkmask, rows, linekill, linebands
from groups import line_groups
from lab import merge, split
from specs import SPECS
SRC=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","handwriting","2026-10-10")
DESC=set("gjpqy,;Q")
NOSIT=DESC|set("'\"-~^=*")
def load(f,rot):
    im=Image.open(os.path.join(SRC,f)).convert("RGB")
    if rot: im=im.rotate(rot,expand=True)
    return cv2.cvtColor(np.array(im),cv2.COLOR_RGB2BGR)
def parse(spec, gs):
    out=[];i=0
    for tok in spec.split():
        if tok.startswith("_"):
            i+=int(tok[1:] or 1); continue
        if len(tok)>2 and tok[0]=="{" and tok[-1]=="}":
            cs=tok[1:-1]; out+=list(zip(cs,split(gs[i],len(cs)))); i+=1; continue
        n=1
        if ":" in tok[1:]:
            c,n=tok.rsplit(":",1); n=int(n)
        else: c=tok
        g=gs[i]
        for k in range(1,n): g=merge(g,gs[i+k])
        out.append((c,g)); i+=n
    assert i==len(gs), (spec,i,len(gs))
    return out
samples=[]
for f,x0,x1,rot,rowspec in SPECS:
    im=load(f,rot); m=inkmask(im); rs=rows(m,x0,x1); K=linekill(im); LB=linebands(im); BS=cv2.cvtColor(im,cv2.COLOR_BGR2LAB)[...,2]; _g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY); NM=np.clip(_g.astype(np.float32)/np.maximum(cv2.medianBlur(_g,61).astype(np.float32),1)*255,0,255)
    for r,spec in rowspec.items():
        a,b=rs[r]; gs=line_groups(m,a,b,x0,x1)
        items=parse(spec,gs)
        sit=[(g['x']+g['w']/2,g['y']+g['h']) for c,g in items if c not in NOSIT]
        xs,ys=np.array(sit).T
        k,c0=(np.polyfit(xs,ys,1) if len(sit)>=4 else (0,np.median(ys)))
        res=ys-(k*xs+c0); ok=abs(res)<max(6,2.5*np.median(abs(res)))
        if ok.sum()>=4: k,c0=np.polyfit(xs[ok],ys[ok],1)
        for c,g in items:
            cx=g['x']+g['w']/2; base=k*cx+c0
            km=K[g['y']:g['y']+g['h'],g['x']:g['x']+g['w']]
            raw=g['mask']; core=raw&~km
            core=cv2.morphologyEx(core.astype(np.uint8),cv2.MORPH_OPEN,np.ones((2,2),np.uint8))>0
            cols=np.where(core.sum(0)>=2)[0]
            cm=raw.copy()
            if len(cols):
                inside=np.zeros(raw.shape[1],bool); inside[max(0,cols[0]-2):cols[-1]+3]=True
                cm=raw&(~km|inside[None,:])
            n_,lb,st,_=cv2.connectedComponentsWithStats(cm.astype(np.uint8),8)
            cm=np.isin(lb,[i for i in range(1,n_) if st[i,4]>=max(12,0.01*cm.sum())])
            ys_,xs_=np.where(cm); g=dict(g); 
            if len(ys_):
                cm=cm[ys_.min():ys_.max()+1,xs_.min():xs_.max()+1]; g['y']+=ys_.min(); g['x']+=xs_.min(); g['h'],g['w']=cm.shape
            samples.append(dict(raw=g['mask'],char=c,file=f,row=r,mask=cm,line=LB[g['y']:g['y']+g['h'],g['x']:g['x']+g['w']].copy(),bstar=BS[g['y']:g['y']+g['h'],g['x']:g['x']+g['w']].copy(),norm=NM[g['y']:g['y']+g['h'],g['x']:g['x']+g['w']].copy(),top=g['y'],bottom=g['y']+g['h'],base=base,x=g['x']))
# scale per file: median cap height of flat-topped caps
for f in set(s['file'] for s in samples):
    caps=[s['base']-s['top'] for s in samples if s['file']==f and s['char'] in "BDEFHIKLMNPRTUVWXZ"]
    ch=float(np.median(caps))
    for s in samples:
        if s['file']==f: s['cap']=ch
    print(f,"cap px",ch,len(caps))
import pickle; pickle.dump(samples,open("samples.pkl","wb"))
from collections import Counter
cnt=Counter(s['char'] for s in samples); print(len(samples),"samples",len(cnt),"chars")
print("".join(sorted(cnt)))
