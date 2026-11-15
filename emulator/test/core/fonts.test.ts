// The fonts come from Appendix O of the manual (pp. 141-216). Expected glyphs here
// were typed from the manual's pages, not from the generated data.
import { describe, expect, it } from "vitest";
import { fontForCode, type Glyph } from "../../src/core/display/fonts";

function art(g: Glyph): string[] {
  const rows: string[] = [];
  for (let y = 0; y < g.height; y++) {
    rows.push(
      Array.from({ length: g.width }, (_, x) => (g.bits[y * g.width + x] ? "#" : ".")).join(""),
    );
  }
  return rows;
}

describe("Appendix O glyphs", () => {
  it("7-High Regular (SS7) A, B, and E are as drawn on p. 144", () => {
    const font = fontForCode("3");
    expect(art(font.glyph("A"))).toEqual([
      "..#..",
      ".#.#.",
      "#...#",
      "#...#",
      "#####",
      "#...#",
      "#...#",
    ]);
    expect(art(font.glyph("B"))).toEqual([
      "####.",
      "#...#",
      "#...#",
      "####.",
      "#...#",
      "#...#",
      "####.",
    ]);
    expect(art(font.glyph("E"))).toEqual(["####", "#...", "#...", "###.", "#...", "#...", "####"]);
  });

  it("each 1AH code selects the manual's set at its height", () => {
    // Appendix G, p. 82: "1" five high, "3" seven high, "5" seven high fancy,
    // "6" ten high, "8" full height fancy, "9" full height standard.
    const fonts = ["1", "3", "5", "6", "8", "9"].map((code) => fontForCode(code, 16));
    expect(fonts.map((f) => [f.name, f.height])).toEqual([
      ["five high standard", 5],
      ["seven high standard", 7],
      ["seven high fancy", 7],
      ["ten high standard", 10],
      ["full height fancy", 16],
      ["full height standard", 16],
    ]);
  });

  it("full height is the 15-high set on a Sign shorter than 16 rows (Table 69: 15/16 row)", () => {
    expect(fontForCode("9", 15).height).toBe(15);
    expect(fontForCode("8", 15).height).toBe(15);
  });

  it("the five high set has no lowercase, so lowercase shows as capitals", () => {
    const font = fontForCode("1");
    expect(art(font.glyph("w"))).toEqual(art(font.glyph("W")));
  });

  it("characters are proportional: each glyph is trimmed to its lit columns", () => {
    const font = fontForCode("3");
    expect(font.glyph("!").width).toBe(1);
    expect(font.glyph("M").width).toBe(5);
  });
});
