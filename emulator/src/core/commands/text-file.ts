// Write and read TEXT File, "A" and "B" (pp. 17-20).
//
// Content is stored exactly as received after the File Label, so Control Codes
// the Emulator does not model read back unchanged.
import { PRIORITY_LABEL, PRIORITY_SIZE } from "../memory";
import { configuredFile, fitContent, writeFile } from "./files";
import type { CommandTable } from "./types";

export const textFileCommands: CommandTable = {
  A(cmd, ctx) {
    const label = cmd.data.slice(0, 1);
    const content = cmd.data.slice(1);
    const body = `A${cmd.data}`;
    if (label === PRIORITY_LABEL) {
      // Always exists, 125 bytes; a write with no ASCII Message ends it (p. 20).
      if (content === "") {
        ctx.state.priority = null;
      } else {
        const fitted = fitContent(ctx, "PRIORITY", content, PRIORITY_SIZE, label, body);
        if (fitted === null) return;
        ctx.state.priority = { label, type: "TEXT", data: fitted };
      }
      ctx.state.displayRestartedAtMs = cmd.atMs;
      return;
    }
    if (writeFile(ctx, "TEXT", label, content, body)) {
      // "When writing to a TEXT file, the display will blank" (p. 18).
      // "After the transmission is over, the unit will begin displaying the last
      // received TEXT file" (p. 18).
      ctx.state.displayRestartedAtMs = cmd.atMs;
      ctx.state.displayStartLabel = label;
    }
  },

  // The Response returns Command Code "A", the File Label, and the content (Table 14, p. 19).
  B(cmd, ctx) {
    const label = cmd.data.slice(0, 1);
    if (label === PRIORITY_LABEL) {
      ctx.respond(`A${label}${ctx.state.priority?.data ?? ""}`);
      return;
    }
    if (!configuredFile(ctx, label, "TEXT", `B${cmd.data}`)) return;
    ctx.respond(`A${label}${ctx.state.files[label]?.data ?? ""}`);
  },
};
