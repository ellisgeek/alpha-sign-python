// TEXT File content through the display model: the manual's worked examples
// (Tables 47-51, pp. 65-68) and the Appendix G Control Codes (pp. 81-82).
import { describe, expect, it } from "vitest";
import { buildDisplay, DEFAULT_READINGS, model4120C } from "../../src/core";
import { lineTexts, RESTART_MS, sequence, stateWith } from "./display-helpers";

const ESC = "\x1b";

function shown(options: Parameters<typeof stateWith>[0], atMs = RESTART_MS + 1) {
  return buildDisplay(stateWith(options), model4120C, atMs);
}

describe("the manual's TEXT File examples", () => {
  it('Table 47: "HELLO" in ROTATE on the bottom line', () => {
    // Data Field after the Label: <ESC>"&aHELLO" (Table 47, p. 65).
    const display = shown({ text: { D: `${ESC}&aHELLO` } });
    expect(display).toMatchObject({
      fileLabel: "D",
      frameIndex: 0,
      mode: "ROTATE", // "a" 61H Rotate code
      drawnAs: "ROTATE",
      position: "bottom", // "&" 26H bottom line
      specialGraphic: null,
    });
    expect(lineTexts(display)).toEqual(["HELLO"]);
  });

  it("Table 48: SNOW text, a trailing ROTATE, then the WELCOME Special Graphic", () => {
    // <ESC>""n2Hello There"<ESC>""a"<ESC>"&n8" (Table 48, pp. 65-66).
    const state = stateWith({ text: { ">": `${ESC}"n2Hello There${ESC}"a${ESC}&n8` } });
    const shownFrames = sequence((t) => buildDisplay(state, model4120C, t), 20_000).map(
      ({ display }) => ({
        frameIndex: display.frameIndex,
        mode: display.mode,
        drawnAs: display.drawnAs,
        position: display.position,
        specialGraphic: display.specialGraphic,
        lines: lineTexts(display),
      }),
    );
    expect(shownFrames.slice(0, 3)).toEqual([
      // "2" (32H) = SNOW; the Emulator draws it as HOLD and names it.
      {
        frameIndex: 0,
        mode: "SNOW",
        drawnAs: "HOLD",
        position: "top", // 22H = Top Line
        specialGraphic: null,
        lines: ["Hello There"],
      },
      // "a" with no ASCII Message: the previous text is ROTATEd off the Top Line.
      {
        frameIndex: 1,
        mode: "ROTATE",
        drawnAs: "ROTATE",
        position: "top",
        specialGraphic: null,
        lines: [],
      },
      // "8" (38H) = WELCOME, an animation with no ASCII Message, on the Bottom Line.
      {
        frameIndex: 2,
        mode: "WELCOME",
        drawnAs: "HOLD",
        position: "bottom",
        specialGraphic: "WELCOME",
        lines: [],
      },
    ]);
  });

  it("Table 49: two lines of HOLD text on the Top Line, the counter code kept but not drawn", () => {
    // <ESC>""bCongratulations!"<CR><BS>"z days without an accident!" (Table 49, p. 67).
    // The Top Line of a two-line Sign holds one line, so the second shows next.
    const state = stateWith({
      text: { "1": `${ESC}"bCongratulations!\r\bz days without an accident!` },
    });
    const pages = sequence((t) => buildDisplay(state, model4120C, t), 8_000);
    expect(
      pages.slice(0, 2).map(({ display }) => [display.mode, display.position, lineTexts(display)]),
    ).toEqual([
      ["HOLD", "top", ["Congratulations!"]],
      ["HOLD", "top", [" days without an accident!"]],
    ]);
  });

  it("Table 50: the Priority TEXT File takes over in FLASH, middle, Full Height Standard", () => {
    // "A0" <ESC>" c"<SUB>"9EMERGENCY" (Table 50, p. 68); p. 20: other TEXT Files stop.
    const display = shown({ text: { A: "other" }, priority: `${ESC} c\x1a9EMERGENCY` });
    expect(display).toMatchObject({ fileLabel: "0", mode: "FLASH", position: "middle" });
    expect(display.lines).toEqual([
      [{ text: "EMERGENCY", color: 1, font: "full height standard", wide: false, flash: false }],
    ]);
  });

  it("Table 51: an empty Priority TEXT File lets the other TEXT Files run again", () => {
    // "A0" with no data (Table 51, p. 68): "Whatever was running ... will resume running."
    const display = shown({ text: { A: `${ESC} bback` }, priority: "" });
    expect(display.fileLabel).toBe("A");
    expect(lineTexts(display)).toEqual(["back"]);
  });
});

describe("Appendix G Control Codes (pp. 81-82)", () => {
  const runsOf = (data: string, extra: Parameters<typeof stateWith>[0] = {}) =>
    shown({ ...extra, text: { A: `${ESC} b${data}` } }).lines;

  it("1CH selects the character color by its code", () => {
    // 1CH + "1" = Red, "2" = Green, "3" = Amber, "8" = Yellow (p. 82).
    expect(runsOf("\x1c1R\x1c2G\x1c3A\x1c8Y")[0]?.map((r) => [r.text, r.color])).toEqual([
      ["R", 1],
      ["G", 2],
      ["A", 3],
      ["Y", 8],
    ]);
  });

  it("1AH selects a font; a set the Emulator has not drawn uses the default font", () => {
    // 1AH + "1" = Five high standard, "3" = Seven high standard, "2" = Five stroke (p. 82).
    expect(runsOf("\x1a1a\x1a3b\x1a2c")[0]?.map((r) => [r.text, r.font])).toEqual([
      ["a", "five high standard"],
      // The same style either way, so one run.
      ["bc", "seven high standard"],
    ]);
  });

  it("12H and 11H turn wide characters on and off; 07H turns character flash on and off", () => {
    expect(runsOf("a\x12b\x11c\x071d\x070e")[0]?.map((r) => [r.text, r.wide, r.flash])).toEqual([
      ["a", false, false],
      ["b", true, false],
      ["c", false, false],
      ["d", false, true],
      ["e", false, false],
    ]);
  });

  it("1DH attribute 0 is Wide ON or OFF", () => {
    // 1DH + "0" + "1" or "0" = Wide ON or OFF (p. 82).
    expect(runsOf("\x1d01w\x1d00n")[0]?.map((r) => [r.text, r.wide])).toEqual([
      ["w", true],
      ["n", false],
    ]);
  });

  it("0DH starts a new line", () => {
    expect(lineTexts(shown({ text: { A: `${ESC} bONE\rTWO` } }))).toEqual(["ONE", "TWO"]);
  });

  it("0BH calls the date in each listed format", () => {
    // The test clock reads Saturday 2026-11-07 (helpers.ts START_CLOCK_MS).
    const date = (format: string) => lineTexts(shown({ text: { A: `${ESC} b\x0b${format}` } }))[0];
    expect(date("0")).toBe("11/07/26"); // MM/DD/YY
    expect(date("1")).toBe("07/11/26"); // DD/MM/YY
    expect(date("2")).toBe("11-07-26"); // MM-DD-YY
    expect(date("3")).toBe("07-11-26"); // DD-MM-YY
    expect(date("4")).toBe("11.07.26"); // MM.DD.YY
    expect(date("5")).toBe("07.11.26"); // DD.MM.YY
    expect(date("6")).toBe("11 07 26"); // MM DD YY
    expect(date("7")).toBe("07 11 26"); // DD MM YY
    expect(date("8")).toBe("Nov.07, 2026"); // MMM.DD, YYYY
    expect(date("9")).toBe("Saturday"); // Day of week
  });

  it("13H calls the time of day in the clock's time format (p. 29)", () => {
    // 12:00 noon on the test clock; "S" am/pm by default. The layout is the Emulator's own.
    const state = stateWith({ text: { A: `${ESC} b\x13` } });
    expect(lineTexts(buildDisplay(state, model4120C, RESTART_MS))).toEqual(["12:00PM"]);
    state.clock.timeFormat = "M";
    expect(lineTexts(buildDisplay(state, model4120C, RESTART_MS))).toEqual(["12:00"]);
  });

  it("10H calls a STRING File's current content, with its own Control Codes", () => {
    // 10H + STRING File Label (p. 81); STRING data may hold 1CH colors (p. 37).
    const lines = runsOf("Temp \x10T", { strings: { T: "\x1c272F" } });
    expect(lines[0]?.map((r) => [r.text, r.color])).toEqual([
      ["Temp ", 1],
      ["72F", 2],
    ]);
  });

  it("a missing STRING File shows nothing in its place", () => {
    expect(lineTexts(shown({ text: { A: `${ESC} bx\x10Qy` } }))).toEqual(["xy"]);
  });

  it("0CH New page is ignored by default on the 4000 Series", () => {
    // newPageDoubleHeight Reading, default "ignored" (Tables 69, 70).
    expect(lineTexts(shown({ text: { A: `${ESC} bONE\x0cTWO` } }))).toEqual(["ONETWO"]);
  });

  it("0CH New page starts a new page when the Reading says drawn", () => {
    const state = stateWith({ text: { A: `${ESC} bONE\x0cTWO` } });
    const readings = { ...DEFAULT_READINGS, newPageDoubleHeight: "drawn" as const };
    const pages = sequence((t) => buildDisplay(state, model4120C, t, readings), 8_000);
    expect(pages.slice(0, 2).map(({ display }) => lineTexts(display))).toEqual([["ONE"], ["TWO"]]);
  });

  it("speed codes change how long a ROTATE takes: Speed 5 is faster than Speed 1", () => {
    // 15H = Speed 1 (slowest), 19H = Speed 5 (fastest) (p. 81).
    const rotateEnds = (speedCode: string) => {
      const state = stateWith({ text: { A: `${ESC} a${speedCode}HELLO${ESC} bNEXT` } });
      const pages = sequence((t) => buildDisplay(state, model4120C, t), 20_000);
      return pages.find(({ display }) => display.frameIndex === 1)?.atMs ?? Infinity;
    };
    expect(rotateEnds("\x19")).toBeLessThan(rotateEnds("\x15"));
  });
});
