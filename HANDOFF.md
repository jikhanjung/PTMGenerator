# Handoff

Where the project stands right now, so a new session can pick up without
re-deriving it. **This file is state, not a plan** — the work list lives in
`TODOs.md`, the reasoning behind past changes in `devlog/`.

---

## ▶ Current state (2026-07-28)

**`v0.2.0-alpha.2`** — released 2026-07-28, pre-release. Two things have landed
since the tag and neither is released yet:

1. **The built-in PTM fitter** (P02 phases 1–4, devlog 010). PTMs are fitted
   in-process by default; `PTMfitter.exe` stays selectable under
   **Preferences → PTM Engine**.
2. **A Windows installer, and a data directory** (devlog 011). onefile became
   onedir, releases ship an Inno Setup installer, and settings and logs moved to
   `%USERPROFILE%\PaleoBytes\PTMGenerator2`. **The installer has never been
   built on Windows** — run `gh workflow run build.yml` before tagging.

| | |
|---|---|
| Tests | **308 passed**, ~6 s, no display needed |
| Coverage | **92%** overall, `core/` 94–100% (gate: 85%) |
| Lint / types | ruff 20 rule groups, mypy over `core/` + `ui/` — all clean, all gating |
| CI | 5 workflows, all green: test, build, release, docs, security, codeql |
| Releases | `v0.2.0-alpha.1`, `v0.2.0-alpha.2` — both built and self-tested on Windows |
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

Three things changed in the last cycle that CI structurally cannot verify,
because every test mocks the serial port:

1. **Serial error handling** — the new "COM3 could not be opened" dialog and the
   recovery path around it.
2. **The capture loop** — now a `CaptureSession` the UI drives. The sequencing
   is tested exhaustively with fakes, but never against real camera timing.
   This is the largest behavioural change of the cycle.
3. **The utf-8 fallback** — against an `image_data.csv` actually written by an
   older build on Korean Windows, not a synthesised one.

Until that run happens, `stage beta` is premature. Everything else in `TODOs.md`
is smaller than this.

## ▶ Resuming work

```bash
make install-dev     # deps + pre-commit hooks
make test            # 308 tests, ~6 s
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

One cycle, 2026-07-27 → 28. The project went from a 1,217-line single file with
no working test suite to the process the sibling projects run.

| | Before | Now |
|---|---|---|
| Largest file | 1,217 lines | 530 (`ui/main_window.py`) |
| Tests | 0 that completed | 308 |
| Coverage | — | 92% |
| ruff rule groups | 0 | 20 |
| CI workflows | 0 | 5 |
| Releases | 0 | 2 |
| Manual | none | 2 languages |

`devlog/README.md` indexes the write-ups; 003–011 cover this cycle. Eight bugs
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
