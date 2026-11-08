// The headless host's command line, as the Python fixture starts it (story 49).
import { type ChildProcess, spawn } from "node:child_process";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

const root = join(import.meta.dirname, "..", "..");
let child: ChildProcess | undefined;

afterEach(() => {
  child?.kill();
  child = undefined;
});

function firstLine(proc: ChildProcess): Promise<string> {
  return new Promise((resolve, reject) => {
    let out = "";
    proc.stdout?.on("data", (chunk: Buffer) => {
      out += chunk.toString();
      const end = out.indexOf("\n");
      if (end >= 0) resolve(out.slice(0, end));
    });
    proc.once("exit", (code) => reject(new Error(`exited ${code} before printing`)));
  });
}

describe("headless CLI", () => {
  it("prints the free ports it picked for --port 0 on one line, then serves", async () => {
    child = spawn(
      join(root, "node_modules", ".bin", "tsx"),
      ["src/host/main.ts", "headless", "--port", "0"],
      { cwd: root, stdio: ["ignore", "pipe", "inherit"] },
    );
    const line = await firstLine(child);
    const match = /^tcp=(\d+) http=(\d+)$/.exec(line);
    expect(match).not.toBeNull();
    const res = await fetch(`http://127.0.0.1:${match?.[2]}/snapshots`);
    expect(res.status).toBe(200);
  }, 20_000);
});
