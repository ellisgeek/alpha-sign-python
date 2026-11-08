// Readings: one setting per unclear point in the manual (docs/emulator-spec.md,
// "Readings"). Each default cites its source. When docs/hardware-results.md
// records a real Sign, change the default for that model and cite the row.

export interface Readings {
  /** Per-File overhead in the memory budget. Default 11 (p. 27, note 1). */
  perFileOverhead: 11 | 13;
  /** Whether a DOTS PICTURE's size counts against memory. Default false (p. 27, note 1). */
  dotsPictureCounted: boolean;
  /** Read General Information reply length. Default "29" (p. 29 field list). */
  generalInfoLength: "28" | "29" | "29+NUL";
  /** Tone repeat count R plays R or R + 1 times. Default "R+1" (library's assumption; p. 22 unclear). */
  toneRepeats: "R" | "R+1";
  /** NEWS FLASH and TRUMPET Special Graphics accepted as. Default "both" (Table 66 gives both). */
  newsFlashTrumpetForm: "letters" | "hex" | "both";
  /** NEW_PAGE and double height on the 4000 Series. Default "ignored" (Tables 69, 70). */
  newPageDoubleHeight: "drawn" | "ignored";
  /** Two-digit year on Alpha 1.0. Default "window" 1997-2096 (p. 28, note 15). */
  twoDigitYear: "window" | "19xx";
  /** A nested Command whose STX lacks 100 ms of silence. Default "drop" (p. 11). */
  missingStxPause: "drop" | "accept";
  /** Network Query answer. Default "response-packet" (library's assumption; p. 32 unclear). */
  networkQueryFraming: "response-packet" | "bare";
  /** A write larger than its File. Default "ignore" (assumption; the manual does not say). */
  oversizedWrite: "truncate" | "ignore";
}

export const DEFAULT_READINGS: Readings = {
  perFileOverhead: 11,
  dotsPictureCounted: false,
  generalInfoLength: "29",
  toneRepeats: "R+1",
  newsFlashTrumpetForm: "both",
  newPageDoubleHeight: "ignored",
  twoDigitYear: "window",
  missingStxPause: "drop",
  networkQueryFraming: "response-packet",
  oversizedWrite: "ignore",
};
