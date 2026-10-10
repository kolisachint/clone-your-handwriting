import pickle,numpy as np,cv2,sys
from PIL import Image,ImageDraw,ImageFont
s=pickle.load(open(sys.argv[1] if len(sys.argv)>1 else 'samples.pkl','rb'))
s=sorted(s,key=lambda x:(x['char'],x['file'],x['row']))
CW,CH=110,150; cols=16; n=len(s); R=-(-n//cols)
im=Image.new('RGB',(cols*CW,R*CH),'white'); d=ImageDraw.Draw(im)
f=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',16)
for i,x in enumerate(s):
    r,c=divmod(i,cols); ox,oy=c*CW,r*CH
    sc=60/x['cap']; m=x['mask'].astype(np.uint8)*255
    h,w=m.shape; nh,nw=max(1,int(h*sc)),max(1,int(w*sc))
    m=cv2.resize(m,(nw,nh),interpolation=cv2.INTER_AREA)
    by=oy+100; top=int(by-(x['base']-x['top'])*sc)
    d.line([ox+2,by,ox+CW-4,by],fill=(120,170,230))
    d.line([ox+2,by-60,ox+CW-4,by-60],fill=(220,220,220))
    g=Image.fromarray(255-m).convert('L')
    px=ox+(CW-nw)//2
    im.paste(Image.new('RGB',(nw,nh),(20,20,90)),(px,top),Image.fromarray(m))
    d.text((ox+3,oy+3),f"{x['char']} {x['file'][4:8]}r{x['row']}",fill=(200,0,0),font=f)
    d.rectangle([ox,oy,ox+CW-1,oy+CH-1],outline=(230,230,230))
im.save(sys.argv[2] if len(sys.argv)>2 else 'sheet.png')
print(im.size)
