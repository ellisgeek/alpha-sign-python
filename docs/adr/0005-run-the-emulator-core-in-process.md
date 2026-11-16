# Run the Emulator core in Python's process, from a separate package

Python code can run the Emulator's core in its own process, with no Node. The core
(`emulator/src/core`) is built into one JavaScript file and run in V8 through the
`mini-racer` package. A thin Python wrapper calls the core's Line: `receive`,
`advance`, and each Emulated Sign's snapshot. The file and the wrapper ship as their
own package, `alpha-led-sign-emulator`. The TUI (#7) uses it for its preview, and the
Python tests can use it where real time is not what they test.

ADR 0002 left one way into the core from Python: the headless host under Node,
through `socket://` and its HTTP control channel. That made Node a dependency of any
Python feature that draws the display, and it made every Python test against the
Emulator run in real time. The core has no I/O, no timers, and no clock, so it runs
unchanged in an embedded engine. A prototype drew the same pixels as the page in
about 0.5 ms per frame.

## Considered options

- **Start the headless host under Node** (#7 as first written). Users of the TUI
  would need Node, and a preview would mean a subprocess, two ports, and polling
  `/snapshots` 15 times a second.
- **Port the renderer to Python.** A second renderer to keep in step with the first.
  It would also put the Emulator's code next to the library's, and ADR 0002 keeps
  them apart so that the Emulator stays an independent reading of the manual.
- **`quickjs` as the engine.** Its wheels are small (0.5-2 MB), but its last release
  was in November 2023, and its QuickJS lacks ES2022 built-ins the core uses
  (`Object.hasOwn`). `mini-racer` is current and runs the core as is. Its wheels are
  about 20 MB, and only users of the `tui` extra install them.
- **Put the bundle in the `alpha-led-sign` wheel.** The bundle holds the glyphs
  copied from Appendix O, and ADR 0003 keeps them out of the Python package. A
  separate package keeps that true and carries its own notice for the glyphs.

## Consequences

- This changes two of ADR 0002's consequences. Python tests can run the Emulator
  in-process with virtual time. The Emulator is published, as a Python package. It
  is still not published to npm.
- Independence still holds. The core never references the Python side, and the
  wrapper never imports `alpha_led_sign`. A test fails if it does. Only the library's
  `tui` package and the tests import the wrapper; `alpha_led_sign` itself does not.
- `alpha-led-sign-emulator` has the same version as `alpha-led-sign` and is released
  with it. The `tui` extra pins it to the same version. Releases (ADR 0001) cover both.
- Building the package needs Node, once, at release time and in CI. A contributor who
  works only in Python doesn't need it: the tests that use the in-process Emulator
  skip when the bundle is not built, as the headless host's tests skip without Node.
- The core must run in `mini-racer`'s V8, not only in Node and browsers. A CI test runs
  the built bundle through the wrapper, so a core change that breaks it fails there.
- The headless host stays. The hardware suite (`-m emulator`) still reaches the
  Emulator over `socket://` in real time, because it tests the library's timing (the
  nested-STX pause, a tone's silence) and the real `SerialTransport`. A test that
  checks only what a Sign stores or shows can use the in-process Emulator and take
  milliseconds.
- When the package exists, the README's license note names it as the one package that
  contains the glyph data.
