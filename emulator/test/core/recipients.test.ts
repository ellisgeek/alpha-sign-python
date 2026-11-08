// Recipients (Table 4 items C, D, I, p. 10-11; Table 5; Appendix F Tables 38-40, 44).
import { describe, expect, it } from "vitest";
import { createLine, type EmulatorModel, model4120C } from "../../src/core";
import { bytes, recordingCommands, START_CLOCK_MS, SYNC } from "./helpers";

/** Sends a write with the given header to one Sign; true if the Sign ran it. */
function heard(header: string, signAddress: number, model: EmulatorModel = model4120C): boolean {
  const { commands, received } = recordingCommands("A");
  const line = createLine([{ model, signAddress }], { startClockMs: START_CLOCK_MS, commands });
  line.receive(bytes(`${SYNC}\x01${header}\x02AAHELLO\x04`), 0);
  line.advance(10);
  return received.length === 1;
}

const oneLineModel: EmulatorModel = { ...model4120C, name: "one-line test model", lines: 1 };

describe("Sign Type", () => {
  it('"Z" reaches every Sign type (Table 38, p. 58)', () => {
    expect(heard("Z00", 1)).toBe(true);
  });

  it('"?" reaches every Sign type (Table 5)', () => {
    expect(heard("?00", 1)).toBe(true);
  });

  it('"a" reaches a 4120C and "g" (4120R) does not (Table 5)', () => {
    expect(heard("a00", 1)).toBe(true);
    expect(heard("g00", 1)).toBe(false);
  });

  it('"1" reaches one-line Signs only (Table 39, p. 59); the 4120C is a two-line Sign', () => {
    expect(heard("102", 2, oneLineModel)).toBe(true);
    expect(heard("102", 2)).toBe(false);
    expect(heard("202", 2)).toBe(true);
  });

  it('"0" is the Response code and reaches no Sign (Table 5)', () => {
    expect(heard("000", 1)).toBe(false);
  });
});

describe("Sign Address", () => {
  it('"00" is broadcast (p. 11)', () => {
    expect(heard("Z00", 0x2a)).toBe(true);
  });

  it('an exact address reaches only that Sign; addresses are hex (Table 44: "26" = 26H)', () => {
    expect(heard("Z26", 0x26)).toBe(true);
    expect(heard("Z26", 26)).toBe(false);
  });

  it('"1?" reaches 10H through 1FH (Table 40, p. 59)', () => {
    expect(heard("Z1?", 0x10)).toBe(true);
    expect(heard("Z1?", 0x1f)).toBe(true);
    expect(heard("Z1?", 0x0f)).toBe(false);
    expect(heard("Z1?", 0x20)).toBe(false);
  });

  it('"0?" reaches 01H through 0FH (p. 11)', () => {
    expect(heard("Z0?", 0x01)).toBe(true);
    expect(heard("Z0?", 0x0f)).toBe(true);
    expect(heard("Z0?", 0x10)).toBe(false);
  });
});

describe("Multiple Type Codes and Sign Addresses (Table 44, p. 63)", () => {
  const header = "a01,r1?,U26";

  it("reaches a 4120C at 01H through the first pair", () => {
    expect(heard(header, 0x01)).toBe(true);
  });

  it("does not reach a 4120C whose address only another pair's type would match", () => {
    expect(heard(header, 0x15)).toBe(false);
    expect(heard(header, 0x26)).toBe(false);
  });

  it("lists an unreadable header in ignored", () => {
    const { commands } = recordingCommands("A");
    const line = createLine([{ model: model4120C, signAddress: 1 }], {
      startClockMs: START_CLOCK_MS,
      commands,
    });
    line.receive(bytes(`${SYNC}\x01Z0\x02AAHELLO\x04`), 0);
    line.advance(10);
    expect(line.signs()[0]?.snapshot().ignored).toMatchObject([
      { reason: "malformed-packet", bytes: "Z0" },
    ]);
  });
});

describe("Line with two Signs", () => {
  it("each Sign hears only the Packets addressed to it", () => {
    const { commands, received } = recordingCommands("A");
    const line = createLine(
      [
        { model: model4120C, signAddress: 1 },
        { model: model4120C, signAddress: 2 },
      ],
      { startClockMs: START_CLOCK_MS, commands },
    );
    line.receive(bytes(`${SYNC}\x01Z02\x02AAHELLO\x04`), 0);
    line.advance(10);
    expect(received).toHaveLength(1);
  });
});
