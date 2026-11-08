# Hardware results

What a real Sign did for each item on the hardware checklist in [spec.md](spec.md).
Fill in a row after each hardware run. When a result disagrees with the manual, add
the overrides field to `SignModel` and use it in that model's profile.

Run the automatic tests with `ALPHA_SIGN_PORT=... uv run pytest -m hardware`, and the
witnessed ones with `ALPHA_SIGN_PORT=... ALPHA_SIGN_WITNESS=1 uv run pytest -m witness -s`.
Set `ALPHA_SIGN_CAPTURE=<path>` to keep the bytes as test vectors.

| Item | What the manual says | What the 4120C did | Firmware | Date |
|---|---|---|---|---|
| Network Query answers | Only the `UAAZ` data (p. 32). | Not yet run. | | |
| General Information length | 28 or 29 characters; the field list adds up to 29 plus an optional NUL (p. 29). | Not yet run. | | |
| Programmable tone repeats | `R` is the repeat count; it does not say whether the first play counts (p. 22). | Not yet run. | | |
| NEWS FLASH and TRUMPET | `"A"`/`"B"`, with hex 3AH/3BH beside them (Table 66). | Not yet run. | | |
| NEW_PAGE on the 4000 Series | Not listed (Table 69). | Not yet run. | | |
| Double height on the 4000 Series | Not listed (Table 70). | Not yet run. | | |
| Two-digit year on Alpha 1.0 | The 1997-2096 window is given for Alpha 2.0 and later only (p. 28, note 15). | Not yet run. | | |
| Per-File overhead | 11 bytes per File (p. 27, note 1). [readerboard](https://github.com/mjaksn/readerboard) reports 13. | Not yet run. | | |
| DOTS PICTURE File in the memory budget | Its size is left out of the sum (p. 27, note 1). | Not yet run. | | |
| Total memory | 28,000 bytes (Table 5, brochure). | Not yet run. | | |
