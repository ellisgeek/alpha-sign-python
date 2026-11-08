// The headless host over real localhost sockets: TCP for the library, HTTP
// JSON for the control channel (docs/emulator-spec.md, "Parts and their
// interfaces", stories 38, 49, 50).
import { connect, type Socket } from "node:net";
import { setTimeout as sleep } from "node:timers/promises";
import { afterEach, describe, expect, it } from "vitest";
import type { CommandTable } from "../../src/core";
import { type Headless, startHeadless } from "../../src/host/headless";
import { bytes, SYNC, text } from "../core/helpers";

let host: Headless | undefined;

afterEach(async () => {
  await host?.close();
  host = undefined;
});

async function control(path: string, init?: { method: string; body?: unknown }): Promise<unknown> {
  if (!host) throw new Error("no host");
  const res = await fetch(`http://127.0.0.1:${host.httpPort}${path}`, {
    method: init?.method ?? "GET",
    ...(init?.body === undefined
      ? {}
      : { body: JSON.stringify(init.body), headers: { "content-type": "application/json" } }),
  });
  const json: unknown = await res.json();
  if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { json });
  return json;
}

async function openTcp(): Promise<Socket> {
  if (!host) throw new Error("no host");
  const socket = connect(host.tcpPort, "127.0.0.1");
  await new Promise((resolve) => socket.once("connect", resolve));
  return socket;
}

async function ignoredReasons(): Promise<string[]> {
  const [sign] = (await control("/snapshots")) as { ignored: { reason: string }[] }[];
  return sign?.ignored.map((i) => i.reason) ?? [];
}

describe("headless host", () => {
  it("picks free ports when asked for port 0", async () => {
    host = await startHeadless({ tcpPort: 0, httpPort: 0 });
    expect(host.tcpPort).toBeGreaterThan(0);
    expect(host.httpPort).toBeGreaterThan(0);
    expect(host.tcpPort).not.toBe(host.httpPort);
  });

  it("starts with one 4120C on the Line and returns its snapshot", async () => {
    host = await startHeadless({ tcpPort: 0, httpPort: 0 });
    const snapshots = (await control("/snapshots")) as { signType: string; signAddress: number }[];
    // Type Code "a" is the 4120C (Table 5, p. 10).
    expect(snapshots.map((s) => [s.signType, s.signAddress])).toEqual([["a", 1]]);
  });

  // A nested Command's STX needs 100 ms of silence after it (p. 11). "Z" is not
  // in Table 6, so each Command that gets through is listed as unknown.
  const FIRST = `${SYNC}\x01Z01\x02Z\x03\x02`;
  const SECOND = "Z\x03\x04";

  it("stamps TCP bytes on arrival: a real 150 ms pause after a nested STX counts", async () => {
    host = await startHeadless({ tcpPort: 0, httpPort: 0 });
    const socket = await openTcp();
    socket.write(bytes(FIRST));
    await sleep(150);
    socket.write(bytes(SECOND));
    await sleep(50);
    expect(await ignoredReasons()).toEqual(["unknown-command", "unknown-command"]);
    socket.destroy();
  });

  it("stamps TCP bytes on arrival: no pause after a nested STX is caught", async () => {
    host = await startHeadless({ tcpPort: 0, httpPort: 0 });
    const socket = await openTcp();
    socket.write(bytes(FIRST + SECOND));
    await sleep(50);
    expect(await ignoredReasons()).toEqual(["unknown-command", "missing-stx-pause"]);
    socket.destroy();
  });

  // The core does not answer TEXT File Commands yet, so this round trip uses a
  // stand-in: "A" stores the File, "B" answers with it the way Table 46 shows.
  const storeAndRead: CommandTable = {
    A: (cmd, ctx) => {
      ctx.state.files[cmd.data.slice(0, 1)] = {
        label: cmd.data.slice(0, 1),
        type: "TEXT",
        data: cmd.data.slice(1),
      };
    },
    B: (cmd, ctx) => {
      const file = ctx.state.files[cmd.data];
      if (file) ctx.respond(`A${file.label}${file.data}`);
    },
  };

  it("answers a read over TCP with the Table 46 Response (Table 45, p. 64)", async () => {
    host = await startHeadless({ tcpPort: 0, httpPort: 0, commands: storeAndRead });
    const socket = await openTcp();
    const received: Buffer[] = [];
    socket.on("data", (chunk: Buffer) => received.push(chunk));
    socket.write(bytes(`${SYNC}\x01Z01\x02ACFILE C\x04`));
    socket.write(bytes(`${SYNC}\x01Z01\x02BC\x04`));
    await sleep(100);
    // Table 46: <NUL> x 20, <SOH>"000"<STX>"ACFILE C"<ETX>"020C"<EOT>.
    expect(text(new Uint8Array(Buffer.concat(received)))).toBe(
      `${"\x00".repeat(20)}\x01000\x02ACFILE C\x03020C\x04`,
    );
    socket.destroy();
  });

  it("puts the chosen Signs and Readings on the Line, from power-up", async () => {
    host = await startHeadless({ tcpPort: 0, httpPort: 0 });
    const socket = await openTcp();
    socket.write(bytes(FIRST + SECOND));
    await sleep(50);
    await control("/reset", {
      method: "POST",
      body: {
        signs: [
          { model: "4120C", signAddress: 1 },
          { model: "4120C", signAddress: 2, readings: { perFileOverhead: 13 } },
        ],
      },
    });
    const line = (await control("/line")) as {
      signs: { model: string; signAddress: number; readings: { perFileOverhead: number } }[];
    };
    expect(line.signs.map((s) => [s.model, s.signAddress, s.readings.perFileOverhead])).toEqual([
      ["4120C", 1, 11],
      ["4120C", 2, 13],
    ]);
    const snapshots = (await control("/snapshots")) as { signAddress: number; ignored: [] }[];
    expect(snapshots.map((s) => [s.signAddress, s.ignored.length])).toEqual([
      [1, 0],
      [2, 0],
    ]);
    socket.destroy();
  });

  it("starts the Sign clocks at the time given in a reset", async () => {
    host = await startHeadless({ tcpPort: 0, httpPort: 0 });
    await control("/reset", { method: "POST", body: { clock: "2026-11-07T23:59:30" } });
    const [sign] = (await control("/snapshots")) as {
      clock: { year: number; month: number; day: number; hour: number; minute: number };
    }[];
    expect(sign?.clock).toMatchObject({ year: 2026, month: 11, day: 7, hour: 23, minute: 59 });
  });

  it("refuses a reset it can't read, with the reason", async () => {
    host = await startHeadless({ tcpPort: 0, httpPort: 0 });
    await expect(
      control("/reset", { method: "POST", body: { signs: [{ model: "9999", signAddress: 1 }] } }),
    ).rejects.toMatchObject({ json: { error: expect.stringContaining("9999") } });
    await expect(
      control("/reset", { method: "POST", body: { signs: [{ signAddress: 256 }] } }),
    ).rejects.toMatchObject({ json: { error: expect.stringContaining("signAddress") } });
  });
});
