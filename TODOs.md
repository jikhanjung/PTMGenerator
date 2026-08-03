# TODOs

Work to do, short and medium term, with enough context to pick each one up
later. **This file is the plan**; `HANDOFF.md` is the current state, and
`devlog/` is why past changes were made the way they were.

---

## Fit a high-resolution capture — the release gate

**This is the next thing to do, and it unblocks everything below it.** Shoot a
capture on the mirrorless body at full resolution and fit it with the built-in
fitter. If the PTM comes out correct, three things follow in order: retire
`PTMfitter.exe` (phase 5, below), then release — the version stops being a
pre-release.

The hardware run of 2026-08-03 (devlog 017) verified the whole happy path on the
alpha.3 installer — Arduino, shutter, capture loop, polling, folder discovery,
and a PTM fitted in-process — but the capture was ≤24MP, which the external
fitter already handles. So the fitter is proven correct on real files and
unproven at the sizes that motivated writing it. `PTMfitter.exe` is 32-bit and
fails above roughly 24 megapixels; a 45MP body exceeds it. Until this run, the
headroom is known only from `ptm_fitter.memory_estimate` and a measured 641 MB
peak on synthetic 48MP data.

Watch memory while it runs — that is the number the estimate is guessing at.

## Finish the in-process fitter — P02 phase 5

Phases 1–4 are done: the container reader/writer (`core/ptm_format.py`), the fit
(`core/ptm_fitter.py`), streaming so memory does not scale with the capture, and
the **PTM Engine** preference that selects it — built-in by default, with
`PTMfitter.exe` still selectable. See devlog 010.

**Phase 5 — retire the external fitter.** Blocked on the capture above, and on
nothing else. `core/ptm_builder.py` then loses `generate`, the staging
directory, the codepage-encoding rules for `.lp`, the whitespace check and the
exit-code-1 quirk — most of the module. The **PTM Engine** preference goes with
it, along with the `PTMfitter.exe` path setting in the preferences dialog and
its docs. The preference is what made keeping the fallback safe; once the
built-in fitter has done the thing the external one cannot, there is nothing
left to fall back to.

**Move the fit off the UI thread.** `generate_ptm_natively` pumps the event loop
from its progress callback, which keeps the dialog responsive but is not what
the quality guide's §11 asks for. A `QThread` worker is the right shape, and is
worth doing at the same time as the capture loop, which has the same problem.

---

## Hardware verification — what is left

Every test mocks `serial.Serial`, so this list can only be worked through by
hand. The 2026-08-03 run (devlog 017) cleared the happy path; what remains is
failure handling and the installer lifecycle.

**Done 2026-08-03**, against the alpha.3 installer on the real dome: Arduino
control and the shutter, a capture loop against real camera timing, polling for
the arriving image, the dated capture folder being discovered, a PTM fitted
in-process, and the installer installing and launching.

**Not blocking the release** — a bad outcome in any of these is a confusing
dialog or a lost preference, not a capture that cannot run. Worth clearing
anyway, and the installer pair is cheap enough to do in the same sitting as the
high-resolution capture:

- **The installer's upgrade and uninstall paths** — install over the top, then
  uninstall and confirm the two locations survive separately (devlog 014 split
  them): `preferences.json` under `%LOCALAPPDATA%\PaleoBytes\PTMGenerator2` and
  the dated log under `%USERPROFILE%\PaleoBytes\PTMGenerator2\logs`. Neither is
  under the install directory, which the uninstaller removes. Check the Start
  Menu shortcut under PaleoBytes while you are there. **Most worth doing before
  a non-alpha release** — it is the first one anyone installs over an existing
  copy.
- **Serial error handling** — unplug the board mid-run, and start a capture with
  the Arduino IDE's serial monitor holding the port. Both should report which
  port and why, and offer to continue.
- **The utf-8 fallback** — open an `image_data.csv` actually written by an
  earlier build on Korean Windows, not a synthesised one.
- **PTM generation from a Korean path** — the `.lp` codepage handling was
  measured under WSL interop, not on a Korean Windows desktop. Moot once
  phase 5 deletes the codepage rules along with the external fitter.
- **The preferences migration** — against a real `%APPDATA%\PaleoBytes\
  PTMGenerator2.ini` written by 0.1.2, not a synthesised one. The serial port
  and the language are what must come across.

---

## Process status against the sibling projects

Where PTMGenerator2 stands against the process `../Modan2` and `../CTHarvester`
run. Verified 2026-07-28, after the built-in fitter and the installer (devlog
010–011); both shipped in v0.2.0-alpha.3, which is the last tag.

| # | Item | Status | Where it stands |
|---|---|---|---|
| 1 | Cross-platform CI matrix + headless smoke test | ✅ | 3 OS x Python 3.12, `tests/test_smoke.py`. No xvfb — Qt's offscreen plugin |
| 2 | Lint + tests gating | ✅ | ruff, mypy, the test matrix and the translation check all gate. No `\|\| true` anywhere |
| 3 | Expand the lint ruleset incrementally | ✅ | All of the guide's groups landed 2026-07-28: `E, F, I, N, UP, B, C4, SIM, PTH, RUF, DTZ, S, TRY, LOG, G, RET, PIE, PERF, A, C90`. Waivers argued in `pyproject.toml` |
| 4 | `filterwarnings = error` | ✅ | `pyproject.toml`, one narrow documented ignore for PyQt5's sip shims |
| 5 | Lockfile + pip-audit + Dependabot | ✅ | 9 per-platform locks with hashes, pip-audit on all three runtime locks, `.github/dependabot.yml` |
| 6 | Coverage gate | ✅ | `--cov-fail-under=85` on the Linux leg; actual is 93% across 347 tests |
| 7 | Static type checking, scoped | ✅ | mypy gates over `core/` **and** `ui/`, `check_untyped_defs` on for both (devlog 013) |
| 8 | Dead-code / complexity automation | ✅ | `C90` enforced at the guide's threshold of 15 |
| 9 | Packaged artifact + installer | ✅ | `--self-test` runs against the frozen .exe before Inno Setup packages it (`reusable_build.yml`). Signing still open |
| 10 | Property-based tests | ✅ | `tests/test_light_positions_properties.py`, hypothesis over the adjustment angle |

**Done 2026-07-28.** From the R01 audit (devlog 005–006): the serial-open crash
and the platform-default encodings, the naive-datetime DST bug, the full lint
ruleset, `--self-test`, property-based tests for the light geometry, and mypy
widened to `ui/` with body checking on for `core/`. Then (devlog 007–008): the
on-demand build workflow and the Windows icon defect it found, the first two
releases (`v0.2.0-alpha.1`, `v0.2.0-alpha.2`), the utf-8 fallback that keeps
legacy capture tables loading, and the Korean manual.

**Not doing: signed installers.** Item 9's remaining half. There is no
certificate, and an unsigned installer with a SmartScreen warning is what this
audience already downloads. Revisit if the tool is distributed outside the lab.
Now that there *is* an installer, this is the only thing between it and a
warning-free install.

**Not doing: branch protection on `main`.** The guide (§14) and Appendix A item
2 both call for it, and it is deliberately declined here. This is a
single-maintainer repository with no review partner, so requiring pull requests
buys nothing that the pre-commit hooks and the gating CI do not already provide,
and costs a PR round-trip on every one-line fix. Revisit if a second person
starts committing. Recording it so a later audit reads this as a decision
rather than an oversight.

---

## Convert `os.path` to `pathlib`

`PTH` is enabled but eleven rules are waived in `pyproject.toml`. The paths are
strings on the wire (CSV rows, `.lp` lines), so the conversion has to keep
`str()` at the boundaries. Doable module by module; `core/image_data.py` and
`core/ptm_builder.py` are the bulk of it.

## `image_data.csv` lives in the capture directory

`update_csv()` writes to `self.working_directory` (`ui/main_window.py`), but
`load_csv_data()` reads from `self.edtDirectory.text()`. Those used to be the
same folder. Since the monitored-root change (devlog 009) they are deliberately
not: the field holds the folder the user picked, and `working_directory` holds
the dated subfolder the shots actually landed in.

So reopening a capture whose images went into a subfolder reads from the parent
and finds no CSV. Worth collapsing to one source — `working_directory` is the
right one.

## Arduino firmware is untested and unlinted

`PTMController/PTMController.ino` is outside everything above. It has no build
check in CI — `arduino-cli compile` would at least catch a syntax error before
someone flashes it. Low priority while the firmware is stable.
