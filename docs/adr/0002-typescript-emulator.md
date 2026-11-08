# Write the Sign emulator in TypeScript for the browser

The Emulator (docs/emulator-spec.md) is written in TypeScript. Its core runs
in the browser, where a page draws each Emulated Sign's display, and under
Node, where a headless host serves CI and the Python tests. It lives in
`emulator/` as its own npm project.

Graphical output is required. A browser draws an LED matrix on a canvas and
plays tones with Web Audio, with no GUI toolkit to install.

A second language also makes the Emulator independent by construction. It
can't import the library's encoder, decoder, or data, so it is a second
implementation of the manual, written from the manual. CLAUDE.md requires
expected bytes from an independent source, and an emulator that shared the
library's code would only check the library against itself. When the two
implementations agree, that is evidence; when they disagree, one of them has
misread the manual.

A Python emulator was considered, because the Python tests could then run it
in-process with virtual time. It was rejected for the reasons above.

## Consequences

- The Python tests reach the Emulator through the headless host and
  `SerialTransport` over `socket://`, so pauses are real: a test that sounds
  a tone takes 3 s. The core's own tests keep virtual time.
- The core follows the same rule as `alpha_led_sign.protocol`: no I/O, no timers,
  no clock. Time is an input.
- The emulator project must never reference the Python package or its
  capability data. A test in `emulator/` fails if it does.
- Contributors who work on the Emulator need Node (the current LTS, in
  `emulator/.nvmrc`). Python-only work does not, and the Emulator tests skip
  when Node is missing.
- The Emulator is not published and has no version of its own.
  Releases (ADR 0001) cover the Python package only.
