// The host's command line: `headless` runs the core with a control channel;
// `serve` runs the bridge and the page (Vite) and opens the browser.
import { join } from "node:path";
import { parseArgs } from "node:util";
import { BRIDGE_PATH, startBridge } from "./bridge";
import { startHeadless } from "./headless";

const USAGE = `Usage:
  npm run headless -- [--port N] [--http-port N] [--host H]
      Runs the Emulated Signs in Node. TCP --port for the library (default 0 = free port),
      HTTP JSON control channel on --http-port (default 0). Prints "tcp=<port> http=<port>".
  npm run serve -- [--port N] [--http-port N] [--page-port N] [--host H] [--no-open]
      Runs the bridge (TCP --port, default 4120; WebSocket on --http-port, default 4121,
      path ${BRIDGE_PATH}) and the page (Vite, --page-port, default 5173), and opens the browser.
      Prints "tcp=<port> http=<port> page=<url>".`;

async function main(argv: string[]): Promise<void> {
  const [mode, ...rest] = argv;
  const { values } = parseArgs({
    args: rest,
    options: {
      port: { type: "string" },
      "http-port": { type: "string" },
      "page-port": { type: "string" },
      host: { type: "string", default: "127.0.0.1" },
      "no-open": { type: "boolean", default: false },
      help: { type: "boolean", default: false },
    },
  });
  if (values.help || (mode !== "headless" && mode !== "serve")) {
    console.log(USAGE);
    process.exitCode = values.help ? 0 : 2;
    return;
  }
  const host = values.host;

  if (mode === "headless") {
    const headless = await startHeadless({
      tcpPort: port(values.port, 0),
      httpPort: port(values["http-port"], 0),
      host,
    });
    console.log(`tcp=${headless.tcpPort} http=${headless.httpPort}`);
    onExit(() => headless.close());
    return;
  }

  const bridge = await startBridge({
    tcpPort: port(values.port, 4120),
    httpPort: port(values["http-port"], 4121),
    host,
  });
  const bridgeUrl = `ws://${host}:${bridge.httpPort}${BRIDGE_PATH}`;
  const pagePath = `/?bridge=${encodeURIComponent(bridgeUrl)}`;
  const { createServer } = await import("vite");
  const vite = await createServer({
    configFile: join(import.meta.dirname, "..", "..", "vite.config.ts"),
    server: {
      host,
      port: port(values["page-port"], 5173),
      open: values["no-open"] ? false : pagePath,
    },
  });
  await vite.listen();
  const pageUrl = `${vite.resolvedUrls?.local[0]?.replace(/\/$/, "") ?? ""}${pagePath}`;
  console.log(`tcp=${bridge.tcpPort} http=${bridge.httpPort} page=${pageUrl}`);
  onExit(async () => {
    await vite.close();
    await bridge.close();
  });
}

function port(value: string | undefined, fallback: number): number {
  if (value === undefined) return fallback;
  const n = Number(value);
  if (!Number.isInteger(n) || n < 0 || n > 65535) throw new Error(`bad port ${value}`);
  return n;
}

function onExit(close: () => Promise<void>): void {
  const stop = () => {
    close().finally(() => process.exit(0));
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);
}

main(process.argv.slice(2)).catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
