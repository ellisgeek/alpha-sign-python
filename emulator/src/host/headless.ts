// The headless host: runs the core itself, with a TCP port for the library and
// an HTTP JSON control channel (docs/emulator-spec.md, "Parts and their
// interfaces"). Byte times are taken at the TCP port; the Line advances on
// every input and every `tickMs`.
//
// Control API (JSON; errors are {error} with status 400 or 404):
//   GET  /snapshots  every Sign's SignSnapshot, in Line order; pixels.colors is an array
//   GET  /line       {nowMs, signs: [{model, signAddress, readings}]}
//   POST /reset      body {signs?, clock?}: power up a new Line. signs: [{model?: "4120C",
//                    signAddress: 1-255, readings?: Partial<Readings>}] (default: keep).
//                    clock: "YYYY-MM-DDTHH:MM[:SS]" Sign local time (default: host time).
//                    Replies like GET /line.
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import {
  type CommandTable,
  createLine,
  findModel,
  type Line,
  type SignSnapshot,
} from "../core/index";
import { DEFAULT_SIGNS, parseClock, parseSigns, SetupError, type SignSpec } from "./line-setup";
import { listenTcp, localWallClockMs, monotonicClock } from "./tcp";

export interface HeadlessOptions {
  tcpPort: number;
  httpPort: number;
  /** Interface to listen on. Default 127.0.0.1. */
  host?: string;
  /** How often the Line is advanced when no input arrives. Default 5 ms. */
  tickMs?: number;
  /** The Command dispatch table. Default: the core's. Tests can pass a stand-in. */
  commands?: CommandTable;
}

export interface Headless {
  readonly tcpPort: number;
  readonly httpPort: number;
  close(): Promise<void>;
}

export async function startHeadless(options: HeadlessOptions): Promise<Headless> {
  const host = options.host ?? "127.0.0.1";
  const now = monotonicClock();
  let signs: SignSpec[] = DEFAULT_SIGNS;
  let line: Line = powerUp(signs, localWallClockMs());

  function powerUp(specs: SignSpec[], startClockMs: number): Line {
    const setups = specs.map((s) => ({
      model: findModel(s.model),
      signAddress: s.signAddress,
      readings: s.readings,
    }));
    return createLine(setups, {
      startClockMs,
      startMs: now(),
      ...(options.commands ? { commands: options.commands } : {}),
    });
  }

  function step(): void {
    for (const out of line.advance(now())) tcp.send(out.bytes);
  }

  const tcp = await listenTcp(options.tcpPort, host, now, (bytes, atMs) => {
    line.receive(bytes, atMs);
    step();
  });

  const http = createServer((req, res) => {
    handle(req, res).catch((error: unknown) => {
      if (error instanceof SetupError) reply(res, 400, { error: error.message });
      else reply(res, 500, { error: String(error) });
    });
  });

  async function handle(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const path = new URL(req.url ?? "/", "http://host").pathname;
    if (req.method === "GET" && path === "/snapshots") {
      step();
      reply(
        res,
        200,
        line.signs().map((s) => snapshotJson(s.snapshot())),
      );
      return;
    }
    if (req.method === "GET" && path === "/line") {
      reply(res, 200, { nowMs: now(), signs });
      return;
    }
    if (req.method === "POST" && path === "/reset") {
      const body = await readJson(req);
      const nextSigns = body.signs === undefined ? signs : parseSigns(body.signs);
      const clock = body.clock === undefined ? localWallClockMs() : parseClock(body.clock);
      line = powerUp(nextSigns, clock);
      signs = nextSigns;
      reply(res, 200, { nowMs: now(), signs });
      return;
    }
    reply(res, 404, { error: `no route ${req.method} ${path}` });
  }

  const httpPort = await new Promise<number>((resolve, reject) => {
    http.once("error", reject);
    http.listen(options.httpPort, host, () => {
      const address = http.address();
      if (address === null || typeof address === "string") throw new Error("no HTTP address");
      resolve(address.port);
    });
  });

  const timer = setInterval(step, options.tickMs ?? 5);

  return {
    tcpPort: tcp.port,
    httpPort,
    async close() {
      clearInterval(timer);
      http.closeAllConnections();
      await Promise.all([tcp.close(), new Promise<void>((done) => http.close(() => done()))]);
    },
  };
}

async function readJson(req: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  const text = Buffer.concat(chunks).toString("utf8").trim();
  if (text === "") return {};
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new SetupError("body is not JSON");
  }
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new SetupError("body must be a JSON object");
  }
  return value as Record<string, unknown>;
}

function reply(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}

/** A snapshot as JSON: the pixel colors become a plain array. */
function snapshotJson(snapshot: SignSnapshot): unknown {
  const { pixels } = snapshot.display;
  return {
    ...snapshot,
    display: { ...snapshot.display, pixels: { ...pixels, colors: Array.from(pixels.colors) } },
  };
}
