// Packet parsing through the Line (manual pp. 10-14, Appendix F).
import { describe, expect, it } from "vitest";
import { createLine, model4120C } from "../../src/core";
import { bytes, recordingCommands, START_CLOCK_MS, SYNC } from "./helpers";

function lineWith(codes: string, signAddress = 1) {
  const { commands, received } = recordingCommands(codes);
  const line = createLine([{ model: model4120C, signAddress }], {
    startClockMs: START_CLOCK_MS,
    commands,
  });
  const sign = line.signs()[0];
  if (!sign) throw new Error("no sign");
  return { line, sign, received };
}

describe("Packet parser", () => {
  it("runs the Command in the Table 38 standard packet (p. 58)", () => {
    const { line, received } = lineWith("A");
    line.receive(bytes(`${SYNC}\x01Z00\x02AAHELLO\x04`), 0);
    line.advance(10);
    expect(received).toEqual([
      { code: "A", data: "AHELLO", atMs: 0, dataAtMs: [0, 0, 0, 0, 0, 0] },
    ]);
  });

  it("accepts five SOHs in place of the sync NULs (Table 4 item A)", () => {
    const { line, received } = lineWith("A");
    line.receive(bytes("\x01\x01\x01\x01\x01\x01Z00\x02AAHELLO\x04"), 0);
    line.advance(10);
    expect(received.map((c) => c.data)).toEqual(["AHELLO"]);
  });
});

describe("Checksums (p. 12)", () => {
  it("runs the Command in the Table 41 packet, Checksum 01FB (p. 60)", () => {
    const { line, sign, received } = lineWith("A");
    line.receive(bytes(`${SYNC}\x01Z00\x02AAHELLO\x0301FB\x04`), 0);
    line.advance(10);
    expect(received.map((c) => c.data)).toEqual(["AHELLO"]);
    expect(sign.snapshot().serialErrors).toBe(0x40);
    expect(sign.snapshot().ignored).toEqual([]);
  });

  it("drops a Command with a bad Checksum, sets register bit 4, and lists it (pp. 12, 31)", () => {
    const { line, sign, received } = lineWith("A");
    line.receive(bytes(`${SYNC}\x01Z00\x02AAHELLO\x0301FC\x04`), 0);
    line.advance(10);
    expect(received).toEqual([]);
    const snap = sign.snapshot();
    // p. 31: default 01000000B, Serial Checksum Error is bit 4 -> 01010000B.
    expect(snap.serialErrors).toBe(0b01010000);
    expect(snap.ignored).toMatchObject([{ reason: "bad-checksum", bytes: "AAHELLO", atMs: 0 }]);
  });
});

describe("Nested Packets (pp. 13-14)", () => {
  // The library pauses after each STX; here every STX is followed by 100 ms.
  function sendPaused(line: ReturnType<typeof lineWith>["line"], parts: string[]): number {
    let t = 0;
    for (const part of parts) {
      line.receive(bytes(part), t);
      t += part.endsWith("\x02") ? 100 : 1;
    }
    return t;
  }

  it("runs both Commands of the Table 42 packet with Checksums 00C4 and 01FB (p. 61)", () => {
    const { line, received } = lineWith("AE");
    const end = sendPaused(line, [`${SYNC}\x01Z00\x02`, "E'S\x0300C4\x02", "AAHELLO\x0301FB\x04"]);
    line.advance(end);
    expect(received.map((c) => [c.code, c.data])).toEqual([
      ["E", "'S"],
      ["A", "AHELLO"],
    ]);
  });

  it("runs both Commands of the Table 43 packet without Checksums (p. 62)", () => {
    const { line, received } = lineWith("AE");
    const end = sendPaused(line, [`${SYNC}\x01Z00\x02`, "E'S\x03\x02", "AAHELLO\x03\x04"]);
    line.advance(end);
    expect(received.map((c) => c.code)).toEqual(["E", "A"]);
  });

  it("drops a nested Command whose STX is not followed by 100 ms (p. 11)", () => {
    const { line, sign, received } = lineWith("AE");
    line.receive(bytes(`${SYNC}\x01Z00\x02`), 0);
    line.receive(bytes("E'S\x03\x02AAHELLO\x03\x04"), 100);
    line.advance(200);
    expect(received.map((c) => c.code)).toEqual(["E"]);
    expect(sign.snapshot().ignored).toMatchObject([
      { reason: "missing-stx-pause", bytes: "AAHELLO", atMs: 100 },
    ]);
  });

  it("accepts the same Packet under the 'accept' Missing STX pause Reading", () => {
    const { commands, received } = recordingCommands("AE");
    const line = createLine(
      [{ model: model4120C, signAddress: 1, readings: { missingStxPause: "accept" } }],
      { startClockMs: START_CLOCK_MS, commands },
    );
    line.receive(bytes(`${SYNC}\x01Z00\x02`), 0);
    line.receive(bytes("E'S\x03\x02AAHELLO\x03\x04"), 100);
    line.advance(200);
    expect(received.map((c) => c.code)).toEqual(["E", "A"]);
  });

  it("accepts a nested STX followed by exactly 100 ms (p. 11: at least 100 ms)", () => {
    const { line, received } = lineWith("AE");
    line.receive(bytes(`${SYNC}\x01Z00\x02E'S\x03\x02`), 0);
    line.receive(bytes("AAHELLO\x03\x04"), 100);
    line.advance(200);
    expect(received.map((c) => c.code)).toEqual(["E", "A"]);
  });
});

describe("Command Codes (Table 6, p. 11)", () => {
  it("ignores a code outside Table 6 and sets register bit 5 (p. 31)", () => {
    const { line, sign } = lineWith("");
    line.receive(bytes(`${SYNC}\x01Z00\x02Qxyz\x04`), 0);
    line.advance(10);
    const snap = sign.snapshot();
    expect(snap.serialErrors).toBe(0b01100000);
    expect(snap.ignored).toMatchObject([{ reason: "unknown-command", bytes: "Qxyz" }]);
  });

  it("ignores a Table 6 code with no handler without flagging the register", () => {
    const { line, sign } = lineWith("");
    line.receive(bytes(`${SYNC}\x01Z00\x02AAHELLO\x04`), 0);
    line.advance(10);
    const snap = sign.snapshot();
    expect(snap.serialErrors).toBe(0x40);
    expect(snap.ignored).toMatchObject([{ reason: "unsupported-command", bytes: "AAHELLO" }]);
  });
});

describe("Line time", () => {
  it("does not process bytes until the Line is advanced to their time", () => {
    const { line, received } = lineWith("A");
    line.receive(bytes(`${SYNC}\x01Z00\x02AAHELLO\x04`), 500);
    line.advance(499);
    expect(received).toEqual([]);
    line.advance(500);
    expect(received).toHaveLength(1);
  });

  it("drops bytes that arrive while input is blocked (tone silence, p. 27 note 4)", () => {
    const { commands, received } = recordingCommands("A");
    commands.E = (_cmd, ctx) => {
      ctx.state.inputBlockedUntilMs = 3000;
    };
    const line = createLine([{ model: model4120C, signAddress: 1 }], {
      startClockMs: START_CLOCK_MS,
      commands,
    });
    line.receive(bytes(`${SYNC}\x01Z00\x02E(0\x04`), 0);
    line.receive(bytes(`${SYNC}\x01Z00\x02AAHELLO\x04`), 1000);
    line.receive(bytes(`${SYNC}\x01Z00\x02AAAGAIN\x04`), 3000);
    line.advance(3000);
    expect(received.map((c) => c.data)).toEqual(["AAGAIN"]);
    const ignored = line.signs()[0]?.snapshot().ignored;
    expect(ignored).toMatchObject([{ reason: "input-blocked", atMs: 1000 }]);
    expect(ignored?.[0]?.bytes).toBe(`${SYNC}\x01Z00\x02AAHELLO\x04`);
  });
});
