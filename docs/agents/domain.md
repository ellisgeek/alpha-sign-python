# Domain Docs

How the engineering skills use this repo's domain docs. The repo is
single-context: one `GLOSSARY.md` and one `docs/adr/`, both at the root.

## Before exploring, read these

- **`GLOSSARY.md`**: the terms, grouped by area (Addressing, Wire format,
  Memory, Content, Scheduling, Emulator).
- **`docs/adr/`**: the ADRs that touch the area you're about to work in.

## Use the glossary's vocabulary

When your output names a domain concept (an issue title, a refactor proposal,
a hypothesis, a test name), use the glossary's term, capitalised as it is
there (Sign Model, Sign Address, File). Each entry's `_Avoid_` line lists the
synonyms it replaces.

A concept missing from the glossary is a signal: either you're inventing
language the project doesn't use (reconsider) or there's a real gap (note it
for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, say so explicitly and say why it is
worth reopening:

> _Contradicts ADR 0004 (markup syntax), but worth reopening because…_
