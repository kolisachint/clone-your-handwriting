import glob,sys
from PIL import Image,ImageDraw,ImageFont
a=glob.glob("/tmp/v5/raw/*.ttf")[0]; b=glob.glob("/tmp/v5/hand/*.ttf")[0]
chars="AHkl4o1+=!sMu*"
size=150; cw=int(size*0.95); W=60+cw*7; im=Image.new("RGB",(W,2*(size*2+150)+20),"white"); d=ImageDraw.Draw(im)
B=ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf",30)
for half,cs in enumerate([chars[:7],chars[7:]]):
    oy=half*(size*2+150)
    for r,(lab,f) in enumerate([("before",a),("after",b)]):
        y=oy+50+r*(size+60); d.text((20,y-40),lab,font=B,fill=(150,40,30) if r==0 else (11,110,79))
        F=ImageFont.truetype(f,size)
        for i,c in enumerate(cs):
            d.line([40+i*cw,y+size,40+(i+1)*cw-20,y+size],fill=(190,215,245),width=2)
            d.text((50+i*cw,y+size),c,font=F,fill=(20,24,60),anchor="ls")
im.save(sys.argv[1]); print(im.size)
