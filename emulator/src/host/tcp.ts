// The TCP port the library connects to (`socket://host:port`). Every byte is
// stamped with its arrival time here, where it enters the Emulator, so a slow
// relay behind this point can't fake or hide a missing pause (story 38).
import { createServer, type Server, type Socket } from "node:net";

export interface TcpPort {
  readonly port: number;
  /** Writes bytes to every connected client. */
  send(bytes: Uint8Array): void;
  close(): Promise<void>;
}

export function listenTcp(
  port: number,
  host: string,
  now: () => number,
  onBytes: (bytes: Uint8Array, atMs: number) => void,
): Promise<TcpPort> {
  const clients = new Set<Socket>();
  const server: Server = createServer((socket) => {
    socket.setNoDelay(true);
    clients.add(socket);
    socket.on("data", (chunk: Buffer) => onBytes(new Uint8Array(chunk), now()));
    socket.on("close", () => clients.delete(socket));
    socket.on("error", () => clients.delete(socket));
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => {
      const address = server.address();
      if (address === null || typeof address === "string") throw new Error("no TCP address");
      resolve({
        port: address.port,
        send(bytes) {
          for (const socket of clients) socket.write(bytes);
        },
        close() {
          for (const socket of clients) socket.destroy();
          return new Promise((done) => server.close(() => done()));
        },
      });
    });
  });
}

/** Milliseconds on a monotonic clock that starts at 0 when it is made. */
export function monotonicClock(): () => number {
  const start = performance.now();
  return () => performance.now() - start;
}

/** Host wall-clock ms whose UTC fields read as the host's local time (the core's convention). */
export function localWallClockMs(): number {
  const now = new Date();
  return now.getTime() - now.getTimezoneOffset() * 60_000;
}
