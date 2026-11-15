# Spec: Capture a real Sign's display and copy it into the emulator

Status: needs-triage

Make the emulator's 4120C draw what a real 4120C draws: the same glyphs, the same Mode
animations and timings, the same Special Modes and Special Graphics, and the same color
effects. Everything is recorded from a real Sign on a phone, turned into pixel frames by
a capture tool, and copied into the emulator as data.

Page numbers are from the protocol manual (`docs/reference/M-Protocol.pdf`). The
hardware facts so far are in `docs/hardware-results.md`.

## Update, 2026-11-15: glyphs come from the manual

Appendix O of the manual (pp. 141-216) draws every font's glyphs as dot grids. The
emulator now uses them ([ADR 0003](../../docs/adr/0003-fonts-from-appendix-o.md)), so
glyph shapes need no capture. Capture still measures spacing (space, half space, gaps,
fixed width), character styles, positions, Modes, Special Modes and Graphics, and color
effects. Read "Fonts" and the glyph rows of the plan below in that light.

## Decision: exact copies

The emulator ships the real Sign's glyph bitmaps and animation frames. This reverses two
lines of `docs/emulator-spec.md`:

- "Fonts. The emulator ships its own bitmap fonts, drawn for this project ... not
  copies of Alpha's fonts."
- "Special Modes and Special Graphics. ... Drawings that copy Alpha's animations are
  not wanted."

Record the change as `docs/adr/0003-copy-the-real-signs-display.md` before any copied
data lands, and edit both lines. The glyphs and animations are Alpha's designs. Check
how that sits with the repository's license before a release publishes them.

## Goals

- Every font the 4000 Series has draws exactly as on a 4120C, for characters 20H-7FH
  (Appendix G). The fonts are the six with a Capability: five high, seven high, seven
  high fancy, ten high, full height, full height fancy.
- Wide, double-wide, and flashing characters, and fixed-width spacing, match.
- Every Standard Mode in Table 65 that the 4000 Series has moves frame for frame as on
  the Sign, at each Speed (1-5), with the Sign's timings.
- Every Special Mode (Table 66) and Special Graphic (Table 67) plays as on the Sign.
- Color effects match: autocolor (a plain write showed TALL in red, orange, and green on
  2026-11-15), rainbow 1 and 2, color mix, and CYCLE COLORS.
- Each copied item cites its capture: firmware, date, and the source video.

## Non-goals

- Characters past 7FH, and the fonts the 4000 Series lacks (stroke, shadow, slim, the
  BetaBrite 1036 fonts).
- Sign Models other than the 4120C. The tooling must not be specific to one, but only a
  4120C is captured now.
- Sound.
- Bit-exact copies of random effects (TWINKLE, SPARKLE, SNOW, and others that use
  randomness). These match in timing, density, and colors, not pixel for pixel. See
  "Random effects".

## The capture rig

- A phone on a tripod, square on to the Sign, filling the frame with the display.
- Focus and exposure locked (on iPhone: press and hold to set AE/AF lock), white
  balance fixed, room lights dim and steady.
- Static content (glyphs, colors): normal video at 30 or 60 fps. The tool averages
  several frames per item.
- Moving content (Modes, Special Modes, Special Graphics): slow motion at 240 fps,
  about 4.2 ms per frame. That resolves a 20 ms step.
- One continuous recording per session. Raw videos stay out of git: they are large, and
  only the frames derived from them are copied. Keep them in a folder named in the
  session manifest so that a capture can be re-derived.

## Pipeline

Three parts, each one a step that can be checked on its own.

### 1. Session runner (Python, in the library repo)

A script under `tools/display_capture/` drives the Sign through a **capture plan**: a
list of items, each one some content to show and how long to hold it. For each item it:

1. Shows a **marker**: a DOTS PICTURE (Command "I", p. 39) that encodes the item's
   number as lit columns in a fixed pattern, held for 1 s. The marker tells the
   analyzer where each item starts and which item it is, with no clock sync needed.
2. Blanks the display for a fixed gap.
3. Sends the item's content and logs the send time.
4. Waits the item's hold time.

It writes a **session manifest** (JSON): the Sign's firmware from General Information,
the date, the line settings, the plan, and each item's send time. The runner sends raw
Commands where the library refuses content. It does so the way the witnessed tests
already do, with strict mode off.

The library leaves writing DOTS PICTURE content out of scope. The runner builds the "I"
Command itself from p. 39, and Table 60 ("Write DOTS PICTURE file example") gives a worked example to test it
against.

### 2. Calibration

The first item of every session is a calibration set, sent as DOTS PICTURES so that
every pixel's true value is known:

- All pixels off, then each palette color in turn over the whole display (p. 40 pixel
  codes 1-8: red, green, amber, dim red, dim green, brown, orange, yellow).
- A checkerboard, and its inverse.
- Single lit pixels in the four corners.

From these the analyzer finds the 120x16 LED grid in the image (a homography from the
corner pixels, refined by the checkerboard) and learns each color's appearance. The
calibration passes when the checkerboards and color fields read back with no wrong
pixels. If they don't, the session is rejected before anything is copied.

### 3. Video analyzer (Python, in the library repo)

1. `ffmpeg` decodes the video. `ffprobe` gives each frame's presentation time, because
   phone video can have a variable frame rate.
2. Each LED's color is sampled at the center of its grid cell and classified against
   the calibration colors as off or one of the eight palette codes. That gives one
   120x16 matrix per video frame.
3. The marker frames split the video into items and number them. Each item is checked
   against the manifest.
4. Repeated identical frames are merged, so each item becomes a list of distinct
   frames, each with a start time and how long it lasted.
5. The output is one capture file per item, in the text format of
   `emulator/test/core/__golden__/` (one character per pixel), with a header giving
   the firmware, date, video, frame rate, and item.

LED multiplexing and PWM can flicker against the camera's shutter. The analyzer takes
the brightest reading over a short window, about one LED refresh period. It flags any
pixel that differs between neighboring frames of a held image, which would mean
flicker rather than motion.

## What to capture

| Set | Items | Notes |
|---|---|---|
| Glyphs | each font: 20H-7FH in HOLD, a few characters at a time with spaces between | The analyzer cuts glyphs at blank columns. The plan knows which characters each item shows. |
| Spacing | each font: runs like "AAAA", "A A", "il", and the same text in fixed width (1EH "1") | Gap between characters, space width, half space (7EH), fixed-width cell. |
| Character styles | wide, double-wide, flashing, in the seven high font | Flash period comes from the slow-motion video. |
| Positions | one line of text at top, middle, bottom, and fill, in each font | Baselines and vertical placement. |
| Colors | each color Control Code, then autocolor, rainbow 1 and 2, color mix | Autocolor may depend on the Frame or Line. Capture several strings. |
| Standard Modes | each Table 65 Mode the 4000 Series has, at Speed 1-5, with short and long text | Long text wraps or scrolls differently from short text. |
| Special Modes | each Table 66 Mode, 3 runs each | Three runs show which parts are random. |
| Special Graphics | each Table 67 Graphic, plus WELCOME and SLOT MACHINE, 2 runs each | Two runs confirm they repeat exactly. |
| Run Sequence timing | two Files of two Frames each | Hold time per Frame and the gap between Files. |

## Changing the emulator

- **Fonts.** A generator script turns the glyph captures into one TypeScript data
  module per font (`emulator/src/core/display/fonts/*.ts`). It replaces the drawn
  tables in `fonts.ts`, and `fontForCode` maps each code to its real font. The
  emulator project must not import from the Python package (the independence test), so
  the generated files are checked in, not read at build time.
- **Mode timings.** Measured values replace the constants in `modes.ts` (`stepMs`,
  `HOLD_MS`, `VERTICAL_STEP_FACTOR`, `FLASH_HALF_PERIOD_MS`), one set per Speed.
- **Standard Modes the emulator does not draw yet** (SCROLL, ROLL and WIPE IN and OUT,
  COMPRESSED ROTATE, EXPLODE, CLOCK, AUTOMODE). Each gets a drawing algorithm worked
  out from its captures and checked against them. AUTOMODE may be a recorded choice of
  other Modes. The captures will show.
- **Special Graphics.** These show no message, so they play back as recorded frame
  lists: a new "recorded animation" path in `build-display.ts`.
- **Special Modes.** These move the message, so they need algorithms, like the
  Standard Modes. For the random ones, see below.
- **Colors.** Autocolor, rainbow, and color mix are worked out from the captures.
  `docs/emulator-spec.md` currently says "Autocolor and the default color are drawn
  red", and that line changes.

### Random effects

TWINKLE, SPARKLE, SNOW, SPRAY, STARBURST, and EXPLODE may use randomness. Compare the
three runs of each. If they are identical, play the capture back. If they differ, write
an algorithm with a seeded random source that matches the captures' timing, density,
and colors. Its test checks those measures against the captures, not single pixels.

## Tests

- **Fidelity tests.** For each captured item, the emulator renders the same content on
  the same timeline, and the test compares its frames with the capture. A fixed item
  must match exactly. A random item must match in its measures. These tests replace the
  hand-approved goldens wherever a capture exists.
- **Analyzer tests.** A short synthetic video, made by rendering known matrices to
  images with blur and noise, must decode back to those matrices.
- **Runner tests.** The DOTS PICTURE encoder is tested against the manual's worked
  example (Table 60). The marker encoding is tested both ways: encode, then decode.

## Work, in order

Each line becomes an issue in `.scratch/emulator-display-capture/issues/`.

1. ADR 0003 and the `docs/emulator-spec.md` changes (the decision above).
2. DOTS PICTURE write in the runner, tested against Table 60. Then show a checkerboard
   on the Sign.
3. Prototype: one phone photo of the calibration set, read into a 120x16 matrix with
   no wrong pixels. This de-risks everything after it. If the grid or colors can't be
   read reliably, change the rig (diffuser, distance, exposure) before going on.
4. Session runner with markers and the manifest.
5. Video analyzer: frames, grid, colors, splitting, merging, capture files. Blocked by
   3.
6. Glyph and spacing session. Generate the font modules, replace `fonts.ts`, and
   re-approve the goldens. Blocked by 4 and 5.
7. Fidelity test harness. Blocked by 5.
8. Standard Mode session. Measure the timings, fix the drawn Modes, and add the
   missing ones. Blocked by 6 and 7.
9. Colors session, and the autocolor, rainbow, and color mix logic. Blocked by 7.
10. Special Graphics session, and recorded playback. Blocked by 7.
11. Special Modes session, with playback or seeded algorithms. Blocked by 8.

## Open questions

- Is 240 fps enough? The 4120C's refresh rate isn't known. The prototype (3) shows
  whether LED scanning bands the image.
- Can the camera tell dim red from off, and brown from amber, at one exposure? If not,
  calibrate at two exposures, or record colors in a separate pass.
- Does the Sign speed up or slow down a Mode with the amount of text? The short and long
  text captures answer this.
- Where do raw videos live long-term? A path in the manifest is enough for one person,
  not for a team.
- What does the repository's license say about shipping Alpha's glyphs and animations?
  This needs an answer before a release that includes them.
