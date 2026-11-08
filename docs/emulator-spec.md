# Spec: Sign emulator

This spec covers the Sign emulator that the main [spec](spec.md) lists as out of scope
("planned and needs its own spec"). Terms in **bold** are defined in
[GLOSSARY.md](../GLOSSARY.md). Page and table numbers refer to the Alpha Sign
Communications Protocol manual, 9708-8061F ([reference/](reference/)).

Status (November 2026): MVP built. "MVP and deferred work" at the end lists what is
built, the assumptions it makes, and what is not built yet.

## Problem Statement

A developer of `alpha_led_sign` has one real Sign, a 4120C, and every hardware checklist
item still waits for it. Until it is connected, the only test double is
`FakeTransport`. It records bytes and plays back canned Responses, but it does not act
on what it receives. It cannot show that a Memory Configuration followed by a TEXT File
write and a read gives the same Message back. It cannot show that a Run Sequence cycles,
or that a STRING File updates without blanking. Discovery with two Sign Addresses
can't be tested either, because the developer owns only one Sign.

The developer also can't see anything. A Message with the wrong Mode, color, or Display
Position passes every byte test and still looks wrong. Today the only way to find out is
to walk to a real Sign, if one is there. Contributors who own no Sign at all have no
way to try the library.

## Solution

A Sign emulator written in TypeScript. It acts like one or more Signs on a serial line
and draws what each Sign shows as an LED matrix in a browser page.

It has three parts:

1. A pure **core**. Bytes and their arrival times go in. Response bytes, with the times
   to send them, come out, together with a snapshot of each Sign's state. The snapshot
   holds the Files, the Memory Configuration, the clock, the Run Sequence, the Serial
   Error Status Register, the tones played, and what the display shows. The core has
   no I/O and no clock of its own. It follows the same rule as `alpha_led_sign.protocol`.
2. A **page** that runs the core in the browser and draws the display. Bytes reach it
   through a small bridge (TCP to WebSocket).
3. A **headless host** that runs the same core under Node with no page, behind the same
   TCP port. CI and the Python tests use it.

The Python library reaches the emulator with no new adapter. `SerialTransport` already
opens `socket://host:port`. Because the emulator is a separate program in another
language, it is a second implementation of the manual written from the manual itself.
When the library and the emulator agree, that is evidence. When they disagree, one of
them has misread the manual.

The emulator's answers are never hardware results. Where the manual is unclear, the
emulator has a setting for each reading, and the default is changed to match a real
Sign once [hardware-results.md](hardware-results.md) records one.

## User Stories

### Seeing the display

1. As an application developer without a Sign, I want to see what my code would show,
   so that I can build a display before I own the hardware.
2. As an application developer, I want the page to draw the display at the Sign
   Model's real size in pixels, so that I can judge whether my text fits.
3. As an application developer, I want each pixel drawn in the color the Sign would
   use (red, green, amber, and the mixes a tricolor Sign has), so that color Control
   Codes look right.
4. As an application developer, I want a red-only Sign Model to draw only red, so that
   I see what a 4120R owner would see.
5. As an application developer, I want each Frame drawn in its Mode (HOLD, ROTATE,
   FLASH, ROLL and WIPE in each direction, and the others), so that I can choose a Mode
   by looking at it.
6. As an application developer, I want a Mode the emulator can't draw yet to show as
   HOLD with a visible label naming the Mode, so that I know it was received and only
   the drawing is missing.
7. As an application developer, I want each Frame drawn at its Display Position (top,
   middle, bottom, fill), so that two-line layouts look right.
8. As an application developer, I want speed, font, wide, and flashing Control Codes to
   change how the text is drawn, so that I can see their effect.
9. As an application developer, I want the time and date Control Codes to show the
   emulated clock, so that I can check how they look.
10. As an application developer, I want a STRING File reference to show the STRING
    File's current content, so that I can watch a live value change.
11. As an application developer, I want writing a STRING File to update the display
    without blanking it, and writing a TEXT File to blank it (p. 37), so that I see the
    same difference a real Sign shows.
12. As an application developer, I want a Special Graphic to show as a placeholder
    animation labelled with its name, so that I know the Sign would play it.
13. As an application developer, I want the page to show which TEXT File and Frame are
    on the display, so that I can follow the Run Sequence.
14. As an application developer, I want the page to play a tone through the browser when
    the speaker is on, so that I can hear alerts.
15. As an application developer, I want the page to show each Sign on the line next to
    the others, labelled with its Sign Type and Sign Address, so that I can watch a
    network of Signs.

### Acting like a Sign

16. As an application developer, I want the emulator to act only on Packets whose
    Recipient matches its Sign Type and Sign Address, including wildcard Sign Types and
    `?` address patterns (p. 11), so that addressing mistakes show up.
17. As an application developer, I want a Memory Configuration to replace every File
    and erase its content (p. 21), so that the emulator behaves like the Sign.
18. As an application developer, I want a write to a File that is not in the Memory
    Configuration to be ignored, so that I find out I forgot to configure it.
19. As an application developer, I want a write larger than its File's size to be
    handled the way the Sign handles it, so that I find size mistakes.
20. As an application developer, I want the emulator to start with TEXT File `A` as
    every Sign does at power-up (p. 17), so that `show` works on a fresh emulator.
21. As an application developer, I want the Priority TEXT File to take over the
    display until it is cleared (p. 20), so that I can test urgent notices.
22. As an application developer, I want Run Times and Run Days to decide which TEXT
    Files run, using the emulated clock, so that I can test a schedule.
23. As an application developer, I want a Run Time or Run Day write to end the Priority
    TEXT File (p. 20), so that the emulator matches the manual.
24. As an application developer, I want to set the emulated clock from the library and
    from the page, so that I can test a schedule at any time of day.
25. As an application developer, I want a soft reset to keep memory and clear memory to
    erase it (pp. 21, 22), so that recovery code can be tested.
26. As an application developer, I want a Sign Address write (p. 26) to change the
    Sign Address the emulated Sign answers to, so that re-addressing can be tested.

### Reading back

27. As an application developer, I want a TEXT File read (p. 19) to return the
    Message as the Sign stored it, so that read and write round trips can be tested.
28. As an application developer, I want a STRING File read (p. 38) to return its
    content, so that live values can be checked.
29. As an application developer, I want Read General Information (p. 29) to report the
    firmware, clock, speaker, and memory left, so that `info` can be tested.
30. As an application developer, I want the Serial Error Status Register (p. 31) to
    record Checksum errors and other errors the emulator can detect, and to reset when
    read, so that `serial_errors` can be tested.
31. As an application developer, I want a Packet with a bad Checksum to be ignored and
    recorded in the register, so that I see what a damaged Packet does.
32. As an application developer, I want Control Codes the emulator does not model to be
    stored and read back unchanged, so that pass-through can be tested.
33. As an application developer, I want each Sign on the line to answer a Network
    Query 1 s + 0.5 s x its Sign Address after the query (p. 32), so that discovery
    timing can be tested.
34. As an application developer, I want two Signs at the same Sign Address to garble
    each other's answers (p. 32), so that discovery's handling of collisions can be
    tested.

### Timing

35. As a maintainer, I want the emulator to check for the 100 ms of silence after each
    STX in a nested Packet (p. 11), so that a missing pause is caught before it reaches
    a real Sign.
36. As a maintainer, I want the emulator to ignore data that arrives during the silence
    a tone needs (p. 27, note 4), so that a missing wait after a tone is caught.
37. As a maintainer, I want the core to take time as an input, so that its tests run
    instantly and never sleep.
38. As a maintainer, I want byte times taken where bytes enter the emulator (at the TCP
    port), so that WebSocket delay can't fake or hide a missing
    pause.

### Readings of unclear points

39. As a maintainer, I want each hardware checklist item that changes how a Sign
    behaves to have an emulator setting with one value per reading, so that I can run
    the library against either reading.
40. As a maintainer, I want each setting's default to cite where it came from (the
    manual, or a row in hardware-results.md), so that the emulator stays traceable.
41. As a maintainer, I want the defaults to follow hardware-results.md once a row is
    filled in, so that the emulator becomes a record of how real Signs behave.

### Sign Models

42. As a maintainer, I want an emulated Sign's model to be data (Sign Type, pixel size,
    lines, colors, memory, Protocol Versions), so that adding a model needs no new code.
43. As a maintainer, I want the emulator's model data entered from Table 5 and the
    brochure, not read from the library's capability JSON, so that a mistake in the
    library's extraction can't be repeated by the emulator.
44. As an application developer, I want to put several Signs of different Sign Models
    on one line, so that I can test Sign Types and broadcasts.
45. As an application developer, I want a Control Code from a Protocol Version the
    emulated Sign does not accept to be ignored, as the Sign would ignore it, so that I
    see the cost of sending it.

### Connecting

46. As an application developer, I want to point `Sign.open` at a `socket://` URL and
    reach the emulator, so that I need no new Transport.
47. As an application developer, I want to start the bridge and open the page with one
    command, so that seeing my display takes no setup.
48. Dropped: opening a real serial port from the page (Web Serial). See Out of Scope.
    The number is kept so that later story numbers, which the tests cite, stay the same.
49. As a maintainer, I want the headless host to pick a free port and print it, so that
    test runs can start it in parallel.
50. As a maintainer, I want a control channel on the headless host to reset it, choose
    the Signs on the line and their settings, and fetch snapshots, so that a test can
    set up and check the emulator.

### Testing the library with the emulator

51. As a maintainer, I want the automatic hardware tests to run against the emulator
    with one pytest marker, so that the hardware suite works offline and in CI.
52. As a maintainer, I want tests that erase memory or change the Sign Address to be
    allowed against the emulator without the hardware opt-in flags, so that the whole
    automatic suite runs.
53. As a maintainer, I want emulator tests to be skipped with a clear reason when Node
    is not installed, so that a Python-only checkout still passes.
54. As a maintainer, I want captures made against the emulator to be marked as
    emulator captures and refused as test vectors, so that they can never replace a
    `# PROVISIONAL` vector from a real Sign.
55. As a maintainer, I want discovery tested against two emulated Signs at two Sign
    Addresses, so that sorting and timing are checked before I own a second Sign.
56. As a contributor without a Sign, I want to try the witnessed tests while watching
    the page, so that I can learn the checklist, knowing the results are not recorded.

## Implementation Decisions

### Why TypeScript in the browser

- Graphical output is required. The browser draws an LED matrix with a canvas and plays
  tones with Web Audio, with no GUI toolkit to install.
- A second language makes the emulator independent by construction. It can't import
  the library's encoder, decoder, or data. CLAUDE.md requires expected bytes from an
  independent source, and an emulator that shared the library's code would only check
  the library against itself.
- The cost: the Python tests can't run the emulator in-process with virtual time.
  Through the headless host, pauses are real, so a test that sounds a tone takes 3 s.
  The core's own tests keep virtual time.
- This decision should be recorded as ADR 0002.

### Architecture

- The core is pure. It has no I/O, no timers, and no clock. Time is an input in
  milliseconds. It never imports browser or Node APIs, so the page, the headless host,
  and the tests all run the same core.
- The core models a **Line**: the serial network that one or more emulated Signs listen
  on. Every Sign on the Line sees every byte. Responses from several Signs are merged
  in time order, and answers that overlap in time are garbled together.
- The core's shape (a sketch; names may change):

  ```ts
  interface Line {
    receive(bytes: Uint8Array, atMs: number): void;  // bytes from the library
    advance(toMs: number): Outgoing[];               // runs the Signs up to toMs
    signs(): EmulatedSign[];
  }
  interface Outgoing { bytes: Uint8Array; atMs: number }  // to send to the library
  interface EmulatedSign {
    readonly model: EmulatorModel;
    readonly settings: Readings;
    snapshot(): SignSnapshot;
  }
  interface SignSnapshot {
    signType: string; signAddress: number;
    memoryConfiguration: FileEntry[]; files: Record<string, StoredFile>;
    clock: EmulatedClock; runSequence: RunSequence; priority: StoredFile | null;
    serialErrors: number; speakerOn: boolean; tones: TonePlayed[];
    display: DisplayState;  // what is shown, as a model and as pixels
    ignored: IgnoredInput[];  // Packets and codes dropped, with the reason
  }
  interface DisplayState {
    fileLabel: string | null; frameIndex: number; mode: string; position: string;
    lines: TextRun[][];   // text and color runs per line
    pixels: { width: number; height: number; colors: Uint8Array };  // palette index per pixel
  }
  ```

- `ignored` exists because a real Sign ignores bad input without saying so. The
  emulator says so, in the snapshot and on the page.
- The emulated clock starts from the host's time when the emulator starts, and then
  moves forward with the time input. A Set Time or Set Date Command changes it.

### Parts and their interfaces

- **Core.** The Line, the emulated Signs, the Packet parser, the display model, the
  renderer that turns the display model into pixels, and the Response encoder.
- **Page.** Runs the core, steps it on animation frames with the browser's clock, draws
  the pixels on a canvas, plays tones, and shows the snapshot (Files, clock, Run
  Sequence, register, ignored input). Settings and the Signs on the Line can be changed
  from the page. Input comes from the bridge over WebSocket.
- **Bridge.** A small Node program. It listens on TCP for the library, stamps each byte
  with its arrival time, and relays it to the page over WebSocket. Bytes from the page
  carry the time to send them, and the bridge sends them then.
- **Headless host.** The same Node program with no page: it runs the core itself. It
  listens on a TCP port (port 0 picks a free one and prints it) and offers a control
  channel over HTTP with JSON: reset, set the Signs on the Line and their settings, set
  the clock, and fetch snapshots.
- One command starts the bridge and opens the page. Another starts the headless host.

### What the emulator models

- **Packets.** Sync bytes, SOH, Sign Type, Sign Address, then STX, Command, optional ETX
  and Checksum, repeated, then EOT (pp. 10-14). A Command with a bad Checksum is
  ignored and recorded in the Serial Error Status Register (p. 31).
- **Recipients.** Sign Type matching, including the group Sign Types such as `Z` (all
  Signs) and `1` (all one-line Signs), and Sign Address `00` and `?` patterns (p. 11).
- **Commands.** Every Command the library sends today: write and read TEXT File, write
  and read STRING File, and the special functions (Memory Configuration, clear memory,
  time, date, day, time format, speaker, tones, soft reset, Run Times, Run Sequence,
  Run Days, serial error read and clear, General Information, Sign Address, Network
  Query). A Command the emulator does not know is ignored and listed in `ignored`.
- **Content.** TEXT Files are parsed into Frames and Segments. Control Codes that the
  emulator does not model are kept as bytes, so that a read returns them unchanged.
- **Memory.** The Memory Configuration decides which Files exist and their sizes.
  Memory left is the model's memory minus each File's size and overhead, with the
  overhead and the DOTS PICTURE rule taken from settings.
- **Display.** The Run Sequence chooses the TEXT File, Run Times and Run Days filter it
  by the emulated clock, and the Priority TEXT File overrides it. Each Frame is laid
  out at its Display Position and drawn in its Mode. Mode timings are approximations:
  the manual does not give them.
- **Fonts.** The emulator ships its own bitmap fonts, drawn for this project, one per
  font Control Code the 4000 Series has. They are not copies of Alpha's fonts, so
  text widths are close to a real Sign's but not exact.
- **Modes, in order.** First HOLD, ROTATE, FLASH, ROLL and WIPE in each direction, and
  the Display Positions. Then the remaining Alpha 1.0 Modes. Special Modes and Special
  Graphics are placeholders until a real Sign has been watched.

### Readings (settings for unclear points)

A **Reading** is one emulator setting that picks how an unclear point in the manual
behaves. Each one has a default with a cited source. Each one maps to a row of the
hardware checklist or to an assumption written here.

| Reading | Values | Default and source |
|---|---|---|
| Per-File overhead | 11 or 13 bytes | 11 (p. 27, note 1) |
| DOTS PICTURE size in the memory budget | counted or not | not counted (p. 27, note 1) |
| General Information length | 28, 29, or 29 plus NUL | 29 (p. 29 field list) |
| Tone repeats | `R` plays or `R + 1` plays | `R + 1` (the library's assumption, p. 22 unclear) |
| NEWS FLASH and TRUMPET form | letters, hex 3AH/3BH, or both | both (Table 66 gives both) |
| NEW_PAGE and double height on the 4000 Series | drawn or ignored | ignored (Tables 69, 70) |
| Two-digit year on Alpha 1.0 | 1997-2096 window or 19xx | window (p. 28, note 15) |
| Missing STX pause | drop the nested Command, or accept it | drop (p. 11) |
| Network Query answer framing | Response Packet with Checksum, or bare data | Response Packet (the library's assumption, p. 32 unclear) |
| Oversized write | truncate or ignore | ignore (assumption; the manual does not say) |

When hardware-results.md gets a row, the default for that Sign Model changes to the
observed value and cites the row. Settings are per emulated Sign, so one Line can hold
both readings side by side.

### Sign Models

- An emulator model is data: name, Sign Type, columns and rows in pixels, lines, color
  palette (tricolor or red only), memory bytes, maximum messages, accepted Protocol
  Versions, and firmware string for General Information.
- The 4120C comes first (Table 5, brochure). A custom model can be built from the page
  or the control channel. Other 4000 Series models and the BetaBrite are added as data.
- The emulator does not read `alpha_led_sign`'s capability JSON or registry.
- Capabilities in the emulator decide drawing, not validation. A Control Code the model
  can't use is ignored and listed in `ignored`.

### Python side

- No new Transport. Tests and users reach the emulator through `SerialTransport` with
  `socket://`.
- A pytest fixture starts the headless host on a free port, sets up the Line through
  the control channel, and points the hardware suite at it with the existing
  `ALPHA_SIGN_PORT` variable. A new `emulator` marker selects this run.
- Under the emulator, the erase and re-address tests run without
  `ALPHA_SIGN_ALLOW_ERASE` and `ALPHA_SIGN_ALLOW_READDRESS`, and the second-address
  test uses a second emulated Sign.
- Captures from an emulator run record the emulator and its settings in place of a
  firmware string. The capture tooling refuses to turn them into test vectors.
- The fixture skips with a reason when Node is not installed. CI installs Node and runs
  the emulator tests.

### Tooling

- The emulator is its own TypeScript project in this repository, with strict type
  checking, npm (it comes with Node), the current Node LTS, Vite for the page, Vitest
  for tests, Biome for lint and format, and Playwright for the one page test.
- prek gets hooks for Biome and the type check. CI gets a job for the emulator's tests
  and the Python `emulator` run.
- The emulator is not published and has no version of its own for now. The
  releases cover the Python package only. Commits follow the same Conventional Commits
  rules, so emulator subjects reach the changelog and must make sense to users.

## Testing Decisions

### What a good test is

- The same rules as the main spec. Tests go through a public seam, and expected values
  come from a source independent of the code: a worked example in the manual (Appendix
  F, Tables 38-59, Appendix G), a field layout on a cited page, or bytes captured from
  a real Sign. The citation goes in the test name or a comment.
- A test never builds its expected bytes with the emulator's encoder, and never with
  the Python library. Agreement between the two implementations is checked by the
  Python `emulator` run, not used to make expected values.
- Response bytes that have no manual example and no capture yet are checked field by
  field against the cited layout, and marked `PROVISIONAL` until a capture replaces
  them.
- Core tests pass time in. They never sleep and never use timers.

### Seams

| Seam | Tested through it | Catches | Misses |
|---|---|---|---|
| Emulator core: bytes and times in, Response bytes and snapshots out | Packet parsing, Recipients, Commands, Files, memory, schedule, clock, Readings, Responses, display model, pixels | Wrong reading of the manual in the emulator, timing rules, display layout | How a real Sign draws, real timing on a wire |
| Library hardware suite over the headless host (`-m emulator`) | `Sign`, reads, discovery, pauses through `SerialTransport` and TCP | Disagreement between the library's and the emulator's reading of the manual, round trips, multi-Sign discovery | Anything both implementations misread the same way |
| Page (one Playwright test) | The page with the bridge | The page loads, connects, and lights pixels after a write | Drawing details |

This is one new seam, the core. The Python run reuses the existing hardware seam with
the emulator in place of a Sign.

### What gets tested where

- **Packets and Commands.** Appendix F worked examples and the Tables 38-44 Packets are
  fed in, and the snapshot is checked: the Files and content they set up. A bad
  Checksum sets the register bit (p. 31).
- **Content.** The Tables 47-51 and Appendix G examples are fed in and checked through
  the display model: text runs, colors, Modes, Display Positions.
- **Pixels.** A few golden images per Mode at a fixed time, approved by a person
  looking at them and stored with the tests. They show that drawing did not change.
  They are not evidence about real Signs.
- **Schedule.** Run Sequence, Run Times, Run Days, and the Priority TEXT File, with the
  clock set by the test.
- **Timing.** A nested Packet with and without 100 ms after an STX, and data during a
  tone's silence, with times given by the test.
- **Line.** Two Signs answering a Network Query at their times (p. 32), and two Signs
  at one Sign Address garbling each other.
- **Readings.** Each Reading is tested at each of its values.
- **Independence.** A check fails if the emulator project references the Python
  package's files or data.

### Prior art

- The library's Packet and Text File tests (Tables 38-51, Appendix G) are the model for
  the core's tests, and their manual citations can be followed for the same examples.
- `FakeTransport` and the recording Transport in the Python tests. The emulator does
  not replace `FakeTransport`: late, partial, and garbled Responses stay with it.
- The hardware suite and its environment variables, which the `emulator` run reuses.
- [readerboard](https://github.com/mjaksn/readerboard) has a PySide6 sign simulator
  and protocol notes that are worth reading before drawing Modes.

## Out of Scope

- Pixel-exact drawing. The fonts are original and the Mode timings are approximations.
- Fault injection (dropped, late, or corrupted bytes on the Line). `FakeTransport`
  covers those cases. It could come later as a Line setting.
- Web Serial. The page does not open a real serial port. The serial path (baud rate,
  8N1 or 7E2, the USB-serial adapter) is tested against a real Sign, with the hardware
  tests.
- Parity, framing, and overrun errors, which TCP can't produce.
- Counters, Alpha 2.0 and 3.0 Commands and Control Codes, DOTS PICTURE content, and
  extended characters, the same as the library.
- Alpha's Ethernet adapters and serial servers, and the ESPHome bridge.
- Publishing the emulator to npm or hosting the page.
- Using emulator results as hardware results or as test vectors.
- Running the witnessed tests against the emulator as a recorded result.

## Further Notes

### Glossary additions

- **Emulator**: the program in this spec, which acts like Signs on a Line. _Avoid_:
  simulator, mock.
- **Emulated Sign**: one Sign inside the Emulator, with an emulator model and settings.
- **Line**: the serial network that Signs listen on, shared by every Sign attached to
  it. _Avoid_: bus.
- **Reading**: an Emulator setting that picks one reading of an unclear point in the
  manual.

### Open questions

- **What a Sign does with an oversized write.** The manual does not say. The default is
  a guess until a real Sign shows it.
- **Mode timing.** The manual gives speeds but no durations. Measuring a real 4120C
  with a video would give real values.
- **Special Modes and Special Graphics.** Placeholders until someone watches a real
  Sign play each one. Drawings that copy Alpha's animations are not wanted.
- **One Node program or two.** The bridge and the headless host are one program with
  two modes in this spec. If the page's needs and CI's needs pull apart, they can be
  split.

## MVP and deferred work

### What is built

- The core: the Packet parser with Checksums and nested Packets, Type Codes and Sign
  Addresses, TEXT and STRING Files, the Special Functions, the Memory Configuration and
  Memory Pool, Responses, the Serial Error Status Register, the Readings, and the
  silence after a tone.
- The display for HOLD, ROTATE, FLASH, ROLL in four directions, and WIPE in four
  directions, with the 4120C's fonts and two lines.
- The headless host, with a TCP port for the library and a JSON control channel, and
  the bridge.
- The page, which draws each Sign's LED matrix and state and sets the clock.
- The emulator run of the hardware tests: `uv run pytest -m emulator`.

How to run each part is in [CONTRIBUTING.md](../CONTRIBUTING.md).

### Interfaces as built

- **Headless host.** `npm run headless -- [--port N] [--http-port N]` prints one line,
  `tcp=<port> http=<port>`. Port 0 picks a free port. The default Line is one 4120C at
  Sign Address 1. Byte times are taken at the TCP port, and Responses go to every
  connected TCP client.
- **Control channel** (JSON over HTTP; errors are `{error}` with 400 or 404):
  - `GET /snapshots`: every Sign's snapshot, in Line order.
  - `GET /line`: the time, and each Sign's model, Sign Address, and Readings.
  - `POST /reset` with `{signs?, clock?}`: a new Line at power-up. `signs` is a list of
    `{model, signAddress, readings?}`. `clock` is the Sign's local time as
    `YYYY-MM-DDTHH:MM[:SS]`, and the host's local time if it is left out. The control
    channel sets the clock only through a reset.
- **Bridge.** `npm run serve` starts the bridge, the page, and a browser. The page finds
  the bridge from its `?bridge=` query, and `?signs=4120C:1,2` puts more Signs on the
  Line. Messages are JSON over WebSocket. Bytes are strings with one character per byte.
  Times are in ms on the bridge's clock, which the page uses as Line time.
  - The bridge sends `hello` on connect, and `rx` with the library's bytes and their
    arrival time.
  - The page sends `tx` with Response bytes and the time to send them.
  - Either side can ask for the bridge's clock with `time`.
- **Page clock.** The page sets the clock by feeding Set Time, Set Date, and Set Day
  Packets to its own Line, the same Commands the library sends.

### Assumptions in the MVP

Each of these is a guess until a real Sign or the manual settles it. The ones marked
PROVISIONAL in the code are marked there too.

- **Power-up memory.** TEXT File `A`, unlocked, size `0000`. Size `0000` is read as "all
  memory left", and it counts only the per-File overhead in the memory budget
  (PROVISIONAL).
- **Firmware.** The 4120C model reports the firmware `EMU4120C`, revision `A`, date
  `1126`. These are invented, so that no one takes them for a real Sign's (PROVISIONAL).
- **General Information length.** The 28-character Reading leaves out the revision
  letter (PROVISIONAL).
- **DOTS PICTURE size.** When the Reading counts a DOTS PICTURE File, its size is rows
  times columns bytes (PROVISIONAL).
- **Colors.** Autocolor and the default color are drawn red.
- **Run Sequence.** An empty Run Sequence runs every TEXT File in Label order.
- **Where the display starts.**
  - After a TEXT File write, the display starts at that File (pp. 17, 18).
  - A soft reset starts it again from the Run Sequence, as at power-up.
  - Clear memory goes back to the power-up state.
- **Reads.** A read of a File that is not in the Memory Configuration gets no answer.
- **When Commands run.** A Command takes effect as soon as it is complete, and its
  Response is sent at the Packet's EOT. A Command that ends with ETX and no Checksum is
  complete only when the next byte arrives, because the Sign expects a Checksum after
  ETX (p. 12).
- **Tone silence.** Input is ignored for 3000 ms after a tone `0` or `1`. After a
  programmable tone it is ignored for duration x 100 ms x plays. The EOT that closes
  the tone's own Packet is accepted.
- **Mode timings** (the manual gives none):
  - HOLD and FLASH: 3000 ms per Frame.
  - ROTATE: 20 ms per pixel at Speed 4.
  - ROLL and WIPE left and right: 20 ms per pixel, then a 3000 ms hold.
  - ROLL and WIPE up and down: 80 ms per pixel, then a 3000 ms hold.
  - Flashing characters: 500 ms on, 500 ms off.

### Not modelled

- Special Functions with no handler are ignored and listed in `ignored`, with no
  register bit: Run Times, Run Days, Network Query, dimming, and the rest the library
  does not send.
- ASCII Printable formats (p. 15), the 1 s serial timeout, and the number of sync bytes.
- The 100 ms pause is checked after every STX but the first in a Packet. The first STX
  needs none.

### Deferred past the MVP

- Run Times and Run Days. The display runs the Run Sequence without them, and the page
  says they are not modelled.
- Network Query and collisions on the Line. When Network Query lands, the fixture gets a
  second emulated Sign for the second-address test, and the discovery test runs.
- Sound: tones are recorded, but nothing plays them in the browser (Web Audio).
- Modes other than those above. They show as HOLD, with the Mode's name as a label.
- Special Graphics animation. The page shows the Special Graphic's name only.
- Marking captures as emulator captures. For now, `ALPHA_SIGN_CAPTURE` is refused under
  `-m emulator`, so no emulator capture can be made at all.
- Sign Models other than the 4120C. The model is still data, so adding one is a new
  entry, not new code.
- Custom Sign Models made from the page.
- A dark theme for the page.

### Results and open checks

- `uv run pytest -m emulator`: 10 passed, 8 skipped, none failed. Two tests need
  Network Query, and six are witnessed tests. The library and the emulator did not
  disagree anywhere.
- The erase tests pass because the emulator's default Readings (11 bytes of overhead per
  File, DOTS PICTURE Files counting only the overhead) match the library's PROVISIONAL
  values. That is two readings agreeing, not evidence about a real Sign.
- The golden pixel images in `emulator/test/core/__golden__/` were looked at and approved
  in November 2026. A change to them needs a person's approval again; `npx vitest run -u`
  accepts changed images.
- The page test needs Chromium once: `npx playwright install chromium`. CI installs it.
