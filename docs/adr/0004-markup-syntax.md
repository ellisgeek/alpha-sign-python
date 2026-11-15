# Write content as brace markup with a vocabulary derived from the enums

Content can be written as one string: text, with tokens in braces such as
`{color red}`, `{string T}`, and `{frame rotate top}`. `{{` and `}}` are literal
braces. The markup is a second spelling of the content model (Message, Frame,
Segment) and adds nothing the model lacks. `Sign.show`, `write_text`,
`write_string`, and `priority` read a `str` as markup; `to_markup` writes it back.

Enum values are spelled as the member name in lowercase, less the kind as a prefix
(`Speed.SPEED_3` is `{speed 3}`). A new enum member gets a spelling with no table
to update. Token kinds (`color`, `string`, `frame`, ...) are one small map per
Control Code type. Kinds and values ignore case; File Labels do not, because `a`
and `A` are different Files.

Braces were chosen over angle tags (`<red>...</red>`), which suggest closing tags
that Control Codes, being switches, don't have, and over `[red]`, which is common
in sign text. tonymagro/asign uses the same `{Token}` style.

## Consequences

- Users will store markup in configuration files, so the spelling is a public
  format. Renaming an enum member renames its token: treat it as a breaking change.
- A `str` given to a `Sign` method can no longer hold a literal brace without
  escaping it (`escape_markup`). A `str` inside a list of Segments, and the protocol
  types, stay literal.
- File Labels `}` and space can't be written in a token; `to_markup` writes such a
  reference as `{raw ...}`.
- Shorthands such as `{red}` can be added later without breaking anything.
