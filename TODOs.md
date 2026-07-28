# TODOs

Work to do, short and medium term, with enough context to pick each one up
later. **This file is the plan**; `HANDOFF.md` is the current state, and
`devlog/` is why past changes were made the way they were.

---

## Verify the alpha against real hardware — blocks `stage beta`

Every test mocks `serial.Serial`, so three changes from the last cycle have
never met an Arduino. Nothing in CI can substitute for this, and it is larger
than everything else on this list.

- **Serial error handling** — unplug the board mid-run, and start a capture with
  the Arduino IDE's serial monitor holding the port. Both should report which
  port and why, and offer to continue.
- **The capture loop** — a full 50-LED run against real camera timing. The
  sequencing moved into `core/capture_session.py` and is tested exhaustively
  with fakes; what is unverified is whether the preparation and polling windows
  still suit a real shutter and a real card write.
- **The utf-8 fallback** — open an `image_data.csv` actually written by an
  earlier build on Korean Windows, not a synthesised one.

Once that passes: `python scripts/bump_version.py stage beta`.

---

## Process status against the sibling projects

Where PTMGenerator2 stands against the process `../Modan2` and `../CTHarvester`
run. Verified 2026-07-28, at v0.2.0-alpha.2.

| # | Item | Status | Where it stands |
|---|---|---|---|
| 1 | Cross-platform CI matrix + headless smoke test | ✅ | 3 OS x Python 3.12, `tests/test_smoke.py`. No xvfb — Qt's offscreen plugin |
| 2 | Lint + tests gating | ✅ | ruff, mypy, the test matrix and the translation check all gate. No `\|\| true` anywhere |
| 3 | Expand the lint ruleset incrementally | ✅ | All of the guide's groups landed 2026-07-28: `E, F, I, N, UP, B, C4, SIM, PTH, RUF, DTZ, S, TRY, LOG, G, RET, PIE, PERF, A, C90`. Waivers argued in `pyproject.toml` |
| 4 | `filterwarnings = error` | ✅ | `pyproject.toml`, one narrow documented ignore for PyQt5's sip shims |
| 5 | Lockfile + pip-audit + Dependabot | ✅ | 9 per-platform locks with hashes, pip-audit on all three runtime locks, `.github/dependabot.yml` |
| 6 | Coverage gate | ✅ | `--cov-fail-under=85` on the Linux leg; actual is 88% across 161 tests |
| 7 | Static type checking, scoped | ⚠️ | mypy gates over `core/` **and** `ui/`. `check_untyped_defs` is on for `core/` only — see below |
| 8 | Dead-code / complexity automation | ✅ | `C90` enforced at the guide's threshold of 15 |
| 9 | Packaged-artifact smoke test | ✅ | `--self-test` runs against the built .exe in `release.yml`. Installer signing still open |
| 10 | Property-based tests | ✅ | `tests/test_light_positions_properties.py`, hypothesis over the adjustment angle |

**Done 2026-07-28.** From the R01 audit (devlog 005–006): the serial-open crash
and the platform-default encodings, the naive-datetime DST bug, the full lint
ruleset, `--self-test`, property-based tests for the light geometry, and mypy
widened to `ui/` with body checking on for `core/`. Then (devlog 007–008): the
on-demand build workflow and the Windows icon defect it found, the first two
releases (`v0.2.0-alpha.1`, `v0.2.0-alpha.2`), the utf-8 fallback that keeps
legacy capture tables loading, and the Korean manual.

**Not doing: signed installers.** Item 9's remaining half. There is no
certificate, and an unsigned single .exe with a SmartScreen warning is what this
audience already downloads. Revisit if the tool is distributed outside the lab.

**Not doing: branch protection on `main`.** The guide (§14) and Appendix A item
2 both call for it, and it is deliberately declined here. This is a
single-maintainer repository with no review partner, so requiring pull requests
buys nothing that the pre-commit hooks and the gating CI do not already provide,
and costs a PR round-trip on every one-line fix. Revisit if a second person
starts committing. Recording it so a later audit reads this as a decision
rather than an oversight.

---

## Turn on `check_untyped_defs` for `ui/`

`core/` has it; `ui/` does not. It is the setting that matters — the code
carries few annotations, and by default mypy skips the *bodies* of unannotated
functions, so scope alone buys very little.

Enabling it for `ui/` surfaces 111 findings, but they are two systemic patterns
rather than 111 mistakes:

* `QApplication.instance()` and `menuBar().addMenu()` are typed as Optional, so
  every use is a `union-attr` warning. Mechanical: assert once and reuse.
* The entry point bolts `.translator`, `.language` and `.settings` onto the
  QApplication object. No stub knows about them, and it is a real design smell —
  a small typed holder passed to the windows would fix both the warnings and the
  smell. That is the actual work here, and it is a refactor, not a lint pass.

PyQt5 ships its own `.pyi` stubs and `py.typed`, so no third-party stub package
is needed — the earlier note here claiming otherwise was wrong.

## Enable the remaining ruff rule groups

`N` (naming) will fire on the Qt-mirroring attribute names (`btnOkay`,
`edtPtmFitter`) and the `Okay` method; those are deliberate and want per-file
waivers rather than a rename. `C901` needs a threshold picked and
`take_picture_process` / `setup_ui` checked against it. `S` (bandit) and `TRY`
are probably clean already — try them and see.

## Convert `os.path` to `pathlib`

`PTH` is enabled but eight rules are waived in `pyproject.toml`. The paths are
strings on the wire (CSV rows, `.lp` lines), so the conversion has to keep
`str()` at the boundaries. Doable module by module; `core/image_data.py` and
`core/ptm_builder.py` are the bulk of it.

## Translate the manual

`docs/manual/` is English-only. The application UI is fully translated
(Korean, 44 strings), so the manual is the odd one out. `sphinx-intl` is already
in the docs extra; the workflow is the same extract/translate/compile cycle as
the `.ts` files.

## `image_data.csv` lives in the capture directory

`update_csv()` writes to `self.current_directory`, but `load_csv_data()` reads
from `self.edtDirectory.text()`. They are the same in practice because opening a
directory sets both, but nothing enforces it. Worth collapsing to one source.

## Arduino firmware is untested and unlinted

`PTMController/PTMController.ino` is outside everything above. It has no build
check in CI — `arduino-cli compile` would at least catch a syntax error before
someone flashes it. Low priority while the firmware is stable.
