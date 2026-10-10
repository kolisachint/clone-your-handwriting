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
ap.add_argument("--alphabet-only",action="store_true")
ap.add_argument("--no-complete",action="store_true")
ap.add_argument("--dump",default=None,help="write per-glyph facts (json) for the review stage")
ARGS=ap.parse_args()
EXCLUDE={("X","IMG_0077.jpg",7),("x","IMG_0077.jpg",7),("A","IMG_0081.jpg",1),("-","IMG_0077.jpg",4)}
from geometry import deskew, slant, shear
from complete import complete
BAD_ROWS={("IMG_0080.jpg",208)}           # word row mis-aligned by words.py
EXCLUDE|={("V","IMG_0080.jpg",200)}
raw=pickle.load(open("samples.pkl","rb"))
if os.path.exists("word_samples.pkl") and not ARGS.alphabet_only:
    raw+=pickle.load(open("word_samples.pkl","rb"))
s=[]
for x in raw:
    if (x['char'],x['file'],x['row']) in EXCLUDE or (x['file'],x['row']) in BAD_ROWS: continue
    x=deskew(x); x['slope']=0.0                 # row tilt removed
    s.append(x)
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
from strokes import _nbrs as _nb
# letters made of several separate marks
EXPECT={'i':2,'j':2,'!':2,'?':2,';':2,':':2,'%':3,'"':2,'=':2}
# capital I: the alphabet form (with bars) keeps it apart from l
PREFER_ALPHA=set("I")
# natural t is a cross (+-like); clear styles use the textbook t
PREFER_ALPHA_CLEAR=set("tgy")
# manager review: hand-picked copies where the automatic pick was a hurried one
OVERRIDE={'A':[('IMG_0077.jpg',0)]}
def _quality(x):
    """(pieces, loose ends) after cleanup. Hurried copies have stray pieces or
    extra loose ends (stubs, overshoots)."""
    big,sk,_=clean(x['mask'],x.get('line'),x['cap'],2,bstar=x.get('bstar'),norm=x.get('norm'))
    pieces=cv2.connectedComponents(big.astype(np.uint8),connectivity=8)[0]-1
    ys,xs_=np.nonzero(sk); ends=sum(1 for y,xx in zip(ys,xs_) if len(_nb(sk,y,xx))==1)
    return pieces,ends
def medoid(xs):
    """the writer's most typical copy: keep copies with the usual number of
    pieces (so i keeps its dot), prefer fewer loose ends, then pick the one
    closest to all the others."""
    if len(xs)==1: return xs[0]
    for x in xs:
        if 'q' not in x: x['q']=_quality(x)
    ch=xs[0]['char']
    if ch in PREFER_ALPHA or (ch in PREFER_ALPHA_CLEAR and ARGS.style in ('typed','access')):
        a=[x for x in xs if x.get('src')!='words']; xs=a or xs
    for f,r in OVERRIDE.get(ch,[]):
        for x in xs:
            if x['file']==f and x['row']==r: return x
    P=[x['q'][0] for x in xs]
    if ch in EXPECT and EXPECT[ch] in P: mode=EXPECT[ch]
    else: mode=max(set(P),key=lambda p:(P.count(p),-p))
    xs=[x for x in xs if x['q'][0]==mode]
    emin=min(x['q'][1] for x in xs)
    xs=[x for x in xs if x['q'][1]<=emin+1]
    if len(xs)<3: return min(xs,key=lambda x:(x['q'][1],-x['mask'].sum()))
    C=[canon(x) for x in xs]
    D=[[np.abs(a-b).sum() for b in C] for a in C]
    return xs[int(np.argmin(np.sum(D,1)))]
@dataclass
class GB: char:str; ink:np.ndarray; baseline_px:int; px_per_mm:float
UP=4
DESC=set("gjpqyQ,;")   # f sits on the line in this hand (judge: f below baseline)
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
# lowercase whose top is at x-height but which are not in XH
XH_TOP=XH|set("gjpqy")   # bodies of descenders sit at x-height too (top = x-height)
def top_h(x): return (x['base']-x['top'])/x['cap']
target['xtop']=float(np.median([top_h(x) for c in "gpqy" for x in by.get(c,[])]))
def norm_scale(x):
    """scale so the letter's top lands on its group's line (cap / x-height /
    ascender). Hurried letters that came out small or big are pulled to the
    writer's own average; shapes are not changed. Clamp so nothing is
    distorted beyond +-25%."""
    c=x['char']; k=None
    if c in CAPS: k='cap'
    elif c in XH: k='x'
    elif c in ASC: k='asc'
    elif c in "gpqy": k='xtop'
    if not k: return 1.0
    r=target[k]/max(top_h(x),1e-6); return float(np.clip(r,0.80,1.25))

STYLE=ARGS.style
# metrics from the writer's own lines (judge compares glyphs against these)
L.X_HEIGHT_UNITS=int(round(target['x']/target['cap']*L.CAP_HEIGHT_UNITS))
# Typed / accessibility get a little more air between letters
L.SIDE_BEARING_UNITS={"raw":60,"hand":60,"paper":60,"typed":70,"access":95}[STYLE]
L.SPACE_ADVANCE_UNITS={"raw":300,"hand":300,"paper":300,"typed":320,"access":380}[STYLE]
glyphs=[];chosen={}
cleaned={}
COMPLETED=[]
FACTS={}
rep=[]
for ch,xs in sorted(by.items()):
    x=dict(medoid(xs)); chosen[ch]=x
    sc=norm_scale(x); x['cap']=x['cap']/sc
    if STYLE=="access" and ch in XH|set("bdhkltfgjpqy"):
        x['cap']=x['cap']/1.0   # placeholder, x-height boost applied below
    big,sk,w=clean(x['mask'],x.get('line'),x['cap'],UP,bstar=x.get('bstar'),norm=x.get('norm'))
    base_row=(x['base']-x['top']+4)*UP; C=x['cap']*UP
    rep=[]
    kind=('cap' if ch in CAPS else 'x' if ch in XH else 'asc' if ch in ASC else 'desc' if ch in "gjpqy" else 'other')
    if not ARGS.no_complete and kind!='other':
        big,sk,rep=complete(big,sk,int(round(base_row)),int(round(base_row-C)),int(round(base_row-target['x']*C)),kind)
        if rep: COMPLETED.append((ch,len(rep)))
    cleaned[ch]=(x,big,sk,w)
    FACTS[ch]=dict(char=ch,samples=len(xs),picked=f"{x['file']}#{x['row']}",src=x.get('src','alpha'),
        quality=list(map(int,x.get('q',(0,0)))),scale=round(float(sc),3),
        completed=[dict(target=r['target'],added_px=int(r['added_px'])) for r in rep],
        overridden=ch in OVERRIDE, kind=kind)
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
print(len(glyphs),"glyphs",STYLE); print("completed strokes:",COMPLETED)
if ARGS.dump:
    import json
    json.dump(dict(style=STYLE,family=ARGS.family,targets={k:round(v,4) for k,v in target.items()},
                   stroke_rel=round(WREL,4),glyphs=FACTS),open(ARGS.dump,"w"),indent=1,ensure_ascii=False); print(paths)
