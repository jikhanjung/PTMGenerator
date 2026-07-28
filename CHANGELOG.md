# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Fixed
- **PTM generation no longer breaks on a path containing a space or Hangul.**
  The `.lp` file listed absolute paths, and PTMfitter splits each line on
  whitespace, so a space in the path was read as a light coordinate. It also
  reads the file in the machine's ANSI codepage rather than UTF-8. The `.lp`
  now lists bare filenames, is written in that codepage, and the fitter runs in
  the image folder; the `.ptm` is moved to wherever you asked for it afterwards.
  Measured against the shipped `PTMfitter.exe` — see `core/ptm_builder.py`.
- **A failed fit is reported.** PTMfitter exits 1 on success, so its status
  cannot be used; the application now checks that a `.ptm` actually appeared
  and says so when it did not, instead of reporting success.

### Changed
- **The chosen folder is now watched recursively until the first shot lands.**
  Tethering software commonly files images into a dated subfolder that does not
  exist before the day's first shot, so the only folder you could pick was the
  parent — and shots landing one level down were never seen. Whichever folder
  the first shot arrives in becomes the working folder for that run, and
  `image_data.csv` is written there. Later polls look only in that folder, so
  a root holding many dated folders costs nothing per poll. A new run
  rediscovers it, so a session started after midnight does not keep writing
  into yesterday's folder. Both folders are shown: the field at the top is what
  is being watched, and the line above the capture list is where shots are
  going.

## [0.2.0-alpha.2] - 2026-07-28
### Added
- **The manual is available in Korean**, at
  <https://jikhanjung.github.io/PTMGenerator/ko/>, with a language switcher on
  every page that keeps you on the page you were reading. The API reference and
  the changelog stay in English — see `docs/manual/locale/README.md` for why.

## [0.2.0-alpha.1] - 2026-07-28
### Added
- **The manual is published at <https://jikhanjung.github.io/PTMGenerator/>**,
  rebuilt on every push.
- **`--self-test`.** Starts the application headlessly, verifies every bundled
  icon and translation resolves, and exits non-zero if anything is missing. Run
  against the executable in CI before a release is published.
- **A global exception handler.** An error inside a button handler used to abort
  the application silently; it now logs to `output.log` and shows a dialog.
- **The project now has a test suite, CI and a release process.** `tests/` runs
  under pytest with no display required (Qt's offscreen platform), covering the
  serial protocol, the capture state machine, the light geometry, the CSV and
  `.lp` formats and the windows themselves.
- **`version.py` is the single source of truth for the version.** The window
  title, `pyproject.toml`, the PyInstaller spec's output filename and the
  release workflow's tag check all read it. Bump it with
  `python scripts/bump_version.py <part>`; see `VERSION_MANAGEMENT.md`.
- Prompt before starting a capture with no controller attached, offering to
  continue anyway for trying the interface out without hardware.
- `.gitattributes`, so line endings are normalized on check-in.

### Changed
- **The application is split into `core/` and `ui/`.** `core/` holds the
  serial protocol, capture sequencing, dome geometry and file formats and
  imports no PyQt5, so it is testable without a display or a controller; `ui/`
  holds the two windows. `PTMGenerator2.py` is now an entry point.
- One build spec, `PTMGenerator2.spec`, replacing the six near-identical
  versioned copies. It derives the output name from `version.py`.
- Image extensions are matched from one shared list. Polling accepted `.gif`
  and `.bmp` and matched case-insensitively while rebuilding a table from a
  directory did neither, so a run containing `.JPG` files could not be reopened.
- Superseded implementations moved to `legacy/`.

### Fixed
- **Crash when the configured serial port cannot be opened.** The port name is
  saved in preferences, so an unplugged board, a port held by the Arduino IDE,
  or a re-enumerated USB device aborted the application with no message. It now
  reports which port and why, and offers to continue without it.
- **`image_data.csv` and `.lp` files are written as UTF-8.** They were written
  in the platform's default encoding, so a run captured on Korean Windows could
  not be reopened on Linux, and vice versa.

  *Existing captures keep working.* Reading falls back through utf-8-sig →
  cp949 → latin-1, so a table written by an earlier version still loads,
  including one with Korean names written on Korean Windows. It is rewritten as
  UTF-8 the next time the run is saved. A file re-saved by a spreadsheet, which
  adds a byte-order mark, also loads.
- **Interval detection no longer miscounts across a daylight-saving change.**
  It compared naive local datetimes, so a gap spanning the transition read as
  hundreds of missed shots.
- **The Open Directory button's missing icon.** It referenced a file that has
  never existed in the repository; `QIcon()` fails silently on a missing path,
  so it rendered blank from the first release.
- **Crash when no serial port is configured.** Pressing Stop — and several
  other paths — reached for a serial object that was never created, raising
  `AttributeError`.
- **Crash on Retake Picture before any row had been selected.**
- Post Shutter Polling accepts fractional seconds; an integer validator had
  made the default of `1.0` impossible to edit.
- Switching language relabelled every preference row except Post Shutter
  Polling and Light Position Adjustment.
- Korean translations for the eight strings that were still falling back to
  English, and the compiled `.qm` files regenerated.

### Removed
- `interval.py`, a prototype that could not be imported or run: it executed at
  module level against a hardcoded desktop path and unpacked three return
  values into two. Its working successor lives in `core/image_data.py`.

---

## [0.1.2] - 2025-11-07

### Added
- Image selection: each captured shot can be included or excluded from PTM
  generation from the capture table.

### Changed
- Improved polling behaviour when waiting for a shot to land.
- Better directory handling.

## [0.1.1] - 2024-12-27

### Changed
- Directory handling.
- Light position adjusted; polling sleeps one second between checks.

## [0.1.0] - 2024-06-27

First packaged release of the PyQt5 rewrite: serial control of the LED dome,
automated capture with retries, `.lp` generation and PTM creation via
PTMfitter, and English/Korean interface.
