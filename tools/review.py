import glob,sys
from PIL import Image,ImageDraw,ImageFont
root=sys.argv[1]; out=sys.argv[2]
B="/System/Library/Fonts/Supplemental/Arial Bold.ttf"; R="/System/Library/Fonts/Supplemental/Arial.ttf"
S=[("v0.2 (before)","raw","alphabet pages only, tilt and size not fixed"),
   ("1  Handwritten","hand","your strokes as written, stray ink removed"),
   ("2  Paper","paper","same strokes, one even pen line"),
   ("3  Typed","typed","hand wobble smoothed, lighter, more space"),
   ("4  Accessibility","access","bold, slashed 0, taller lowercase, wide spacing")]
T1="Hope you are well. Thank you so much!"; T2="AKMH 1240 kudo  hello@mail.com"
W=1500; rh=300
im=Image.new("RGB",(W,80+rh*len(S)),"white"); d=ImageDraw.Draw(im)
d.text((40,22),"AnnaHand v0.3 — four styles",font=ImageFont.truetype(B,40),fill=(20,20,20))
for i,(name,key,desc) in enumerate(S):
    y=80+i*rh; ttf=glob.glob(f"{root}/{key}/*.ttf")[0]; f=ImageFont.truetype(ttf,62)
    d.rectangle([0,y,W,y+rh-8],fill=(246,246,242) if i==0 else (255,255,255))
    d.text((40,y+14),name,font=ImageFont.truetype(B,30),fill=(150,40,30) if i==0 else (11,110,79))
    d.text((40,y+52),desc,font=ImageFont.truetype(R,24),fill=(80,80,80))
    d.text((40,y+165),T1,font=f,fill=(20,24,60),anchor="ls")
    d.text((40,y+255),T2,font=f,fill=(20,24,60),anchor="ls")
    d.line([0,y+rh-8,W,y+rh-8],fill=(220,220,220),width=2)
im.save(out); print(im.size)
