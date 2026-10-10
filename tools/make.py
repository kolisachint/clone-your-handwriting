import pickle,numpy as np,cv2,sys,os
from collections import defaultdict
from dataclasses import dataclass
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from handfont.vectorize import trace_glyph
from handfont.build import build_font
from handfont import layout as L
EXCLUDE={("X","IMG_0077.jpg",7),("x","IMG_0077.jpg",7),("A","IMG_0081.jpg",1),("-","IMG_0077.jpg",4)}
s=[x for x in pickle.load(open("samples.pkl","rb")) if (x['char'],x['file'],x['row']) not in EXCLUDE]
by=defaultdict(list)
for x in s: by[x['char']].append(x)
def canon(x,N=64):
    """place sample on a fixed canvas: cap height -> 32px, baseline at row 48, centred."""
    sc=32/x['cap']; m=x['mask'].astype(np.float32)
    h,w=m.shape; m=cv2.resize(m,(max(1,int(w*sc)),max(1,int(h*sc))),interpolation=cv2.INTER_AREA)
    c=np.zeros((N+32,N),np.float32); top=int(48-(x['base']-x['top'])*sc)
    hh,ww=m.shape; x0=(N-ww)//2
    y0=max(0,top); m=m[y0-top:]; hh=min(m.shape[0],c.shape[0]-y0); ww=min(ww,N-max(0,x0))
    c[y0:y0+hh,max(0,x0):max(0,x0)+ww]=m[:hh,max(0,-x0):max(0,-x0)+ww]
    return cv2.GaussianBlur(cv2.dilate(c,np.ones((3,3))),(5,5),0)
def medoid(xs):
    if len(xs)<3: return max(xs,key=lambda x:x['mask'].sum()) if len(xs)==2 and False else xs[0] if len(xs)==1 else xs[int(np.argmax([x['file']=='IMG_0077.jpg' for x in xs]))]
    C=[canon(x) for x in xs]
    D=[[np.abs(a-b).sum() for b in C] for a in C]
    return xs[int(np.argmin(np.sum(D,1)))]
@dataclass
class GB: char:str; ink:np.ndarray; baseline_px:int; px_per_mm:float
UP=4
DESC=set("fgjpqyQ,;")
FLOAT=set("'\"-~^*=+—<>")
CAPS=set("ABCDEFGHIJKLMNOPRSTUVWXYZ0123456789")
XH=set("acemnorsuvwxz")
ASC=set("bdhkl")
for xs in by.values():
    for x in xs:
        if x['char'] not in DESC|FLOAT: x['base']=x['bottom']   # sit on the line
def h(x): return (x['base']-x['top'])/x['cap']
def med(cs): return float(np.median([h(x) for c in cs for x in by.get(c,[])]))
target={'cap':med(CAPS),'x':med(XH),'asc':med(ASC)}
print("target heights (rel. to cap)",target)
def norm_scale(x):
    c=x['char']; k=None
    if c in CAPS: k='cap'
    elif c in XH: k='x'
    elif c in ASC: k='asc'
    if not k: return 1.0
    r=target[k]/max(h(x),1e-6); return float(np.clip(r,0.85,1.18))
glyphs=[];chosen={}
for ch,xs in sorted(by.items()):
    x=dict(medoid(xs)); chosen[ch]=x
    sc=norm_scale(x); x['cap']=x['cap']/sc
    m=x['mask'].astype(np.float32); m=np.pad(m,4)
    big=cv2.resize(m,None,fx=UP,fy=UP,interpolation=cv2.INTER_CUBIC)
    big=cv2.GaussianBlur(big,(0,0),UP*0.9)>0.45
    base=(x['base']-x['top']+4)*UP
    ppm=x['cap']*UP*L.UNITS_PER_MM/L.CAP_HEIGHT_UNITS
    glyphs.append(trace_glyph(GB(ch,big,int(round(base)),ppm)))
import copy
def synth(ch,src,fn):
    if ch in by or src not in chosen: return
    x=dict(chosen[src]); x=fn(x); x['char']=ch
    m=np.pad(x['mask'].astype(np.float32),4)
    big=cv2.GaussianBlur(cv2.resize(m,None,fx=UP,fy=UP,interpolation=cv2.INTER_CUBIC),(0,0),UP*0.9)>0.45
    ppm=x['cap']*UP*L.UNITS_PER_MM/L.CAP_HEIGHT_UNITS
    glyphs.append(trace_glyph(GB(ch,big,int(round((x['base']-x['top']+4)*UP)),ppm)))
def colon(x):
    d=x['mask']; gap=int(x['cap']*0.35); h,w=d.shape
    m=np.zeros((h*2+gap,w),bool); m[:h]=d; m[h+gap:]=d
    x['mask']=m; x['top']=x['bottom']-m.shape[0]; x['base']=x['bottom']; return x
def under(x):
    x['base']=x['top']-int(x['cap']*0.08); return x
synth(':','.',colon); synth('_','—',under)
out=sys.argv[1] if len(sys.argv)>1 else "out"
fam=sys.argv[2] if len(sys.argv)>2 else "Anna Hand"
paths=build_font(glyphs,fam,__import__('pathlib').Path(out),version="0.1.0")
pickle.dump({k:(v['file'],v['row']) for k,v in chosen.items()},open(os.path.join(out,"chosen.pkl"),"wb"))
print(len(glyphs),"glyphs"); print(paths)
