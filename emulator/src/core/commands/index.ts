// The Command dispatch table. One module per Command family; each exports a
// `CommandTable` keyed by Command Code. To add a family, add a module and list
// it in `families` below. Nothing else needs to change.
import { specialFunctionCommands } from "./special-functions";
import { stringFileCommands } from "./string-file";
import { textFileCommands } from "./text-file";
import type { CommandTable } from "./types";

const families: CommandTable[] = [textFileCommands, specialFunctionCommands, stringFileCommands];

/** Merges families; a Command Code claimed twice is a programming error. */
export function mergeCommandTables(tables: CommandTable[]): CommandTable {
  const merged: CommandTable = {};
  for (const table of tables) {
    for (const [code, handler] of Object.entries(table)) {
      if (code in merged) throw new Error(`Command Code ${code} registered twice`);
      merged[code] = handler;
    }
  }
  return merged;
}

export const defaultCommands: CommandTable = mergeCommandTables(families);

/**
 * Every Command Code in Table 6 (p. 11). A code outside this set is illegal and
 * sets register bit 5 (p. 31); a code inside it with no handler is only
 * "unsupported" by the Emulator.
 */
export const TABLE_6_COMMAND_CODES = new Set("ABEFGHIJKLMNOT");
