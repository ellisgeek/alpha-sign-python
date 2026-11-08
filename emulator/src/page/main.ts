// The emulator page: runs the core in the browser, fed by the bridge, steps it
// on animation frames, and draws each Sign on the Line with its state
// (docs/emulator-spec.md, "Page").
import "@fontsource/atkinson-hyperlegible-next/400.css";
import "@fontsource/atkinson-hyperlegible-next/700.css";
import "@fontsource/atkinson-hyperlegible-mono/400.css";
import "./style.css";
import { bytesToString, createLine, findModel, type Line, stringToBytes } from "../core/index";
import { BridgeLink, type BridgeStatus } from "./bridge";
import { clockPackets, parseClockInput } from "./clock-set";
import { pageSettings } from "./settings";
import { SignView } from "./sign-view";

const settings = pageSettings(location.search);
const statusEl = document.querySelector<HTMLElement>("#bridge-status");
const lineTimeEl = document.querySelector<HTMLElement>("#line-time");
const signsEl = document.querySelector<HTMLElement>("#signs");
if (!statusEl || !lineTimeEl || !signsEl) throw new Error("page markup is missing");

/** The Signs' clocks start at the browser's local time (spec: "Architecture"). */
function localWallClockMs(): number {
  const now = new Date();
  return now.getTime() - now.getTimezoneOffset() * 60_000;
}

let line: Line | null = null;
let views: SignView[] = [];
let lineNowMs = 0;

function powerUp(startMs: number): void {
  const setups = settings.signs.map((s) => ({
    model: findModel(s.model),
    signAddress: s.signAddress,
  }));
  line = createLine(setups, { startClockMs: localWallClockMs(), startMs });
  lineNowMs = startMs;
  signsEl?.replaceChildren();
  views = line.signs().map((sign) => {
    const view = new SignView(sign, { onSetClock: setClock });
    signsEl?.append(view.root);
    return view;
  });
}

/** Feeds every Sign the Set Time, Set Date, and Set Day of Week Packets. */
function setClock(date: string, time: string): boolean {
  const setting = parseClockInput(date, time);
  if (!line || !setting) return false;
  for (const packet of clockPackets(setting)) line.receive(stringToBytes(packet), lineNowMs);
  step();
  return true;
}

const STATUS_TEXT: Record<BridgeStatus, string> = {
  connecting: "Connecting to the bridge",
  connected: "Bridge connected",
  closed: "Bridge closed, retrying",
};

let link: BridgeLink | null = null;
if (settings.bridge) {
  const url = settings.bridge;
  link = new BridgeLink(url, {
    onHello(bridgeNowMs) {
      // A first hello, or a restarted bridge whose clock began again at 0.
      if (!line || bridgeNowMs < lineNowMs) powerUp(bridgeNowMs);
    },
    onRx(data, atMs) {
      line?.receive(stringToBytes(data), atMs);
      step();
    },
    onStatus(status) {
      if (!statusEl) return;
      statusEl.textContent = STATUS_TEXT[status];
      statusEl.title = url;
      statusEl.dataset.status = status;
    },
  });
} else {
  statusEl.textContent = "No bridge: start the page with npm run serve";
  statusEl.dataset.status = "closed";
  powerUp(performance.now());
}

function nowMs(): number {
  const local = performance.now();
  return link ? link.clock.now(local) : local;
}

function step(): void {
  if (!line) return;
  lineNowMs = Math.max(lineNowMs, nowMs());
  for (const out of line.advance(lineNowMs)) link?.send(bytesToString(out.bytes), out.atMs);
}

function frame(): void {
  step();
  if (line && lineTimeEl) {
    lineTimeEl.textContent = `Line ${(lineNowMs / 1000).toFixed(1)} s`;
    for (const view of views) view.update(lineNowMs);
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
