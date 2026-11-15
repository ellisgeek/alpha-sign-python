# alpha-led-sign

A typed Python library for controlling Alpha-protocol LED message signs (for
example the Alpha 4000 Series) over a serial line.

It covers the Alpha 1.0 protocol: TEXT and STRING Files with Modes, colors,
fonts, and live time, date, and STRING values; the Priority TEXT File; Memory
Configuration and scheduling; the clock; tones; reads; and finding Signs on a
network. Every byte sequence is tested against the worked examples in Alpha's
protocol manual.

## Example

```python
from datetime import datetime

from alpha_led_sign import (
    Color, CurrentTime, Frame, Message, Mode, Position, Sign, StringFile, StringRef,
    TextFile, models,
)

with Sign.serial("/dev/tty.usbserial-1410", model=models.ALPHA_4120C) as sign:
    sign.show("Hello")  # TEXT File "A"

    # Writing the Memory Configuration erases every File on the Sign.
    sign.configure_memory([TextFile("A", size=512), StringFile("T", size=16)])
    sign.write_text("A", Message(
        Frame(Mode.ROTATE, Position.TOP, [Color.RED, "Temp: ", StringRef("T")]),
        Frame(Mode.HOLD, Position.BOTTOM, [Color.GREEN, CurrentTime()]),
    ))
    sign.write_string("T", "72F")  # updates without blanking the display
    sign.set_clock(datetime.now())

    sign.priority(Frame(Mode.FLASH, content=["EMERGENCY"]))
    sign.clear_priority()
```

## Markup

A string given to `show`, `write_text`, `write_string`, or `priority` is markup:
text, with Control Codes and Frames in braces.

```python
sign.write_text("A", "{frame rotate top}{color red}Temp: {string T}"
                     "{frame hold bottom}{color green}{time}")
sign.write_string("T", escape_markup(reading))  # outside values: keep braces literal
print(to_markup(sign.read_text("A")))
```

A token is a kind and its values: `{color red}`, `{font seven_high}`,
`{speed 3}`, `{wide on}`, `{date mmm_dd_yyyy}`, `{time}`, `{new_line}`,
`{string T}`, `{picture A}`, and `{raw 1F...}` for bytes the library does not
model. Values are the enum member names in lowercase. `{frame MODE POSITION}`
starts a Frame (`{frame special snow}`, `{frame graphic fireworks}`); `{{` and
`}}` are literal braces. A string inside a list of Segments is never parsed.

The default position is `fill`. On a two-line Sign such as the 4000 Series, Fill,
Top, and Bottom show fonts at most 7 rows high, so use `{frame hold middle}` for
`{font full_height}`; the library warns otherwise.

## Pictures

```python
arrow = DotsPicture.parse("0010\n0111\n1111\n0111\n0010")  # p. 40 pixel codes
sign.configure_memory([TextFile("A", size=64), DotsPictureFile("P", rows=5, columns=4)])
sign.write_dots_picture("P", arrow)  # the size must match its File
sign.show("Go {picture P}")
```

`Sign.serial` accepts any [pyserial URL](https://pyserial.readthedocs.io/en/latest/url_handlers.html),
including `socket://host:port` for a serial-to-TCP bridge. The default line
settings are 9600 baud, 8N1; pass `serial_format=SerialFormat.SEVEN_E_TWO` for
7E2.

## Sign Models

A Sign Model profile (`models.ALPHA_4120C`, the rest of the 4000 Series,
`models.BETABRITE`) gives the Sign Type to address and the Capabilities from
the manual's tables. Content a model lacks raises a warning, or
`UnsupportedCapability` with `Sign(..., strict=True)`. `models.GENERIC` works
with any Alpha sign and checks only the Protocol Version.

## Scheduling

```python
from datetime import time

from alpha_led_sign import RunDay, RunDays, RunTime

sign.set_run_times({
    "A": RunTime.between(time(8, 0), time(17, 0)),  # 10-minute steps
    "B": RunTime.ALWAYS,
})
sign.set_run_days({"A": RunDays(RunDay.WEEKDAYS)})
sign.run_sequence("AB")  # each File during its Run Time
```

Writing Run Times or Run Days ends a Priority TEXT File. The Sign also has
`set_speaker`, `tone`, and `set_sign_address`.

## Reading and discovery

```python
sign.read_text("A")         # -> Message
sign.read_string("T")       # -> ("72F",)
sign.info()                 # firmware, clock, memory
sign.serial_errors().ok     # did the last Packets arrive intact?

from alpha_led_sign import discover
discover(sign.transport, max_address=15)  # Signs and their Sign Addresses
```

Every Sign that matches the address answers a read, so reads to Sign Address 0
(the default) or a `?` pattern raise `ValueError`. Give the Sign's own address, or
pass `broadcast_reads=True` when only one Sign is on the line.

Discovery waits 1 s plus 0.5 s for each address searched, because each Sign
answers in turn. Lower `max_address` when the addresses are known to be small.

## Status

The library has been run against a real 4120C. What it found, item by item against
the manual, is in [docs/hardware-results.md](docs/hardware-results.md); the hardware
checklist in [docs/spec.md](docs/spec.md) lists what still needs confirmation. To
run the hardware tests:

```sh
ALPHA_SIGN_PORT=/dev/tty.usbserial-1410 uv run pytest -m hardware
```

The design, test seams, and open work are in [docs/spec.md](docs/spec.md);
the domain terms are in [GLOSSARY.md](GLOSSARY.md). See
[CONTRIBUTING.md](CONTRIBUTING.md) to work on it.
