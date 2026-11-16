# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(see [ADR 0001](docs/adr/0001-semantic-versioning.md)).

## [0.1.0] - 2026-11-16

### Added

- Encode Packets with checksums, nesting, and required pauses
- Write TEXT Files with Frames, Modes, and Control Codes
- Add Sign Model profiles and validate Commands against them
- Add SPECIAL FUNCTION Commands for clock, memory, scheduling, and sound
- Write STRING Files for live values without blanking the display
- Control a Sign over a serial port with a task-shaped API
- Read TEXT and STRING Files, General Information, and serial errors back
- Discover Signs and their Sign Addresses with a Network Query
- Set Run Times, Run Days, the speaker, tones, and the Sign Address from Sign, and check Memory Configurations
- Add a Sign emulator that draws Alpha Signs in a browser and runs the hardware tests offline
- Add examples for a Vegas mode light show and for how fast a Sign takes new data
- Model the 4120C as measured on a real Sign, and refuse broadcast reads unless broadcast_reads=True
- Write, read, and call SMALL DOTS PICTURE Files, and draw them in the emulator
- Draw the emulator's text with the manual's own fonts from Appendix O
- Write and read Messages as markup, such as "{color red}Temp: {string T}"
- Warn that a two-line Sign shows fonts over 7 rows high at 7 rows outside the Middle position
- Add a command-line interface, installed with the cli extra
- End a Packet at Clear Memory, since a 4120C drops any Command that follows it
