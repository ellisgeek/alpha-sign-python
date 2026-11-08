// Setting the emulated clock from the page (story 24): the page feeds the
// Signs the same Write SPECIAL FUNCTION Packets a library would send.
import { describe, expect, it } from "vitest";
import { clockPackets, parseClockInput } from "../../src/page/clock-set";

const HEAD = "\x00\x00\x00\x00\x00\x01Z00\x02E";

describe("clockPackets", () => {
  it("sets the time of day, the date, and the day of week", () => {
    // 2026-11-07 is a Saturday.
    expect(clockPackets({ year: 2026, month: 11, day: 7, hour: 14, minute: 30 })).toEqual([
      // Table 52 (p. 69): Set Time of Day 14:30, to all signs.
      `${HEAD} 1430\x04`,
      // Set Date, mmddyy (p. 26).
      `${HEAD};110726\x04`,
      // Set Day of Week, "7" = Saturday (p. 22).
      `${HEAD}&7\x04`,
    ]);
  });

  it("pads one-digit fields with a zero", () => {
    expect(clockPackets({ year: 2031, month: 3, day: 2, hour: 7, minute: 5 })).toEqual([
      `${HEAD} 0705\x04`,
      `${HEAD};030231\x04`,
      // 2031-03-02 is a Sunday: "1" (p. 22).
      `${HEAD}&1\x04`,
    ]);
  });
});

describe("parseClockInput", () => {
  it("reads the page's date and time inputs", () => {
    expect(parseClockInput("2026-11-07", "14:30")).toEqual({
      year: 2026,
      month: 11,
      day: 7,
      hour: 14,
      minute: 30,
    });
  });

  it("returns null when either input is empty or malformed", () => {
    expect(parseClockInput("", "14:30")).toBeNull();
    expect(parseClockInput("2026-11-07", "")).toBeNull();
    expect(parseClockInput("2026-13-07", "14:30")).toBeNull();
  });
});
