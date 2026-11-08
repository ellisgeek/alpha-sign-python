// Response Packets (Table 14, p. 19; Table 18, p. 36; Tables 45-46, p. 64).
import { describe, expect, it } from "vitest";
import { type CommandTable, createLine, encodeResponse, model4120C } from "../../src/core";
import { bytes, START_CLOCK_MS, SYNC, text } from "./helpers";

// Table 46: <NUL> x 20, <SOH>"000"<STX>"ACFILE C"<ETX>"020C"<EOT>.
const TABLE_46 = `${"\x00".repeat(20)}\x01000\x02ACFILE C\x03020C\x04`;

// A stand-in Read TEXT File handler: answers Table 45 the way Table 46 shows.
const readC: CommandTable = {
  B: (cmd, ctx) => {
    if (cmd.data === "C") ctx.respond("ACFILE C");
  },
};

describe("Response encoder", () => {
  it("frames the Table 46 Response to Read TEXT File C (p. 64)", () => {
    expect(text(encodeResponse("ACFILE C"))).toBe(TABLE_46);
  });
});

describe("Responses on the Line", () => {
  it("sends the Table 46 Response at the read Packet's EOT (Table 45, p. 64)", () => {
    const line = createLine([{ model: model4120C, signAddress: 6 }], {
      startClockMs: START_CLOCK_MS,
      commands: readC,
    });
    line.receive(bytes(`${SYNC}\x01Z06\x02BC`), 1000);
    line.receive(bytes("\x04"), 1005);
    const out = line.advance(2000);
    expect(out.map((o) => ({ text: text(o.bytes), atMs: o.atMs }))).toEqual([
      { text: TABLE_46, atMs: 1005 },
    ]);
  });

  it("holds a delayed Response until the Line reaches its send time", () => {
    const delayed: CommandTable = { B: (_cmd, ctx) => ctx.respond("ACX", { delayMs: 500 }) };
    const line = createLine([{ model: model4120C, signAddress: 6 }], {
      startClockMs: START_CLOCK_MS,
      commands: delayed,
    });
    line.receive(bytes(`${SYNC}\x01Z06\x02BC\x04`), 0);
    expect(line.advance(499)).toEqual([]);
    expect(line.advance(500).map((o) => o.atMs)).toEqual([500]);
    expect(line.advance(1000)).toEqual([]);
  });

  it("never sends a Response for a Packet that does not end with EOT", () => {
    const line = createLine([{ model: model4120C, signAddress: 6 }], {
      startClockMs: START_CLOCK_MS,
      commands: readC,
    });
    line.receive(bytes(`${SYNC}\x01Z06\x02BC\x03`), 0);
    line.receive(bytes(`${SYNC}\x01Z06\x02BC\x04`), 50);
    expect(line.advance(100).map((o) => o.atMs)).toEqual([50]);
  });

  it("merges Responses from two Signs in time order", () => {
    const byAddress: CommandTable = {
      B: (_cmd, ctx) =>
        ctx.respond(`AC${ctx.state.signAddress}`, {
          delayMs: ctx.state.signAddress === 1 ? 300 : 100,
        }),
    };
    const line = createLine(
      [
        { model: model4120C, signAddress: 1 },
        { model: model4120C, signAddress: 2 },
      ],
      { startClockMs: START_CLOCK_MS, commands: byAddress },
    );
    line.receive(bytes(`${SYNC}\x01Z00\x02BC\x04`), 0);
    const out = line.advance(1000);
    expect(out.map((o) => o.atMs)).toEqual([100, 300]);
  });
});
