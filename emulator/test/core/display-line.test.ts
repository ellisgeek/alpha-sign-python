// The display driven through the Line: Packets in, the snapshot's display out.
import { describe, expect, it } from "vitest";
import { lineTexts } from "./display-helpers";
import { bytes, oneSign, SYNC } from "./helpers";

const ESC = "\x1b";
/** A Packet to every Sign carrying one Command (Table 38 form, p. 58). */
const packet = (command: string) => `${SYNC}\x01Z00\x02${command}\x04`;

describe("the display through the Line", () => {
  it("begins with the last received TEXT File after a write (p. 18)", () => {
    const { sign, send } = oneSign();
    // Memory Configuration (p. 21): A and B, TEXT, unlocked, 100H bytes, Always.
    send(packet("E$AAU0100FF00BAU0100FF00"));
    send(packet(`AA${ESC} bFIRST`));
    send(packet(`AB${ESC} bSECOND`));
    const display = sign.snapshot().display;
    expect(display.fileLabel).toBe("B");
    expect(lineTexts(display)).toEqual(["SECOND"]);
  });

  it("a STRING write changes the text in place; the Frame keeps running (p. 37)", () => {
    const { sign, line, send, now } = oneSign();
    send(packet("E$AAU0100FF00TBL0010FF00"));
    send(packet("GT1"));
    send(packet(`AA${ESC} bONE${ESC} bT=\x10T`));
    const wrote = now();
    // Find the second Frame, then update the STRING File while it shows.
    let t = wrote;
    while (sign.snapshot().display.frameIndex !== 1 && t < wrote + 20_000) {
      t += 50;
      line.advance(t);
    }
    expect(lineTexts(sign.snapshot().display)).toEqual(["T=1"]);
    line.receive(bytes(packet("GT2")), t + 10);
    line.advance(t + 20);
    expect(sign.snapshot().display.frameIndex).toBe(1);
    expect(lineTexts(sign.snapshot().display)).toEqual(["T=2"]);
  });
});
