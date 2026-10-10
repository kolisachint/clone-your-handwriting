"""contact sheet of every candidate per char, after deskew + cleanup, marking the auto pick."""
import sys,numpy as np,cv2
sys.argv=['make.py','/tmp/x','x']
exec(open('make.py').read().split('glyphs=[];chosen={}')[0])
from PIL import Image,ImageDraw,ImageFont
chars=sys.stdin.read().strip()
f=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',14)
CW,CH=96,130; rows=[]
for ch in chars:
    xs=by.get(ch,[]); md=medoid(xs) if xs else None
    im=Image.new('RGB',(CW*max(1,len(xs)),CH),'white'); d=ImageDraw.Draw(im)
    for i,x in enumerate(xs):
        big,sk,w=clean(x['mask'],x.get('line'),x['cap'],UP,bstar=x.get('bstar'),norm=x.get('norm'))
        sc=64/(x['cap']*UP); m=cv2.resize(big.astype(np.uint8)*255,None,fx=sc,fy=sc,interpolation=cv2.INTER_AREA)
        base=int((x['base']-x['top']+4)*UP*sc); oy=95-base; ox=i*CW+(CW-m.shape[1])//2
        d.line([i*CW,95,i*CW+CW-6,95],fill=(150,190,240))
        im.paste((20,20,70),(ox,oy),Image.fromarray(m))
        d.text((i*CW+2,2),f"{i} {x['file'][5:8]}r{x['row']}",font=f,fill=(200,0,0) if x is md else (120,120,120))
    rows.append(im)
W=max(r.width for r in rows); out=Image.new('RGB',(W,CH*len(rows)),'white')
for i,r in enumerate(rows): out.paste(r,(0,i*CH))
out.save(sys.argv[-1] if False else '/tmp/cands.png'); print(out.size)
