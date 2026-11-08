# Version releases with SemVer

Releases use [Semantic Versioning](https://semver.org/), `MAJOR.MINOR.PATCH`,
starting at `0.1.0`. Tags carry no `v` prefix.

This is a library that other code depends on, and SemVer tells a dependent
from the number alone whether an upgrade can break it. That lets dependents
write a range such as `alpha-led-sign~=0.3.0` and take fixes without reading
every changelog.

The library is young, and its interface will change often while the protocol
coverage grows, so it starts at 0.x. Before 1.0, a breaking change bumps the
minor number, and a feature or a fix bumps the patch number: `~=0.3.0` never
takes a breaking change. Version 1.0 marks the interface as stable, and from
then on SemVer's usual rules apply: breaking changes bump the major number,
features the minor, fixes the patch.

CalVer (`YYYY.M.MICRO`) was considered, because it would need no judgment
about what an upgrade breaks. It was rejected: a date tells a dependent
nothing about compatibility, so the only safe dependency on a CalVer library
is an exact pin.

## Consequences

- The Conventional Commit types choose the next version. `just release` asks
  git-cliff for it (`--bumped-version`, configured under
  `[tool.git-cliff.bump]`) and writes it to `pyproject.toml` with
  `uv version`. Do not edit versions by hand.
- A commit that breaks users must say so, with `!` after the type and a
  `BREAKING CHANGE:` footer that says what users must do. A missing marker
  gives a release the wrong number.
- git-cliff builds `CHANGELOG.md` in Keep a Changelog format from the
  Conventional Commits, so commit subjects are the release notes. Write them
  for users.
