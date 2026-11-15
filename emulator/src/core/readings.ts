// Readings: one setting per unclear point in the manual (docs/emulator-spec.md,
// "Readings"). Each default cites its source. When docs/hardware-results.md
// records a real Sign, change the default for that model and cite the row.

export interface Readings {
  /** Per-File overhead in the memory budget. Default 11 (p. 27, note 1). */
  perFileOverhead: 11 | 13;
  /**
   * Whether a DOTS PICTURE's size counts against memory. Default true, as a real 4120C
   * counted it (docs/hardware-results.md); p. 27, note 1 leaves it out.
   */
  dotsPictureCounted: boolean;
  /** Read General Information reply length. Default "29" (p. 29 field list). */
  generalInfoLength: "28" | "29" | "29+NUL";
  /** Tone repeat count R plays R or R + 1 times. Default "R+1" (library's assumption; p. 22 unclear). */
  toneRepeats: "R" | "R+1";
  /**
   * NEWS FLASH and TRUMPET Special Graphics accepted as (Table 66 gives both forms).
   * Default "none": a real 4120C played neither (docs/hardware-results.md); Appendix G
   * limits them to the BetaBrite 1036.
   */
  newsFlashTrumpetForm: "letters" | "hex" | "both" | "none";
  /**
   * NEW_PAGE and double height on the 4000 Series. Default "ignored" (Tables 69, 70); a
   * real 4120C did neither (docs/hardware-results.md).
   */
  newPageDoubleHeight: "drawn" | "ignored";
  /**
   * Two-digit year on Alpha 1.0. Default "window" 1997-2096 (p. 28, note 15); a real
   * 4120C used it (docs/hardware-results.md).
   */
  twoDigitYear: "window" | "19xx";
  /** A nested Command whose STX lacks 100 ms of silence. Default "drop" (p. 11). */
  missingStxPause: "drop" | "accept";
  /** Network Query answer. Default "response-packet" (library's assumption; p. 32 unclear). */
  networkQueryFraming: "response-packet" | "bare";
  /**
   * A write larger than its File (the manual does not say). Default "measured", what a
   * real 4120C did (docs/hardware-results.md): a TEXT File keeps its size + 1 bytes and
   * flags a buffer overflow; a STRING File is emptied and flags an illegal command.
   */
  oversizedWrite: "measured" | "truncate" | "ignore";
  /**
   * SMALL DOTS PICTURE rows sent sooner than 100 ms after the Width. Default "drop"
   * (p. 40 asks for the pause).
   */
  missingDotsPause: "drop" | "accept";
  /**
   * A SMALL DOTS PICTURE whose size differs from its Memory Configuration entry.
   * Default "drop" (p. 39: it "must match"); "accept" keeps it as sent.
   */
  dotsPictureSize: "drop" | "accept";
}

export const DEFAULT_READINGS: Readings = {
  perFileOverhead: 11,
  dotsPictureCounted: true,
  generalInfoLength: "29",
  toneRepeats: "R+1",
  newsFlashTrumpetForm: "none",
  newPageDoubleHeight: "ignored",
  twoDigitYear: "window",
  missingStxPause: "drop",
  networkQueryFraming: "response-packet",
  oversizedWrite: "measured",
  missingDotsPause: "drop",
  dotsPictureSize: "drop",
};
