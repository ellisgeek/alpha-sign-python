# Short names for the development commands; CONTRIBUTING.md and CI use them.
# Run `just` to list them.

# Pass variadic arguments to recipes as "$@", so quoted arguments stay whole.
set positional-arguments
set shell := ["bash", "-uc"]

# List the recipes
default:
    @just --list

# Install the dev tools, the git hooks, and the emulator's npm packages
setup: emu-install
    uv sync
    uv run prek install

# Run the Python checks: ruff, ruff format, ty, actionlint, file checks (extra arguments go to prek)
check *args:
    uv run prek run -a "$@"

# Run the offline Python tests (extra arguments go to pytest)
test *args:
    uv run pytest "$@"

# Run the tests that talk to a real sign on the given serial port (extra arguments go to pytest)
test-hardware port *args:
    ALPHA_SIGN_PORT="$1" uv run pytest -m hardware "${@:2}"

# Run the witnessed tests, which ask the person watching the sign on the given port
test-witness port *args:
    ALPHA_SIGN_PORT="$1" ALPHA_SIGN_WITNESS=1 uv run pytest -m witness -s "${@:2}"

# Run the hardware tests against the emulator (extra arguments go to pytest)
test-emulator *args:
    uv run pytest -m emulator "$@"

# Build the documentation site into great-docs/_site
docs:
    uv run --group docs great-docs build

# Preview the documentation site in a browser
docs-preview:
    uv run --group docs great-docs preview

# Build the sdist and wheel into dist/
build:
    uv build

# Bump the version, write the changelog, commit, and tag locally (never pushes)
release:
    #!/usr/bin/env bash
    set -euo pipefail

    # Untracked files (e.g. local editor settings) can't end up in the release.
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
      echo "error: working tree has uncommitted changes" >&2
      exit 1
    fi

    current="$(uv version --short)"

    # Release the current version as-is if it was never tagged (e.g. the first
    # release); otherwise let git-cliff pick the next SemVer version from the
    # Conventional Commits since the last tag ([tool.git-cliff.bump]).
    if git rev-parse -q --verify "refs/tags/$current" >/dev/null; then
      version="$(uv run --frozen git-cliff --bumped-version 2>/dev/null)"
      if [[ "$version" == "$current" ]]; then
        echo "error: no commits since $current call for a release" >&2
        exit 1
      fi
      uv version --quiet --no-sync "$version"
    else
      version="$current"
    fi

    uv run --frozen git-cliff --tag "$version" --output CHANGELOG.md
    # git-cliff leaves an extra blank line at the end; keep exactly one newline.
    changelog="$(cat CHANGELOG.md)"
    printf '%s\n' "$changelog" > CHANGELOG.md

    git add pyproject.toml uv.lock CHANGELOG.md
    git commit --quiet -m "build(release): $version"
    git tag -a "$version" -m "$version"

    echo "Tagged $version. Review it, then publish with:"
    echo "  git push origin HEAD $version"

# Print the release notes for the tagged version: its CHANGELOG.md entry
release-notes:
    uv run --frozen git-cliff --current --strip all

# Upload dist/ to PyPI, skipping files already there (the Release workflow, with trusted publishing)
publish:
    uv publish --check-url https://pypi.org/simple/

# Install the emulator's npm packages
emu-install:
    cd emulator && npm ci

# Install the browser for emu-test-page (extra arguments go to playwright, e.g. --with-deps)
emu-install-browser *args:
    cd emulator && npx playwright install "$@" chromium

# Run the emulator's tests
emu-test:
    cd emulator && npm test

# Run the emulator page's browser test (Playwright; once: just emu-install-browser)
emu-test-page:
    cd emulator && npm run test:page

# Run the emulator's checks: typecheck and lint
emu-check:
    cd emulator && npm run check

# Build the emulator's page into emulator/dist
emu-build:
    cd emulator && npm run build

# Run the headless emulator host (extra arguments go to it, e.g. --port 0)
emu-headless *args:
    cd emulator && npm run headless -- "$@"

# Run the bridge and the emulator page, and open the browser
emu-serve *args:
    cd emulator && npm run serve -- "$@"

# Run the Python and emulator checks
check-all: check emu-check

# Run the Python and emulator tests, and the hardware tests against the emulator
test-all: test emu-test test-emulator
