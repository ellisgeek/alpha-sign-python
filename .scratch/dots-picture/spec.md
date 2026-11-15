# Spec: Write and read SMALL DOTS PICTURE Files

Status: resolved

Let an application developer put a picture on a Sign: build a **DOTS PICTURE File**'s
content, write it, call it from a TEXT File, and read it back. Page numbers are from
the protocol manual (`docs/reference/M-Protocol.pdf`).

## Facts from the manual

- Write SMALL DOTS PICTURE is Command Code `I`; Read is `J` (pp. 39-41). Neither is
  marked with a Protocol Version, so both are Alpha 1.0 and earlier.
- Data Field: File Label, Height (2 hex digits, 0-31), Width (2 hex digits, 0-255),
  then one Row Bit Pattern per row, each followed by CR. LF after CR is optional and
  is not sent back by a read. The last CR is optional (p. 40).
- After the Width there must be at least 100 ms of silence before the rows (p. 40).
- Pixel characters: `0` off, `1` red, `2` green, `3` amber, `4` dim red, `5` dim
  green, `6` brown, `7` orange, `8` yellow. "Some signs do not support the full range
  of colors" (p. 40).
- A row with too many characters is cut at Width; one with too few is padded with off
  pixels (p. 40).
- Height and Width "must match" the File's entry in the Memory Configuration (p. 39).
- The Response to `J` carries Command Code `I`, the File Label, and the same data
  (Table 24, p. 41).
- A TEXT File calls a picture with Control Code `14H` and the File Label (p. 81).
- Table 60 (p. 76) is a worked example: a 15x9 arrow written to File `A` of a 4160C,
  with no Checksum.
- LARGE (`M`/`N`) and RGB (`K`/`L`) DOTS PICTURE Files are for AlphaVision and Alpha
  3.0 Signs. They stay out of scope.
- Table 70 note 1: a graphic must fit the Sign's resolution.

## Decisions

- **Names.** `DotsPicture` is the content (a grid of pixels). `PixelColor` is the
  enum of pixel codes. `DotsPictureRef(label)` is the Segment that calls a picture.
  `Sign.write_dots_picture(label, picture)` and `Sign.read_dots_picture(label)`.
  `DotsPictureFile` stays the Memory Configuration entry.
- **Building a picture.** `DotsPicture` is frozen: a tuple of rows of `PixelColor`.
  `DotsPicture.parse(text)` reads one row per line in the manual's digits. No image
  loading (no Pillow); that may come later as an optional extra.
- **Rules that raise `ValueError`**: more than 31 rows or 255 columns, rows of
  different lengths, a character that is not a pixel code, a bad File Label.
- **Advisory validation** (warn, or raise in strict mode): a picture larger than the
  Sign Model's display; a Sign Model without `Capability.GRAPHIC`; a pixel other
  than off or red on a model without `Capability.COLOR`. Colors 4-8 on a tricolor
  model are not checked until hardware shows which ones work.
- **No size check against the Memory Configuration.** `Sign` does not track what it
  configured. The rule is documented on `write_dots_picture`.
- **Encoding.** The Command is sent as two Chunks with a 0.1 s pause after the Width,
  in single and nested Packets alike. Every row ends in CR, the last one too, and no
  LF is sent (as in Table 60).
- **Decoding a read is lenient**, as the manual says the Sign is: LF is ignored, a
  missing last CR is accepted, short rows are padded with OFF, and long rows are cut.
- **The `14H` Control Code** decodes to `DotsPictureRef` in place of `RawControl`.
  It needs `Capability.GRAPHIC`.

## Hardware checklist additions

| Item | Library's assumption | Test |
|---|---|---|
| Colors 4-8 in a DOTS PICTURE on the 4120C. | Not checked. | Witnessed: a picture with one column of each color. |
| A picture whose size differs from its Memory Configuration entry. | Not checked. | Automatic, needs erase permission: write a mismatched picture, read it back. |
| The 100 ms pause after the Width. | Needed (p. 40). | Automatic: write without the pause through a raw Packet, read back. |
| The bytes of a `J` Response. | Rows end in CR, the last one too. | Automatic: capture. |
| A picture called between two runs of text. | Drawn at the text cursor. | Witnessed. |

## Issues

See `issues/`. The Emulator slice is a separate branch after the library slices.
