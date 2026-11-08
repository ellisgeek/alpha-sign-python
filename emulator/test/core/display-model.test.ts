// Which TEXT File and Frame the display shows, and when it blanks.
import { describe, expect, it } from "vitest";
import {
  buildDisplay,
  DEFAULT_READINGS,
  type EmulatorModel,
  model4120C,
  RED_PALETTE,
} from "../../src/core";
import { art, lineTexts, RESTART_MS, sequence, stateWith } from "./display-helpers";

const ESC = "\x1b";

const filesShown = (state: ReturnType<typeof stateWith>, forMs = 20_000) =>
  sequence((t) => buildDisplay(state, model4120C, t), forMs).map(
    ({ display }) => display.fileLabel,
  );

describe("the Run Sequence", () => {
  it("runs the TEXT Files in Run Sequence order (p. 23)", () => {
    const state = stateWith({
      text: { A: `${ESC} bAAA`, B: `${ESC} bBBB` },
      runSequence: ["B", "A"],
    });
    expect(filesShown(state).slice(0, 3)).toEqual(["B", "A", "B"]);
  });

  it("skips a Label that is not a TEXT File (p. 23: the next File Label is processed)", () => {
    const state = stateWith({
      text: { A: `${ESC} bAAA` },
      strings: { S: "x" },
      runSequence: ["S", "Z", "A"],
    });
    expect(filesShown(state)).toEqual(["A"]);
  });

  it("starts at the last received TEXT File after a restart (p. 18)", () => {
    const state = stateWith({
      text: { A: `${ESC} bAAA`, B: `${ESC} bBBB`, C: `${ESC} bCCC` },
      startLabel: "B",
    });
    expect(filesShown(state).slice(0, 3)).toEqual(["B", "C", "A"]);
  });

  it("shows a blank display when no TEXT File has content", () => {
    const display = buildDisplay(stateWith({ text: { A: "" } }), model4120C, RESTART_MS + 5);
    expect(display.fileLabel).toBeNull();
    expect(display.pixels.colors.every((c) => c === 0)).toBe(true);
  });
});

describe("blanking", () => {
  it("a STRING File update changes the text without restarting the display (p. 37)", () => {
    const state = stateWith({
      text: { A: `${ESC} bONE${ESC} bT=\x10T` },
      strings: { T: "1" },
    });
    const pages = sequence((t) => buildDisplay(state, model4120C, t), 10_000);
    const second = pages.find(({ display }) => display.frameIndex === 1);
    if (!second) throw new Error("second Frame never shown");
    const at = second.atMs + 50;
    expect(lineTexts(buildDisplay(state, model4120C, at))).toEqual(["T=1"]);
    const files = state.files;
    files.T = { label: "T", type: "STRING", data: "2" };
    const after = buildDisplay(state, model4120C, at);
    expect(after.frameIndex).toBe(1);
    expect(lineTexts(after)).toEqual(["T=2"]);
  });

  it("a TEXT write restarts the display from the first Frame (p. 17: the display blanks)", () => {
    const state = stateWith({ text: { A: `${ESC} bONE${ESC} bTWO` } });
    const pages = sequence((t) => buildDisplay(state, model4120C, t), 10_000);
    const second = pages.find(({ display }) => display.frameIndex === 1);
    if (!second) throw new Error("second Frame never shown");
    state.displayRestartedAtMs = second.atMs + 50;
    expect(buildDisplay(state, model4120C, second.atMs + 50).frameIndex).toBe(0);
  });

  it("before the restart time the display is blank", () => {
    // A ROLL UP starts from an empty display, so its first moment is dark.
    const state = stateWith({ text: { A: `${ESC} eHELLO` } });
    const display = buildDisplay(state, model4120C, RESTART_MS);
    expect(display.pixels.colors.every((c) => c === 0)).toBe(true);
  });
});

describe("Modes the Emulator does not draw yet", () => {
  it("draw as HOLD with the Mode named (Table 66 TWINKLE)", () => {
    const display = buildDisplay(
      stateWith({ text: { A: `${ESC}0n0SPARKS` } }),
      model4120C,
      RESTART_MS + 5,
    );
    expect(display).toMatchObject({ mode: "TWINKLE", drawnAs: "HOLD", position: "fill" });
    expect(display.pixels.colors.some((c) => c !== 0)).toBe(true);
  });

  it("label a Special Graphic by its Table 67 name (S = THANK YOU)", () => {
    const display = buildDisplay(
      stateWith({ text: { A: `${ESC}0nS` } }),
      model4120C,
      RESTART_MS + 5,
    );
    expect(display).toMatchObject({
      mode: "THANK YOU",
      drawnAs: "HOLD",
      specialGraphic: "THANK YOU",
      lines: [],
    });
  });

  it("accept NEWS FLASH as the newsFlashTrumpetForm Reading says (Table 66)", () => {
    const at = (form: "letters" | "hex" | "both", specifier: string) =>
      buildDisplay(stateWith({ text: { A: `${ESC}0n${specifier}` } }), model4120C, RESTART_MS + 5, {
        ...DEFAULT_READINGS,
        newsFlashTrumpetForm: form,
      }).specialGraphic;
    expect(at("both", "A")).toBe("NEWS FLASH");
    expect(at("both", ":")).toBe("NEWS FLASH");
    expect(at("letters", ";")).toBeNull();
    expect(at("hex", "B")).toBeNull();
    expect(at("hex", ";")).toBe("TRUMPET");
  });

  it("a Message with no Mode Field draws as HOLD named AUTOMODE", () => {
    const display = buildDisplay(stateWith({ text: { A: "plain" } }), model4120C, RESTART_MS);
    expect(display).toMatchObject({ mode: "AUTOMODE", drawnAs: "HOLD", position: "fill" });
    expect(lineTexts(display)).toEqual(["plain"]);
  });
});

describe("palettes", () => {
  it("a red-only model draws every color as red (Table 69 note 1: R signs are red only)", () => {
    const redModel: EmulatorModel = { ...model4120C, name: "4120R", palette: RED_PALETTE };
    const state = stateWith({ text: { A: `${ESC} b\x1c2GREEN \x1c3AMBER` } });
    const display = buildDisplay(state, redModel, RESTART_MS + 5);
    expect(display.lines[0]?.map((r) => r.color)).toEqual([1]);
    expect(new Set(art(display.pixels).replace(/\n/g, ""))).toEqual(new Set([".", "R"]));
  });
});
