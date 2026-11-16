# Hackeriet's 4200C teardown notes

Everything on the Hackeriet wiki page about their Alpha 4200C, restated here so that it
survives if the page changes. The facts below are Hackeriet's, not this project's.

- Source: [Ericsson / Alpha-American 4200C LED Sign](https://wiki.hackeriet.no/infra/led-display-sign),
  Hackeriet wiki. Read on 2026-11-15.
- The page's photos and logic analyzer screenshots are not copied; see the source.
- The last section, "How this compares with our 4120C", is this project's and is kept
  apart from Hackeriet's facts.

## The Sign

- An Ericsson-branded Alpha-American (Adaptive Micro Systems) **4200C**, given to
  Hackeriet by pere and asle.
- Manufactured 2004-04-08.
- Power: 100-240 V AC, 50/60 Hz, 1.5 A. Indoor use only.
- Status when documented: it works and shows a test message at power-up. How it was
  meant to be operated was not known to them.
- They describe it as a programmable LED display of the kind used for transit, public
  information, and industrial messages.

## Microcontroller

- A **TS80C32X2**, compatible with the Intel 8051.
- Datasheet: <https://ww1.microchip.com/downloads/en/devicedoc/doc4184.pdf>
- Intel *MCS 51 Microcontroller Family User's Manual*:
  <https://datasheets.chipdb.org/Intel/MCS51/MANUALS/27238302.PDF>

## Firmware

- The EPROM label reads **"4200c CUST 1018-6008e"**, and the Sign shows **CUST** while
  it boots, so it seems to run custom firmware.
- Dumps, in four files:
  - <https://hackeriet.no/tmp/bango/dump01.BIN>
  - <https://hackeriet.no/tmp/bango/dump02.BIN>
  - <https://hackeriet.no/tmp/bango/dump03.BIN>
  - <https://hackeriet.no/tmp/bango/dump04.BIN>
- Total size 128 KB (131,072 bytes). SHA-1
  `e5e3bdad5e507f658a874d40483de60161152777`. The page gives no size or hash for each
  file.

## Firmware analysis

- The 8051 is a Harvard design with two separate 16-bit address spaces, program memory
  and external data memory (XRAM). It can address 64 KB of each. Hackeriet's working
  idea: the 128 KB ROM is used as two 64 KB halves. Either one is program memory and
  one is XRAM, or both are program memory with bank switching.
- After reset an 8051 starts at 0000H (Intel's manual).
- The first 256 bytes of the low and high halves are alike. Both hold
  "(c) COPYRIGHT ADAPTIVE MICRO SYSTEMS, INC. 1991" at the same offset.
- Every other ASCII string is in the low half.
- Both halves begin `02 01 00`: `LJMP 0x0100`. So both look like code, which points to
  bank-switched program memory. The real program seems to start at 0x0100 in each.
- Data extent:
  - low half: 0x0000-0xC3EF;
  - high half: 0x0000-0x8EF3.
- From about 0x1000 the high half has patterns with many zeros. That suggests data, not
  code, and it isn't strings. Possibly font data.
- At 0x0100 in the high half, the code sets bits on I/O ports and then loops forever.
  The low half has NOPs at the same addresses. So that code probably switches to the
  low bank, maybe through port P1.
- Ghidra can load Intel 8051 binaries.

## Ports

- One RJ-style modular jack on the back panel, carrying RS-232 IN, RS-485 IN, and
  RS-485 OUT.
- An IR sensor behind a red sticker, visible with a panel removed.
- RJ-12 pinout, counted from the left with the clip down:

| Pin | Signal | Their USB-TTL / DB-9 hookup |
|---|---|---|
| 1 | Ground | GND / DB-9 pin 5 |
| 2 | RS-485 (+) | |
| 3 | RXD | adapter TXD / DB-9 pin 3 |
| 4 | TXD | adapter RXD / DB-9 pin 2 |
| 5 | RS-485 (-) | |
| 6 | +5 V, 200 mA max | |

- A small dongle with resistors came with the Sign. They think it terminates and biases
  the RS-485 line.

## Communication

- They expect the Alpha Sign Communications Protocol: serial Packets framed with STX
  and ETX, carrying text, control commands, and time-based messages. Several Signs can
  share one RS-485 network.
- Their suggested first connection, untested: RS-232 IN, one device, 9600 or 19200
  baud, 8 data bits, no parity, 1 stop bit, no flow control.

## Display driver (logic analyzer)

They captured the cable between the main board and the chain of driver boards. Some
channels were duplicated or missing in the capture, so parts are inferred.

- Six lines: a data line and a clock line for red, the same for green, and two more.
- The display is 16 rows by 200 columns. Each module is 8 bits wide, with 25 modules
  per row, so each channel carries 200 bits per row.
- Each row is shifted out starting with the **bottom** row, 8 bits at a time (one
  module, left to right). The red channel is sent first, then the green channel on its
  own lines. Then the row select moves up one row and the next row is sent.
- The row select wraps around by itself. They suspect a pulse at the end of the first
  row of each frame resets the output latches.

## Infrared

Normal setup of the Sign seems to be by IR: a remote control, or an IR message loader
plugged into the RJ-12 jack. They found no capture of the remote in the usual
collections:

- [LIRC remote configurations](https://lirc.sourceforge.net/remotes/)
- [Flipper IRDB](https://github.com/Lucaslhm/Flipper-IRDB)

## Resources they list

- [Alpha American technical manuals](https://www.alpha-american.com/Technical-Manuals.html)
- [Alpha Sign Communications Protocol](https://www.alpha-american.com/alpha-manuals/M-Protocol.pdf)
  (`M-Protocol.pdf` here)
- [Cables, adapters, and interfaces](https://www.alpha-american.com/alpha-manuals/M-Cables-Adapters-Interfaces.pdf)
  (`M-Cables-Adapters-Interfaces.pdf` here)
- [rainfay/LedSign](https://github.com/rainfay/LedSign): C programs for Adaptive Micro
  Systems signs, which may or may not work with theirs.

## How this compares with our 4120C

This project's notes, not Hackeriet's.

- **Firmware number.** Our 4120C reports firmware `10184403` rev `O` (1206) in General
  Information. That is the same numbering as their label's "1018-6008e", so our label
  probably reads "1018-4403". Theirs says CUST; ours is not known to be custom.
- **Line settings.** 9600 baud 8N1 works on our 4120C over RS-232
  ([hardware-results.md](../hardware-results.md)). 19200 was not tried.
- **Pinout.** Their RJ-12 pinout matches the 4000 Series sign port in *Networking Alpha
  Signs* (pp. 33, 35) and TechMemo 02-0010A, including the 200 mA limit on +5 V.
- **Display.** Their row-scanned red and green channels fit our tricolor 4120C (red,
  green, and amber where both are lit). The 4120C is 120 columns, so 15 modules a row,
  if it uses the same driver boards.
- **Firmware plan.** What this means for dumping and studying our 4120C's ROM is in
  [issue #3](https://github.com/ellisgeek/alpha-sign-python/issues/3).
