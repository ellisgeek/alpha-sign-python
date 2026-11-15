# CLAUDE.md

A typed Python library that controls Alpha-protocol LED signs over serial. The
first target is the 4120C.

Read before you work:

- `GLOSSARY.md` before naming anything (code, tests, docs, issues).
- `docs/spec.md` before a design or test change: architecture, test seams,
  Remaining work.
- `docs/adr/` before changing something an ADR settled.
- `CONTRIBUTING.md` for setup, the emulator, hardware runs, fixing older
  commits, squashing a finished effort, releases, and where the manuals come
  from.

Architecture: `alpha_led_sign.protocol` is pure: bytes in, bytes out. A pause the
protocol needs is data on the `Packet`'s chunks, and the sender sleeps. A Sign
Model is data, not a subclass: everything that differs between Sign Models
lives in that data.

Tests: test-first, at the seams in `docs/spec.md`. Expected bytes come from an
independent oracle, preferably a worked example in the manual, cited by table
or page.

Checks: `uv run prek run -a` and `uv run pytest`; after a change under
`emulator/`, also `npm test` there. prek runs the first on commit and pytest
on push.

Commits: Conventional Commits with Angular types only (`build`, `ci`, `docs`,
`feat`, `fix`, `perf`, `refactor`, `test`), checked by a `commit-msg` hook.
Subjects become the changelog, so write them for users. Work on a branch and
merge it with a regular merge commit; a local merge takes the subject
`refactor: merge branch '<name>'`.

Releases: `scripts/release.sh` sets the version and the changelog.

After committing, stop and report what is committed locally. Push, open a
pull request, tag, release, or publish only when asked: pushed commits can't
be amended without a force push.

## Agent skills

### Issue tracker

GitHub Issues on `ellisgeek/alpha-sign-python`, through `gh`; earlier efforts
are markdown under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five defaults, unchanged. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context. See `docs/agents/domain.md`.
