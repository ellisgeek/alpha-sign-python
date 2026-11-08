// One Sign on the page: its LED matrix and the panels that show its state.
import type { EmulatedSign, SignSnapshot } from "../core/index";
import { printBytes, registerErrors } from "./format";
import { Matrix } from "./matrix";

const PANEL_EVERY_MS = 200;
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const RUN_ORDER: Record<string, string> = {
  T: "by Run Times; Run Times are not modelled by the emulator yet",
  S: "in sequence, ignoring Run Times",
  D: "by Run Times, then deleted; Run Times are not modelled by the emulator yet",
};

/** `h("td", {class: "x"}, "text", child)`: a small DOM builder; strings become text nodes. */
function h(
  tag: string,
  attrs: Record<string, string> = {},
  ...children: (Node | string)[]
): HTMLElement {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  el.append(...children);
  return el;
}

const hex2 = (n: number) => n.toString(16).toUpperCase().padStart(2, "0");
const pad2 = (n: number) => String(n).padStart(2, "0");

export interface SignViewEvents {
  /** Date "YYYY-MM-DD" and time "HH:MM" from the inputs; false if unusable. */
  onSetClock(date: string, time: string): boolean;
}

export class SignView {
  readonly root: HTMLElement;
  private readonly matrix: Matrix;
  private readonly title: HTMLElement;
  private readonly readout: HTMLElement;
  private readonly panels: Record<"files" | "clock" | "run" | "register" | "ignored", HTMLElement>;
  private readonly clockReading: HTMLElement;
  private readonly clockInputs: { date: HTMLInputElement; time: HTMLInputElement };
  private pitch: number | "fit" = "fit";
  private lastPanelsAt = Number.NEGATIVE_INFINITY;
  private lastPanelsKey = "";

  constructor(
    private readonly sign: EmulatedSign,
    events: SignViewEvents,
  ) {
    const { model } = sign;
    this.matrix = new Matrix(model.columns, model.rows, model.palette);
    this.matrix.canvas.setAttribute("role", "img");
    this.title = h("h2");
    this.readout = h("p", { class: "readout" });

    const pitch = h("select", { "aria-label": "LED pitch" }) as HTMLSelectElement;
    pitch.append(h("option", { value: "fit" }, "fit width"));
    for (const p of [4, 6, 8, 10, 12]) pitch.append(h("option", { value: String(p) }, `${p} px`));
    pitch.addEventListener("change", () => {
      this.pitch = pitch.value === "fit" ? "fit" : Number(pitch.value);
    });

    this.clockReading = h("output", { class: "num" });
    const date = h("input", { type: "date", "aria-label": "Date" }) as HTMLInputElement;
    const time = h("input", { type: "time", "aria-label": "Time" }) as HTMLInputElement;
    this.clockInputs = { date, time };
    const clockNote = h("span", { class: "note", role: "status" });
    const clockForm = h(
      "form",
      { class: "clock-set" },
      date,
      time,
      h("button", { type: "submit" }, "Set clock"),
      clockNote,
    );
    clockForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const ok = events.onSetClock(date.value, time.value);
      clockNote.textContent = ok ? "" : "Pick a date and a time first";
    });

    this.panels = {
      files: h("div"),
      clock: h("div"),
      run: h("div"),
      register: h("div"),
      ignored: h("div"),
    };

    this.root = h(
      "section",
      { class: "sign" },
      h(
        "header",
        { class: "sign-head" },
        this.title,
        h("label", { class: "pitch" }, "LED pitch ", pitch),
      ),
      h("div", { class: "case" }, this.matrix.canvas),
      this.readout,
      h(
        "div",
        { class: "panels" },
        panel("Files", this.panels.files, "files"),
        panel("Clock", h("div", {}, this.clockReading, this.panels.clock, clockForm), "clock"),
        panel("Run Sequence", this.panels.run, "run"),
        panel("Serial Error Status Register", this.panels.register, "register"),
        panel("Ignored input", this.panels.ignored, "ignored"),
      ),
    );
  }

  update(nowMs: number): void {
    const snap = this.sign.snapshot();
    const { display } = snap;
    const { columns } = this.sign.model;
    // Fit: the largest whole-pixel LED pitch the page width allows (the case adds 38 px).
    const fit = Math.floor((this.root.clientWidth - 38) / columns);
    this.matrix.setPitch(this.pitch === "fit" ? Math.min(16, Math.max(3, fit)) : this.pitch);
    this.matrix.draw(display.pixels);
    const label = `${this.sign.model.name}, Sign Type ${snap.signType}, Sign Address ${hex2(snap.signAddress)}`;
    if (this.root.getAttribute("aria-label") !== label) {
      this.root.setAttribute("aria-label", label);
      this.title.textContent = label;
    }
    const text = display.lines.map((runs) => runs.map((r) => r.text).join("")).join(" / ");
    const matrixLabel = `LED matrix, ${display.pixels.width} by ${display.pixels.height} pixels${text ? `: ${text}` : ", blank"}`;
    if (this.matrix.canvas.getAttribute("aria-label") !== matrixLabel) {
      this.matrix.canvas.setAttribute("aria-label", matrixLabel);
    }
    this.renderReadout(snap);

    const c = snap.clock;
    const isoDate = `${c.year}-${pad2(c.month)}-${pad2(c.day)}`;
    const hhmm = `${pad2(c.hour)}:${pad2(c.minute)}`;
    this.clockReading.textContent = `${DAYS[c.dayOfWeek - 1]} ${isoDate} ${hhmm}:${pad2(c.second)}`;
    // Start the inputs at the Sign's clock so "Set clock" needs only the field that changes.
    const { date, time } = this.clockInputs;
    if (date.value === "" && document.activeElement !== date) date.value = isoDate;
    if (time.value === "" && document.activeElement !== time) time.value = hhmm;

    if (nowMs - this.lastPanelsAt < PANEL_EVERY_MS) return;
    this.lastPanelsAt = nowMs;
    const { clock: _clock, display: _display, ...rest } = snap;
    const key = JSON.stringify(rest) + c.timeFormat;
    if (key === this.lastPanelsKey) return;
    this.lastPanelsKey = key;
    this.renderPanels(snap);
  }

  private renderReadout(snap: SignSnapshot): void {
    const d = snap.display;
    const parts: (Node | string)[] = [];
    if (d.fileLabel === null) {
      parts.push("Blank");
    } else {
      parts.push(h("b", {}, `TEXT File ${d.fileLabel}`), `, Frame ${d.frameIndex + 1}, ${d.mode}`);
      if (d.position !== "none") parts.push(`, ${d.position}`);
      if (snap.priority && d.fileLabel === "0") parts.push(", Priority TEXT File");
      if (d.mode !== d.drawnAs) {
        parts.push(" ", h("span", { class: "flag" }, `${d.mode} is drawn as ${d.drawnAs}`));
      }
      if (d.specialGraphic) {
        parts.push(" ", h("span", { class: "flag" }, `Special Graphic ${d.specialGraphic}`));
      }
    }
    const key = parts.map((p) => (typeof p === "string" ? p : p.textContent)).join("");
    if (this.readout.dataset.key === key) return;
    this.readout.dataset.key = key;
    this.readout.replaceChildren(...parts);
  }

  private renderPanels(snap: SignSnapshot): void {
    // Files: the Memory Configuration with each File's content.
    const rows = snap.memoryConfiguration.map((entry) => {
      const data = snap.files[entry.label]?.data ?? "";
      return h(
        "tr",
        {},
        h("td", { class: "num" }, entry.label),
        h("td", {}, entry.type),
        h("td", { class: "num" }, entry.size),
        h("td", {}, entry.locked ? "locked" : "unlocked"),
        h("td", { class: "bytes", title: printBytes(data) }, printBytes(data) || " "),
      );
    });
    if (snap.priority) {
      rows.unshift(
        h(
          "tr",
          { class: "priority" },
          h("td", { class: "num" }, "0"),
          h("td", {}, "Priority"),
          h("td", {}, ""),
          h("td", {}, ""),
          h("td", { class: "bytes" }, printBytes(snap.priority.data)),
        ),
      );
    }
    this.panels.files.replaceChildren(
      table(["Label", "Type", "Size", "Lock", "Content"], rows, "No Files configured"),
    );

    this.panels.clock.replaceChildren(
      h(
        "p",
        { class: "note" },
        snap.clock.timeFormat === "M" ? "24-hour format" : "Standard (am/pm) format",
        snap.speakerOn ? ", speaker on" : ", speaker off",
      ),
    );

    const run = snap.runSequence;
    this.panels.run.replaceChildren(
      h("p", {}, h("span", { class: "num" }, run.labels.length ? run.labels.join(" ") : "none")),
      h(
        "p",
        { class: "note" },
        `Order ${run.order}: ${RUN_ORDER[run.order] ?? "?"}${run.locked ? ", locked" : ""}`,
      ),
    );

    const errors = registerErrors(snap.serialErrors);
    this.panels.register.replaceChildren(
      h(
        "p",
        {},
        h("span", { class: "num" }, `${hex2(snap.serialErrors)}H`),
        " ",
        h("span", { class: "num note" }, snap.serialErrors.toString(2).padStart(8, "0")),
      ),
      errors.length
        ? h("ul", { class: "errors" }, ...errors.map((e) => h("li", {}, e)))
        : h("p", { class: "note" }, "No errors recorded"),
    );

    const ignored = [...snap.ignored]
      .reverse()
      .map((item) =>
        h(
          "tr",
          {},
          h("td", { class: "num" }, (item.atMs / 1000).toFixed(3)),
          h("td", {}, item.reason),
          h("td", {}, item.detail ?? ""),
          h("td", { class: "bytes", title: printBytes(item.bytes) }, printBytes(item.bytes)),
        ),
      );
    this.panels.ignored.replaceChildren(
      table(["Time (s)", "Reason", "Detail", "Bytes"], ignored, "Nothing ignored"),
    );
    this.root
      .querySelector(".panel-ignored h3 .count")
      ?.replaceChildren(snap.ignored.length ? String(snap.ignored.length) : "");
  }
}

function panel(title: string, body: HTMLElement, name: string): HTMLElement {
  const heading = h("h3", {}, title);
  if (name === "ignored") heading.append(" ", h("span", { class: "count" }));
  return h("section", { class: `panel panel-${name}` }, heading, body);
}

function table(head: string[], rows: HTMLElement[], empty: string): HTMLElement {
  if (rows.length === 0) return h("p", { class: "note" }, empty);
  return h(
    "table",
    {},
    h("thead", {}, h("tr", {}, ...head.map((t) => h("th", { scope: "col" }, t)))),
    h("tbody", {}, ...rows),
  );
}
