// The Emulator core: pure, no I/O, no timers, no clock. Time is an input.
export { bytesToString, checksum, stringToBytes } from "./bytes";
export { clockAt } from "./clock";
export { defaultCommands, mergeCommandTables, TABLE_6_COMMAND_CODES } from "./commands/index";
export {
  type CommandContext,
  type CommandHandler,
  type CommandTable,
  type ReceivedCommand,
  SERIAL_ERRORS_CLEAR,
  SerialError,
} from "./commands/types";
export { buildDisplay } from "./display/build-display";
export { createLine, type LineOptions, type SignSetup } from "./line";
export {
  type EmulatorModel,
  findModel,
  MODELS,
  model4120C,
  type PaletteColor,
  type ProtocolVersion,
  RED_PALETTE,
  TRICOLOR_PALETTE,
} from "./model";
export { DEFAULT_READINGS, type Readings } from "./readings";
export { encodeResponse } from "./response";
export { NESTED_STX_PAUSE_MS } from "./sign";
export type * from "./types";
