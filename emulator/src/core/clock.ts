// The emulated clock. It starts from a wall-clock value given to the Line and
// moves with Line time; it never reads a real clock.
import type { ClockState, DayOfWeek, EmulatedClock } from "./types";

/** A clock that reads `startClockMs` at Line time `atLineMs`. */
export function startClock(startClockMs: number, atLineMs: number): ClockState {
  return { offsetMs: startClockMs - atLineMs, dayOfWeekShift: 0, timeFormat: "S" };
}

export function clockAt(clock: ClockState, lineMs: number): EmulatedClock {
  const wallMs = lineMs + clock.offsetMs;
  const t = new Date(wallMs);
  // getUTCDay: 0 = Sunday; the manual numbers Sunday 1 (p. 30).
  const dayOfWeek = (((t.getUTCDay() + clock.dayOfWeekShift) % 7) + 1) as DayOfWeek;
  return {
    wallMs,
    year: t.getUTCFullYear(),
    month: t.getUTCMonth() + 1,
    day: t.getUTCDate(),
    hour: t.getUTCHours(),
    minute: t.getUTCMinutes(),
    second: t.getUTCSeconds(),
    dayOfWeek,
    timeFormat: clock.timeFormat,
  };
}

const DAY_MS = 86_400_000;

/** Sets the time of day, keeping the date (Set Time of Day, p. 21). Seconds start at 0. */
export function setTimeOfDay(
  clock: ClockState,
  lineMs: number,
  hour: number,
  minute: number,
): void {
  const wallMs = lineMs + clock.offsetMs;
  const dayStart = Math.floor(wallMs / DAY_MS) * DAY_MS;
  clock.offsetMs = dayStart + hour * 3_600_000 + minute * 60_000 - lineMs;
}

/**
 * Sets the date, keeping the time of day. The day of week is its own setting
 * that the Sign moves on at midnight (Set Day of Week, p. 22), so a new date
 * leaves it alone.
 */
export function setDate(
  clock: ClockState,
  lineMs: number,
  year: number,
  month: number,
  day: number,
): void {
  const before = clockAt(clock, lineMs);
  const timeOfDay = before.wallMs - Math.floor(before.wallMs / DAY_MS) * DAY_MS;
  clock.offsetMs = Date.UTC(year, month - 1, day) + timeOfDay - lineMs;
  setDayOfWeek(clock, lineMs, before.dayOfWeek);
}

/** Sets the day of week, 1 = Sunday (p. 22). */
export function setDayOfWeek(clock: ClockState, lineMs: number, dayOfWeek: number): void {
  const fromDate = new Date(lineMs + clock.offsetMs).getUTCDay();
  clock.dayOfWeekShift = (((dayOfWeek - 1 - fromDate) % 7) + 7) % 7;
}
