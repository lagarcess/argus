# Cuadrao brand artwork

Source files for the Cuadrao mark, the wordmark and the mark-and-wordmark lockups. Generated files say so below; edit the sources, not the outputs. Any lane that draws these (web, iOS) takes the SVGs as they are: do not redraw, approximate or re-colour them.

## Files

| File | What it is | Use on |
| --- | --- | --- |
| `../app/icon.svg` | The mark on its deep-green tile. Source of the app icon and favicon | Home screen, favicon |
| `cuadrao-mark-light.svg` | The mark without its tile, light-surface colours | Light backgrounds |
| `cuadrao-mark-dark.svg` | The mark without its tile, the tiled icon's own colours | `#172b26` only (see below) |
| `cuadrao-wordmark.svg`, `cuadrao-wordmark-dark.svg` | The lowercase wordmark as outlines, `#172b26` and `#fafbf8` | Light, dark |
| `cuadrao-lockup-light.svg`, `cuadrao-lockup-dark.svg` | Mark and wordmark together, one composition | Light, dark |
| `../scripts/make-brand-assets.py` | Generates the wordmark and the lockups from the font and the marks | |

The tiled icon and the two marks draw the same three shapes with the same transform; `__tests__/brand-mark.test.ts` keeps them identical.

## The wordmark

Lowercase `cuadrao`, exactly as the website draws it (`.wordmark` in `components/business.module.css`):

- Font: Space Grotesk 2.0.0, upright, weight **700**, `line-height: 1`.
- Letter-spacing: **-0.085em** (no kerning pairs apply to this word, so the spacing is the whole of it).
- Website sizes: 35 px on desktop, 31 px on narrow screens. Colour is the page ink, `#172b26`, on light; the page paper, `#fafbf8`, on the dark footer.
- Font file: `../app/fonts/SpaceGrotesk[wght].woff2`. Licence: SIL Open Font License 1.1, copyright 2020 The Space Grotesk Project Authors; text in `../app/fonts/OFL-1.1-Space-Grotesk.txt`, attribution in `../app/fonts/FONT-ATTRIBUTION.md`.
- The outlined SVGs are the same letters as paths, so an app can show the wordmark without shipping or approximating the font. Their coordinates are font units (1 em = 1000): the ink spans x 46 to 3416 and y -700 (top of the d) to 14 (the o's overshoot), with the baseline at y 0 and the x-height at 486.

The earlier icon sheets showed a lighter, looser wordmark (weight 600, letter-spacing -0.045em). That was an approximation. The website's is the one above.

## Lockup

Proposed geometry, in wordmark units where the wordmark's font size is 1 em. It matches the finalists sheet the founder reviewed; it becomes the guide once the founder agrees the welcome-screen mock.

- Mark height: **1 em** (the mark's own bounds are 56.2 by 48 in its 64-unit grid, so its width is 1.17 em). That is 2.06 times the x-height and 1.43 times the height of the d.
- Gap between the mark and the wordmark's first letter: **0.25 em**.
- Vertical alignment: the mark's centre sits halfway between the baseline and the top of the d (0.35 em above the baseline). The mark overhangs the d by 0.15 em above and the baseline by 0.15 em below.
- Clear space: 0.5 em on every side.
- Minimum size: lockup at a wordmark font size of 20 px; the mark alone down to 16 px (the favicon size).

The lockup SVGs have exactly this geometry, cropped to their ink, with no clear space built in. The lockups and the wordmarks carry an intrinsic `width` and `height` (268 and 200 wide, in the aspect of their viewBox) so a tool that sizes an SVG by its root attributes does not rasterize it at viewBox size; the art scales freely.

## Colours

| Role | Light surface | Dark surface |
| --- | --- | --- |
| Background | `#fafbf8` (page paper) | `#172b26` (page ink, the footer) |
| Wordmark | `#172b26` | `#fafbf8` |
| Mark: front square | `#2f5a49` to `#1d4236` | `#fffcf2` to `#e3dcc2` |
| Mark: back square | `#cfdccf` to `#bccdbf` | `#8fa38f` to `#5b7566` at 55% opacity |
| Mark: overlap | `#a6e06a` to `#6fbf46` | `#b6e87a` to `#7fcb4f` |

All gradients run top-left to bottom-right. The dark mark's back square is semi-transparent, so `cuadrao-mark-dark.svg` and `cuadrao-lockup-dark.svg` are drawn for a `#172b26` background; on any other dark colour the back square changes tone.

Other website colours: muted text `#56635e`, hairlines `#dce0da`, accent `#d7ddc0`, Personal pages' paper `#f7f5ef`, the closing band `#f7f5ee`.
