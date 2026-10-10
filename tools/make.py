import pickle,numpy as np,cv2,sys,os
from collections import defaultdict
from dataclasses import dataclass
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from handfont.vectorize import trace_glyph
from handfont.build import build_font
from handfont import layout as L
from cleanup import clean
from strokes import restroke, skeleton
import argparse
ap=argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("family")
ap.add_argument("--style",default="hand",choices=["raw","hand","paper","typed","access"])
ARGS=ap.parse_args()
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

STYLE=ARGS.style
# Typed / accessibility get a little more air between letters
L.SIDE_BEARING_UNITS={"raw":60,"hand":60,"paper":60,"typed":70,"access":95}[STYLE]
L.SPACE_ADVANCE_UNITS={"raw":300,"hand":300,"paper":300,"typed":320,"access":380}[STYLE]
glyphs=[];chosen={}
cleaned={}
for ch,xs in sorted(by.items()):
    x=dict(medoid(xs)); chosen[ch]=x
    sc=norm_scale(x); x['cap']=x['cap']/sc
    if STYLE=="access" and ch in XH|set("bdhkltfgjpqy"):
        x['cap']=x['cap']/1.0   # placeholder, x-height boost applied below
    cleaned[ch]=(x,)+clean(x['mask'],x.get('line'),x['cap'],UP,bstar=x.get('bstar'),norm=x.get('norm'))
# one pen width for the whole font (relative to cap height), from the writer's own median
WREL=float(np.median([w/(x['cap']*UP) for x,_,_,w in cleaned.values()]))
print("stroke width / cap:",round(WREL,4))
def ink_for(x,big,sk):
    pw=WREL*x['cap']*UP
    if STYLE=="raw":
        m=np.pad(x['mask'],4).astype(np.float32)
        return cv2.GaussianBlur(cv2.resize(m,None,fx=UP,fy=UP,interpolation=cv2.INTER_CUBIC),(0,0),UP*0.9)>0.45
    if STYLE=="hand": return big
    def ironed(sk,k):
        m=restroke(sk,pw*0.85).astype(np.float32)
        m=cv2.GaussianBlur(m,(0,0),UP*k)>0.45
        return skeleton(m)
    if STYLE=="paper":
        return cv2.GaussianBlur(restroke(sk,pw*1.0).astype(np.float32),(0,0),UP*0.7)>0.5
    if STYLE=="typed":
        return cv2.GaussianBlur(restroke(ironed(sk,1.0),pw*0.85).astype(np.float32),(0,0),UP*0.7)>0.5
    if STYLE=="access":
        return cv2.GaussianBlur(restroke(ironed(sk,1.0),pw*1.45).astype(np.float32),(0,0),UP*0.8)>0.5
def slash_zero(m,pw):
    m=m.astype(np.uint8).copy(); ys,xs=np.nonzero(m)
    y0,y1,x0,x1=ys.min(),ys.max(),xs.min(),xs.max(); cy,cx=(y0+y1)/2,(x0+x1)/2
    hy,hx=(y1-y0)*0.30,(x1-x0)*0.26
    cv2.line(m,(int(cx-hx),int(cy+hy)),(int(cx+hx),int(cy-hy)),1,max(2,int(pw)),cv2.LINE_AA)
    return m>0
def emit(ch,x,ink):
    # vertical offset of the padded big bitmap: baseline row
    base=(x['base']-x['top']+4)*UP
    ppm=x['cap']*UP*L.UNITS_PER_MM/L.CAP_HEIGHT_UNITS
    if STYLE=="access" and ch in LOWER_BOOST:
        # bigger x-height: scale lowercase 8% about the baseline
        ppm=ppm/1.08
    glyphs.append(trace_glyph(GB(ch,ink,int(round(base)),ppm)))
LOWER_BOOST=set("abcdefghijklmnopqrstuvwxyz")
for ch,(x,big,sk,w) in cleaned.items():
    ink=ink_for(x,big,sk)
    if STYLE=="access" and ch=="0": ink=slash_zero(ink,WREL*x['cap']*UP*1.3)
    emit(ch,x,ink)
def synth(ch,src,fn):
    if ch in by or src not in chosen: return
    x=dict(cleaned[src][0]); x=fn(x)
    big,sk,_=clean(x['mask'],None,x['cap'],UP)
    emit(ch,x,ink_for(x,big,sk))
def colon(x):
    d=x['mask']; gap=int(x['cap']*0.35); h,w=d.shape
    m=np.zeros((h*2+gap,w),bool); m[:h]=d; m[h+gap:]=d
    x['mask']=m; x['top']=x['bottom']-m.shape[0]; x['base']=x['bottom']; return x
def under(x):
    x['base']=x['top']-int(x['cap']*0.08); return x
synth(':','.',colon); synth('_','—',under)
paths=build_font(glyphs,ARGS.family,__import__('pathlib').Path(ARGS.out),version="0.2.0")
print(len(glyphs),"glyphs",STYLE); print(paths)
