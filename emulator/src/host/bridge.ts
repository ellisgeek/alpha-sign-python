// The bridge: TCP for the library, WebSocket for the page, which runs the core
// (docs/emulator-spec.md, "Parts and their interfaces"). Bytes from the library
// are stamped on arrival at the TCP port; bytes from the page carry the time to
// send them, on the bridge's clock, and are sent then.
//
// WebSocket messages are JSON. Byte strings are one char per byte (0-255), the
// core's convention (`bytesToString` / `stringToBytes`).
//   bridge -> page  {type:"hello", nowMs}       on connect: the bridge's clock now
//   bridge -> page  {type:"rx", atMs, data}     bytes from the library, arrival time
//   bridge -> page  {type:"time", nowMs}        answer to a time request
//   page -> bridge  {type:"tx", atMs, data}     bytes to send at atMs (now if past)
//   page -> bridge  {type:"time"}               asks for the bridge's clock
import { createServer, type Server } from "node:http";
import { type WebSocket, WebSocketServer } from "ws";
import { listenTcp, monotonicClock } from "./tcp";

export interface BridgeOptions {
  tcpPort: number;
  /** HTTP port that serves the WebSocket at `/ws`. */
  httpPort: number;
  /** Interface to listen on. Default 127.0.0.1. */
  host?: string;
}

export interface Bridge {
  readonly tcpPort: number;
  readonly httpPort: number;
  close(): Promise<void>;
}

export const BRIDGE_PATH = "/ws";

export async function startBridge(options: BridgeOptions): Promise<Bridge> {
  const host = options.host ?? "127.0.0.1";
  const now = monotonicClock();
  const pages = new Set<WebSocket>();
  const timers = new Set<NodeJS.Timeout>();

  function toPages(message: object): void {
    const text = JSON.stringify(message);
    for (const page of pages) page.send(text);
  }

  const tcp = await listenTcp(options.tcpPort, host, now, (bytes, atMs) => {
    toPages({ type: "rx", atMs, data: String.fromCharCode(...bytes) });
  });

  function sendAt(data: string, atMs: number): void {
    const bytes = Uint8Array.from(data, (ch) => ch.charCodeAt(0) & 0xff);
    const wait = atMs - now();
    if (wait <= 0) {
      tcp.send(bytes);
      return;
    }
    const timer = setTimeout(() => {
      timers.delete(timer);
      tcp.send(bytes);
    }, wait);
    timers.add(timer);
  }

  const http: Server = createServer((_req, res) => {
    res.writeHead(404, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: `the bridge serves only a WebSocket at ${BRIDGE_PATH}` }));
  });
  const wss = new WebSocketServer({ server: http, path: BRIDGE_PATH });
  wss.on("connection", (ws) => {
    pages.add(ws);
    ws.on("close", () => pages.delete(ws));
    ws.send(JSON.stringify({ type: "hello", nowMs: now() }));
    ws.on("message", (raw) => {
      let message: { type?: unknown; atMs?: unknown; data?: unknown };
      try {
        message = JSON.parse(String(raw));
      } catch {
        return;
      }
      if (message.type === "tx" && typeof message.data === "string") {
        sendAt(message.data, typeof message.atMs === "number" ? message.atMs : 0);
      } else if (message.type === "time") {
        ws.send(JSON.stringify({ type: "time", nowMs: now() }));
      }
    });
  });

  const httpPort = await new Promise<number>((resolve, reject) => {
    http.once("error", reject);
    http.listen(options.httpPort, host, () => {
      const address = http.address();
      if (address === null || typeof address === "string") throw new Error("no HTTP address");
      resolve(address.port);
    });
  });

  return {
    tcpPort: tcp.port,
    httpPort,
    async close() {
      for (const timer of timers) clearTimeout(timer);
      for (const page of pages) page.terminate();
      wss.close();
      http.closeAllConnections();
      await Promise.all([tcp.close(), new Promise<void>((done) => http.close(() => done()))]);
    },
  };
}
