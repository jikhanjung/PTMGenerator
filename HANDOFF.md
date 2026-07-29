# Handoff

Where the project stands right now, so a new session can pick up without
re-deriving it. **This file is state, not a plan** — the work list lives in
`TODOs.md`, the reasoning behind past changes in `devlog/`.

---

## ▶ Current state (2026-07-29)

**`v0.2.0-alpha.3`** — released 2026-07-29, pre-release. Nothing is waiting
behind the tag: `main` and `v0.2.0-alpha.3` are the same commit. Two things
went out with it that no earlier release had:

1. **The built-in PTM fitter** (P02 phases 1–4, devlog 010). PTMs are fitted
   in-process by default, with no size ceiling beyond memory; `PTMfitter.exe`
   stays selectable under **Preferences → PTM Engine**.
2. **A Windows installer, and somewhere to put settings and logs** (devlog 011,
   013, 014). onefile became onedir, releases ship an Inno Setup installer
   into `%LOCALAPPDATA%\Programs\PaleoBytes\PTMGenerator2`, settings are
   `preferences.json` in the OS config location and the log is a dated file in
   `~/PaleoBytes/PTMGenerator2/logs/`. mypy now genuinely covers `ui/`.

The artifact is `PTMGenerator2_v0.2.0-alpha.3_build3_Installer.exe` (41 MB).
The whole release matrix is green and `--self-test` ran against the frozen
executable before Inno Setup packaged it — but **nobody has installed it**.
That, and the hardware run, is what `TODOs.md` is about.

| | |
|---|---|
| Tests | **347 passed**, ~6 s, no display needed |
| Coverage | **93%** overall (gate: 85%). `core/self_test.py` is the outlier at 29% — it checks the frozen bundle, which the suite is not |
| Lint / types | ruff 20 rule groups, mypy over `core/` **and** `ui/` with `check_untyped_defs` on both — all clean, all gating |
| CI | 6 workflows, all green: test, build, release, docs, security, codeql (plus `reusable_build.yml`, which build and release both call) |
| Releases | `v0.2.0-alpha.1`, `v0.2.0-alpha.2`, `v0.2.0-alpha.3` — all built and self-tested on Windows. alpha.3 is the first to ship an installer |
| Artifact | Inno Setup installer, per-user, `%LOCALAPPDATA%\Programs\PaleoBytes\PTMGenerator2` |
| Manual | published, English + Korean |

- Application: <https://github.com/jikhanjung/PTMGenerator/releases>
- Manual: [en](https://jikhanjung.github.io/PTMGenerator/en/) ·
  [ko](https://jikhanjung.github.io/PTMGenerator/ko/)

One thing is deliberately half-finished: **P02 phase 5**, deleting the external
fitter and the path workarounds it forces on `core/ptm_builder.py`. It is
blocked on the built-in fitter having fitted a real capture, which needs a
camera change. Everything else is complete and tested.

## ▶ The one thing blocking progress

**The alpha has never met an Arduino.**

Four things now shipped in alpha.3 that CI structurally cannot verify — every
test mocks the serial port, and no runner installs the installer:

1. **Serial error handling** — the "COM3 could not be opened" dialog and the
   recovery path around it.
2. **The capture loop** — now a `CaptureSession` the UI drives. The sequencing
   is tested exhaustively with fakes, but never against real camera timing.
   This is the largest behavioural change of the cycle.
3. **The utf-8 fallback** — against an `image_data.csv` actually written by an
   older build on Korean Windows, not a synthesised one.
4. **The installer** — it compiles, the artifact is a valid Inno Setup binary
   and the frozen executable passes `--self-test`, but the install, the
   upgrade-over-the-top and the uninstall have never been run.

alpha.3 exists so this can happen against a real build: it is the first release
that carries the installer and the built-in fitter, so the earlier tags cannot
stand in for it. Until the run happens, `stage beta` is premature. Everything
else in `TODOs.md` is smaller than this.

## ▶ Resuming work

```bash
make install-dev     # deps + pre-commit hooks
make test            # 347 tests, ~6 s
make lint type-check
```

Read `CLAUDE.md` before changing anything — it carries the conventions and the
gotchas. The three that have actually caused problems:

- Constructing a main window replaces `sys.stdout` and opens today's log in
  `~/PaleoBytes/PTMGenerator2/logs/`.
- A script that builds a window writes to the developer's real preferences
  unless it sets `PTMGENERATOR2_DATA_DIR` first. This has happened.
- Every `core.resources.ICON` entry must exist on disk. `QIcon()` returns a null
  icon rather than raising, which is how a nonexistent icon shipped from the
  first release until `--self-test` found it.

Two rules that are load-bearing rather than stylistic:

- **`core/` imports no PyQt5**, asserted in a subprocess by
  `tests/test_smoke.py`. It is why the suite runs in three seconds and why the
  capture policy is testable at all. Qt work belongs in `ui/`.
- **Run `gh workflow run build.yml` before pushing a version tag.** The build
  has failed on Windows for a reason a Linux build could not see (devlog 007),
  and a failure during a release leaves the tag already pushed.

## ▶ Releasing

1. Describe the change under `## [Unreleased]` in `CHANGELOG.md`.
2. `gh workflow run build.yml` if anything touching the executable changed.
3. `python scripts/bump_version.py stage beta` (or `prerelease`, `patch`, …).
4. `git push && git push origin v<version>`.

Never edit `version.py` by hand. Full detail in `VERSION_MANAGEMENT.md`.

---

## Where things came from

One cycle, 2026-07-27 → 29. The project went from a 1,217-line single file with
no working test suite to the process the sibling projects run.

| | Before | Now |
|---|---|---|
| Largest file | 1,217 lines | 696 (`ui/main_window.py`) |
| Tests | 0 that completed | 347 |
| Coverage | — | 93% |
| ruff rule groups | 0 | 20 |
| CI workflows | 0 | 6 |
| Releases | 0 | 3 |
| Manual | none | 2 languages |

`devlog/README.md` indexes the write-ups; 003–016 cover this cycle. Eight bugs
were fixed along the way, each with a regression test verified to fail against
the previous code — the crashes are listed in `CHANGELOG.md` under
`[0.2.0-alpha.1]`.

Worth knowing, because they shape how things are set up now:

- **CI caught three failures local runs could not** — a bare `pytest` not
  putting the repo root on `sys.path`, a Windows-only path-separator assumption,
  and the PyInstaller icon. That is the argument for the 3-OS matrix.
- **`--self-test` found a missing icon on its first run.** The file had never
  existed in the repository.
- **mypy had been checking almost nothing** — it skips the bodies of unannotated
  functions by default, and this code carries few annotations.
