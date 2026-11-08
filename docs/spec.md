# Spec: `alpha-led-sign`

This spec says what the library does, why it is built the way it is, how it is tested,
and what work is still open. Terms in **bold** are defined in
[GLOSSARY.md](../GLOSSARY.md). Decisions with a longer story are in [adr/](adr/).
Page and table numbers refer to the Alpha Sign Communications Protocol manual,
9708-8061F ([reference/](reference/), with the 4000 Series brochure and the networking
manual). Stories and decisions marked **(waits for hardware)** are covered by
[Remaining work](#remaining-work).

Status (November 2026): the library covers Alpha 1.0 Packet framing, TEXT and STRING
Files, Sign Models and the memory budget, special functions and scheduling, the serial
Transport, `Sign`, reads, and discovery. All of it passes offline. Every hardware
checklist item has a test, but none has run against a real **Sign** yet.

## Problem Statement

A developer who owns an Alpha LED sign, such as a 4120C, wants to drive it from Python:
show text, update live values, set the clock, schedule **TEXT Files**, and read back
what the Sign holds. The protocol is a 1990s serial byte format with sync bytes,
nested **Commands**, **Checksums**, silent pauses the Sign needs, and a large set of
**Control Codes** that vary by **Sign Model**.

The Python libraries that exist are BetaBrite-only, untested, or written for Python 2
(see [Prior art](#prior-art)). None of them describes Sign Models as data, so none can
tell the developer that a **Mode** or font will not work on their Sign before they
send it. None of them covers reads, scheduling, and discovery together. A developer
today has to read an 80-page manual and hand-build bytes. A mistake in those bytes
gives no error: the Sign ignores the **Packet**, or shows something wrong, or erases
its memory.

## Solution

A typed Python 3.12+ library, `alpha_led_sign`, with three layers:

1. A pure **protocol** layer that turns typed Commands into Packet bytes and Response
   bytes back into typed values. It has no I/O and no clock. The pauses the Sign needs
   are part of the encoded Packet, as data.
2. A **Transport** seam with four operations (write, pause, read, close). The library
   ships one production adapter: a serial port opened from any pyserial URL.
3. A **`Sign`** facade with task-shaped methods (`show`, `write_text`,
   `write_string`, `configure_memory`, `set_clock`, `priority`, reads, and so on). It
   builds Commands, checks them against the Sign Model, encodes them, and sends them
   with the required pauses.

Sign Models are frozen data built from the manual's capability tables (Tables 68-70).
A Sign Model lists the **Protocol Versions** and **Capabilities** it supports.
Validation warns by default and raises in strict mode. A generic model works with any
Alpha Sign before it has a profile.

Every expected byte string in the tests comes from a source that is independent of
the code: the manual's worked examples (cited by table or page) or bytes captured
from a real Sign.

## User Stories

### Sending content

1. As an application developer, I want to show a line of text on my Sign with one
   call, so that I can confirm the Sign works before I learn the protocol.
2. As an application developer, I want to write a **Message** of several **Frames** to
   a named TEXT File, so that the Sign shows each Frame in turn.
3. As an application developer, I want to give each Frame a Mode and a **Display
   Position**, so that I can control how and where each part appears on a two-line
   Sign.
4. As an application developer, I want to put colors, fonts, speeds, wide text,
   flashing text, and new lines inside a Frame as typed values, so that I never write
   escape bytes by hand.
5. As an application developer, I want to insert the Sign's own time and date into a
   Frame, so that the Sign keeps them current without more writes from me.
6. As an application developer, I want to show a **Special Graphic** (fireworks,
   "Thank You") or a **Special Mode** in a Frame, so that I can use the built-in
   animations.
7. As an application developer, I want plain text, a single Frame, or a full Message
   to be accepted wherever content goes, so that simple cases stay short.
8. As an application developer, I want text with characters the Sign cannot display
   to be refused before anything is sent, so that I don't get garbage on the Sign.
9. As an application developer, I want a Packet whose data would contain a framing
   byte to be refused, so that a bad value can't cut a Packet short on the wire.

### Live values

10. As an application developer, I want to update a **STRING File** without blanking
    the display, so that I can show a temperature or a count that changes often.
11. As an application developer, I want to reference a STRING File from inside a
    TEXT File, so that the TEXT File shows the latest value each time it runs.
12. As an application developer, I want STRING content longer than 125 bytes to be
    refused, so that I learn about the limit (p. 37) at once.
13. As an application developer, I want Control Codes that a STRING File can't hold
    (Table 19) to be refused, so that I don't send content the Sign drops.

### Priority TEXT File

14. As an application developer, I want to show a **Priority TEXT File** that takes
    over the display, so that an urgent notice interrupts the normal cycle.
15. As an application developer, I want to clear the Priority TEXT File with one call,
    so that the Sign goes back to its **Run Sequence**.
16. As an application developer, I want a Priority Message over 125 bytes to be
    refused, so that I learn about the fixed size (p. 20).

### Memory

17. As an application developer, I want to set the **Memory Configuration** (the TEXT,
    STRING, and **DOTS PICTURE Files**, with sizes) in one call, so that I can lay out
    a Sign for my application.
18. As an application developer, I want the documentation of that call to say plainly
    that it erases every **File**, so that I don't wipe a Sign by accident.
19. As an application developer, I want a Memory Configuration that breaks a protocol
    rule (a STRING File of size 0, or a TEXT File of size 0 that is not last) to be
    refused, so that the Sign does not reject it without telling me.
20. As an application developer, I want a warning when my Memory Configuration needs
    more memory than my Sign Model has, so that I find out before the Sign runs out.
21. As an application developer using strict mode, I want that memory overflow to
    raise, so that my setup script stops.
22. As an application developer, I want to clear all memory, so that I can return a
    Sign to a known state.
23. As an application developer, I want to soft-reset a Sign and keep its memory, so
    that I can recover a Sign that stopped responding.

### Clock and scheduling

24. As an application developer, I want to set the time, date, and day of the week
    from one `datetime` in one Packet, so that the Sign's clock is set in one step.
25. As an application developer, I want to choose 12-hour or 24-hour time, so that
    the Sign shows time the way my users read it.
26. As an application developer, I want to set the Run Sequence, so that I control
    which TEXT Files the Sign cycles through.
27. As an application developer, I want to say whether the Run Sequence follows **Run
    Times** and whether it is locked, so that I can match how the Sign is used.

28. As an application developer, I want to set a Run Time for each TEXT File as a pair
    of times of day, or as Always, Never, or All Day, so that Files show only when they
    apply.
29. As an application developer, I want a Run Time that is not on a 10-minute step to
    be refused, so that I learn about the protocol's resolution (Appendix B).
30. As an application developer, I want to set the days each TEXT File runs on, so
    that weekday-only content stays off at weekends.
31. As an application developer, I want the documentation of Run Time and Run Day
    writes to say that they end a Priority TEXT File (p. 20), so that I am not
    surprised.

### Sound and addressing

32. As an application developer, I want to sound a built-in tone, so that the Sign
    can draw attention.
33. As an application developer, I want to play a tone of a given pitch, length, and
    repeat count, so that I can choose my own alert sound.
34. As an application developer, I want the library to wait after a tone until the
    Sign can take data again, so that the next write is not lost.
35. As an application developer, I want to turn the speaker on or off, so that I
    control whether tones sound.
36. As an application developer, I want to set a Sign's **Sign Address** from
    software, so that I can put several Signs on one line.
37. As an application developer, I want that call to refuse to send to the broadcast
    address unless I say so, so that I don't give every Sign the same address.
38. As an application developer, I want the `Sign` object to address the new Sign
    Address after it changes it, so that my next call still reaches that Sign.

### Reading back

39. As an application developer, I want to read a TEXT File back as a Message, so that
    I can see what a Sign is showing.
40. As an application developer, I want to read a STRING File back as its Segments,
    so that I can check a live value.
41. As an application developer, I want Control Codes the library does not model to
    survive a read and a write back unchanged, so that reading a File set up by other
    software does not damage it.
42. As an application developer, I want to read the Sign's General Information
    (firmware, clock, speaker, memory), so that I can check a Sign's state.
43. As an application developer, I want to read the Serial Error Status Register, so
    that I can learn whether my last Packets arrived intact.
44. As an application developer, I want a read that gets no complete answer in time
    to raise a timeout error, so that my program does not hang.
45. As an application developer, I want a late answer to an earlier, timed-out read to
    be skipped, so that it is not taken as the answer to my current read.
46. As an application developer, I want a damaged or malformed Response to raise an
    error, so that I never act on bad data.

### Discovery

47. As an application developer, I want to find every Sign on a line and its Sign
    Type and Sign Address, so that I can configure a network of Signs I didn't set up.
48. As an application developer, I want to limit discovery to low addresses, so that
    I don't wait over two minutes when my Signs use small addresses.
49. As an application developer, I want a discovered Sign to tell me its registered
    Sign Model when its Sign Type identifies exactly one, so that I can open it with
    the right profile.
50. As an application developer, I want garbled answers (two Signs at one address,
    p. 32) to be skipped with a warning, so that one bad answer doesn't hide the rest.

### Sign Models and validation

51. As an application developer, I want a ready-made profile for each Sign in the
    4000 Series and for the BetaBrite, so that I don't enter the manual's tables by
    hand.
52. As an application developer, I want to look up a Sign Model by name, so that a
    configuration file can choose it.
53. As an application developer, I want a warning when I send a Mode, font, color, or
    Control Code my Sign Model lacks, so that I can find out why the Sign ignored it.
54. As an application developer, I want a strict mode that raises in that case and
    sends nothing, so that tests and setup scripts fail fast.
55. As an application developer, I want a code from a newer Protocol Version than my
    Sign accepts to be reported even for the generic model, so that I don't send Alpha
    3.0 codes to an Alpha 1.0 Sign.
56. As an application developer with a Sign that has no profile, I want a generic
    model that reaches any Alpha Sign and skips Capability checks, so that I can still
    use the library.
57. As an application developer whose Sign differs from the manual, I want to replace
    a profile's Capabilities, so that validation matches my hardware.

### Connection

58. As an application developer, I want to open a Sign from a serial device path, so
    that a USB-serial adapter works with no more setup.
59. As an application developer, I want to choose the baud rate and 8N1 or 7E2, so
    that I can match how my Sign is set.
60. As an application developer, I want to use `socket://host:port`, so that a raw TCP
    serial bridge works without a new adapter.
61. As an application developer, I want to supply my own Transport, so that I can
    reach a Sign through hardware the library doesn't know about.
62. As an application developer, I want `Sign` to work as a context manager, so that
    the port closes when I am done.
63. As an advanced developer, I want to build Commands and encode Packets myself,
    without `Sign`, so that I can send Commands the facade does not wrap.
64. As an advanced developer, I want to import every public Command and code from
    the protocol package, so that I don't depend on internal module names.
65. As an application developer, I want the scheduling argument types exported from
    the top-level package, so that a scheduling call needs no deep imports.
66. As an application developer, I want every public name to have type hints, so that
    my editor and type checker catch mistakes.

### Maintainers and hardware testers

67. As a maintainer, I want every expected byte in the tests to cite a manual table or
    page or a hardware capture, so that a test can't pass by repeating the code's own
    mistake. **(waits for hardware:** three Response vectors are hand-summed until a capture replaces them**)**
68. As a maintainer, I want to add a Sign Model by adding one data entry, so that
    support grows without new classes.
69. As a maintainer, I want to add a Command by adding one small class, so that Alpha
    2.0 and 3.0 support doesn't change the Packet encoder.
70. As a maintainer, I want a test that fails when a Mode, Special Mode, or font has
    no entry in the requirements lookup, so that validation can't skip a new code.
71. As a maintainer, I want a test that imports every public name, so that removing an
    export fails CI.
72. As a hardware tester, I want to run the hardware tests against my Sign with
    environment variables for port, model, address, baud, and format, so that one
    suite works for any Sign set up any way.
73. As a hardware tester, I want tests that erase memory to run only when I allow it,
    so that a test run doesn't wipe a Sign in use.
74. As a hardware tester, I want to record every byte written and read in a hardware
    run to a file, so that those captures become test vectors.
75. As a hardware tester, I want to measure the per-File memory overhead on a real
    Sign, so that the model's memory budget is right.
76. As a hardware tester, I want witnessed tests that ask me what I saw or heard, so
    that the checklist items a machine can't check still get a recorded answer.
77. As a maintainer, I want each hardware result recorded with the manual's claim,
    the Sign's behavior, the firmware, and the date, so that profile overrides are
    traceable.

## Implementation Decisions

### Facts from the manual that shape the design

| Fact | Source | Consequence |
|---|---|---|
| The 4000 Series accepts EZ KEY II and Alpha 1.0 only: 1200-9600 baud, 7E2 or 8N1. | Table 3, p. 8 | Every Command and Control Code has a known minimum Protocol Version. Each Sign Model lists the versions it accepts. |
| 4120C: Sign Type `a`, 120x16 pixels, 2 lines, tricolor, 28,000 bytes, 81 messages. | Table 5; brochure | One data entry in the model registry, not code. |
| Packet: 5+ NUL, SOH, Sign Type, 2-hex-digit Sign Address, then STX, Command, optional ETX and Checksum, repeated for each Command, then EOT. | pp. 10-14 | One pure encoder handles single, nested, and checksummed Packets. |
| A nested Packet needs at least 100 ms of silence after each STX. A tone Command needs 3 s of silence after it. | pp. 11, 27 | The encoder returns byte chunks with the pauses between them. Sleeping is the sender's job, so tests stay instant. |
| Writing the Memory Configuration erases every File. | p. 21 | The API makes this explicit and hard to call by accident. |
| A STRING File updates without blanking the display; max 125 bytes. A TEXT write blanks the display. | p. 37 | `write_string` is the route for live values. |
| Reads return a Response Packet (type `0`, address `00`) with a Checksum. | pp. 19, 38 | One Response decoder for all reads. |
| The pauses after STX and after tones are part of the protocol. | pp. 11, 27 | A network bridge can merge writes and lose them. A bridge must keep them, or the library must avoid nesting through it. |
| Appendix F has worked examples with Checksums (`AAHELLO` gives `01FB`). | pp. 58-68 | These are the test vectors. |

### Architecture

- The protocol layer is pure: bytes in, bytes out. It has no I/O, no clock, and no
  sleeps. It does not import the Sign Model registry.
- A Packet is a sequence of Chunks. Each Chunk has bytes and the silence (in seconds)
  the line must keep after it. A nested Packet needs 100 ms after each STX (pp. 11,
  13, 14). A fixed tone needs 3 s after the Packet (p. 27, note 4). A programmable
  tone needs its full play time. Converting a Packet to bytes joins the Chunks and
  drops the pauses, for logging and comparison.
- Sending a Packet means writing each Chunk and then asking the Transport to pause.
  A Transport's write returns only once the bytes have left, so a pause is real
  silence on the line. Pause is part of the Transport seam so that a bridge adapter
  can keep the silences its own way.
- **Content is a list of Segments.** A string is literal text. An enum member or a
  small value object is a Control Code. An inline markup parser may come later and
  must produce the same model.

### Extensibility rules

These keep the library open to other Series and Sign Models. Nothing may be specific
to one Sign Model.

1. **A Sign Model is data.** It is a frozen record: name, Sign Type, Series, columns,
   rows, lines, memory bytes, maximum messages, accepted Protocol Versions, and
   Capabilities. Unknown values are `None`. Capabilities of `None` means "unknown: do
   not check". Adding a model means adding one entry. There are no per-model
   subclasses.
2. **Capabilities come from the manual.** The registry is built at import time from
   the extracted Tables 68-70, which ship inside the package as JSON and are mapped to
   library enums. A table cell with a footnote counts as supported. The "R" (red-only)
   4000 Series models lose the color Capability (Table 69, note 1).
3. **Overrides wait for evidence.** Until hardware shows the first difference from the
   manual, an override is a copy of a model with replaced Capabilities. A declared
   overrides field arrives with that first difference. **(waits for hardware)**
4. **Every code's needs are looked up in one place.** Each Command declares the
   minimum Protocol Version it needs. For every Mode, color, font, and other Control
   Code, one requirements function gives the minimum version and the Capability. A
   test checks that each Mode, Special Mode, and font has an entry. Validation
   compares both against the model.
5. **Commands are an open set.** Each Command is a small class with a Command Code and
   a method that returns its Data Field. Adding Alpha 2.0 and 3.0 Commands means adding
   classes. The Packet encoder does not change.
6. **Validation is advisory by default.** The manual's tables have gaps, so strict
   mode raises and advisory mode warns and sends anyway.
7. **A generic model exists.** Sign Type `Z`, Alpha 1.0, no Capability checks. It
   works with any Alpha Sign before it has a profile.

### Interfaces

- **Protocol encoder.** Takes one or more **Recipients**, a non-empty sequence of
  Commands, and a checksum flag (default on). Returns a Packet. It refuses an empty
  Command list, a Command that must be last (reads, tones) followed by another, and
  Command data that contains a framing byte (SOH, STX, ETX, EOT). A lone Command
  without a Checksum has no ETX (Table 38). Nested Commands always end in ETX.
- **Recipient.** A Sign Type (one ASCII character) and a Sign Address: an integer
  0-255, or a two-character hex pattern where `?` matches any digit (p. 11).
- **Command.** Each has a one-character Command Code, a method that returns its Data
  Field, the minimum Protocol Version it needs, whether it must be last, the pause it
  needs after it, and the codes it contains (for validation). Reads also parse a
  decoded Response into a typed value.
- **Response decoding.** A decoder takes one Response Packet (Type Code `0`, address
  `00`, p. 19) and returns its Commands, checking every Checksum. A reader takes bytes
  in pieces, however they arrive, and returns each complete Response, or the error it
  failed with, in order. It keeps unfinished bytes as pending.
- **Validation.** Takes a Sign Model, Commands, and a strict flag. It collects every
  problem. Strict mode raises `UnsupportedCapability` with all of them, before
  anything is sent. Advisory mode warns once per problem with
  `UnsupportedCapabilityWarning` and lets the send go on.
- **Transport.** `write(bytes)`, `pause(seconds)`, `read(timeout) -> bytes`, `close()`.
  `read(0)` returns only bytes that have already arrived. `read` returns empty bytes
  on timeout. The interface stays small so that a new adapter (a bridge, an emulator)
  needs no changes elsewhere.
- **SerialTransport.** Opens any pyserial URL (an idea taken from readerboard): a
  device such as `/dev/tty...`, `loop://` for tests, or `socket://host:port` for a raw
  TCP bridge. Defaults: 9600 baud, 8N1. 7E2 is the other format Alpha 1.0 accepts
  (Table 3).
- **Sign.** Built from a Transport, a Sign Model (default generic), a Sign Address
  (default 0), a strict flag (default off), a checksum flag (default on), and a read
  timeout (default 2 s). A class method opens it on a serial URL. Task methods:
  `show`, `write_text`, `write_string`, `priority`, `clear_priority`,
  `configure_memory`, `clear_memory`, `soft_reset`, `set_time_format`,
  `run_sequence`, `set_clock`, `beep`, `read_text`, `read_string`, `info`,
  `serial_errors`. Lower-level methods: `send` (validate, encode, and send Commands in
  one Packet) and `query` (send one read and parse its answer). Scheduling, sound,
  and addressing: `set_run_times`, `set_run_days`, `set_speaker`, `tone`,
  `set_sign_address`, and order (default by Run Time) and lock (default unlocked)
  arguments on `run_sequence`.
- **Default File.** `show` and `read_text` use TEXT File `A`, which every Sign has at
  power-up (p. 17). `show` uses HOLD and fills the display unless told otherwise.
- **Discovery.** Takes a Transport (not a `Sign`), a highest address (default 255),
  and a checksum flag. It broadcasts a Network Query (`F-`, p. 32) to Sign Type `Z`,
  address 0, and waits 1 s + 0.5 s per address + a 1 s margin, because each Sign
  answers 1 s + 0.5 s x its address after the query. It returns the answers sorted
  by Sign Address. Each answer has the Sign Type, the Sign Address, the Sign's serial
  error status, and its Sign Model when exactly one registered model has that Sign
  Type.
- **Connection.** The 4120C is reached over USB-serial to RJ11. `SerialTransport` is
  the only production Transport. Alpha's own Ethernet adapters and serial servers are
  not supported.

### Read behavior

- Before it sends a read, `Sign` throws away every Response that has already arrived.
  If part of a Response had arrived, the rest of it is skipped when it comes.
- `Sign` counts reads whose answers have not arrived. A Response that answers a
  different kind of read is skipped while that count is above zero, and raises once
  it is zero.
- A late answer to the same kind of read cannot be told apart from the real one. It
  is taken as the answer. Callers must use one Sign Address per Sign so that only one
  Sign answers.
- A Response that fails to decode always raises. It is never skipped.

### Errors

| Error | When |
|---|---|
| `ValueError` | A value breaks a protocol rule, when the value is built: a bad File Label, Sign Type, Sign Address, size, Run Time, tone value, character, too-long STRING or Priority content, an illegal Control Code for a STRING File, framing bytes in data, a Command after one that must be last. |
| `UnsupportedCapability` | Strict validation: the Sign Model lacks a Capability or Protocol Version a Command needs. Also a Memory Configuration larger than the model's memory. |
| `UnsupportedCapabilityWarning` | The same problems, in advisory mode. |
| `ResponseError` (a `ValueError`) | A Response is malformed, fails its Checksum, or is not what the read expected. |
| `UnexpectedResponseError` (a `ResponseError`) | A well-formed Response answers a different read. |
| `SignTimeoutError` (a `TimeoutError`) | A read got no complete Response within the read timeout. |

The rule: a protocol rule (true for every Sign) raises `ValueError`. Model data (true
for some Signs, from tables with known gaps) goes through validation and is advisory
by default. The name `UnsupportedCapability` has no `Error` suffix; it is part of the
public interface. A wider base class (such as `ValidationError`) would be a separate
change.

### Rules added after review

- A STRING File of size 0, or a TEXT File of size 0 that is not last, raises
  `ValueError` (p. 27, note 1: size 0 is valid only for a last TEXT File).
- `SignModel` has a per-File overhead field, default 11 bytes (p. 27, note 1;
  readerboard reports 13, so this is model data). The memory budget counts TEXT and
  STRING sizes plus the overhead for every File, DOTS PICTURE Files included (the
  cautious reading of note 1). The check is skipped when the memory size is unknown.
  An overflow is `UnsupportedCapability` in strict mode and a warning otherwise.
- `set_sign_address` refuses address 0 or a `?` pattern (both reach more than one
  Sign) unless the caller passes `broadcast=True`:
  sent to broadcast, it would give every Sign on the line the same address. The
  refusal sends nothing. After sending, `Sign` addresses the new Sign Address.
- One Sign Address check, in its own protocol module (next to Recipient would make
  an import cycle), is used by Recipient, the address
  Command, and discovery. Lookup by Sign Type (a model only when exactly one has that
  Sign Type) lives in the models module, and the discovered Sign uses it.
- The lock byte of a Memory Configuration entry and of a Run Sequence comes from one
  helper.
- `DiscoveredSign` and the protocol's Network Query answer stay separate types,
  because the protocol layer can't import the models. A File Label type is not
  planned: every path already checks labels, and a NewType adds no runtime check.

### Versioning

- SemVer `MAJOR.MINOR.PATCH` from `0.1.0`, no `v` prefix
  ([ADR 0001](adr/0001-semantic-versioning.md)). Before 1.0 a breaking change bumps
  the minor number. Each one needs `!` and a `BREAKING CHANGE:` footer, which pick the
  next number and which the changelog lists.
- Python 3.12 or later. The only runtime dependency is pyserial. The package ships
  type information. The import name is `alpha_led_sign`, to avoid a clash with the older
  `alphasign` library.

## Testing Decisions

### What a good test is

- It tests behavior through a public seam: bytes out of the encoder, bytes into the
  decoder, or what `Sign` writes to a Transport and returns from it. It does not call
  private helpers or check internal state.
- Its expected value comes from a source independent of the code: a worked example
  in the manual (Appendix F, Tables 38-59, Appendix G), a field layout on a cited
  page, or bytes captured from a real Sign. The citation goes in the test name or a
  comment. A test never computes its expected value the way the code does (no
  hand-summed Checksums, no expected bytes built with the encoder).
- A Packet that has no manual example is tested with checksums off, so that its
  expected bytes are a layout that can be read off the manual.
- A round-trip test (write, then read back) checks symmetry, not bytes. It is named
  as a round trip, and each Control Code in it also has a decode test against
  literal bytes.
- Tests are written first. They are fast and offline. Pauses are checked as data and
  never slept.

### Seams

| Seam | Modules tested | Catches | Misses |
|---|---|---|---|
| Protocol encode and decode (pure bytes) | Packet framing, Commands, codes, Messages, Response decoding and the reader, requirements | Framing, Checksum, nesting, pauses, Control Code bytes, field layouts, value rules | Whether a Sign accepts them |
| `Sign` over `FakeTransport` | `Sign`, validation through `Sign`, discovery, read behavior | The right Packets and pauses, validation before sending, Response parsing, timeouts, late answers | Serial timing and hardware quirks |
| Hardware (opt-in, `-m hardware`) | The whole library against a real Sign | Firmware behavior, baud and parity, gaps in the manual's tables | Not run in CI; needs a connected Sign |

The Sign Model registry is tested directly as data against Table 3, Table 5, Tables
68-70, and the brochure. `SerialTransport` is tested over pyserial's `loop://`.

Test adapters sit at the Transport seam: `FakeTransport`, a recording Transport that
keeps every byte for captures, and later the Sign emulator
([emulator-spec.md](emulator-spec.md)), which the hardware suite reaches over
`socket://`. Witnessed tests are a subset
of the hardware seam: the test asks the person watching a question, such as how many
plays they heard, and checks their answer.

Hardware runs take these environment variables: `ALPHA_SIGN_PORT` (required),
`ALPHA_SIGN_MODEL`, `ALPHA_SIGN_ADDRESS`, `ALPHA_SIGN_BAUD`, `ALPHA_SIGN_FORMAT`,
`ALPHA_SIGN_ALLOW_ERASE=1` (tests that write the Memory Configuration),
`ALPHA_SIGN_ALLOW_READDRESS=1` (a capture at a second Sign Address; needs a nonzero
`ALPHA_SIGN_ADDRESS`), `ALPHA_SIGN_CAPTURE=<path>` (write all traffic, with model,
firmware, and date, to JSON), and `ALPHA_SIGN_WITNESS=1` with pytest's `-s`
(`-m witness`).

### Prior art in the codebase

- Packet tests compare encoder output with Tables 38-44 byte for byte.
- Text File tests compare Frames and Control Codes with Tables 47-51 and Appendix G.
- `Sign` tests record writes and pauses on `FakeTransport` and replay canned
  Responses to it, including late, partial, and garbled ones.
- The requirements test checks that every Mode, Special Mode, and font has an entry.
- One test runs the README's example end to end over `FakeTransport`.

### Hardware checklist

Each hardware test maps to one of these items: a place where the manual is unclear or
the library made an assumption. Each result is recorded with the manual's claim, what
the Sign did, the firmware, and the date, in
[hardware-results.md](hardware-results.md). The first result that disagrees with the
manual brings in the overrides field (extensibility rule 3).

| Item | Library's assumption | Test |
|---|---|---|
| Network Query answers: the manual gives only the `UAAZ` data. | Each arrives as a Response Packet (`E-UAAZ` with a Checksum), like other special function reads. | Automatic |
| General Information: the manual says 28 or 29 characters, but its field list adds up to 29 plus an optional NUL. | 29 characters. | Automatic |
| Programmable tones: whether `R` (repeats) counts the first play. | It doesn't: the library waits for `R + 1` plays. | Witnessed: "Did you hear 3 plays?" |
| NEWS FLASH and TRUMPET: Table 66 gives `"A"`/`"B"` and also hex 3AH/3BH. | The letters. | Witnessed: show each form. |
| NEW_PAGE and double height on the 4000 Series: missing from Tables 69 and 70. | Not supported. | Witnessed: show each. |
| Two-digit year on Alpha 1.0: p. 28, note 15 gives the 1997-2096 window for Alpha 2.0 and later only. | The window applies to every Sign. | Witnessed: set 2026-11-07, show the date. |
| Per-File overhead: the manual says 11 bytes, readerboard reports 13. Whether DOTS PICTURE Files count. | 11 bytes, DOTS PICTURE included. | Automatic, needs erase permission: measure free memory with one File and with three. |
| Total memory: General Information against the model's memory size. | 28,000 bytes on the 4000 Series. | Automatic, with the overhead test. |

## Out of Scope

- An ESPHome Wi-Fi bridge Transport. Its design must keep the protocol's pauses. With
  `socket://` support, a raw-TCP UART bridge may work with no new adapter, but the
  pause concern still applies.
- Alpha's own Ethernet adapters and serial servers.
- A Sign emulator. It has its own spec, [emulator-spec.md](emulator-spec.md): a
  TypeScript program that the library reaches over `socket://`, with no new Transport.
- Writing DOTS PICTURE File content. A Memory Configuration can reserve DOTS PICTURE
  Files already.
- Counters, Alpha 2.0 and 3.0 Commands and Control Codes, ASCII Printable formats, and
  extended characters past printable ASCII.
- An inline markup language for content (for now).
- Use of one `Sign` from more than one thread. `Sign` has no locking.
- Retries and automatic reconnects. A failed write or read raises to the caller.
- Logging. Callers can log `bytes(packet)`.
- Nine-character File names (p. 28, note 14).

## Remaining work

Everything left needs a real Sign. Delete each item when it is done, and drop its
**(waits for hardware)** marks.

1. **Run the hardware suite on the 4120C.** Run `-m hardware` and `-m witness` with
   capture, erase, and re-address allowed. Record each checklist result in
   [hardware-results.md](hardware-results.md). At the first result that disagrees
   with the manual, add the overrides field to `SignModel` and use it in the 4120C
   profile (extensibility rule 3).
2. **Replace the hand-summed Response vectors with captures.** Three canned Responses
   in the tests (two Network Query answers and one Serial Error Status Response) are
   marked `# PROVISIONAL`. Replace each with captured bytes, cited as captured from a
   4120C with its firmware and date. Discovery needs answers from two Sign Addresses:
   use the re-address capture, or else one captured answer at two places in the
   stream.

## Further Notes

### Open questions

- **Reads to more than one Sign.** `query` says to use one Sign Address per Sign, but
  nothing stops a read sent to address 0 or a `?` pattern. With more than one Sign on
  the line, their answers collide. Should `Sign` refuse a read to a broadcast or
  wildcard Recipient, as `set_sign_address` will refuse broadcast?
- **Overhead per DOTS PICTURE File** and the **two-digit year on Alpha 1.0**: open
  until the hardware checklist answers them.

### Future projects

- **A DOTS PICTURE editor.** A web tool for drawing and editing DOTS PICTURE File
  content pixel by pixel, at a Sign Model's size and in its colors. It needs its own
  spec. Notes for that spec:
  - It depends on work that is out of scope today. The library can't write DOTS
    PICTURE content yet, and the Sign emulator ([emulator-spec.md](emulator-spec.md))
    does not draw DOTS PICTURE Files.
  - It should reuse the emulator's palette, its model data (pixel size, tricolor or
    red only), and its renderer, so that the editor previews a picture the way the
    emulator draws it.
  - Saved pictures should be in a form that both the library and the emulator can
    load, so that a picture can be sent to a Sign or shown on the emulator.
  - Its expected bytes follow the same rule as everything else: they come from the
    manual's DOTS PICTURE layout or from a capture, never from the editor's own
    encoder.

### Prior art

| Project | Lang | Notes |
|---|---|---|
| [mjaksn/readerboard](https://github.com/mjaksn/readerboard) | Python 3.11+, MIT | The closest in ambition: an HTTP service, not a library. Byte values are pinned to manual citations in tests. Tests use a fake transport and pyserial `loop://`. It has a PySide6 sign simulator and [protocol notes](https://github.com/mjaksn/readerboard/blob/main/docs/protocol-notes.md). Its README reports 13 bytes of overhead per File, where the manual says 11. |
| [msparks/alphasign](https://github.com/msparks/alphasign) | Python 2 era | The best-known library. BetaBrite-oriented, no visible tests. |
| [prototux/python-alphasign](https://github.com/prototux/python-alphasign) | Python 3, Apache-2.0 | Tested on a 210C. No tests; reads and special functions are on its TODO list. |
| [tonymagro/asign](https://github.com/tonymagro/asign) | Go | A `{Token}` template language over raw packets. Useful input for a later markup layer. |
| [jonathankoren/betabrite](https://github.com/jonathankoren/betabrite), [depili/betabrite](https://github.com/depili/betabrite) (Ruby), [jon-proulx/alphasign](https://github.com/jon-proulx/alphasign) (Ruby, archived), [bm16ton/betabrite_alpha_led-signs](https://github.com/bm16ton/betabrite_alpha_led-signs) (C) | various | Small or BetaBrite-only. |

None of them treats Sign Models as data, and none targets the 4000 Series. No ESPHome
or ESP32 Alpha-sign project turned up.
