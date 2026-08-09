# Argus Breakpoints

Status: Active Alpha implementation

`.agent/designs/argus/DESIGN.md` section 8 fixes the width bands. This page says
what each band means and what the shell actually changes at it. It is
deliberately not a catalogue of views. A catalogue goes stale the day it lands
and gives false confidence in the meantime.

**Doc for intent, baselines for fact.** If this page and a baseline disagree,
the baseline is right and this page is out of date.

## The bands

| Band | Width | What the shell does |
|------|-------|---------------------|
| Mobile Small | <400px | Same shell as Mobile. Nothing branches here; it is the width the type scale is written from. |
| Mobile | 400 to 720px | Navigation lives in a drawer behind the top bar. No activity rail. Omnisearch is a single list; a dossier opens as a sheet on top of it. Settings is a bottom sheet. |
| Tablet | 720 to 1024px | The sidebar rail and the activity rail appear. The sidebar preference appears with them. Omnisearch is still a single list, and a dossier is still an overlay. Settings is still a sheet. |
| Desktop | 1024 to 1280px | The sidebar is expanded and permanent. Omnisearch becomes two panes, so a dossier is a pane rather than an overlay. Settings becomes an anchored menu instead of a sheet. |
| Large | 1280 to 1920px | Same as Desktop. Content stops growing; margins take the extra width. |

Two stops carry nearly all the behavior:

- **720** is where the rails arrive. In code this is the `tablet:` variant, so a
  rule written as `hidden tablet:block` is a 720 rule.
- **1024** is where overlays become panes and the sheet becomes a menu. This is
  the stop that changes navigation shape rather than just density.

Below 720 every capture should be reachable one-handed: the drawer opens from
the top bar, and tap targets in sheets are 44px.

## What is enforced

`web/e2e/breakpoint-baselines.spec.ts` holds `toHaveScreenshot` baselines for
legal pages, auth screens, and settings panels, at 390, 720, and 1024 in English
dark, plus one crossed cell per surface at 390 in Spanish light. That crossed
cell is where the two things most likely to break meet: the longest copy and the
inverted theme.

Run it, and refresh baselines, with the command in the header of
`web/e2e/breakpoint-baselines.playwright.config.ts`. Baselines are suffixed by
platform, so a macOS run never argues with the committed Linux set.

## What is not enforced, and why

Nothing under `web/components/chat/` is baselined. That surface is being
rewritten, and a baseline committed against it is a baseline somebody
regenerates instead of reads.

Most of Argus is model output. An answer, a quick take, and a discovery summary
differ every run and cannot be baselined at any width. Baselines are scoped to
chrome: the frame around an answer, never the answer.

Settings panels are captured as the panel element rather than the whole page.
The settings sheet floats over the chat shell, so a full-page baseline would go
red on every chat change for reasons that have nothing to do with settings.

## Keeping the suite worth having

A visual suite that cries wolf gets switched off, which is worse than not having
one. Everything in the config exists to remove a reason for a false red: fixture
data so no live content reaches a capture, a fixed timezone and locale because
the allowance panel renders dates, `deviceScaleFactor: 1` so a retina laptop and
a CI container rasterise the same, frozen animations and a hidden caret, and a
per-pixel threshold that absorbs font antialiasing without absorbing a moved
element.

If a baseline goes red, read the diff before regenerating it. Regenerating a red
baseline without reading it converts the suite into a rubber stamp.

## Evidence

`docs/evidence/breakpoint-audit/` holds a capture and the rendered text of every
guest and signed-in surface at each band, produced by
`web/e2e/breakpoint-audit.spec.ts`. Those specs assert nothing; they exist so a
reviewer can read a surface instead of a claim about it.
