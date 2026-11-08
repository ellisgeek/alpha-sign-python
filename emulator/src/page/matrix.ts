// Draws a DisplayState's pixels on a canvas as round LEDs at the model's real
// pixel size: one LED per pixel, `pitch` CSS pixels apart.
import type { DisplayState, PaletteColor } from "../core/index";

export class Matrix {
  readonly canvas: HTMLCanvasElement;
  private readonly ctx: CanvasRenderingContext2D;
  private last: Uint8Array | null = null;
  private pitch = 0;

  constructor(
    private readonly columns: number,
    private readonly rows: number,
    private readonly palette: PaletteColor[],
  ) {
    this.canvas = document.createElement("canvas");
    const ctx = this.canvas.getContext("2d");
    if (!ctx) throw new Error("no 2D canvas");
    this.ctx = ctx;
  }

  /** Sets the LED pitch in CSS pixels; redraws on the next `draw`. */
  setPitch(pitch: number): void {
    if (pitch === this.pitch) return;
    this.pitch = pitch;
    const scale = window.devicePixelRatio || 1;
    this.canvas.width = Math.round(this.columns * pitch * scale);
    this.canvas.height = Math.round(this.rows * pitch * scale);
    this.canvas.style.width = `${this.columns * pitch}px`;
    this.canvas.style.height = `${this.rows * pitch}px`;
    this.last = null;
  }

  draw(pixels: DisplayState["pixels"]): void {
    const { colors } = pixels;
    if (this.last && sameColors(this.last, colors)) return;
    this.last = colors.slice();
    const { ctx } = this;
    const step = this.canvas.width / this.columns;
    const radius = step * 0.4;
    ctx.fillStyle = "#050404";
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    // One path per palette index keeps a frame to a few fills.
    const paths = this.palette.map(() => new Path2D());
    for (let y = 0; y < this.rows; y++) {
      for (let x = 0; x < this.columns; x++) {
        const index = colors[y * this.columns + x] ?? 0;
        const path = paths[index] ?? paths[0];
        const cx = (x + 0.5) * step;
        const cy = (y + 0.5) * step;
        path?.moveTo(cx + radius, cy);
        path?.arc(cx, cy, radius, 0, Math.PI * 2);
      }
    }
    paths.forEach((path, i) => {
      ctx.fillStyle = this.palette[i]?.rgb ?? "#000";
      ctx.fill(path);
    });
  }
}

function sameColors(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}
