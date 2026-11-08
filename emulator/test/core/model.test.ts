// Looking up a Sign Model by name (docs/emulator-spec.md, "Sign Models").
import { describe, expect, it } from "vitest";
import { findModel, model4120C } from "../../src/core";

describe("findModel", () => {
  it("finds the 4120C by its name", () => {
    expect(findModel("4120C")).toBe(model4120C);
  });

  it("names the known Sign Models when the name is unknown", () => {
    expect(() => findModel("9999X")).toThrow('unknown Sign Model "9999X"; known: 4120C');
  });
});
