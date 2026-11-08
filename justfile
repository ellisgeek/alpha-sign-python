# Short names for the common commands. Each recipe only wraps a command that
# CONTRIBUTING.md also shows in raw form. Run `uv run just` (or `just`) to list them.

# List the recipes
default:
    @just --list

# Install the dev tools, the git hooks, and the emulator's npm packages
setup:
    uv sync
    uv run prek install
    cd emulator && npm ci

# Run the Python checks: ruff, ruff format, ty, actionlint, file checks
check:
    uv run prek run -a

# Run the offline Python tests (extra arguments go to pytest)
test *args:
    uv run pytest {{ args }}

# Run the tests that talk to a real sign on the given serial port
test-hardware port:
    ALPHA_SIGN_PORT={{ port }} uv run pytest -m hardware

# Bump the version, write the changelog, commit, and tag locally (never pushes)
release:
    scripts/release.sh

# Run the emulator's tests
emu-test:
    cd emulator && npm test

# Run the emulator page's browser test (Playwright; once: npx playwright install chromium)
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
    cd emulator && npm run headless -- {{ args }}

# Run the bridge and the emulator page, and open the browser
emu-serve *args:
    cd emulator && npm run serve -- {{ args }}

# Run the hardware tests against the emulator (extra arguments go to pytest)
test-emulator *args:
    uv run pytest -m emulator {{ args }}

# Run the Python and emulator checks
check-all: check emu-check

# Run the Python and emulator tests, and the hardware tests against the emulator
test-all: test emu-test test-emulator
