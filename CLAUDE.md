# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Project overview

PTMGenerator2 automates Polynomial Texture Mapping capture for artefact
documentation. An Arduino-driven dome lights 50 LEDs one at a time and fires a
DSLR shutter for each; the application drives that over serial, waits for each
photo to land on disk, builds the light-position (`.lp`) file, and hands
everything to the fitter — built in by default, `PTMfitter.exe` if asked.

The shipped artifact is a per-user Windows installer built with Inno Setup. The
Arduino firmware in `PTMController/` is a separate concern, flashed with the
Arduino IDE.

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
| `core/ptm_builder.py` | `.lp` content, and which fitter runs |
| `core/ptm_fitter.py` | The built-in least-squares fit, streaming so memory does not scale with the capture |
| `core/ptm_format.py` | Reading and writing the PTM 1.2 container |
| `core/resources.py` | Bundled-file lookup, frozen or not |
| `core/self_test.py` | What `--self-test` checks: icons, translations, the light table |
| `core/settings.py` | Preference keys, defaults, coercion |
| `core/preferences.py` | The JSON store, and migration from the old QSettings `.ini` |
| `core/paths.py` | `~/PaleoBytes/PTMGenerator2` — preferences and dated logs |
| `ui/geometry.py` | QRect ↔ `[x, y, w, h]`, because JSON cannot hold a QRect |
| `ui/main_window.py` | Widgets, the one-second timer, rendering what the session decides |
| `ui/preferences_window.py` | The Edit > Preferences dialog |
| `ui/error_handling.py` | The `sys.excepthook` backstop |
| `PTMGenerator2.py` | Entry point. `--self-test` checks the bundle and exits |
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
make test            # 331 tests, ~6s, no display needed
make test-cov        # with a coverage report
make lint            # ruff check + ruff format --check
make type-check      # mypy over core/ and ui/
make run             # run the application
make build           # PyInstaller -> dist/PTMGenerator2/PTMGenerator2.exe
make translations    # pylupdate5 extract + pyside6-lrelease compile (the UI)
make docs            # the manual, English and Korean
make docs-i18n       # re-extract strings into the Korean manual catalogues
make lock            # regenerate the per-platform lockfiles
```

Check a Windows build without releasing: `gh workflow run build.yml`. That is
also the only way to build the installer — Inno Setup is Windows-only, so
`installer/PTMGenerator2.iss.template` cannot be exercised locally on Linux. The
tests in `tests/test_packaging.py` check it against the spec instead.

Tests select Qt's offscreen platform plugin themselves, so **no xvfb is needed**
and none should be added.

## Conventions

- **The installer's `AppId` must never change.** Inno keys upgrade detection,
  the Add/Remove Programs entry and `{app}` off it, so a new one makes every
  existing installation invisible to the installer and leaves it behind.
- **Never edit `version.py` by hand.** Use `python scripts/bump_version.py
  <part>`; it rolls `CHANGELOG.md`, commits and tags. See `VERSION_MANAGEMENT.md`.
- **ruff is pinned to an exact version** in three places that must move
  together: `pyproject.toml`, `.pre-commit-config.yaml`, and the dev lockfiles
  (`make lock`). CI installs from the lockfile rather than naming a version.
- **`.qm` files are committed** and PyInstaller bundles them. Editing a `.ts`
  without running `make translations` ships stale strings; CI checks for drift.
- **Qt-mirroring attribute names** (`btnOkay`, `edtPtmFitter`, `Okay`) are
  deliberate. Do not rename them to snake_case.
- **Every entry in `core.resources.ICON` must exist on disk.** `core/self_test.py`
  checks them. `QIcon()` on a missing path yields a null icon rather than
  raising, so a typo here is invisible until someone looks at the window.
- **The `›` in "Edit › Preferences"** is U+203A and is the key the `.ts` files
  are indexed on. Changing it orphans the Korean translation.
- Four documents, four jobs. Keep them apart or they drift into each other:
  `HANDOFF.md` is the **current state** (where things stand, what is in flight);
  `TODOs.md` is the **plan** (work to do, with enough context to resume);
  `devlog/` is the **record** (why a past change was made that way, including
  what was rejected); `CHANGELOG.md` is what **shipped**.
- Add a `devlog/` entry per piece of work, and check at each release cycle that
  none is missing — they have been forgotten before, when work spanned several
  commits. See `devlog/README.md`.

## Gotchas

- **Everything the application writes outside the capture folder goes to
  `core.paths.data_dir()`** — `~/PaleoBytes/PTMGenerator2`, which is
  `%USERPROFILE%\PaleoBytes\PTMGenerator2` on Windows. Never under the install
  directory: the installer deletes that on uninstall. `PTMGENERATOR2_DATA_DIR`
  redirects it, which is how the suite stays out of the developer's real data —
  a script that builds a window without setting it will write there, and this
  has happened.
- **`initialize_variables()` replaces `sys.stdout`** with an `OutputRedirector`
  appending to `logs/PTMGenerator2_<YYYYMMDD>.log`. One file per day, opened
  in append mode. Tests restore stdout — see `tests/conftest.py`.
- **Preferences are JSON, not QSettings.** `core.preferences.Preferences` keeps
  the QSettings method names (`value`, `setValue`, `sync`) so `core/settings.py`
  and both windows are unchanged, but a key containing `/` nests and types
  survive the round trip. A QRect cannot be stored — `ui/geometry.py` converts.
  An old `.ini` is imported on first run and left in place.
- **A QApplication must outlive its widgets.** PyQt5 destroys it as soon as the
  last Python reference goes, so the `qapp` fixture is session-scoped.
- **`app.translator` and `app.language`** are attached to the QApplication by the
  entry point, and `read_settings()` expects them to exist.
- **`detect_irregular_intervals`** rebuilds a capture table from files on disk;
  the name is historical and kept because it is referenced from the docs.
- **A new dependency in `core/` is a new dependency of the documentation.**
  `docs/manual/api.rst` autodocs `core/`, autodoc imports what it documents, and
  the docs build runs with `-W`. Adding an import to `core/` without adding it
  to `docs/manual/requirements.txt` fails the Documentation workflow, not the
  tests. This has happened (devlog 010).
- **`check_untyped_defs` is on for both `core/` and `ui/`.** Without it mypy
  skips the bodies of unannotated functions, and this code carries few
  annotations — a clean run would mean almost nothing. Keep it on.
- **Do not shadow a Qt method with an attribute.** `self.statusBar`,
  `self.layout` and `self.parent` all did; each hid an inherited method that
  would then raise `TypeError` if anyone called it. They are `status_bar`,
  `form_layout` and gone respectively. This is not the same as the deliberate
  Qt-mirroring names below, which shadow nothing.
- **`sys.excepthook` is installed by the entry point** (`ui/error_handling.py`).
  An exception escaping a Qt slot otherwise aborts the process silently.

## Release

1. Describe the change under `## [Unreleased]` in `CHANGELOG.md`.
2. `python scripts/bump_version.py patch` (or `minor`, `preminor beta`, …).
3. `git push && git push origin v<version>`.

Run `gh workflow run build.yml` first if anything touching the executable
changed. The build has failed on Windows for a reason Linux could not see
(devlog 007), and a failure during a release leaves the tag already pushed.

`release.yml` refuses the tag if it disagrees with `version.py`, gates on the
full test matrix, builds the Windows executable, and publishes a release whose
notes come from the matching `CHANGELOG.md` section.
