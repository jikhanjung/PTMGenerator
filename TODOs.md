# TODOs

Deferred work, with enough context to pick up later. Newest first.

---

## Process status against the sibling projects

Where PTMGenerator2 stands against the process `../Modan2` and `../CTHarvester`
run. Verified 2026-07-28.

| # | Item | Status | Where it stands |
|---|---|---|---|
| 1 | Cross-platform CI matrix + headless smoke test | ✅ | 3 OS x Python 3.12, `tests/test_smoke.py`. No xvfb — Qt's offscreen plugin |
| 2 | Lint + tests gating | ✅ | ruff, mypy, the test matrix and the translation check all gate. No `\|\| true` anywhere |
| 3 | Expand the lint ruleset incrementally | ⚠️ | `E, F, I, UP, B, C4, SIM, PTH, RUF`. Missing the guide's `N`, `LOG`, `DTZ`, `TRY`, `S`, `C901` |
| 4 | `filterwarnings = error` | ✅ | `pyproject.toml`, one narrow documented ignore for PyQt5's sip shims |
| 5 | Lockfile + pip-audit + Dependabot | ✅ | 9 per-platform locks with hashes, pip-audit on all three runtime locks, `.github/dependabot.yml` |
| 6 | Coverage gate | ✅ | `--cov-fail-under=85` on the Linux leg; actual is 88% |
| 7 | Static type checking, scoped | ⚠️ | mypy gating over `core/` only. `ui/` is the open part |
| 8 | Dead-code / complexity automation | ❌ | `C901` not enabled; no complexity ceiling |
| 9 | Packaged-artifact smoke test | ⚠️ | `release.yml` checks the .exe exists and is non-empty; it does not run it |
| 10 | Property-based tests | ❌ | None. The light-vector maths is the obvious candidate |

---

## Widen mypy to `ui/`

`core/` is clean and gating. `ui/` needs PyQt5 stubs (`PyQt5-stubs`, which the
sibling projects use) and a module-at-a-time cleanup — `main_window.py` first,
then `preferences_window.py`, each one clean before it joins the `mypy` invocation
in `.github/workflows/test.yml` and `.pre-commit-config.yaml`.

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

## Run the frozen executable in CI

`release.yml` builds the .exe and checks it is non-empty. It does not start it,
so a bundle missing `icons/` or `translations/` would ship. The sibling project
solved this with a `--self-test` entry point that constructs the window, prints
a version line and exits; the same would work here and would have caught, for
example, `resource_path` regressions.

## Translate the manual

`docs/manual/` is English-only. The application UI is fully translated
(Korean, 44 strings), so the manual is the odd one out. `sphinx-intl` is already
in the docs extra; the workflow is the same extract/translate/compile cycle as
the `.ts` files.

## Property-based tests for the light geometry

`light_vectors()` has a clean invariant — every output is a unit vector, the
elevation is preserved under any azimuth adjustment, and the adjustment is a
rotation. Hypothesis over the adjustment angle would cover more than the four
fixed angles currently tested.

## `image_data.csv` lives in the capture directory

`update_csv()` writes to `self.current_directory`, but `load_csv_data()` reads
from `self.edtDirectory.text()`. They are the same in practice because opening a
directory sets both, but nothing enforces it. Worth collapsing to one source.

## Arduino firmware is untested and unlinted

`PTMController/PTMController.ino` is outside everything above. It has no build
check in CI — `arduino-cli compile` would at least catch a syntax error before
someone flashes it. Low priority while the firmware is stable.
