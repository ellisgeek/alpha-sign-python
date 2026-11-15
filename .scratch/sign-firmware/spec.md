# Spec: Dump, study, and modify the 4120C's firmware

Status: needs-triage

Read the 4120C's firmware out of its EPROM and keep a verified copy. Then study it to
answer what the manual leaves open, and finally modify it, or replace it, to change the
built-in animations, fonts, or behavior.

## What is known

- The firmware is on an EPROM in a socket. Alpha's own upgrade procedure for the Series
  4000 (4120C included) is to swap that chip. It sits at the end of the Sign opposite
  the power supply.
- The 4120C reported firmware `10184403`, revision `O`, dated `1206`
  (docs/hardware-results.md). The EPROM label probably reads something like
  "1018-4403" with a revision letter.
- A Hackeriet teardown of a sibling 4200C (firmware label "4200c CUST 1018-6008e")
  found:
  - a TS80C32X2, an Intel 8051-compatible microcontroller;
  - a 128 KB dump, treated as two 64 KB banks, probably switched through port P1;
  - both banks starting with `LJMP 0x0100` and an "ADAPTIVE MICRO SYSTEMS, INC. 1991"
    copyright;
  - a display driver fed one row at a time from the bottom, red data then green.

  It is a different model with different firmware, but likely the same platform.

None of this is confirmed for our 4120C until the Sign is opened. Everything the
Hackeriet page says is restated in `docs/reference/hackeriet-4200c.md`.

## Ground rules

- **The original EPROM is never erased or written.** It is read, then stored. Every
  experiment runs on a copy, so a mistake costs a reflash, not the Sign.
- **The dump stays out of the repository.** It is Adaptive Micro Systems' copyrighted
  code. Keep it in a private location, and list `*.bin` and the dump folder in
  `.gitignore`. Hashes and notes about it may be committed; the bytes may not. Tools
  that read a dump take its path as an argument.
- **Anything extracted from the dump follows the same rule** (fonts, animation frames)
  until ADR 0003 (see `.scratch/emulator-display-capture/spec.md`) and the license
  question there say what may ship.
- **Power off and ground yourself** before touching the board. Keep the EPROM's
  orientation notch photographed before pulling it.

## Equipment

- A Phillips driver for the end cover (torque it back to 24 inch-pounds, per Alpha's
  procedure).
- A chip extractor for the socket type found (DIP or PLCC).
- A universal programmer that reads and writes the chip type found, e.g. an XGecu
  T48 (TL866-3G) for 27C010-class parts.
- For modifying, any one of these:
  - UV-erasable EPROMs of the same type and a UV eraser;
  - a pin-compatible flash part (e.g. SST39SF010A for a 27C010), with the
    write-enable pin handled;
  - an EPROM emulator, such as the open-source EPROM EMU NG. This is the fastest
    loop: build, upload, reset, no chip burning. It is recommended once changes start.
- Optional: a logic analyzer, to watch the bank-switch pin and the display driver lines.

## Phases

### 1. Identify (no risk)

Open the end cover and photograph the board on both sides. Record the EPROM label and
part number, the socket type, the microcontroller, the RAM and its backup battery, the
crystal frequency, and the display driver connector. Write this up in
`docs/hardware-4120c.md`, with the photos kept outside git if they are large.

Exit: the EPROM part number and the CPU are known, and the right programmer and spare
chips can be bought.

### 2. Dump (low risk)

Pull the EPROM. Read it three times, from both ends of the programmer's chip list if it
offers auto-detection, and compare the SHA-256 hashes. Read it once more after
reseating it. Put the original back, and check that the Sign boots and still reports
`10184403` rev `O`. Record the size and hashes in `docs/hardware-4120c.md`.

Exit: one dump whose hash four reads agree on, and a Sign that works as before.

### 3. Study (no risk to the Sign)

Load the dump into Ghidra as 8051 code, with the two banks as separate overlays. Find
the bank switch first, because the code can't be followed across banks without it.
Then look for these, roughly in order:

- **The serial protocol parser.** Search for the Command Codes as compared constants
  (`A`, `B`, `E`, `F`, `G`, `H`, `I`) and the Special Function labels. Name its
  functions after `docs/spec.md`'s terms.
- **The open questions from the hardware results.** These include:
  - the 9 reserved bytes and the free-memory figure 5 short;
  - the 26 Response NULs;
  - the oversized-write rules;
  - why STRING `T` 100 + TEXT `A` 1,000 left 899 bytes;
  - why a 14-byte write cost 7;
  - whether `R` in a programmable tone counts the first play.

  Each answer goes into `docs/hardware-results.md`, citing the address.
- **Font tables.** Search for glyph bitmaps: rows of bits per character, in a layout
  to be found. Once the display-capture effort has a few glyphs captured, search the
  dump for their bit patterns to find the tables directly.
- **Special Graphics and Special Modes.** Frame data or drawing routines for THANK YOU,
  NO SMOKING, FIREWORKS, and the rest, and the Mode routines with their timing loops.
- **Integrity checks.** Any checksum the firmware runs over itself at boot. A modified
  image must pass it.

Compare against the public 4200C dump: shared routines line up and differences point at
model-specific data (display width, memory size).

Exit: an annotated Ghidra project, kept private, and a written map (addresses of the
parser, font tables, animation data, and checksum) in `docs/hardware-4120c.md`.

### 4. Extract (no risk)

A tool reads a dump and writes the font tables and animation frames as data files in
the capture format of `.scratch/emulator-display-capture/spec.md`. Data taken from the
ROM is exact. Camera captures then become checks on the extraction, not the only source.

This phase can replace most of that plan's glyph and Special Graphics capture. Its Mode
timing work still needs video, unless the timing loops can be read with the crystal
frequency.

### 5. Modify (risk to a copy only)

Start with a change that is easy to see and harmless:

1. Patch a string, such as the power-up test message. Fix the checksum, run it from
   the EPROM emulator or a burned copy, and confirm the Sign boots and shows it.
2. Replace one Special Graphic's frames with new ones, built by a tool from the
   emulator's frame format, so the same files drive both.
3. Change a font glyph.
4. Larger changes: new Special Graphics in unused codes, protocol extensions, faster
   Modes. Each is its own issue and its own ADR when it changes what the library must
   support.

The library must work with stock firmware. A modified firmware is a new firmware
revision: the library and the emulator treat it as data (a firmware field or Reading),
never a code fork.

### 6. Rewrite (optional, large)

Write new firmware for the 80C32 that speaks the Alpha 1.0 subset the library uses,
with the display driver and serial timing taken from phase 3. Only worth starting if
phase 5 shows that patching can't reach what is wanted. If it happens, it is its own
project with its own spec.

## Running the real firmware in the emulator (idea)

With the dump and the display driver understood, an 8051 core could run the real
firmware inside the emulator, feeding its display-driver output to the page. The
emulator would then match the Sign exactly, Modes and all, with no capture at all. It is
large. Revisit after phase 3 shows how much of the hardware the firmware touches
(timers, interrupts, the IR receiver, the battery-backed RAM).

## Work, in order

1. Identify the hardware (phase 1). Needs the Sign opened, by a person.
2. Buy the programmer and spare chips that phase 1 calls for.
3. Dump and verify (phase 2), and the `.gitignore` entries first.
4. Ghidra setup with banking; the protocol parser mapped.
5. Answer the hardware-results open questions from the code.
6. Find and extract font tables. Blocked by 4.
7. Find and extract Special Graphics. Blocked by 4.
8. Find the integrity check; patch a string and boot it (phase 5, step 1). Blocked by 4.
9. Further modifications, one issue each. Blocked by 8.

## Open questions

- Is the 4120C's board the same as the 4200C's (80C32, 128 KB, two banks)?
- Is the EPROM DIP or PLCC, and which part, to buy spares and a programmer?
- Does the firmware check itself at boot, and how?
- Where are the Memory Configuration and Files kept? Battery-backed RAM is likely; if
  so, pulling the EPROM with the power off keeps them.
- Which repository, if any, may hold derived data (fonts, frames)? See ADR 0003 in the
  display-capture plan.

## Sources

- Hackeriet wiki, Ericsson / Alpha-American 4200C LED Sign:
  https://wiki.hackeriet.no/infra/led-display-sign (restated in
  `docs/reference/hackeriet-4200c.md`)
- Alpha manual with the Series 4000 EPROM swap procedure:
  https://www.scribd.com/document/563407063/Alpha-Manual
