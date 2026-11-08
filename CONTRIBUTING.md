# Contributing

How to work on this library: setup, checks, the git workflow, releases, and
the reference manuals. `docs/plan.md` covers the design; `docs/adr/` covers
decisions; `GLOSSARY.md` defines the terms used in code and docs.

## Setup and checks

Install [uv](https://docs.astral.sh/uv/). It installs the Python pinned in
`.python-version` and the dev dependencies:

```sh
uv sync
uv run prek install  # git hooks: checks on commit, commit message format, tests on push
```

Then:

```sh
uv run prek run -a   # ruff (lint + format), ty, actionlint, file checks
uv run pytest        # offline tests; also run by the pre-push hook
```

The tests need no sign and no serial port. Tests that talk to a real sign are
marked `hardware` and skipped by default; run them with
`ALPHA_SIGN_PORT=/dev/tty.usbserial-XXXX uv run pytest -m hardware`.

## Writing tests

- Work test-first, at the seams listed in `docs/plan.md`.
- Expected bytes come from an independent source of truth: the worked
  examples in the protocol manual (Appendix F and others), cited by table or
  page in the test name or docstring. Never compute the expected value the way
  the code does.
- `alpha_led_sign.protocol` has no I/O and no clock. A pause the protocol needs is
  part of the encoded `Packet`, so tests check it without sleeping.

## Git workflow

- Make real changes on a branch and open a pull request. Do not push to `main`
  directly. Merge pull requests with a regular merge commit, never a squash or
  rebase merge: the individual commits feed the changelog.
- Commit messages are Conventional Commits with Angular's types only: `build`,
  `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `test`. There is no `style`
  or `chore`; formatting-only changes are `refactor`. A prek `commit-msg` hook
  rejects anything else. Commit subjects become the changelog, so write them
  for users. Mark a breaking change with `!` after the type and a
  `BREAKING CHANGE:` footer that says what users must do. The marker also
  picks the next version number (ADR 0001), so a missing one misnumbers the
  release.
- prek refuses to commit while `.pre-commit-config.yaml` has unstaged changes.
  Commit hook configuration changes first, or together with the change.
- To change an older commit that is not pushed yet, commit the fix with the
  subject `amend! <subject of the commit to change>`, then squash it in:

  ```sh
  SKIP=conventional-pre-commit git commit -m "amend! feat: ..."   # body = new message
  GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash --autostash <base>
  ```

  `SKIP` is needed only because the temporary `amend!` subject is not a
  Conventional Commit; the squashed result is.

## Releases

Releases use [Semantic Versioning](https://semver.org/), `MAJOR.MINOR.PATCH`
(for example `0.1.0`), with no `v` prefix on tags. Before 1.0, a breaking change
bumps the minor number and anything else the patch. See
[ADR 0001](docs/adr/0001-semantic-versioning.md).

To cut a release, run `scripts/release.sh` on a clean `main`:

1. [git-cliff](https://git-cliff.org/) picks the next version from the
   Conventional Commits since the last tag (`--bumped-version`), and
   `uv version` writes it to `pyproject.toml`. The first release of an
   untagged version keeps the version as it is. Never edit the version by
   hand.
2. git-cliff regenerates `CHANGELOG.md` in
   [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format from the
   Conventional Commits. `feat` goes under Added, `fix` under Fixed, `perf`
   and breaking changes under Changed, and `fix(security)` under Security.
   Commits that start with "deprecate" or "remove" go under Deprecated or
   Removed. `docs`, `test`, `build`, `ci`, and `refactor` commits are left out
   unless they are breaking.
3. The script commits `build(release): <version>` and tags it. It never
   pushes.

Review the commit and changelog, then push both:

```sh
git push origin HEAD 0.1.0   # the version the script printed
```

Pushing the tag starts the **Release** workflow. It checks that the tag is
SemVer and matches `pyproject.toml`, runs the checks, builds the sdist and
wheel, and publishes a GitHub release with the changelog entry as notes and
the built files attached.

## Reference manuals

The manuals in `docs/reference/` are Alpha's (Adaptive Micro Systems)
copyrighted documents and are large, so the PDFs are git-ignored. They come
from [alpha-american.com](https://www.alpha-american.com/):

| File | Document |
|---|---|
| [`M-Protocol.pdf`](https://www.alpha-american.com/alpha-manuals/M-Protocol.pdf) | Alpha Sign Communications Protocol, 9708-8061F |
| [`B-Alpha-4000-Series-Indoor-Displays.pdf`](https://www.alpha-american.com/alpha-manuals/B-Alpha-4000-Series-Indoor-Displays.pdf) | Alpha 4000 Series indoor displays brochure |
| [`M-Networking-Alpha-Signs.pdf`](https://www.alpha-american.com/alpha-manuals/M-Networking-Alpha-Signs.pdf) | Networking Alpha signs manual |
| [`M-Alpha-KB.pdf`](https://www.alpha-american.com/alpha-manuals/M-Alpha-KB.pdf) | Alpha knowledge base |

To fetch them all:

```sh
for f in M-Protocol.pdf B-Alpha-4000-Series-Indoor-Displays.pdf M-Networking-Alpha-Signs.pdf M-Alpha-KB.pdf; do
  curl -fsSL -o "docs/reference/$f" "https://www.alpha-american.com/alpha-manuals/$f"
done
```

What the library depends on is committed: Tables 68-70 of the protocol manual,
extracted by `docs/reference/extract_matrices.py` into
`src/alpha_led_sign/capability-matrices.json` (which the Sign Model registry
loads) and `docs/reference/capability-matrices.md` (for reading).
