// The emulator is a second implementation of the manual, written from the
// manual alone (docs/emulator-spec.md, "Independence"). It must not reference
// the Python library's code or its capability data.
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const emulatorRoot = join(import.meta.dirname, "..");
const skipped = new Set(["node_modules", "dist", ".vite"]);
const forbidden = /alpha_led_sign|capability-matrices/;

// This file names the forbidden strings, so it cannot be scanned itself.
const self = relative(emulatorRoot, import.meta.filename);

function* filesUnder(dir: string): Generator<string> {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (skipped.has(entry.name)) continue;
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* filesUnder(path);
    else yield path;
  }
}

function referencesToLibrary(root: string, exclude: string[] = []): string[] {
  const hits: string[] = [];
  for (const path of filesUnder(root)) {
    const rel = relative(root, path);
    if (exclude.includes(rel)) continue;
    if (forbidden.test(readFileSync(path, "utf8"))) hits.push(rel);
  }
  return hits;
}

describe("independence from the Python library", () => {
  it("the check finds a file that imports the library's capability data", () => {
    const dir = mkdtempSync(join(tmpdir(), "emulator-independence-"));
    try {
      mkdirSync(join(dir, "src"));
      writeFileSync(join(dir, "src", "clean.ts"), "export const a = 1;\n");
      writeFileSync(
        join(dir, "src", "model.ts"),
        'import data from "../../src/alpha_led_sign/data/capability-matrices/4120C.json";\n',
      );
      writeFileSync(join(dir, "notes.md"), "Copied from alpha_led_sign.protocol\n");
      expect(referencesToLibrary(dir).sort()).toEqual(["notes.md", join("src", "model.ts")]);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("no emulator file references alpha_led_sign or its capability matrices", () => {
    expect(referencesToLibrary(emulatorRoot, [self])).toEqual([]);
  });
});
