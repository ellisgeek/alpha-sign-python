# Draw the emulator's fonts from the manual's Appendix O

The emulator draws text with the glyphs in Appendix O of the protocol manual,
"Font character sets" (pp. 141-216). There, every font is drawn as a grid of dots,
one per pixel of the character cell. `docs/reference/extract_fonts.py` reads those
grids out of the PDF and writes `emulator/src/core/display/manual-glyphs.ts`. Fonts
used to be drawn by hand for this project, and `.scratch/emulator-display-capture`
planned to copy them from video of a real Sign.

Appendix O was missed at first: its glyphs are vector drawings, so text extraction
shows only the labels (`CHR065`). The manual is the source this project trusts for
everything else, so it is the source for glyphs too. It also covers fonts a 4120C
has but no capture session had reached: seven high fancy, ten high, and the 15- and
16-high sets.

## Consequences

- This reverses the emulator spec's "fonts drawn for this project, not copies of
  Alpha's fonts". The glyphs are Alpha's designs. The Python package does not contain
  them. The repository is public under the MIT license, and the README says the glyph
  data and the test images drawn with it are copied from the manual and not covered by
  that license (decided 2026-11-15).
- The manual gives each glyph's cell, not the spacing a Sign uses. The widths of a
  space and a half space (7EH), and the gap between characters, are still
  assumptions, and the display capture still measures them.
- The data is generated. Fix the extractor, not `manual-glyphs.ts`.
- Characters past 7FH, the 8-high sets, and the true-descender and "fat" sample
  glyphs are not extracted yet.
