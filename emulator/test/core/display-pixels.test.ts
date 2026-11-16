// Golden pixel images, stored as text art in __golden__/ so a person can look at
// them and approve them in review ("." off, R red, G green, A amber, r dim red,
// g dim green, b brown, o orange, y yellow). They show that drawing did not
// change. They are not evidence about real Signs: the fonts are this project's
// own and the Mode timings are approximations (docs/emulator-spec.md, "Pixels").
// To accept a deliberate change: `npx vitest run -u`, then review the diff.
import { describe, expect, it } from "vitest";
import { buildDisplay, model4120C } from "../../src/core";
import { art, sequence, stateWith } from "./display-helpers";

const ESC = "\x1b";
const GREEN = "\x1c2";
const AMBER = "\x1c3";

/** Pixels `offsetMs` after Frame `frameIndex` of File A first appears. */
function pixelsAt(data: string, frameIndex: number, offsetMs: number): string {
  const state = stateWith({ text: { A: data } });
  const show = (t: number) => buildDisplay(state, model4120C, t);
  const start = sequence(show, 30_000).find(({ display }) => display.frameIndex === frameIndex);
  if (!start) throw new Error(`Frame ${frameIndex} never shown`);
  return art(show(start.atMs + offsetMs).pixels);
}

const golden = (name: string, caption: string, pixels: string) =>
  expect(`# ${caption}\n${pixels}`).toMatchFileSnapshot(`__golden__/${name}.txt`);

describe("golden pixels per Mode", () => {
  // Frame 0 holds green "OLD"; frame 1 brings in amber "NEW" with the Mode.
  const transition = (modeCode: string) => `${ESC} b${GREEN}OLD${ESC} ${modeCode}${AMBER}NEW`;

  it("HOLD: centered text, middle position", async () => {
    await golden("hold", "HOLD, middle, 100 ms in", pixelsAt(`${ESC} bHOLD`, 0, 100));
  });

  it("FLASH: lit in the first half period", async () => {
    await golden("flash-on", "FLASH, 100 ms in (on)", pixelsAt(`${ESC} cFLASH`, 0, 100));
  });

  it("FLASH: dark in the second half period", async () => {
    await golden("flash-off", "FLASH, 600 ms in (off)", pixelsAt(`${ESC} cFLASH`, 0, 600));
  });

  it("ROTATE: text travelling right to left", async () => {
    await golden("rotate", "ROTATE, 1200 ms in", pixelsAt(`${ESC} aHELLO`, 0, 1200));
  });

  for (const [code, name] of [
    ["e", "roll-up"],
    ["f", "roll-down"],
    ["g", "roll-left"],
    ["h", "roll-right"],
    ["i", "wipe-up"],
    ["j", "wipe-down"],
    ["k", "wipe-left"],
    ["l", "wipe-right"],
  ] as const) {
    const vertical = "efij".includes(code);
    // About halfway through the transition (see modes.ts timings).
    const offset = vertical ? 640 : 1200;
    it(`${name.toUpperCase()}: halfway from green OLD to amber NEW`, async () => {
      await golden(
        name,
        `${name.toUpperCase()}, ${offset} ms into the second Frame`,
        pixelsAt(transition(code), 1, offset),
      );
    });
  }

  it("Display Positions: top and bottom lines on a two-line Sign", async () => {
    await golden(
      "top-bottom",
      "HOLD top then HOLD bottom, 100 ms into the bottom Frame",
      pixelsAt(`${ESC}"bTOP${ESC}&b${GREEN}BOTTOM`, 1, 100),
    );
  });
});

describe("golden pixels per font", () => {
  for (const [code, name] of [
    ["1", "five-high"],
    ["3", "seven-high"],
    ["6", "ten-high"],
    ["9", "full-height"],
  ] as const) {
    it(`1AH "${code}": ${name}`, async () => {
      await golden(
        `font-${name}`,
        // Middle: in Fill a two-line Sign draws fonts over 7 rows 7 high (p. 96).
        `1AH "${code}" ${name}, HOLD middle`,
        pixelsAt(`${ESC} b\x1a${code}Ag 129`, 0, 100),
      );
    });
  }

  it("wide characters (12H)", async () => {
    await golden("font-wide", "12H wide, HOLD fill", pixelsAt(`${ESC}0b\x12Wide 12`, 0, 100));
  });

  it("every 7-high character (20H-7FH)", async () => {
    const chars = Array.from({ length: 0x60 }, (_, i) => String.fromCharCode(0x20 + i)).join("");
    const pages = [
      chars.slice(0, 20),
      chars.slice(20, 40),
      chars.slice(40, 60),
      chars.slice(60, 80),
      chars.slice(80),
    ];
    const text = pages.map((p) => `${ESC}0b${p}`).join("");
    const drawn = pages.map((_, i) => pixelsAt(text, i, 100)).join("\n");
    await golden("font-seven-high-all", "Seven high, 20H-7FH, 20 per Frame", drawn);
    // Five Frames of 20 characters: under coverage on a CI runner this takes
    // about 9 s, past vitest's 5 s default.
  }, 30_000);
});
