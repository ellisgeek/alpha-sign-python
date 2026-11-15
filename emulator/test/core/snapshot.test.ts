// A fresh Emulated Sign's snapshot, its model data, and its Readings.
import { describe, expect, it } from "vitest";
import { createLine, model4120C } from "../../src/core";
import { START_CLOCK_MS } from "./helpers";

function freshSign(readings = {}) {
  const line = createLine([{ model: model4120C, signAddress: 0x26, readings }], {
    startClockMs: START_CLOCK_MS,
    startMs: 1000,
  });
  const sign = line.signs()[0];
  if (!sign) throw new Error("no sign");
  return { line, sign };
}

describe("4120C model data", () => {
  it("matches Table 5, Table 3, the 4000 Series brochure, and the hardware", () => {
    expect(model4120C).toMatchObject({
      signType: "a", // Table 5, p. 10: "a" 61H = 4120C sign
      columns: 120, // brochure p. 2: 120 x 16 pixels
      rows: 16,
      lines: 2, // brochure p. 1: two-line display, 1 or 2 line messages
      memoryBytes: 28872, // a real 4120C reported 28,872 (docs/hardware-results.md); brochure p. 2 says 28,000
      maxMessages: 81, // brochure p. 2: 81 different messages
      protocolVersions: ["EZKEY II", "Alpha 1.0"], // Table 3, p. 8: 4000 Series
    });
    // Tricolor: the nine pixel codes of p. 40 ("0" off through "8" yellow).
    expect(model4120C.palette.map((c) => c.name)).toEqual([
      "off",
      "red",
      "green",
      "amber",
      "dim red",
      "dim green",
      "brown",
      "orange",
      "yellow",
    ]);
  });

  it("has General Information firmware fields of the p. 29 widths (PROVISIONAL values)", () => {
    expect(model4120C.firmware.name).toHaveLength(8);
    expect(model4120C.firmware.revision).toHaveLength(1);
    expect(model4120C.firmware.date).toMatch(/^\d{4}$/);
  });
});

describe("snapshot of a fresh Sign", () => {
  it("reports its Sign Type, Sign Address, and a clear register (p. 31: 40H)", () => {
    const snap = freshSign().sign.snapshot();
    expect(snap).toMatchObject({
      signType: "a",
      signAddress: 0x26,
      serialErrors: 0x40,
      speakerOn: false, // p. 29: "FF" speaker disabled (default)
      priority: null,
      tones: [],
      ignored: [],
    });
  });

  it("shows a blank display the size of the model", () => {
    const { display } = freshSign().sign.snapshot();
    expect(display.fileLabel).toBeNull();
    expect(display.pixels.width).toBe(120);
    expect(display.pixels.height).toBe(16);
    expect(display.pixels.colors).toHaveLength(120 * 16);
    expect(display.pixels.colors.every((c) => c === 0)).toBe(true);
  });

  it("starts the clock at the start clock and moves it with Line time", () => {
    const { line, sign } = freshSign();
    expect(sign.snapshot().clock).toMatchObject({
      year: 2026,
      month: 11,
      day: 7,
      hour: 12,
      minute: 0,
      dayOfWeek: 7, // 2026-11-07 is a Saturday; p. 30: "7" = Saturday
      timeFormat: "S", // p. 29: standard am/pm format (default)
    });
    line.advance(1000 + 90 * 60_000);
    expect(sign.snapshot().clock).toMatchObject({ hour: 13, minute: 30 });
  });

  it("returns copies, so changing a snapshot does not change the Sign", () => {
    const { sign } = freshSign();
    sign.snapshot().ignored.push({ atMs: 0, reason: "x", bytes: "" });
    expect(sign.snapshot().ignored).toEqual([]);
  });
});

describe("Readings", () => {
  it("defaults to the cited values in docs/emulator-spec.md, Readings", () => {
    expect(freshSign().sign.settings).toEqual({
      perFileOverhead: 11,
      dotsPictureCounted: true,
      generalInfoLength: "29",
      toneRepeats: "R+1",
      newsFlashTrumpetForm: "none",
      newPageDoubleHeight: "ignored",
      twoDigitYear: "window",
      missingStxPause: "drop",
      networkQueryFraming: "response-packet",
      oversizedWrite: "measured",
      missingDotsPause: "accept",
      dotsPictureSize: "accept",
    });
  });

  it("takes overrides per Sign", () => {
    expect(freshSign({ perFileOverhead: 13 }).sign.settings.perFileOverhead).toBe(13);
  });
});
