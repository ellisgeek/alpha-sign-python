// The page's settings from its query string, and its reading of the bridge's
// clock. Pure, no DOM: `main.ts` passes in `location.search` and times.
import { findModel } from "../core/index";

export interface PageSign {
  model: string;
  signAddress: number;
}

export interface PageSettings {
  /** WebSocket URL of the bridge (`npm run serve` sets `?bridge=`), or null. */
  bridge: string | null;
  signs: PageSign[];
}

const DEFAULT_MODEL = "4120C";

/** `?bridge=<ws url>&signs=4120C:1,2` (a bare number is a 4120C at that Sign Address). */
export function pageSettings(search: string): PageSettings {
  const query = new URLSearchParams(search);
  const signs: PageSign[] = [];
  for (const item of (query.get("signs") ?? "").split(",")) {
    if (item.trim() === "") continue;
    const [model, address] = item.includes(":") ? item.split(":") : [DEFAULT_MODEL, item];
    const signAddress = Number(address);
    if (model === undefined || !knownModel(model)) continue;
    // 1-255; 0 is the broadcast address (p. 11).
    if (!Number.isInteger(signAddress) || signAddress < 1 || signAddress > 255) continue;
    signs.push({ model, signAddress });
  }
  return {
    bridge: query.get("bridge"),
    signs: signs.length > 0 ? signs : [{ model: DEFAULT_MODEL, signAddress: 1 }],
  };
}

function knownModel(name: string): boolean {
  try {
    findModel(name);
    return true;
  } catch {
    return false;
  }
}

/**
 * Bridge time from the page's own clock. Line time is the bridge's clock (it
 * stamps the library's bytes and sends the page's at that clock), so the page
 * keeps an offset: first from the hello, then from the shortest round trip.
 */
export class BridgeClock {
  private offsetMs = 0;
  private bestRttMs = Number.POSITIVE_INFINITY;

  hello(bridgeNowMs: number, localMs: number): void {
    this.offsetMs = bridgeNowMs - localMs;
  }

  roundTrip(sentLocalMs: number, bridgeNowMs: number, receivedLocalMs: number): void {
    const rtt = receivedLocalMs - sentLocalMs;
    if (rtt >= this.bestRttMs) return;
    this.bestRttMs = rtt;
    this.offsetMs = bridgeNowMs - (sentLocalMs + receivedLocalMs) / 2;
  }

  now(localMs: number): number {
    return localMs + this.offsetMs;
  }
}
