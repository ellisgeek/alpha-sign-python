// The Response Packet a Sign sends for a read (Table 14, p. 19; Table 18, p. 36).
import { checksum, stringToBytes } from "./bytes";

const NUL = "\x00";
const SOH = "\x01";
const STX = "\x02";
const ETX = "\x03";
const EOT = "\x04";

/**
 * Frames a Response body: NULs (twenty in Table 14), SOH, Type Code "0", Sign Address
 * "00" ("sent regardless of the sign's actual address"), STX, body, ETX, Checksum, EOT.
 */
export function encodeResponse(body: string, nuls = 20): Uint8Array {
  const sum = checksum(`${STX}${body}${ETX}`);
  return stringToBytes(`${NUL.repeat(nuls)}${SOH}000${STX}${body}${ETX}${sum}${EOT}`);
}
