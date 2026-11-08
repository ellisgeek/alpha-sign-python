// The bridge over real localhost sockets: TCP for the library, WebSocket for
// the page (docs/emulator-spec.md, "Parts and their interfaces", story 38).
import { connect, type Socket } from "node:net";
import { setTimeout as sleep } from "node:timers/promises";
import { afterEach, describe, expect, it } from "vitest";
import { WebSocket } from "ws";
import { type Bridge, startBridge } from "../../src/host/bridge";

let bridge: Bridge | undefined;
const opened: { terminate(): void }[] = [];

afterEach(async () => {
  for (const o of opened.splice(0)) o.terminate();
  await bridge?.close();
  bridge = undefined;
});

type Message = { type: string; atMs?: number; nowMs?: number; data?: string };

async function openPage(): Promise<{ ws: WebSocket; messages: Message[]; hello: Message }> {
  if (!bridge) throw new Error("no bridge");
  const ws = new WebSocket(`ws://127.0.0.1:${bridge.httpPort}/ws`);
  opened.push(ws);
  const messages: Message[] = [];
  const hello = await new Promise<Message>((resolve) => {
    ws.on("message", (raw) => {
      const message = JSON.parse(String(raw)) as Message;
      if (message.type === "hello") resolve(message);
      else messages.push(message);
    });
  });
  return { ws, messages, hello };
}

async function openTcp(): Promise<Socket> {
  if (!bridge) throw new Error("no bridge");
  const socket = connect(bridge.tcpPort, "127.0.0.1");
  opened.push({ terminate: () => socket.destroy() });
  await new Promise((resolve) => socket.once("connect", resolve));
  return socket;
}

describe("bridge", () => {
  it("relays TCP bytes to the page, stamped when they reached the TCP port", async () => {
    bridge = await startBridge({ tcpPort: 0, httpPort: 0 });
    const page = await openPage();
    const tcp = await openTcp();
    tcp.write(Uint8Array.of(0x01, 0x5a));
    await sleep(150);
    tcp.write(Uint8Array.of(0x04));
    await sleep(50);
    expect(page.messages.map((m) => [m.type, m.data])).toEqual([
      ["rx", "\x01Z"],
      ["rx", "\x04"],
    ]);
    const [first, second] = page.messages.map((m) => m.atMs ?? Number.NaN);
    expect(first).toBeGreaterThanOrEqual(page.hello.nowMs ?? Number.NaN);
    expect((second ?? 0) - (first ?? 0)).toBeGreaterThanOrEqual(140);
  });

  it("sends the page's bytes to the library at their send time", async () => {
    bridge = await startBridge({ tcpPort: 0, httpPort: 0 });
    const page = await openPage();
    const tcp = await openTcp();
    const arrivals: { data: string; at: number }[] = [];
    tcp.on("data", (chunk: Buffer) =>
      arrivals.push({ data: chunk.toString("latin1"), at: Date.now() }),
    );
    const sentAt = Date.now();
    const sendAtMs = (page.hello.nowMs ?? 0) + 200;
    page.ws.send(JSON.stringify({ type: "tx", atMs: sendAtMs, data: "\x00\x01000\xff" }));
    await sleep(100);
    expect(arrivals).toEqual([]);
    await sleep(200);
    expect(arrivals.map((a) => a.data)).toEqual(["\x00\x01000\xff"]);
    expect((arrivals[0]?.at ?? 0) - sentAt).toBeGreaterThanOrEqual(180);
  });

  it("answers a time request with the bridge's clock", async () => {
    bridge = await startBridge({ tcpPort: 0, httpPort: 0 });
    const page = await openPage();
    await sleep(30);
    page.ws.send(JSON.stringify({ type: "time" }));
    await sleep(30);
    const [time] = page.messages;
    expect(time?.type).toBe("time");
    expect(time?.nowMs ?? 0).toBeGreaterThanOrEqual((page.hello.nowMs ?? 0) + 25);
  });
});
