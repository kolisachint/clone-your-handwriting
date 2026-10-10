# handfont

Turn your own handwriting into a font.

You write 94 characters on one printed sheet.
You scan or photograph the sheet.
handfont builds a font file you can install and use.

## The 5 steps

1. Print the template.
2. Write on it with a dark pen.
3. Scan or photo the pages.
4. Put the files in `scans/`, then push. Or run the build yourself.
5. Make a release. You get the font files to download.

## Step 1: Print the template

Run this, or ask for `template.pdf` from a release:

    handfont template -o template.pdf

Print on A4 paper at 100% scale. Do not "fit to page".

## Step 2: What to write

- 94 characters: A to Z, a to z, 0 to 9, and punctuation.
- 2 pages.
- About 20 to 30 minutes.

Tips:

- Use a fine black felt-tip pen, 0.5 to 0.8 mm.
- Keep the size even from letter to letter.
- Sit each letter on the baseline.
- Keep letters inside their boxes. Do not touch the border.
- Do not use pencil or blue ink. They do not scan well.

## Step 3: Scan or photograph

Scanner at 300 dpi is best.

A phone photo is fine if:

- the page is flat on a table,
- it is in daylight, with no shadow,
- all four black corner squares are in the photo.

## Step 4: Hand over the files

Put the images in `scans/`. Name them `page-1.jpg` and `page-2.jpg`.
See `scans/README.md` for more detail.

Then either:

- commit and push them, or
- run the build on your own computer (see below).

Or drop the photos in chat for the bot.

## Step 5: Get your font

Make a release. Tag the commit and push the tag:

    git tag v0.1.0
    git push --tags

The release page lists your font files:

- `.otf` and `.ttf` for computers,
- `.woff2` and `.woff` plus `.css` for websites,
- `preview.png` to see the result,
- `template.pdf` to print a new sheet,
- a zip with everything.

Set the family name and version in `font.toml`.

## Using your font everywhere

### Mac, Windows, Linux

Use the `.otf` (Mac) or `.ttf` (Windows, Linux) file.
Install steps are on the release page.

### Websites

Copy the `.woff2` file and the `.css` file into your site folder.
Link the CSS in the page's `<head>`:

    <link rel="stylesheet" href="MyHand.css">

Then use the family name in your CSS:

    body {
      font-family: "MyHand", cursive;
    }

### iPhone and iPad

There is no double-click install.
Use a font installer app from the App Store.
Or use a design app that can import `.otf` files.

### Android

There is no system-wide install.
Use apps that accept custom fonts.
Pick the `.ttf` or `.otf` file in the app's font settings.

### Word and PowerPoint

Install the `.ttf` or `.otf` on your computer first.
Then the font shows in the font list.

### Google Docs

Google Docs cannot use uploaded fonts.
Use Word or your own computer for this font instead.

## Local development

Set up once:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e '.[dev]'

Run the tests:

    python -m pytest -q

Make a template:

    handfont template -o template.pdf

Build the font from your scans:

    handfont build scans --config font.toml -o dist

This writes files into `dist/`.
The `dist/` folder is ignored by git.
