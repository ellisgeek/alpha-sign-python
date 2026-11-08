// The page's end of the bridge WebSocket (src/host/bridge.ts has the messages).
// Reconnects after a second when the bridge goes away.
import { BridgeClock } from "./settings";

export type BridgeStatus = "connecting" | "connected" | "closed";

export interface BridgeEvents {
  /** First hello of a connection: the bridge clock is known from here on. */
  onHello(bridgeNowMs: number): void;
  onRx(data: string, atMs: number): void;
  onStatus(status: BridgeStatus): void;
}

export class BridgeLink {
  readonly clock = new BridgeClock();
  private ws: WebSocket | null = null;
  private timeAskedAt: number | null = null;

  constructor(
    private readonly url: string,
    private readonly events: BridgeEvents,
  ) {
    this.open();
    setInterval(() => this.askTime(), 2_000);
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /** Sends Response bytes to the library at bridge time `atMs`. */
  send(data: string, atMs: number): void {
    if (this.connected) this.ws?.send(JSON.stringify({ type: "tx", atMs, data }));
  }

  private open(): void {
    this.events.onStatus("connecting");
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data)) as {
        type: string;
        nowMs?: number;
        atMs?: number;
        data?: string;
      };
      const local = performance.now();
      if (message.type === "hello" && typeof message.nowMs === "number") {
        this.clock.hello(message.nowMs, local);
        this.events.onStatus("connected");
        this.events.onHello(message.nowMs);
        this.askTime();
      } else if (message.type === "rx" && typeof message.data === "string") {
        this.events.onRx(message.data, message.atMs ?? this.clock.now(local));
      } else if (message.type === "time" && typeof message.nowMs === "number") {
        if (this.timeAskedAt !== null) this.clock.roundTrip(this.timeAskedAt, message.nowMs, local);
        this.timeAskedAt = null;
      }
    });
    ws.addEventListener("close", () => {
      this.events.onStatus("closed");
      this.timeAskedAt = null;
      setTimeout(() => this.open(), 1_000);
    });
  }

  private askTime(): void {
    if (!this.connected || this.timeAskedAt !== null) return;
    this.timeAskedAt = performance.now();
    this.ws?.send(JSON.stringify({ type: "time" }));
  }
}
