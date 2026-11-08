// The page's query string and its estimate of the bridge's clock.
import { describe, expect, it } from "vitest";
import { BridgeClock, pageSettings } from "../../src/page/settings";

describe("pageSettings", () => {
  it("reads the bridge URL that `npm run serve` puts in ?bridge=", () => {
    const search = `?bridge=${encodeURIComponent("ws://127.0.0.1:4121/ws")}`;
    expect(pageSettings(search).bridge).toBe("ws://127.0.0.1:4121/ws");
  });

  it("has no bridge and one 4120C at Sign Address 1 by default", () => {
    expect(pageSettings("")).toEqual({ bridge: null, signs: [{ model: "4120C", signAddress: 1 }] });
  });

  it("puts several Signs on the Line from ?signs=, as model:address or address", () => {
    expect(pageSettings("?signs=4120C:1,2,4120C:255").signs).toEqual([
      { model: "4120C", signAddress: 1 },
      { model: "4120C", signAddress: 2 },
      { model: "4120C", signAddress: 255 },
    ]);
  });

  it("drops Signs it cannot read: an unknown model or an address outside 1-255", () => {
    expect(pageSettings("?signs=9999X:1,0,256,3").signs).toEqual([
      { model: "4120C", signAddress: 3 },
    ]);
  });
});

describe("BridgeClock", () => {
  it("reads bridge time from the hello, before any round trip", () => {
    const clock = new BridgeClock();
    clock.hello(5_000, 1_000);
    expect(clock.now(1_250)).toBe(5_250);
  });

  it("keeps the estimate from the shortest round trip, using its midpoint", () => {
    const clock = new BridgeClock();
    clock.hello(5_000, 1_000);
    // Asked at 2000, answered 9000 at 2040: offset 9000 - 2020.
    clock.roundTrip(2_000, 9_000, 2_040);
    expect(clock.now(3_020)).toBe(10_000);
    // A slower round trip does not replace it.
    clock.roundTrip(4_000, 20_000, 4_400);
    expect(clock.now(3_020)).toBe(10_000);
  });
});
