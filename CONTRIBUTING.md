# Contributing

How to work on this library: setup, checks, the git workflow, releases, and
the reference manuals. `docs/spec.md` covers the design and the open work; `docs/adr/` covers
decisions; `GLOSSARY.md` defines the terms used in code and docs.

## Setup and checks

Install [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/)
(`uv tool install rust-just`, `brew install just`, or any of
[its other installers](https://just.systems/man/en/packages.html)). uv installs
the Python pinned in `.python-version` and the dev dependencies. Then:

```sh
just setup   # dev dependencies, git hooks, the emulator's npm packages
just check   # ruff (lint + format), ty, actionlint, file checks
just test    # offline tests; also run by the pre-push hook
```

`just` with no recipe lists them all. The tests need no sign and no serial
port. Tests that talk to a real sign are marked `hardware` and skipped by
default; run them with `just test-hardware /dev/tty.usbserial-XXXX`.

`just setup` also installs the `alpha-led-sign` command into `.venv/bin`, with
the `cli` extra; activate the environment to run it from the checkout.

### The emulator

`emulator/` is a TypeScript program that acts like a Sign on the line
(`docs/emulator-spec.md`). It needs the Node version in `emulator/.nvmrc`;
`just setup` installs its npm packages (`just emu-install` on its own).

```sh
just emu-test && just emu-check    # its own tests, type check, and lint
just emu-headless --port 0         # Signs on a TCP port; prints "tcp=<port> http=<port>"
just emu-serve                     # the same, with the display in a browser
```

The library reaches it as a serial port with a `socket://` URL, for example
`SerialTransport("socket://127.0.0.1:4120")`.

`just test-emulator` runs the hardware tests against it with no Sign:
a fixture starts the headless host on a free port, sets up one 4120C at Sign
Address 1, and sets `ALPHA_SIGN_PORT` to it. The tests that erase memory run
without `ALPHA_SIGN_ALLOW_ERASE`. Discovery and the witnessed tests are
skipped, and so is the whole run (with the reason) when Node or
`emulator/node_modules` is missing. `ALPHA_SIGN_CAPTURE` is refused: a capture
from the emulator is never a test vector. A pass here shows the library and
the emulator read the manual the same way; only a real Sign settles a
`# PROVISIONAL` value.

### Recipes

The `justfile` at the repo root holds every development command; the docs,
the prek hooks' setup, and CI call its recipes. Recipes that take `[args]`
pass them on (to prek, pytest, or the emulator host).

| Recipe | Does |
|---|---|
| `just setup` | Installs the dev dependencies, the git hooks, and the emulator's npm packages |
| `just check [args]` | Runs prek on every file: ruff, ty, actionlint, file checks |
| `just test [args]` | Runs the offline tests |
| `just coverage [args]` | Runs the offline tests with coverage and prints the lines they miss |
| `just test-hardware PORT [args]` | Runs the hardware tests against the Sign on `PORT` |
| `just test-witness PORT [args]` | Runs the witnessed tests, which ask you what the Sign on `PORT` showed or played |
| `just test-emulator [args]` | Runs the hardware tests against the emulator |
| `just docs` | Builds the documentation site into `great-docs/_site/` |
| `just docs-preview` | Serves the documentation site in a browser |
| `just build` | Builds the sdist and wheel into `dist/` |
| `just release` | Bumps the version, writes the changelog, commits, and tags (never pushes) |
| `just release-notes` | Prints the tagged version's changelog entry (the Release workflow) |
| `just publish` | Uploads `dist/` to PyPI (the Release workflow, with trusted publishing) |
| `just emu-install` | Installs the emulator's npm packages |
| `just emu-install-browser [args]` | Installs Chromium for the page test (CI adds `--with-deps`) |
| `just emu-test` | Runs the emulator's tests |
| `just emu-coverage` | Runs the emulator's tests with coverage of `src/` (writes `emulator/coverage/lcov.info`) |
| `just emu-test-page` | Runs the emulator page's Playwright test (`just emu-install-browser` once first) |
| `just emu-check` | Type checks and lints the emulator |
| `just emu-build` | Builds the emulator's page into `emulator/dist` |
| `just emu-headless [args]` | Runs the headless emulator host (e.g. `--port 0`) |
| `just emu-serve [args]` | Runs the bridge and the emulator page, and opens the browser |
| `just check-all` | `check` and `emu-check` |
| `just test-all` | `test`, `emu-test`, and `test-emulator` |

## Writing tests

- Work test-first, at the seams listed in `docs/spec.md`.
- Expected bytes come from an independent source of truth: the worked
  examples in the protocol manual (Appendix F and others), cited by table or
  page in the test name or docstring. Never compute the expected value the way
  the code does.
- `alpha_led_sign.protocol` has no I/O and no clock. A pause the protocol needs is
  part of the encoded `Packet`, so tests check it without sleeping.

CI uploads coverage to [Codecov](https://codecov.io/gh/ellisgeek/alpha-sign-python)
under three flags: `library-offline`, the library under the offline tests
(`just coverage`); `library-emulator`, the library under the hardware tests run
against the emulator (`just test-emulator --cov`); and `emulator`, the
emulator's TypeScript under its unit tests (`just emu-coverage`). The browser
code in `emulator/src/page/` is mostly tested by the Playwright page test,
which collects no coverage. `codecov.yml` keeps the status checks
informational. The upload authenticates with GitHub's OIDC token, so the
repository needs no Codecov token, only to be added on codecov.io.

## Documentation

The documentation site is built with [great-docs](https://posit-dev.github.io/great-docs/)
from two sources:

- The API reference comes from the docstrings in `src/`. They are Google style,
  and every public module, class, function, and method has one, with `Args`,
  `Returns`, `Yields`, and `Raises` sections that match the code. Ruff checks this
  (the `D`, `DOC`, and `ANN` rules in `pyproject.toml`). An `>>>` example in a
  docstring is a doctest that `just test` runs; an example that needs a Sign
  goes in a fenced code block instead.
- The user guide is the `.qmd` pages in `docs/user_guide/`, in the order of their
  number prefixes.

`great-docs.yml` lists what the reference shows, section by section. A new public
name goes there too. To build and view the site:

```sh
just docs           # writes great-docs/_site/
just docs-preview
```

The `docs` dependency group includes Quarto, so nothing needs a system install.
The first `just docs` installs it.

## Git workflow

- Make real changes on a branch and open a pull request. Do not push to `main`
  directly. Merge pull requests with a regular merge commit, never a squash or
  rebase merge: the individual commits feed the changelog. A local
  `git merge --no-ff` takes the subject `refactor: merge branch '<name>'`,
  because the `commit-msg` hook rejects git's default `Merge branch ...`.
- Use `gh pr merge --delete-branch` only on a pull request whose branch is no
  other pull request's base: GitHub closes the dependent pull request instead
  of retargeting it.
- A finished multi-branch effort may be squashed into one commit on `main`
  when the maintainer asks for it. Keep `backup/<effort>-before-squash` at the
  integration branch's tip, `git merge --squash`, write one user-facing `feat:`
  subject (it is the effort's only changelog line), check the tree matches the
  backup, then delete the merged branches.
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
[ADR 0001](https://github.com/ellisgeek/alpha-sign-python/blob/main/docs/adr/0001-semantic-versioning.md).

To cut a release, run `just release` on a clean `main`:

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
3. The recipe commits `build(release): <version>` and tags it. It never
   pushes.

Review the commit and changelog, then push both:

```sh
git push origin HEAD 0.1.0   # the version the recipe printed
```

Pushing the tag starts the **Release** workflow. It checks that the tag is
SemVer and matches `pyproject.toml`, runs the checks, and builds the sdist and
wheel (`just build`). It uploads them to [PyPI](https://pypi.org/project/alpha-led-sign/)
(`just publish`), then publishes a GitHub release with the changelog entry
(`just release-notes`) as notes and the built files attached. A rerun after a
failed GitHub release skips the files PyPI already has.

PyPI accepts the upload through
[trusted publishing](https://docs.pypi.org/trusted-publishers/), so the
repository holds no token. The publisher is set up once on PyPI: project
`alpha-led-sign`, owner `ellisgeek`, repository `alpha-sign-python`, workflow
`release.yml`, environment `pypi`. The repository has a matching `pypi`
environment (Settings > Environments).

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
| [`M-Cables-Adapters-Interfaces.pdf`](https://www.alpha-american.com/alpha-manuals/M-Cables-Adapters-Interfaces.pdf) | Cables, adapters, and interfaces (sign port and cable pinouts) |
| [`TM-Network-Cabling-Pinouts.pdf`](https://www.alpha-american.com/alpha-manuals/TM-Network-Cabling-Pinouts.pdf) | TechMemo #02-0010A, network cabling and sign connector pinouts |
| [`M-Install-Alpha-Series.pdf`](https://www.alpha-american.com/alpha-manuals/M-Install-Alpha-Series.pdf) | Alpha series sign installation instructions (mounting, serial address) |

To fetch them all:

```sh
for f in M-Protocol.pdf B-Alpha-4000-Series-Indoor-Displays.pdf M-Networking-Alpha-Signs.pdf M-Alpha-KB.pdf \
  M-Cables-Adapters-Interfaces.pdf TM-Network-Cabling-Pinouts.pdf M-Install-Alpha-Series.pdf; do
  curl -fsSL -o "docs/reference/$f" "https://www.alpha-american.com/alpha-manuals/$f"
done
```

What the library depends on is committed: Tables 68-70 of the protocol manual,
extracted by `docs/reference/extract_matrices.py` into
`src/alpha_led_sign/capability-matrices.json` (which the Sign Model registry
loads) and `docs/reference/capability-matrices.md` (for reading).
