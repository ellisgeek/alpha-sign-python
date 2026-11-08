# Implementation plan: `alpha-led-sign`

A typed Python library for controlling Alpha-protocol LED signs. The first target is the 4120C (4000 Series), but no part of the design is specific to it. Terms in **bold** are defined in [GLOSSARY.md](../GLOSSARY.md).

Sources: [M-Protocol.pdf](reference/M-Protocol.pdf) (9708-8061F), [capability-matrices.md](reference/capability-matrices.md) (Tables 68-70, extracted), the 4000 Series brochure, and the networking manual (cabling only).

## Facts that shape the design

| Fact | Source | Consequence |
|---|---|---|
| The 4000 Series accepts EZ KEY II and Alpha 1.0 only: 1200-9600 baud, 7E2 or 8N1. | Table 3, p. 8 | Every Command and Control Code carries the minimum **Protocol Version** it needs. Each **Sign Model** lists the versions it accepts. |
| 4120C: Sign Type `a`, 120x16 pixels, 2 lines, tricolor, 28,000 bytes, 81 messages. | Table 5; brochure | This becomes one data entry in the model registry, not code. |
| Packet: 5+ NUL, SOH, Sign Type, 2-hex-digit Sign Address, then STX, Command, optional ETX and Checksum, repeated for each Command, then EOT. | pp. 10-14 | A single pure encoder handles single, nested, and checksummed Packets. |
| A nested Packet needs at least 100 ms of silence after each STX. A tone Command needs 3 s of silence after it. | pp. 11, 27 | The encoder returns byte chunks with required pauses between them. Sleeping is the sender's job, so tests stay instant. |
| Writing the **Memory Configuration** erases every **File**. | p. 21 | The API makes this explicit and hard to call by accident. |
| A **STRING File** updates without blanking the display; max 125 bytes. A TEXT write blanks the display. | p. 37 | `write_string` is the documented route for live values. |
| Reads return a Response Packet (type `0`, address `00`) with a checksum. | pp. 19, 38 | One Response decoder for all reads. |
| Pauses after STX and after tones are part of the protocol. | pp. 11, 27 | A network bridge can merge writes and lose those pauses. A future bridge must keep them, or the library must avoid nesting when using it. |
| Appendix F has worked examples with checksums (`AAHELLO` gives `01FB`). | pp. 58-68 | These are the test vectors: an independent source of truth. |

## Extensibility rules

These rules keep the library open to other Series and Sign Models:

1. **A Sign Model is data.** `SignModel` is a frozen dataclass: name, Sign Type, columns, rows, lines, memory size, accepted Protocol Versions, and Capabilities. Adding a model means adding one entry. There are no per-model subclasses.
2. **Capabilities come from the manual.** The registry is built from `capability-matrices.json` (Tables 68-70), mapped to library enums. Models can override entries when real hardware disagrees with the manual.
3. **Codes know their Protocol Version.** Every `Mode`, `Color`, `Font`, Control Code, and Command declares the minimum version it needs. Validation compares that against the model.
4. **Commands are an open set.** Each Command is a small dataclass with a command code and an `encode_data()` method. Adding Alpha 2.0/3.0 Commands means adding classes. The Packet encoder does not change.
5. **Validation is advisory by default.** The manual's tables have gaps, so `Sign(..., strict=True)` raises `UnsupportedCapability`, and `strict=False` warns and sends anyway.
6. **A generic model exists.** `models.GENERIC` (Sign Type `Z`, Alpha 1.0, no capability checks) works with any Alpha sign before it has a profile.

## Module layout (proposed)

```
src/alpha_led_sign/
  __init__.py          public re-exports
  protocol/            pure: no I/O, no clocks
    packet.py          Recipient, encode_packet(), checksum, decode_response()
    commands.py        WriteText, ReadText, WriteString, ReadString, special functions
    codes.py           Mode, SpecialMode, SpecialGraphic, Position, Color, Font, Speed, ...
    message.py         Message / Frame / inline content -> TEXT File bytes, and back
    versions.py        ProtocolVersion
  models.py            SignModel, Capability, registry (4120C first, GENERIC)
  transport.py         Transport protocol, SerialTransport (pyserial)
  sign.py              Sign: the facade most callers use
tests/
  fakes.py             FakeTransport (records chunks and pauses, replays responses)
```

### Seams and depth

- **`protocol` (deep, pure).** Small interface: `encode_packet(recipients, commands, *, checksum=True) -> Packet` and `decode_response(bytes)`. All framing, nesting, escaping, and checksum rules live behind it.
- **`Transport` (seam).** `write(chunk)`, `read(timeout)`, `close()`. The production adapter is serial. `FakeTransport` and the planned emulator are test adapters, and a future ESPHome Wi-Fi bridge would be another production adapter. The interface stays small so that bridge needs no changes elsewhere.
- **`Sign` (deep facade).** The interface is task-shaped: `show`, `write_text`, `write_string`, `configure_memory`, `set_clock`, `priority`, `clear_priority`, `read_text`, `info`, `soft_reset`. It builds Commands, validates them against the model, encodes, and sends with the required pauses.

### API sketch (to be confirmed)

```python
from datetime import datetime
from alpha_led_sign import Sign, Message, Frame, Mode, Position, Color, TextFile, StringFile, models

with Sign.serial("/dev/tty.usbserial-1410", model=models.ALPHA_4120C) as sign:
    sign.show("Hello")                                   # TEXT File "A", default Mode
    sign.configure_memory([TextFile("A", size=512), StringFile("T", size=16)])  # erases everything
    sign.write_text("A", Message(
        Frame(Mode.ROTATE, Position.TOP, [Color.RED, "Temp: ", StringRef("T")]),
        Frame(Mode.HOLD, Position.BOTTOM, [Color.GREEN, CurrentTime()]),
    ))
    sign.write_string("T", "72F")                        # no blanking
    sign.set_clock(datetime.now())                       # time, date, weekday in one nested Packet
    sign.priority(Frame(Mode.FLASH, content=["EMERGENCY"]))
    sign.clear_priority()
```

## Delivery phases (vertical slices, test-first)

Each phase is a red-green loop at the agreed seams. No phase starts its tests until the seams are confirmed.

0. **Scaffold.** `uv init --lib`, ruff (lint + format), ty, pytest, pyserial. Git repo.
1. **Packet framing.** Recipients (single, wildcard `?`, multiple), checksum, nesting with and without checksums, pause chunks. Vectors from Appendix F.
2. **TEXT Files.** Message, Frame, Mode, Position, Special Mode/Graphic, Control Codes (color, font, speed, wide, flash, new line/page, time, date, STRING reference). Priority TEXT File.
3. **Sign Models.** `SignModel` and the registry built from the extracted matrices. Profiles: 4120C, the rest of the 4000 Series, GENERIC, plus one non-4000 model (BetaBrite) to prove the extension path. Strict and advisory validation.
4. **Special functions.** Time, date, weekday, time format, Memory Configuration, clear memory, soft reset, Run Time, Run Sequence, Run Day, speaker, tones, serial address.
5. **STRING Files.** Write and the 125-byte limit.
6. **Transport and `Sign`.** SerialTransport (9600 8N1 default, 7E2 option), pause handling.
7. **Reads.** Read TEXT, read STRING, General Information, Serial Error Status Register.
8. **Hardware bring-up.** Opt-in `pytest -m hardware` against the real 4120C via `ALPHA_SIGN_PORT`. A checklist of manual-vs-hardware differences feeds back into the model profile.

Later, out of scope for the prototype: an ESPHome Wi-Fi bridge transport, DOTS PICTURE files, counters, Alpha 2.0/3.0 additions, ASCII Printable formats, extended characters beyond a basic mapping.

## Test seams (confirmed)

| Seam | Catches | Misses |
|---|---|---|
| `protocol` encode/decode (pure bytes) | Framing, checksum, nesting, escaping, Control Code bytes. Checked against the manual's examples. | Whether the sign accepts them. |
| `Sign` over `FakeTransport` | The high-level API produces the right Packets and pauses, validates against the model, and parses canned Responses. | Serial timing and real hardware quirks. |
| Hardware smoke tests (opt-in) | Real 4120C behavior, baud and parity, Modes that the manual lists but the firmware lacks. | Not run in CI, and needs the sign connected. |

A **sign emulator** for testing is planned separately (see below). It will probably sit at the Transport seam as a further adapter, so it can replace `FakeTransport` in some `Sign` tests.

## Decisions

- **Content API:** segment lists are the core model (strings are literal text, enum members and small value objects are Control Codes). An optional inline markup parser comes later and produces the same model.
- **Connection:** the 4120C will use USB-serial to RJ11. `SerialTransport` is the only production transport for now.
- **No official TCP server support.** Alpha's Ethernet adapters and serial servers are out of scope. A later goal is an ESPHome bridge that puts the sign on Wi-Fi. It will be its own Transport adapter, and its design must keep the protocol's pauses (see the facts table).
- **Validation:** warn by default; `strict=True` raises `UnsupportedCapability`.
- **Emulator:** gets its own plan, `docs/emulator-plan.md`.

## Prior art

| Project | Lang | Notes |
|---|---|---|
| [mjaksn/readerboard](https://github.com/mjaksn/readerboard) | Python 3.11+, MIT | The closest in ambition: an HTTP service, not a library. Byte values are pinned to manual citations in tests. Tests use a fake transport and pyserial `loop://`. It has a PySide6 sign simulator and [protocol notes](https://github.com/mjaksn/readerboard/blob/main/docs/protocol-notes.md) worth reading before Phase 4. Its README reports 13 bytes of overhead per file, where the manual says 11, to verify on hardware. |
| [msparks/alphasign](https://github.com/msparks/alphasign) | Python 2 era | The best-known library. BetaBrite-oriented, no visible tests. We use the import name `alpha_led_sign` to avoid a clash. |
| [prototux/python-alphasign](https://github.com/prototux/python-alphasign) | Python 3, Apache-2.0 | Tested on a 210C. No tests, and reads and special functions are on its TODO list. |
| [tonymagro/asign](https://github.com/tonymagro/asign) | Go | A `{Token}` template language over raw packets. Useful input for the later markup layer. |
| [jonathankoren/betabrite](https://github.com/jonathankoren/betabrite), [depili/betabrite](https://github.com/depili/betabrite) (Ruby), [jon-proulx/alphasign](https://github.com/jon-proulx/alphasign) (Ruby, archived), [bm16ton/betabrite_alpha_led-signs](https://github.com/bm16ton/betabrite_alpha_led-signs) (C) | various | Small or BetaBrite-only. |

None of them is model-agnostic in the way rule 1 above describes, and none targets the 4000 Series. No ESPHome or ESP32 Alpha-sign project turned up.

**Idea taken from readerboard:** open ports with pyserial's `serial_for_url()`. Then `SerialTransport` accepts `/dev/tty...`, `loop://` (tests), and `socket://host:port`. A raw-TCP ESPHome UART bridge (for example a stream-server component) could then work with no new adapter, although the pause concern in the facts table still applies.
