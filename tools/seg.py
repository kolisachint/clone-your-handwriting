import cv2,numpy as np,sys
def inkmask(im):
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    bg=cv2.medianBlur(g,61).astype(np.float32)
    norm=cv2.GaussianBlur(np.clip(g.astype(np.float32)/np.maximum(bg,1)*255,0,255),(3,3),0)
    s=cv2.GaussianBlur(hsv[...,1],(3,3),0); h=hsv[...,0]
    blue=(h>100)&(h<140)
    strong=((norm<150)&(s>90)&blue).astype(np.uint8)*255
    weak=((norm<200)&(s>55)&blue).astype(np.uint8)*255
    for m in (strong,weak):
        hor=cv2.morphologyEx(m,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(101,1)))
        hor=cv2.dilate(hor,np.ones((3,1),np.uint8))
        m[:]=cv2.subtract(m,hor)
    weak=cv2.morphologyEx(weak,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3)))
    n,lab=cv2.connectedComponents(weak,connectivity=8)
    good=np.unique(lab[(strong>0)&(weak>0)]); good=good[good>0]
    m=np.isin(lab,good)
    n,lab,st,_=cv2.connectedComponentsWithStats(m.astype(np.uint8),8)
    keep=np.zeros(n,bool); keep[1:]=st[1:,4]>=25
    return keep[lab]
def rows(mask, x0, x1, minh=8):
    prof=mask[:,x0:x1].sum(1)
    on=prof>max(3,prof.max()*0.02)
    out=[];y=0
    while y<len(on):
        if on[y]:
            s=y
            while y<len(on) and on[y]: y+=1
            out.append((s,y))
        y+=1
    return [r for r in out if r[1]-r[0]>=minh]

def linekill(im):
    """pixels that are ruled-line residue (thin horizontal blue), to strip from glyphs."""
    hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    bg=cv2.medianBlur(g,61).astype(np.float32)
    norm=cv2.GaussianBlur(np.clip(g.astype(np.float32)/np.maximum(bg,1)*255,0,255),(3,3),0)
    h=hsv[...,0]; blue=(h>100)&(h<140)
    strong=np.zeros(g.shape,np.uint8); weak=strong.copy()
    # ruled lines: lenient blue mask, long horizontal runs (gaps bridged first)
    lines=((norm<230)&(hsv[...,1]>30)&blue).astype(np.uint8)*255
    lines=cv2.morphologyEx(lines,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_RECT,(9,1)))
    lines=cv2.morphologyEx(lines,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(61,1)))
    # extend each line segment sideways a bit so stubs touching letters are covered,
    # but only keep that extension where the original lenient mask is thin (<=5px tall)
    thin=((norm<230)&(hsv[...,1]>30)&blue).astype(np.uint8)*255
    thick=cv2.morphologyEx(thin,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,7)))
    ext=cv2.dilate(lines,cv2.getStructuringElement(cv2.MORPH_RECT,(41,3)))
    kill=(ext>0)&(thick==0)
    return kill

def linebands(im, thick=9, strip=120):
    """ruled lines (blue and red) as straight bands across the page.
    Found per vertical strip from the row profile of 'darker than paper',
    using the paper's own median as reference, then joined strip to strip."""
    g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY).astype(np.float32)
    bg=cv2.medianBlur(g.astype(np.uint8),61).astype(np.float32)
    dark=np.clip(1-g/np.maximum(bg,1),0,1)
    H,W=dark.shape; out=np.zeros((H,W),bool)
    for x0 in range(0,W,strip):
        sl=dark[:,x0:x0+strip]
        # row score = median over strip: ink strokes are sparse, lines are continuous
        prof=np.median(sl,1)
        prof=np.convolve(prof,np.ones(3)/3,'same')
        thr=max(0.04,np.percentile(prof,97)*0.35)
        y=1
        while y<H-1:
            if prof[y]>thr and prof[y]>=prof[y-1] and prof[y]>=prof[y+1]:
                out[max(0,y-thick//2):y+thick//2+1, x0:x0+strip]=True; y+=4
            else: y+=1
    return out
