# Handoff

Where the project stands right now, so a new session can pick up without
re-deriving it. **This file is state, not a plan** — the work list lives in
`TODOs.md`, the reasoning behind past changes in `devlog/`.

---

## ▶ Current state (2026-08-04)

**`v0.2.0-beta.1`** — released 2026-08-04, pre-release. Nothing is waiting
behind the tag: `main` and `v0.2.0-beta.1` are the same commit.

**Why beta rather than another alpha.** The alpha line was written before
anything had met the hardware. On 2026-08-03 the installed alpha.3 drove the
real dome end to end (devlog 017), and since then the UI defects that run
exposed are fixed (devlog 018) and the application has been read against
`.guides/` in full (devlog 019). What that audit found was not features
missing but **two checks that were not watching anything** — `guard_slot` on
the connected slots, and any test of the `--self-test` gate the build depends
on. Both are closed. The code has stopped being a thing that has never been
run, which is what the alpha label was honest about and no longer is.

What went out under the alpha line and carries forward:

1. **The built-in PTM fitter** (P02 phases 1–4, devlog 010). PTMs are fitted
   in-process by default, with no size ceiling beyond memory; `PTMfitter.exe`
   stays selectable under **Preferences → PTM Engine**.
2. **A Windows installer, and somewhere to put settings and logs** (devlog 011,
   013, 014). onefile became onedir, releases ship an Inno Setup installer
   into `%LOCALAPPDATA%\Programs\PaleoBytes\PTMGenerator2`, settings are
   `preferences.json` in the OS config location and the log is a dated file in
   `~/PaleoBytes/PTMGenerator2/logs/`. mypy now genuinely covers `ui/`.

New in beta.1: the About dialog with build metadata and **Copy diagnostics**,
build numbers derived from the commit count, `SHA256SUMS.txt` with the
release, and `requires-python` narrowed to the one version CI runs.

| | |
|---|---|
| Tests | **407 passed**, ~6 s, no display needed |
| Coverage | **95%** overall (gate: 85%) |
| Lint / types | ruff 20 rule groups, mypy over `core/` **and** `ui/` with `check_untyped_defs` on both — all clean, all gating |
| CI | 6 workflows, all green: test, build, release, docs, security, codeql (plus `reusable_build.yml`, which build and release both call) |
| Releases | `v0.2.0-alpha.1` … `-alpha.3`, `v0.2.0-beta.1` — all built and self-tested on Windows. alpha.3 was the first to ship an installer |
| Artifact | Inno Setup installer, per-user, `%LOCALAPPDATA%\Programs\PaleoBytes\PTMGenerator2` |
| Manual | published, English + Korean |

- Application: <https://github.com/jikhanjung/PTMGenerator/releases>
- Manual: [en](https://jikhanjung.github.io/PTMGenerator/en/) ·
  [ko](https://jikhanjung.github.io/PTMGenerator/ko/)

One thing is deliberately half-finished: **P02 phase 5**, deleting the external
fitter and the path workarounds it forces on `core/ptm_builder.py`. See below —
it is now one capture away. Everything else is complete and tested.

## ▶ The one thing blocking `0.2.0`

**Fit a high-pixel-count capture from the mirrorless body.**

That single test is the gate, and it decides three things at once: whether the
built-in fitter clears the ceiling it was written for, whether `PTMfitter.exe`
can be deleted (P02 phase 5), and whether the version stops being a
pre-release. The plan, as decided 2026-08-03, is to do all three off the back
of it.

It does **not** gate beta.1, which is still a pre-release — that is what the
label is for. What beta.1 claims is that the code has been run against the
hardware and that the checks guarding it are checking something. What it does
not claim is the headroom below.

The reason it is down to one item is the hardware run in **devlog 017**. On
2026-08-03 the alpha.3 installer was installed and driven against the real dome,
and the whole happy path worked: the Arduino and the shutter over a real serial
port, the `CaptureSession` loop against real camera timing, the polling for the
arriving file, the dated capture folder being discovered, and a PTM fitted
in-process with no external fitter. That was the largest untested surface in the
project and it is now behind us.

What that run did **not** cover, because the capture was ≤24MP — inside what the
external fitter already handles — is the headroom. The built-in fitter is proven
*correct on real files*; it is not yet proven on the file sizes that motivated
writing it. Hence the gate above.

Still unverified, and deliberately **not** blocking the release (a bad outcome
is a confusing dialog or a lost preference, not a capture that cannot run):
serial error handling, the installer's upgrade-over-the-top and uninstall paths,
the utf-8 fallback against a real legacy `image_data.csv`, Korean-path PTM
generation, and the preferences migration from a real 0.1.2 `.ini`. The upgrade
and uninstall are cheap and worth running in the same sitting as the high-res
capture — a first non-alpha release is the first one someone installs over an
existing copy. All of it is itemised in `TODOs.md`.

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
