# R01 — Code quality audit against the shared guide

## Date: 2026-07-28

Audited against `../Modan2/docs/CODE_QUALITY_GUIDE.md` v1.0 (2026-07-23), all
fourteen sections plus Appendix A. Verified by running the checks, not by
reading the config.

## Verdict

The Appendix A checklist is in good shape — 6 of 10 done, 2 partial — because
the CI and refactor work landed the expensive items first. What the audit found
is that **the two remaining gaps are the two that actually crash the
application**, and both are in §8 and §10, the sections about the user's machine
rather than the developer's.

## Confirmed defects

### 1. An unavailable serial port kills the application (§8)

Reproduced:

```python
with patch.object(serial, "Serial", side_effect=SerialException("could not open port COM3")):
    window.ensure_serial_ready()
# CRASH: SerialException: could not open port COM3
```

`SerialController.open()` calls `serial.Serial(...)` with no guard. The
exception propagates out of the button's clicked slot, and with no
`sys.excepthook` installed PyQt5 aborts the process. No message, no log entry.

This is not a theoretical path. It happens when the Arduino is unplugged, when
the Arduino IDE's serial monitor is holding the port, when a USB port
re-enumerates to a different COM number, or when a saved port no longer exists
on a different machine. The port name is saved in preferences, so *the app is
guaranteed to try a stale port at some point.*

Ironic given the work already done here: `closeSerial`, `send` and `receive`
were all hardened against there being no port, but the one call that talks to
the OS was not.

### 2. CSV and .lp files are written in the platform's default encoding (§10)

`core/image_data.py:50,66` and `core/ptm_builder.py:51` call `open()` with no
`encoding=`. Demonstrated with a Korean specimen path:

```
bytes on disk (Linux, utf-8): b'0,/tmp/.../\xec\x82\xbc\xec\x97\xbd\xec\xb6\xa9_...'
decoded as cp949 (Korean Windows default): FAILED, illegal multibyte sequence
```

`image_data.csv` is written into the capture directory and read back to reopen a
session, so a run captured on one machine and reopened on another with a
different locale cannot be read. The `.lp` file has the same problem and is
handed to PTMfitter, which will not find an image whose path it cannot decode.

This is the specific defect the guide records from Modan2 ("strict-utf-8 readers
failing on non-ASCII specimen names"), and the domain here — Korean specimen and
directory names — makes it likely rather than hypothetical.

### 3. Naive datetimes in interval detection (§1, DTZ006)

`core/image_data.py:94` converts two float timestamps to naive `datetime`,
subtracts them, and takes `total_seconds()`. Across a DST transition the
difference is wrong by an hour, which would make `detect_irregular_intervals`
read a normal gap as several missed shots and insert phantom placeholder slots.

The conversion earns nothing: `second - first` on the raw timestamps is the same
number, always. Deleting the datetime round-trip removes the rule violation and
the bug together.

## Lint ruleset (§1)

Currently `E, F, I, UP, B, C4, SIM, PTH, RUF`. Violations in the groups the
guide names but this project has not adopted:

| Group | Count | Notes |
|---|---:|---|
| `TRY`, `LOG`, `G`, `RET`, `PIE`, `RUF012`, `C901` | **0** | Free — enable now |
| `DTZ` | 3 | Two are defect 3 above; one is `date.today()` in `bump_version.py` |
| `N` | 4 | Three are the deliberate Qt camelCase; one real (`PtmFitterNotFound` wants an `Error` suffix) |
| `PERF` | 1 | A loop that should be `list.extend` |
| `A` | 1 | `copyright` in `docs/manual/conf.py`, which Sphinx requires |
| `S` | 165 | **162 are `S101` (assert) in tests** — the standard per-file waiver. Only 2 real, both on the PTMfitter subprocess call |

So the honest number is: seven groups are already clean, and the rest is about
ten real findings.

`C901` is clean at the default threshold of 10 — worth recording, because before
the core/ui split `take_picture_process` and `setup_ui` were both well over it.
`setup_ui` is still 98 lines but is straight-line widget construction, which
mccabe correctly does not count as complex.

## Section-by-section

| § | Topic | Status |
|---|---|---|
| 1 | Formatting & linting | ⚠️ ruff pinned and gating; seven zero-violation groups unadopted |
| 2 | Type checking | ⚠️ mypy gating over `core/`; `ui/` not covered |
| 3 | Testing strategy | ⚠️ Layered and marked; **no property-based tests** |
| 4 | Coverage | ✅ 88%, gate at 85% on the reference leg |
| 5 | Cross-platform CI | ✅ 3 OS, smoke test, all gating, no `\|\| true` |
| 6 | Dependencies | ✅ 9 per-platform locks with hashes, pip-audit, Dependabot, tooling pinned |
| 7 | Packaging & release | ⚠️ Built in CI; **artifact is not launched**, not signed |
| 8 | Runtime robustness | ❌ **No excepthook, no slot guards** — defect 1 |
| 9 | Resource management | ✅ Files context-managed except the documented log handle; widgets closed in fixtures |
| 10 | i18n & encoding | ❌ **No `encoding=` anywhere** — defect 2. UI translation itself is complete (44 strings) |
| 11 | Performance | ➖ No benchmarks. The workload is I/O-bound on a 1 Hz timer; not worth instrumenting |
| 12 | Security | ✅ No eval/exec/pickle/yaml. The subprocess call takes a user-configured path with no shell |
| 13 | Dead code & complexity | ✅ `C901` clean; the dead code found in R00 was deleted |
| 14 | Workflow & gating | ✅ pre-commit and CI gating. Branch protection is off by decision, not omission — see `TODOs.md` |

## Appendix A checklist

1. ✅ Cross-platform CI + headless smoke test
2. ✅ Lint + tests gating — CI gates; branch protection deliberately declined (single maintainer)
3. ⚠️ Expand the lint ruleset — seven groups are free
4. ✅ `filterwarnings = error`
5. ✅ Lockfile + pip-audit + Dependabot
6. ✅ Coverage gate
7. ⚠️ Static type checking, scoped — `core/` only
8. ✅ Dead-code / complexity automation
9. ⚠️ Packaged-artifact smoke test — builds, does not launch
10. ❌ Property-based tests

## Proposed order

Highest leverage first, and deliberately not in checklist order — the two crashes
come before any amount of linting.

1. **Guard the serial open, and install a `sys.excepthook`.** The hook is the
   backstop; the guard is the fix. Both with regression tests.
2. **`encoding="utf-8"` on every `open()`**, and read the CSV with `utf-8-sig`
   so a BOM-prefixed file written by a spreadsheet still loads. Regression test
   with a Korean path.
3. **Delete the datetime round-trip** in interval detection.
4. **Enable the seven zero-violation rule groups** plus `DTZ`, `PERF`, `N` with
   the Qt waivers argued in config and `S` with the tests waiver. One commit,
   no behaviour change.
5. ~~**Turn on branch protection** for `main`.~~ Declined 2026-07-28: single
   maintainer, no review partner, so required PRs cost a round-trip per one-line
   fix and add nothing over the pre-commit hooks and the gating CI. See
   `TODOs.md`. Revisit if a second person starts committing.
6. **Launch the frozen executable in CI** — a `--self-test` flag that builds the
   window offscreen, prints the version and exits. Catches a bundle missing
   `icons/` or `translations/`, which source tests cannot.
7. **Property-based tests** for `light_vectors()` — the unit-vector and rotation
   invariants hold for any angle, so hypothesis covers more than four fixed ones.
8. **Widen mypy to `ui/`**.

Items 6–8 are already in `TODOs.md`; 1–5 are new and are added there.
