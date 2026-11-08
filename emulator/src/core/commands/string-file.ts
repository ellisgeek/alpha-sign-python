// Write and read STRING File, "G" and "H" (pp. 37-38).
//
// A STRING write does not blank the display (p. 37), so it leaves
// `displayRestartedAtMs` alone.
import { configuredFile, writeFile } from "./files";
import type { CommandTable } from "./types";

export const stringFileCommands: CommandTable = {
  G(cmd, ctx) {
    writeFile(ctx, "STRING", cmd.data.slice(0, 1), cmd.data.slice(1), `G${cmd.data}`);
  },

  // The Response returns Command Code "G", the File Label, and the data (Table 21, p. 38).
  H(cmd, ctx) {
    const label = cmd.data.slice(0, 1);
    if (!configuredFile(ctx, label, "STRING", `H${cmd.data}`)) return;
    ctx.respond(`G${label}${ctx.state.files[label]?.data ?? ""}`);
  },
};
