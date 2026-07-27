# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Project overview

PTMGenerator2 automates Polynomial Texture Mapping capture for artefact
documentation. An Arduino-driven dome lights 50 LEDs one at a time and fires a
DSLR shutter for each; the application drives that over serial, waits for each
photo to land on disk, builds the light-position (`.lp`) file, and hands
everything to `PTMfitter.exe`.

The shipped artifact is a single Windows executable. The Arduino firmware in
`PTMController/` is a separate concern, flashed with the Arduino IDE.

## Architecture

The boundary that matters is `core/` vs `ui/`. **`core/` imports no PyQt5**, and
`tests/test_smoke.py` asserts that in a subprocess. Keep it that way — it is what
makes the capture policy, the serial protocol and the file formats testable
without a display, a QApplication or a controller attached.

| Module | Responsibility |
|---|---|
| `core/serial_controller.py` | `<ON,n>` / `<SHOOT,n>` / `<OFF>` framing, 9600 baud, port lifecycle. Every method tolerates there being no port |
| `core/capture_session.py` | Sequencing: preparation, polling, retakes, giving up. Takes the shutter and the file poll as arguments |
| `core/light_positions.py` | `POLAR_LIGHT_LIST` (measured off the rig) to unit vectors |
| `core/image_data.py` | `CaptureSlot`, `image_data.csv`, rebuilding a table from a directory, polling for a new file |
| `core/ptm_builder.py` | `.lp` content, and running PTMfitter |
| `core/resources.py` | Bundled-file lookup, frozen or not |
| `core/settings.py` | Preference keys, defaults, coercion from QSettings strings |
| `ui/main_window.py` | Widgets, the one-second timer, rendering what the session decides |
| `ui/preferences_window.py` | The Edit > Preferences dialog |
| `PTMGenerator2.py` | Entry point |
| `version.py` | **Single source of truth for the version** |

### The capture loop

`ui.main_window.take_picture_process` is the timer tick. It asks the session
what to do and renders the result; it decides nothing itself:

```python
result = session.step(shoot=self.serial.shoot, poll=self.poll_for_image)
```

`CaptureSession` walks `idle -> preparing -> polling -> (recorded | retake)` per
slot and finishes when the queue drains. To test capture behaviour, drive
`CaptureSession` directly with fakes — do not construct a window and wait out
real one-second ticks.

### Missing shots

A shot that never arrives is recorded as `CaptureSlot(i, "-", "-", False)`. That
keeps the LED index aligned with `light_vectors()`, so a partial run still
produces a correct `.lp`. Do not compact the list.

## Commands

```bash
make install-dev     # dependencies + pre-commit hooks
make test            # 125 tests, ~1.3s, no display needed
make test-cov        # with a coverage report
make lint            # ruff check + ruff format --check
make type-check      # mypy over core/
make run             # run the application
make build           # PyInstaller -> dist/PTMGenerator2_v<version>_<date>.exe
make translations    # pylupdate5 extract + pyside6-lrelease compile
make lock            # regenerate the per-platform lockfiles
```

Tests select Qt's offscreen platform plugin themselves, so **no xvfb is needed**
and none should be added.

## Conventions

- **Never edit `version.py` by hand.** Use `python scripts/bump_version.py
  <part>`; it rolls `CHANGELOG.md`, commits and tags. See `VERSION_MANAGEMENT.md`.
- **ruff is pinned to an exact version** in three places that must move
  together: `pyproject.toml`, `.pre-commit-config.yaml`, and the lint job in
  `.github/workflows/test.yml`.
- **`.qm` files are committed** and PyInstaller bundles them. Editing a `.ts`
  without running `make translations` ships stale strings; CI checks for drift.
- **Qt-mirroring attribute names** (`btnOkay`, `edtPtmFitter`, `Okay`) are
  deliberate. Do not rename them to snake_case.
- **The `›` in "Edit › Preferences"** is U+203A and is the key the `.ts` files
  are indexed on. Changing it orphans the Korean translation.
- Record deferred work in `TODOs.md`, and add a `devlog/` entry when the
  reasoning behind a change would not be obvious later. See `devlog/README.md`.

## Gotchas

- **`initialize_variables()` replaces `sys.stdout`** with an `OutputRedirector`
  writing `output.log` in the current directory. Tests that build a window run
  in a temp cwd and restore stdout — see `tests/conftest.py`.
- **QSettings is global.** Tests redirect it per test with `QSettings.setPath`.
  Any script that constructs a window will otherwise write to the developer's
  real preferences; this has happened.
- **A QApplication must outlive its widgets.** PyQt5 destroys it as soon as the
  last Python reference goes, so the `qapp` fixture is session-scoped.
- **`app.translator` and `app.language`** are attached to the QApplication by the
  entry point, and `read_settings()` expects them to exist.
- **`detect_irregular_intervals`** rebuilds a capture table from files on disk;
  the name is historical and kept because it is referenced from the docs.

## Release

1. Describe the change under `## [Unreleased]` in `CHANGELOG.md`.
2. `python scripts/bump_version.py patch` (or `minor`, `preminor beta`, …).
3. `git push && git push origin v<version>`.

`release.yml` refuses the tag if it disagrees with `version.py`, gates on the
full test matrix, builds the Windows executable, and publishes a release whose
notes come from the matching `CHANGELOG.md` section.
