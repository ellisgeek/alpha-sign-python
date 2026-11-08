// The page's clock control. It feeds the emulated Signs the Write SPECIAL
// FUNCTION Packets a library would send (pp. 21-26), so the clock changes
// through the Signs' own Commands and nothing else is touched.

export interface ClockSetting {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
}

const two = (n: number) => String(n % 100).padStart(2, "0");

/** One Packet to all Signs ("Z00", Table 38 p. 58) per Command. */
function toAllSigns(label: string, data: string): string {
  return `\x00\x00\x00\x00\x00\x01Z00\x02E${label}${data}\x04`;
}

/** Set Time of Day (p. 21), Set Date (p. 26), Set Day of Week (p. 22; 1 = Sunday). */
export function clockPackets(c: ClockSetting): string[] {
  const dayOfWeek = new Date(Date.UTC(c.year, c.month - 1, c.day)).getUTCDay() + 1;
  return [
    toAllSigns(" ", two(c.hour) + two(c.minute)),
    toAllSigns(";", two(c.month) + two(c.day) + two(c.year)),
    toAllSigns("&", String(dayOfWeek)),
  ];
}

/** Reads `<input type="date">` and `<input type="time">` values; null if either is unusable. */
export function parseClockInput(date: string, time: string): ClockSetting | null {
  const d = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  const t = /^(\d{2}):(\d{2})/.exec(time);
  if (!d || !t) return null;
  const [year, month, day, hour, minute] = [d[1], d[2], d[3], t[1], t[2]].map(Number) as [
    number,
    number,
    number,
    number,
    number,
  ];
  const check = new Date(Date.UTC(year, month - 1, day));
  if (check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) return null;
  if (hour > 23 || minute > 59) return null;
  return { year, month, day, hour, minute };
}
