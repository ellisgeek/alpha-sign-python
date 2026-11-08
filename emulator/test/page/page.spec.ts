// The page with the bridge (docs/emulator-spec.md, "Seams", stories 1, 13, 15, 47):
// it loads, connects to the bridge, and lights pixels after a write.
import { type ChildProcess, spawn } from "node:child_process";
import { connect } from "node:net";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

const root = join(import.meta.dirname, "..", "..");
let serve: ChildProcess | undefined;

test.afterEach(() => {
  serve?.kill("SIGTERM");
  serve = undefined;
});

/** Starts `npm run serve` on free ports and reads its `tcp=... http=... page=...` line. */
function startServe(): Promise<{ tcpPort: number; pageUrl: string }> {
  serve = spawn(
    join(root, "node_modules", ".bin", "tsx"),
    [
      "src/host/main.ts",
      "serve",
      "--port",
      "0",
      "--http-port",
      "0",
      "--page-port",
      "0",
      "--no-open",
    ],
    { cwd: root, stdio: ["ignore", "pipe", "inherit"] },
  );
  const proc = serve;
  return new Promise((resolve, reject) => {
    let out = "";
    proc.stdout?.on("data", (chunk: Buffer) => {
      out += chunk.toString();
      const match = /tcp=(\d+) http=\d+ page=(\S+)\n/.exec(out);
      if (match?.[1] && match[2]) resolve({ tcpPort: Number(match[1]), pageUrl: match[2] });
    });
    proc.once("exit", (code) => reject(new Error(`serve exited ${code}: ${out}`)));
  });
}

function sendTcp(port: number, packet: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const socket = connect(port, "127.0.0.1", () => {
      socket.end(Buffer.from(packet, "latin1"), () => resolve());
    });
    socket.once("error", reject);
  });
}

test("lights the LED matrix after a TEXT File write through the bridge", async ({ page }) => {
  const { tcpPort, pageUrl } = await startServe();
  await page.goto(pageUrl);

  const sign = page.getByRole("region", { name: "4120C, Sign Type a, Sign Address 01" });
  await expect(sign).toBeVisible();
  await expect(page.getByText("Bridge connected")).toBeVisible();

  const matrix = sign.getByRole("img", { name: /LED matrix, 120 by 16/ });
  const litPixels = () =>
    matrix.evaluate((canvas: HTMLCanvasElement) => {
      const ctx = canvas.getContext("2d");
      if (!ctx) return -1;
      const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
      let lit = 0;
      // An unlit LED is dark (palette 0); a lit one has a bright red or green channel.
      for (let i = 0; i < data.length; i += 4) {
        if (Math.max(data[i] ?? 0, data[i + 1] ?? 0) > 160) lit++;
      }
      return lit;
    });
  expect(await litPixels()).toBe(0);

  // Table 38 (p. 58): display "HELLO" on all signs.
  await sendTcp(tcpPort, "\x00\x00\x00\x00\x00\x01Z00\x02AAHELLO\x04");

  await expect.poll(litPixels, { timeout: 5_000 }).toBeGreaterThan(0);
  await expect(sign.getByText("TEXT File A", { exact: false }).first()).toBeVisible();
});
