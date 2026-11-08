// The core is pure (docs/emulator-spec.md, "Architecture"): no I/O, no timers,
// no clock, no browser or Node APIs. `tsconfig.core.json` type-checks it without
// DOM or Node types; this test bans the APIs that the ES library still has.
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const coreRoot = join(import.meta.dirname, "..", "src", "core");

const banned: [string, RegExp][] = [
  ["Date.now", /\bDate\.now\b/],
  ["new Date() without an argument", /new Date\(\s*\)/],
  ["Math.random", /\bMath\.random\b/],
  ["performance", /\bperformance\./],
  ["timers", /\b(setTimeout|setInterval|setImmediate|requestAnimationFrame|queueMicrotask)\b/],
  ["window / document / globalThis", /\b(window|document|navigator)\.|\bglobalThis\b/],
  ["process", /\bprocess\./],
  ["Node modules", /from\s+["']node:|require\(/],
  ["imports from outside the core", /from\s+["']\.\.\/\.\.\//],
];

function* tsFiles(dir: string): Generator<string> {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* tsFiles(path);
    else if (entry.name.endsWith(".ts")) yield path;
  }
}

function violations(source: string): string[] {
  return banned.filter(([, pattern]) => pattern.test(source)).map(([name]) => name);
}

describe("core purity", () => {
  it("the check catches a clock read and a timer", () => {
    expect(violations("const t = Date.now(); setTimeout(f, 1);")).toEqual(["Date.now", "timers"]);
  });

  it("no core file uses I/O, timers, a clock, or platform globals", () => {
    const found: string[] = [];
    for (const path of tsFiles(coreRoot)) {
      for (const name of violations(readFileSync(path, "utf8"))) {
        found.push(`${relative(coreRoot, path)}: ${name}`);
      }
    }
    expect(found).toEqual([]);
  });
});
