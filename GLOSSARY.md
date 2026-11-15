# Alpha Sign Control

Controlling Alpha-protocol LED message signs (the 4000 series, the 4120C in particular) from Python over a serial line.

## Addressing

**Sign**:
One physical display that runs Alpha firmware and listens on a serial network.
_Avoid_: display, device, unit

**Sign Model**:
A specific product, such as the 4120C or the BetaBrite. It fixes a Sign's Sign Type, display size, line count, memory size, supported Protocol Versions, and Capabilities.
_Avoid_: device type, hardware, product

**Series**:
A family of Sign Models that the manual describes together, such as the 4000 Series (4080C, 4120C, 4120R, and others).
_Avoid_: family, line

**Capability**:
One feature a Sign Model can or cannot use: a Mode, a font, a color, or a display option such as time or counters.
_Avoid_: feature flag, support

**Requirement**:
One thing a Command or code needs from a Sign Model to be shown as written: a Protocol Version, a Capability, room in memory, or a display size.
_Avoid_: need, constraint, support

**Protocol Version**:
One revision of the Alpha protocol (EZ KEY II, Alpha 1.0, 2.0, or 3.0). Each Sign Model accepts a known set of them, and later versions add Commands and Control Codes.
_Avoid_: firmware version, protocol level

**Sign Type**:
A one-character code that selects a Sign Model or a group of Signs (for example `a` = 4120C, `1` = all one-line signs, `Z` = all signs). A Sign acts only on Packets whose Sign Type matches it.
_Avoid_: type code (in prose), model id

**Sign Address**:
A number from 0 to 255 that tells Signs of the same Sign Type apart on one network. Address 0 is the broadcast address.
_Avoid_: serial address, id

**Recipient**:
One Sign Type and Sign Address pair, which together select the Signs that act on a Packet.
_Avoid_: target, destination

## Wire format

**Packet**:
One complete transmission: sync bytes, header, one or more Commands, and an end marker.
_Avoid_: frame, message (message means something else here)

**Command**:
One instruction inside a Packet: a Command Code and its data. A Packet with more than one Command is **nested**.
_Avoid_: request, op

**Checksum**:
A 16-bit sum of the bytes of one Command, sent after it so the Sign can reject damaged data.
_Avoid_: CRC, hash

**Response**:
A Packet that a Sign sends back after a read Command.
_Avoid_: reply, ack

## Memory

**File**:
A named area in the Sign's memory that holds content. Each File has one type: TEXT, STRING, or DOTS PICTURE.
_Avoid_: slot, buffer, page

**File Label**:
The single printable character that names a File.
_Avoid_: file name, file id, key

**TEXT File**:
A File that holds a Message. The Sign shows TEXT Files in turn according to the Run Sequence.
_Avoid_: text message, program

**STRING File**:
A small File (max 125 bytes) of plain text that a TEXT File inserts by reference. Writing it updates the display without blanking.
_Avoid_: variable, field

**Priority TEXT File**:
A built-in TEXT File (label `0`) that takes over the display until it is cleared.
_Avoid_: alert, emergency message

**DOTS PICTURE File**:
A File that holds a bitmap a TEXT File can show.
_Avoid_: image, graphic, bitmap file

**Memory Configuration**:
The Sign's table of which Files exist, with their types and sizes. Writing it replaces the whole table and erases every File.
_Avoid_: memory map, allocation, file table

## Content

**Message**:
The content of a TEXT File: one or more Frames shown in sequence.
_Avoid_: text, program

**Frame**:
One part of a Message with a single Mode and Display Position, plus the Segments to show with them.
_Avoid_: page, screen, segment (a Segment is one piece of a Frame)

**Segment**:
One piece of a Frame's or STRING File's content: a run of literal text or one Control Code.
_Avoid_: token, chunk (a Chunk is a piece of a Packet on the wire)

**Mode**:
The transition or effect used to show a Frame, for example rotate, hold, or snow.
_Avoid_: effect, animation, transition

**Special Graphic**:
A built-in animation (fireworks, "Thank You", and so on) that a Frame can show in place of text.
_Avoid_: animation, special mode

**Display Position**:
Which line or lines of a multi-line Sign a Frame uses: top, middle, bottom, or fill.
_Avoid_: line, row, alignment

**Control Code**:
A byte or short byte sequence inside text that changes how the following text looks or inserts live content, such as a color, font, speed, the time, or a STRING File reference.
_Avoid_: escape code, tag, markup

**Markup**:
A string spelling of a Message or of Segments, with Control Codes and Frames written as tokens in braces, such as `{color red}` or `{frame rotate top}`.
_Avoid_: template, tags, format string

## Scheduling

**Run Time**:
The daily start and stop times for a TEXT File, in 10-minute steps, or Always, Never, or All Day.
_Avoid_: schedule, window

**Run Sequence**:
The ordered list of TEXT Files the Sign cycles through.
_Avoid_: playlist, rotation

## Emulator

**Emulator**:
The program in `emulator/` that acts like one or more Signs on a Line and draws what each one shows (docs/emulator-spec.md).
_Avoid_: simulator, mock

**Emulated Sign**:
One Sign inside the Emulator, with an emulator model and its Readings.
_Avoid_: virtual sign, fake sign

**Line**:
The serial network that Signs listen on, shared by every Sign attached to it.
_Avoid_: bus

**Reading**:
An Emulator setting that picks one reading of an unclear point in the manual. Each one has a default with a cited source.
_Avoid_: option, flag, quirk
