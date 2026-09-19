# PoE2 Grand Expedition Rune Tracker

Tracks the Aldur Runes you pick up while walking the Remnants in PoE2's
Grand Expedition content. During the setup phase you walk to each Remnant
and choose a rune combination; whichever slot is marked as carrying
forward gets added to *every subsequent* Remnant's pool, so by the last
Remnant in a 10-remnant chain you're juggling 9+ stacked modifiers with no
in-game way to review what you picked earlier. This app is that missing
tracking/verification layer - **it never recommends anything, it only
records what you captured and warns you if it wasn't actually the
passable slot.**

## How it works

1. Hover the rune slot you're picking in-game (the tooltip shows a name
   like "Electrocuting Rune", its "Monsters gain: ..." effects, and - only
   on the slot that carries forward - the line *"The Runic Modifier in
   this slot will be added to all Monsters unearthed after this
   Remnant."*).
2. Press the hotkey (`Ctrl+3` by default, global via `pynput`).
3. The app grabs a screenshot region around your cursor and identifies the
   rune. **The screen is only ever the input used to figure out which
   rune it is - the name, icon, and effect text you actually see always
   come from a prepared database, never from what was read off the
   screen.** In priority order:
   - **Image similarity (primary)**: the small icon crop at your cursor is
     compared by appearance against a local icon library, pre-seeded with
     all 33 known Remnant rune icons scraped from individual poe2db.tw
     pages (`tools/scrape_remnant_runes.py` -> `data/rune_icon_seed.json` +
     `data/seed_icons/`, e.g. `poe2db.tw/us/Soul_Rune`; cross-checked
     against poe2db's own "Runeshape Combinations" icon legend, which lists
     exactly these 33 - a 34th, "Bait Rune", is deliberately excluded: it
     shares Power Rune's icon verbatim on poe2db and has never actually
     been seen in-game, so it's treated as a wiki data error). A confident
     match wins immediately, using that entry's database name/icon/effect
     text.
   - **OCR as a lookup key (secondary)**: only if image matching isn't
     confident. Windows' built-in OCR (`winocr`) reads whatever text is in
     the tooltip, but that text is *never shown or stored* - it's only
     used to look up the closest matching name in the same database
     (fuzzy string match, tolerant of OCR noise like a dropped letter or a
     misread character). If it doesn't resolve to anything in the
     database, it's discarded rather than displayed as a guess - this is
     what fixes captures that used to show OCR garbage like `Q\Ac` as if
     it were a real name.
   - **Manual pick (last resort)**: if neither finds a confident answer, a
     popup asks you to pick the rune from the same prepared list (not
     free-typed) so what's shown is always a real database name; picking
     one is a one-time cost; after that it's recognized by appearance. The
     popup also shows *why* both prior steps failed (the closest image
     match's score, and whatever OCR actually read) so a bad capture can be
     diagnosed by reading the popup instead of exchanging screenshots.
   - Whichever path resolves it, that capture also, if OCR's raw text
     guess differs from the resolved name, teaches that mapping to a
     learned-alias table so the same OCR misreading resolves instantly
     (as an exact/confident hit, not a fuzzy guess) next time instead of
     needing image matching or a popup again. The *display* icon is never
     touched by any of this, always the clean database asset - even on the
     rare occasion poe2db's own data is wrong (its "Opulent Rune" icon is
     blue, the real in-game one is gold), it's not worth swapping in a
     noisy screenshot crop just to fix that, since the bottom-of-screen
     capture toast (below) already confirms identity as text.
   - Only a capture that **image matching itself already confirmed** - a
     bare image-match hit, or a disambiguation pick that was one of image
     matching's own close candidates - also adds to that rune's small
     history of confirmed appearance signatures (see "The icon library"
     below). A capture resolved by text alone (an OCR alias/fuzzy guess,
     the disambiguation dialog's "OCR guess" button, or a manual pick)
     never does - there's no evidence in that case that the captured icon
     actually *looks like* the resolved rune, so letting it shape future
     image matching risks teaching the matcher a wrong appearance instead
     of a better one. (An earlier version didn't draw this distinction and
     it caused a real, reproduced failure: one text-only misidentification
     could inject an unrelated icon into the wrong rune's history, making
     that rune an easier false match for the *next* capture too, snowballing
     within a couple of presses into "every capture becomes the same wrong
     rune." Fixed - see the icon library section below.)
   - Separately, the app checks whether the "will be added to all Monsters
     unearthed after this Remnant" sentence is present in the tooltip, to
     confirm this was the passable slot. This *can't* come from the
     database - it's per-instance state (which slot you're looking at
     right now), not a property of "Soul Rune" in general - so it's the
     one thing genuinely read fresh off the screen every time.
   - If image matching finds two (or more) icons scored suspiciously close
     to each other - a couple of the visually-similar "rare tier" purple
     icons, say - it declines to silently pick one. If OCR doesn't resolve
     it outright either, a small popup shows those 2-3 image candidates as
     one-click buttons (icon + name); if OCR has a fuzzy (non-exact) guess
     that isn't already one of them, it's folded in as an extra button too
     ("OCR guess"), rather than being silently discarded. Explicitly saying
     "none of these" falls through to the full 33-name list - and, having
     been asked and declined, does *not* then quietly use that fuzzy OCR
     guess anyway; that would defeat the point of asking.
4. A brief toast confirms what was just captured (its name, or a red
   warning if it wasn't the passable slot) - by default it appears right
   next to your cursor (where you were already looking), or pinned to the
   top/bottom/center of the screen if you set `toast_position` to that in
   Settings.
5. The capture is added to the running list on the right side of the
   screen as a compact icon - always the **clean database icon**, never
   the raw (often noisy, transparent-background) screenshot crop. Hover it
   to see its name and effect text (also from the database) - nothing else
   is shown unless you hover, to keep a 9+ entry chain from taking over
   the screen. This hover works even while the overlay is
   locked/click-through in normal play - it's driven by polling the cursor
   position against each icon's screen position rather than native Qt
   hover events, since a click-through window never receives mouse events
   at all. A red **!** appears next to any capture that was **not**
   confirmed passable (meaning it won't actually carry to the next
   Remnant - you probably hovered the wrong slot).

   To fix a bad capture immediately, press the **undo-last hotkey**
   (`Ctrl+4` by default) - no need to unlock/click anything, it just pops the
   most recent entry off the list. For discarding an *older* entry
   specifically, click the small **x** next to it instead (see "Moving
   the overlay" below - that one needs the overlay unlocked, since a
   click-through window can't receive clicks by definition).

## Reset behavior

Same as before: a background thread tails `Client.txt` for zone changes.
Entering a hideout is ignored; entering what looks like a freshly
generated map pops up a "reset the tracker?" confirmation (auto-dismisses
as "keep tracking" after 12s if ignored). A manual **Reset tracker**
button always sits in the control panel regardless of whether that
detection fires correctly.

## Moving the overlay

The rune list is click-through by default so it doesn't block gameplay
clicks (and its **x** discard buttons can't receive clicks either, for the
same reason). Click **"Unlock rune list to move it"** in the control panel
to drag it wherever you want and use the **x** buttons, then **"Lock rune
list in place"** when done to go back to click-through. Both windows
remember their position across restarts (`data/positions.json`).

## Setting the hotkey / other settings, live

Right-click (or double-click) the tray icon in the Windows notification
area → **Settings**. You can rebind the capture hotkey and the undo-last
hotkey (click the button, then just press the key combo you want - it's
recorded directly, no need to type pynput's `<f9>`-style syntax; Save
refuses if you set them to the same key), change the `Client.txt` path,
and tune the capture region. Hit **Save** and it applies immediately - the
hotkey listener and log watcher both restart themselves in the background,
no need to relaunch the app. The tray menu also has **Undo last capture**,
**Reset tracker**, and **Quit**.

## Running it

Either from source:

```bash
pip install -r requirements.txt
python main.py
```

...or as a standalone double-click-able exe - see "Building the .exe"
below. Either way, `Client.txt` is auto-detected from common Steam/GGG
paths on first run; if it's not found, set it from the Settings dialog
(tray icon) instead of hand-editing `config.json`.

## Building the .exe

```powershell
.\build.ps1
```

This installs `pyinstaller` and produces `dist\PoE2RuneTracker\` - a
folder containing `PoE2RuneTracker.exe` plus its dependencies. Copy the
whole folder wherever you like and double-click the exe; `config.json` and
`data/` are created next to it on first run (not buried inside the
bundle), so Settings changes and your capture history persist normally
across runs. Re-run `build.ps1` after any code change to rebuild.

There's no installer/shortcut/autostart setup here - just the exe. Ask if
you want Start Menu shortcuts or launch-at-login added.

## Tuning (config.json, or Settings from the tray icon)

- `record_hotkey` / `undo_hotkey` - pynput hotkey strings, e.g.
  `"<ctrl>+3"` / `"<ctrl>+4"`. Easiest to set via the Settings dialog
  instead of editing these by hand.
- `capture_delay_ms` (default 150) - waits this long after the hotkey
  before actually grabbing the screen. Games commonly have a short hover
  delay before a tooltip updates to the newly-hovered target; capturing
  instantly can catch the *previous* tooltip still rendered (the icon
  already looks right, but OCR reads stale text) - if you see a capture
  get identified as whatever you tracked last even though you moved to a
  clearly different rune, raise this value.
- `capture_width` / `capture_height` - region grabbed around the cursor.
  Defaults are large (900x700) and centered (`capture_offset_x/y = 0`) on
  purpose: PoE2's tooltip appears to reposition itself relative to the
  cursor depending on proximity to a screen edge (e.g. it renders above
  the icon when you're centered on screen, but can shift when you're near
  the edge) - rather than chase that with a fixed offset, the box is just
  big enough to catch it wherever it lands. If you want a smaller/faster
  capture and mostly work centered on screen, you can shrink it and add an
  offset, but expect edge cases near screen borders to need the bigger box.
- `capture_offset_x` / `capture_offset_y` - shifts that region relative to
  the cursor, `0` by default for the reason above.
- `icon_crop_size` - size (px) of the icon thumbnail cropped at the cursor
  position, used for image matching (the primary identification method)
  and as the signature for a brand-new (never-seen) icon.
- `overlay_icon_size` - size (px) the tracked icons render at in the
  overlay column.
- `toast_position` - where the capture-confirmation toast appears:
  `"cursor"` (default, right next to where you were already looking),
  `"bottom"`, `"top"`, or `"center"` of the screen.

## Diagnosing a bad capture

When neither identification path is confident, the "Which rune is this?"
popup shows *why* directly - no need to dig up files:
- the closest image match found and its score vs. the threshold it needed
  to clear (e.g. `closest icon match: 'Fire Rune' (score 185, needs
  <=140)` - a score close to 140 means "nearly matched, tighten crop
  alignment"; a score well over that means "this icon type has no decent
  reference yet"),
- exactly what OCR read (`OCR saw: [...]`) - garbage or empty text here
  points at capture-region alignment, not the matching logic.

Every hotkey press also overwrites `data/last_capture_debug.png` (the full
OCR region) and `data/last_capture_icon_debug.png` (the icon crop) if you
need to see the actual pixels - e.g. to check whether a hover
highlight/glow on the active icon is throwing off its color signature.

## The icon library

`data/icon_library.json` + `data/icon_library/*.png` is the *live*,
self-growing library (auto-created, gitignored) - separate from the
read-only seed data checked into the repo. It stores, per rune name: the
clean display icon and effect text (from the poe2db seed data, if this
name was one of the 33 scraped), and a **history of appearance
signatures**: the original seed signature, kept permanently, plus up to
`HISTORY_SIZE - 1` (default 5) of the most recently confirmed *live*
captures, oldest evicted first - not a single signature that gets
overwritten. `data/ocr_aliases.json` is a small separate flat map of
`garbled OCR text -> resolved name` (see "learned-alias table" above),
also auto-created and gitignored.

Matching a captured icon against this library is a **masked average color
difference**, not a generic perceptual hash. The seed icons are
transparent-background images; a live screenshot capture is always
opaque with the *real* game background behind it. Comparing them naively
(e.g. hashing both after pasting onto some made-up flat background) is
mostly measuring background mismatch, not rune identity - that was the
actual cause of most failed matches, not the matching algorithm itself.
Instead, each reference signature's own alpha channel says which pixels
are the icon glyph; only those pixels are compared, so whatever's behind
the icon in the live capture mostly doesn't affect the result. The
signature is a 48x48 pixel grid, not smaller - a coarser grid loses enough
glyph detail that the 10 "rare tier" purple icons (Soul, Death, Power,
Sky, Oath, Bond, Ward, Time, Life, Earth - visually similar to each other,
sharing the same outer hex-and-glow style, differing only in the inner
swirl) become hard to tell apart.

**Why a history instead of one signature.** A rune's real in-game
appearance isn't a single fixed image - a hovered/active icon commonly
gets a brightness or glow boost the poe2db seed render doesn't have, and
different Remnant locations can put different lighting/backgrounds behind
it. A single reference (even a "self-correcting" one that gets overwritten
by the latest capture) can only ever represent one of those states at a
time - confirming a bright/glowing capture would silently make the normal
state harder to match afterward, and vice versa. Keeping a small set of
real confirmed exemplars per rune and matching against whichever one is
*closest* (nearest-neighbor style) lets both states - and the seed
reference - stay matchable at once, and the library gets more reliable
correctly the more it's actually used, without needing a bigger single
signature or any explicit "mode" detection. Confirmed with a synthetic
test: a deliberately overexposed capture that the seed signature alone
can't match (score 160, needs <=140) becomes matchable, via the newly
added exemplar, the moment it's confirmed once - and the original normal-
brightness capture still matches too, unaffected.

**Only image-corroborated captures grow the history.** A capture is only
added to an entry's history if image matching itself already found it
plausible (a direct hit, or one of a close-call disambiguation's own
candidates) - never for a capture resolved purely by OCR text or a manual
pick, since there's no evidence in that case the icon actually resembles
that entry. This was learned the hard way: an earlier version added
*every* resolved capture to history regardless of path, and one honest
OCR misreading was enough to inject a foreign icon into the wrong rune's
history - which then made that rune a slightly easier nearest-neighbor
match for the *next* capture too, adding another wrong exemplar, and
compounding within a couple of presses into every subsequent capture (of
any rune) misidentifying as that one contaminated entry. Fixed by gating
history growth on `trust_visual` in `identify()`/`register_capture()`.

Calibrated against all 33 real seed icons composited onto several
simulated backgrounds with brightness and resize-jitter variation (792
cases - `tools/accuracy_benchmark.py`, safe to re-run after any matching
change): true matches scored up to ~115 (out of a 0-765 scale), the worst
confusion among the purple family scored 172+ - `MATCH_THRESHOLD` in
`src/icon_db.py` sits comfortably in that gap.

To add more seeded runes later (if GGG adds new Remnant rune types):
inspect the `RemnantRune*`/`RemnantRareRune*` icon filenames referenced in
any rune's poe2db.tw page (e.g. view-source on `poe2db.tw/us/Soul_Rune`
and search for `.webp`), add the new suffix to `CANDIDATE_SUFFIXES` in
`tools/scrape_remnant_runes.py`, and re-run it:

```bash
python tools/scrape_remnant_runes.py
```

This only touches `data/rune_icon_seed.json`/`data/seed_icons/` (the
checked-in seed), never the live library - existing users just pick up
new seed entries automatically since seeding only fills in names it
doesn't already have.

## Known accuracy caveats (untested against a live client)

1. **Capture region alignment** - the icon crop (used for the primary,
   image-match identification path) is a separate, tighter region than
   the OCR box, so it's less prone to misalignment - but both still depend
   on tuning `capture_offset_y`/`icon_crop_size` against your actual UI
   scale. If a rune ever gets misidentified or shows as unrecognized, check
   the control panel status line and the debug PNGs (below).
2. **The OCR-to-database lookup can still fail to resolve** on a genuinely
   bad capture (garbled or empty text), same as image matching can fail to
   find a confident match - when *both* fail, you get the manual-pick
   popup rather than a wrong guess. This is intentional: the app would
   rather ask once than silently show something incorrect.
3. **Passable detection** relies on OCR correctly reading the phrase
   "unearthed after this Remnant" - matched loosely (both key words
   present, joined across OCR line breaks) to tolerate minor OCR noise.
   There's no image-based fallback for this one (it's not visible on the
   icon itself), so a badly-misaligned capture that finds no text at all
   also can't confirm passable status - it'll register the rune (via image
   match) but always as "not confirmed passable" in that case.
4. **Image matching is calibrated against simulated capture conditions**
   (all 33 real seed icons composited onto several synthetic backgrounds
   with brightness/resize-jitter variation - 792/792 correct via
   `tools/accuracy_benchmark.py`), but hasn't been validated against an
   actual PoE2 screenshot yet. If it ever misidentifies one rune as another
   - as opposed to just failing to match at all, which is the safe failure
   mode - that's a sign `MATCH_THRESHOLD` in `src/icon_db.py` needs
   tightening; if it fails to match things that should match, loosening it
   or bumping `icon_crop_size` (more of the icon in frame) are the first
   things to try. Every real confirmed capture also adds to that rune's
   signature history (see "The icon library" above), so accuracy against
   real screenshots should improve the more the app is actually used, even
   without touching `MATCH_THRESHOLD`.
5. **"Likely map" reset detection** (`Generating level ...` log-line
   heuristic) is carried over from PoE1 tooling and unverified against a
   real PoE2 `Client.txt`. The manual reset button always works regardless.

## Project layout

```
main.py                     entry point - wires hotkey/log watcher/overlay/tray together
build.ps1                    PyInstaller build script -> dist/PoE2RuneTracker/
config.json                  all tunables (editable directly, or via Settings)
data/rune_icon_seed.json      checked-in seed data (name/mods/icon) for all 33 known runes
data/seed_icons/*.webp        checked-in seed icons, scraped from poe2db.tw
data/icon_library.json        the LIVE, self-growing icon library - per-entry signature HISTORY (auto-created)
data/icon_library/*.png       clean display icons backing the live library (auto-created)
data/ocr_aliases.json        learned "garbled OCR text -> resolved name" map (auto-created)
data/session.json            current run (auto-created)
data/history.jsonl           completed runs, one JSON object per line (auto-created)
data/captured_icons/*.png    per-entry icon copies shown in the overlay (auto-created)
data/positions.json          remembered overlay window positions (auto-created)
tools/scrape_remnant_runes.py one-off scraper -> data/rune_icon_seed.json + seed_icons/
tools/accuracy_benchmark.py   synthetic image-matching accuracy test, re-run after matching changes
src/capture.py                cursor-centered screenshot grab + icon crop
src/tooltip_parse.py          OCR -> name-guess (a DB lookup key, never shown) + passable-flag
src/icon_db.py                 the self-growing icon library: appearance matching + display assets
src/name_prompt.py            NamePromptDialog (last resort, full list) + DisambiguationDialog (close call, one-click)
src/log_watcher.py            Client.txt tail + area-type classification, live-restartable
src/hotkeys.py                global hotkey listener, live-rebuildable
src/hotkey_capture.py         "press a key" widget -> pynput hotkey string
src/settings_dialog.py        live settings dialog (hotkey, log path, capture region, icon size)
src/tray.py                   system tray icon + right-click menu
src/tracker_state.py          in-memory run state + persistence
src/overlay.py                the five PySide6 windows (list, control panel, hover popup, capture toast, map popup)
src/winutil.py                click-through / no-activate win32 window styles
src/positions.py              drag-to-move position persistence
```
