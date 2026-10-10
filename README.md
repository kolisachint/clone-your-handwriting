# AnnaHand

A font made from YedaAnna's own handwriting.

![preview](previews/preview.png)

## Four styles

![styles](previews/styles.png)

All four come from the same handwriting. Only the pen changes.

1. **AnnaHand** — handwritten. Your strokes as written, stray ink removed.
2. **AnnaHandPaper** — one even pen line, like a gel pen.
3. **AnnaHandTyped** — wobble smoothed, lighter line, a bit more space.
   For long text and documents.
4. **AnnaHandAccess** — bold, wide spacing, taller small letters,
   0 with a slash so it never looks like O. For low vision and small screens.

## Get the font

Each style has its own folder in `fonts/`.

- **Mac, iPhone, iPad:** the `.otf`
- **Windows, Android, Office:** the `.ttf`
- **Websites:** the `.woff2` + the `.css`

Install:

- **Mac:** double-click the `.otf`, then click "Install Font".
- **Windows:** right-click the `.ttf`, then "Install for all users".
- **iPhone / iPad:** open the `.otf` in an app that can install fonts.
- **Web:** copy the `.woff2` and `.css`, link the CSS, then use
  `font-family: "AnnaHand";` (or `AnnaHandTyped`, ...).
- **Google Docs:** cannot use your own fonts.

## What is in it — v0.3

- A to Z, a to z, 0 to 9.
- Most punctuation: `. , ; : ! ? ' " - _ ( ) [ ] { } / \ | ~ ^ @ # & * % + = < >`
- Symbols: `$ € £ ¥ ₹ —`
- Missing: the backtick `` ` ``.

## How it was made

1. Five notebook photos, kept in `handwriting/2026-10-10/`.
2. Each letter was cut out of the alphabet pages (blue ink only, ruled lines removed).
3. Where a letter was written 2 or 3 times, the most typical copy was picked.
4. Letters were put on one baseline and sized to the same cap, x-height and ascender.
5. Stray ink was removed (see below).
6. Outlines were traced and saved as OTF, TTF, WOFF2 and WOFF.

## Fixed in v0.3

- **More samples.** Letters now come from the sentence pages too,
  not only the alphabet lines. About 400 copies, up to 19 per letter.
- **Tilt.** Each written line was slightly tilted (up to 3.5°).
  Every letter is now straightened to its own line first.
- **Sizing.** Every letter is sized to your own average line:
  capitals to cap height, a c e m n ... to x-height, b d h k l to
  ascender height, g p q y bodies to x-height.
- **Unfinished strokes.** Where the pen lifted early (a leg of H, M, h, m,
  b, d stopping short), the stroke is finished to the line in the same
  direction and thickness. See `previews/strokes-finished.png`.
- **Picking the best copy.** Broken or hurried copies (extra loose ends,
  missing dot) are skipped; then the most typical copy wins.

## Stray ink fixed in v0.2

![before and after](previews/cleanup-before-after.png)

- **Ruled-line stubs:** where a letter crossed a notebook line, a bit of
  the line stuck to it (H, 4, k, l, A, 1, +). Removed by finding the
  ruled lines and dropping ink on them that is paler than the pen.
- **Lines inside letters:** a line ran through the top of `o` and across
  `l`. Removed the same way.
- **Ink blots:** pen pressure pooled at stroke ends and joins
  (A, *, u, d). Capped to the normal stroke width.
- Real strokes that lie on a line, like the bottom of `s` or the bar of `4`,
  are pen-dark and stay.

## Every surface

`python tools/package.py` builds `dist/` with one bundle per place
the font is used:

- **web** — WOFF2 + WOFF, one `fonts.css`, `demo.html`
- **desktop** — OTF (Mac, Linux) and TTF (Windows)
- **ios** — `AnnaHand.mobileconfig`: AirDrop to iPhone/iPad, install in
  Settings, then the fonts work in Pages, Keynote, Mail
- **android** — TTF for apps that accept custom fonts
- **office** — TTF + how to embed fonts in Word/PowerPoint files
- **design** — OTF for Figma, Canva, Procreate, Affinity

Tagging a version (`git tag v0.3.0 && git push --tags`) builds these
and attaches the zips to a GitHub Release.

## Add more handwriting

Put new photos in a new dated folder under `handwriting/`.
More copies of each letter make the average shape better.

To rebuild (Python 3.10+):

    pip install -r tools/requirements.txt
    cd tools
    python extract.py          # alphabet lines
    python words.py            # sentence pages (needs extract.py first)
    python make.py ../fonts/AnnaHand AnnaHand --style hand
    python make.py ../fonts/AnnaHandPaper AnnaHandPaper --style paper
    python make.py ../fonts/AnnaHandTyped AnnaHandTyped --style typed
    python make.py ../fonts/AnnaHandAccess AnnaHandAccess --style access

`tools/specs.py` says which characters are on which line of which photo.
New photos need a new entry there.
