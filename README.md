# AnnaHand

A font made from YedaAnna's own handwriting.

![preview](previews/preview.png)

## Get the font

Files are in `fonts/`.

- **Mac, iPhone, iPad:** `AnnaHand-Regular.otf`
- **Windows, Android, Office:** `AnnaHand-Regular.ttf`
- **Websites:** `AnnaHand-Regular.woff2` + `AnnaHand.css`

Install:

- **Mac:** double-click the `.otf`, then click "Install Font".
- **Windows:** right-click the `.ttf`, then "Install for all users".
- **iPhone / iPad:** open the `.otf` in an app that can install fonts.
- **Web:** copy the `.woff2` and `.css`, link the CSS, then use
  `font-family: "AnnaHand";`.
- **Google Docs:** cannot use your own fonts.

## What is in it — v0.1

- A to Z, a to z, 0 to 9.
- Most punctuation: `. , ; : ! ? ' " - _ ( ) [ ] { } / \ | ~ ^ @ # & * % + = < >`
- Symbols: `$ € £ ¥ ₹ —`
- Missing: the backtick `` ` ``.

## How it was made

1. Five notebook photos, kept in `handwriting/2026-10-10/`.
2. Each letter was cut out of the alphabet pages (blue ink only, ruled lines removed).
3. Where a letter was written 2 or 3 times, the most typical copy was picked.
4. Letters were put on one baseline and sized to the same cap, x-height and ascender.
5. Outlines were traced and saved as OTF, TTF, WOFF2 and WOFF.

`previews/samples-used.png` shows every cut-out letter that was considered.

## Add more handwriting

Put new photos in a new dated folder under `handwriting/`.
More copies of each letter make the average shape better.

To rebuild (Python 3.10+):

    pip install -r tools/requirements.txt
    cd tools
    python extract.py          # cut letters out of the photos
    python make.py ../fonts AnnaHand
    python prev.py ../fonts/AnnaHand-Regular.ttf ../previews/preview.png

`tools/specs.py` says which characters are on which line of which photo.
New photos need a new entry there.
