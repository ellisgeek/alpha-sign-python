# CLAUDE.md

A typed Python library that controls Alpha-protocol LED signs over serial. The
first target is the 4120C, but nothing may be specific to one Sign Model. Read
`GLOSSARY.md` for the domain terms, `docs/plan.md` for the design and delivery
phases, and `docs/adr/` for decisions. `CONTRIBUTING.md` covers setup, the git
workflow, and where the manuals come from.

Architecture: `alpha_led_sign.protocol` is pure (bytes in, bytes out, no I/O, no
clocks, no sleeps). Required pauses are returned as data on the `Packet`'s
chunks and the sender sleeps. A Sign Model is data, not a subclass.

Tests: test-first, at the seams listed in `docs/plan.md`. Expected bytes come
from an independent source, preferably the worked examples in the manual
(cite the table or page), never recomputed the way the code does.

Checks: `uv run prek run -a` (ruff, ruff format, ty, actionlint, file checks) and
`uv run pytest`; prek hooks run them on commit and push.

Commits: Conventional Commits, Angular types only (`build`, `ci`, `docs`,
`feat`, `fix`, `perf`, `refactor`, `test`); enforced by a prek `commit-msg` hook.
Subjects become the changelog, so write them for users. Real changes go on a
branch and a pull request.

PRs: Always merge with a regular merge commit (never squash or rebase merge).

Releases: SemVer `MAJOR.MINOR.PATCH` (e.g. `0.1.0`, no `v` prefix; ADR 0001).
`scripts/release.sh` (git-cliff + uv version) bumps, writes the changelog,
commits, and tags locally; pushing the tag triggers the Release workflow,
which publishes. Never edit versions by hand. Never push, tag, or publish a
release unless asked.
