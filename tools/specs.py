# Per photo: (file, x0, x1, rotate_deg, {row_index: "spec"})
# spec tokens, one per ink group left->right:
#   c      group is char c
#   c:N    next N groups merged are char c
#   {ab}   group holds 2 chars, split
#   _      skip group
#   _N     skip N groups
SPECS = [
 ("IMG_0077.jpg", 150, 1450, -90, {
   0: "A B C D E F G H I J K L",
   1: "M N O P Q R S T U V",
   2: "W X Y Z",
   3: "a b c d e f g h i j k l m",
   4: "n o p q r s t u v w x y z",
   5: "A a B b C c D d E e F f G g H h",
   6: "I i J j _ K k L l M m N n O o P p",
   7: "Q q R r S s T t U u V _ W w {Xx}",
   8: "{Yy} Z z",
   9: "0 1 _ 3 4 5 6 7 8 9 0",
   10: "0 1 2 3 {45} 6 7 8 9 0",
 }),
 ("IMG_0077.jpg", 1700, 2800, -90, {
   0: "+ - _ _ = _ < > _ _",
   2: "% _2 _ _ ₹ ₹ $ € £ ¥",
   3: "( ) [ ] { } / \\:2 | ~ ^",
   4: ". , ; !:2 ? ' \":2 _2 _2 _2 _2 — - _",
   5: "@ # & *",
 }),
 ("IMG_0081.jpg", 150, 1400, 0, {
   1: "A B C D E F G H I J K",
   2: "L M N O P Q R S T U V",
   3: "W X Y Z",
   5: "a b c d e f g h i j:2 k l m n o",
   6: "p q r s t u v w x y z _",
 }),
]
