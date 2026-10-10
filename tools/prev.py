import sys
from PIL import Image,ImageDraw,ImageFont
ttf=sys.argv[1]; out=sys.argv[2]
lines=[("ABCDEFGHIJKLMNOPQRSTUVWXYZ",64),("abcdefghijklmnopqrstuvwxyz",64),("0123456789 !?&@#()[]{}%$€₹",56),
("The quick brown fox jumps over the lazy dog.",56),("Pack my box with five dozen liquor jugs.",56),
("Hope you are well. Thank you so much, with love.",48),("Email me: hello@mail.com, call 98765 43210!",48)]
W=1800; H=60+sum(int(s*1.7) for _,s in lines)
im=Image.new("RGB",(W,H),"white"); d=ImageDraw.Draw(im); y=30
for t,s in lines:
    f=ImageFont.truetype(ttf,s); d.text((40,y),t,font=f,fill=(25,30,70)); y+=int(s*1.7)
im.save(out)
