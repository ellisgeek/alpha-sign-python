# Spec: An inline markup language for content

Status: ready-for-agent

Let an application developer write a Message as one string, such as
`"{color red}Hello {time}{frame rotate top}{picture A}"`, instead of a list of
Segments and Frames. The markup is a second spelling of the existing content model
(Message, Frame, Segment); it adds no new Control Codes. This is a breaking change:
`Sign` methods that take a string parse it as markup.

## Decisions

- **Module.** `alpha_sign.markup`, pure, imports only `alpha_sign.protocol`. Exports
  (also from `alpha_sign`): `parse_markup(text) -> Message`,
  `parse_segments(text) -> tuple[Segment, ...]`, `to_markup(Message | Frame |
  Sequence[Segment]) -> str`, `escape_markup(text) -> str`, `MarkupError`.
- **Syntax.** Text is literal except tokens in braces. `{{` and `}}` are literal
  braces. A token is a kind and its arguments, separated by spaces.
- **Vocabulary is derived, not listed.** An enum value is spelled as its member name
  in lowercase, so a new enum member gets a token without a table to maintain:
  - `{color red}`, `{font seven_high}`, `{speed 3}`, `{speed no_hold}`,
    `{spacing fixed_width}`, `{date mmm_dd_yyyy}`
  - switches: `{wide on}`, `{wide off}`, `{flash on}`, `{double_high on}`,
    `{descenders on}`, `{attribute shadow on}`
  - no argument: `{time}`, `{newline}`, `{newpage}`
  - File references: `{string T}`, `{picture A}`
  - bytes the library does not model: `{raw 1F...}` in hex
  - Frame breaks: `{frame MODE [POSITION]}`, e.g. `{frame rotate top}`,
    `{frame special snow}`, `{frame graphic fireworks}`
- **Case.** Kinds and enum values are case-insensitive and render in lowercase. File
  Labels are case-sensitive.
- **Frames.** `{frame ...}` starts a new Frame. Content before the first `{frame}`
  belongs to a leading Frame that takes the caller's Mode and Position (`show`'s
  arguments; HOLD and FILL elsewhere). `parse_segments` refuses `{frame}`.
- **Errors.** `MarkupError(ValueError)` with `.position`, the character offset of the
  problem: unknown kind, bad argument, unclosed `{`, stray `}`.
- **Where parsing happens.** `Sign.show`, `write_text`, `priority`, and
  `write_string` parse a `str` argument. Protocol types (`Frame`, `Message`,
  `WriteString`) and a `str` inside an explicit Segment list stay literal.
- **Escaping.** `escape_markup` doubles braces so that outside values can't inject
  tokens.
- **Reads stay typed.** `read_text` and `read_string` return the model; `to_markup`
  turns it into a string. Parse then render then parse gives the same model.
- **ADR 0004** records the syntax and the derived-vocabulary rule.

## Issues

See `issues/`.
