# PTMGenerator2

A desktop application for automated Polynomial Texture Mapping (PTM) image capture and generation.

**Manual:** [English](https://jikhanjung.github.io/PTMGenerator/en/) ·
[한국어](https://jikhanjung.github.io/PTMGenerator/ko/) — built from
`docs/manual/` and published on every push to `main`.

## Overview

PTMGenerator2 is a PyQt5-based tool designed for archaeological artifact documentation using Polynomial Texture Mapping (PTM) technology. The application automates the process of capturing multiple images under different lighting angles and generates PTM files that can reveal surface details invisible under normal lighting conditions.

An Arduino-driven dome lights 50 LEDs one at a time and fires a DSLR shutter for each one. The application drives that sequence over a serial link, waits for each photo to land on disk, builds the light-position (`.lp`) file, and hands everything to `PTMfitter.exe` to produce the final `.ptm`.

```
  PTMGenerator2.py  ──serial (9600 8N1)──▶  Arduino + 7× 74HC595  ──▶  50 LEDs
        │                                            │
        │                                            └──▶  DSLR shutter
        │
        └── polls the capture directory for the new image file
                                │
                                ▼
                   writes <dirname>.lp  ──▶  PTMfitter.exe -i x.lp -o x.ptm
```

## Features

- **Automated Image Capture**: Control DSLR cameras via Arduino-based LED dome systems
- **Serial Communication**: Coordinate lighting and camera triggering through serial protocol
- **Intelligent Polling**: Automatic detection of newly captured images with retry logic
- **Image Management**: Track, preview, and selectively include/exclude images for PTM generation
- **Multi-language Support**: Available in English and Korean (한국어)
- **PTM Generation**: Create PTM files using the integrated PTMfitter engine

## Requirements

### Software Dependencies

- Python 3.12+
- PyQt5, pyserial, semver — declared in `pyproject.toml`

```bash
pip install -e .            # runtime
pip install -e ".[dev]"     # plus the test and lint tooling
```

To reproduce a build exactly, install from the lockfile for your platform
instead: `pip install --require-hashes -r requirements-linux.lock`.

Windows in practice — `PTMfitter.exe` is a Windows binary and the DSLR tethering
software that drops files into the capture directory is Windows-only. The Python
code itself has no Windows-specific imports and the GUI runs on Linux.

### Hardware Requirements

- DSLR camera with remote shutter capability
- Arduino-based LED dome controller
- Serial connection to Arduino (USB or Bluetooth)

### External Tools

- PTMfitter executable (`ptmfitter.exe`) - Configure path in Preferences

## Installation

1. Clone or download this repository
2. Install dependencies: `pip install -e .`
3. Ensure `ptmfitter.exe` is available (configure path in application preferences)
4. Connect your Arduino LED dome controller via serial port

## Repository layout

| Path | Purpose |
| --- | --- |
| `PTMGenerator2.py` | Entry point. `--self-test` starts headlessly, checks the bundle and exits. |
| `core/` | **Qt-free logic**: serial protocol, capture sequencing, dome geometry, the CSV and `.lp` formats. Imports no PyQt5 — asserted by the test suite. |
| `ui/` | The PyQt5 windows that drive it. |
| `version.py` | Single source of truth for the version. |
| `PTMController/PTMController.ino` | Arduino firmware: shift-register LED driver, shutter, rotary encoder, 7-segment display. |
| `PTMfitter.exe` | Third-party PTM fitter binary invoked by **Generate PTM**. |
| `translations/` | Qt i18n — English and Korean (`.ts` sources, `.qm` compiled). |
| `icons/` | Application icon. |
| `tests/` | pytest suite — no display required. |
| `scripts/bump_version.py` | Version bump, changelog roll, commit and tag. |
| `docs/manual/` | The Sphinx manual published to GitHub Pages. |
| `PTMGenerator2.spec` | PyInstaller build spec. |
| `devlog/`, `TODOs.md` | Design notes and deferred work. |
| `legacy/` | Superseded code, kept for reference only — see below. |

## Usage

### Running the Application

```bash
python PTMGenerator2.py
```

### Basic Workflow

1. **Configure Settings** (Edit → Preferences):
   - Select serial port for Arduino communication
   - Set PTM fitter executable path
   - Configure number of LEDs (default: 50)
   - Adjust retry count and polling delays as needed

2. **Open Working Directory** (File → Open Directory):
   - Choose a folder where captured images will be stored
   - The application will create an `image_data.csv` file to track captures

3. **Test Shot**:
   - Click "Test Shot" to verify camera and LED communication
   - Check that images appear in the working directory

4. **Capture All Images**:
   - Click "Take All Pictures" to begin automated capture sequence
   - The application will cycle through all LED positions
   - Use "Pause/Continue" to temporarily halt the process
   - Use "Stop" to abort the sequence

5. **Review Images**:
   - Select images in the table to preview them
   - Uncheck any images you want to exclude from PTM generation
   - Use "Retake Picture" to recapture selected images

6. **Generate PTM**:
   - Click "Generate PTM" when all images are captured
   - Choose output location and filename
   - The application will create the PTM file using PTMfitter

### Capture sequence internals

For each LED index *i*:

1. Send `<SHOOT,i+1>` over serial — the Arduino turns on LED *i+1* and triggers the shutter.
2. Wait `preparation_time` (2 s), then poll the capture directory for a file newer than the last checkpoint.
3. If nothing arrives within `polling_timeout` (5 s), retake up to `RetryCount` times. After that the slot is recorded as `-` and the run moves on.
4. Show the captured image, record it, advance to the next LED.

When the run finishes, **Generate PTM** converts the LED table (`POLAR_LIGHT_LIST`, polar `[theta, phi]` degrees) into unit light vectors, writes the `.lp` file next to the images, and runs the fitter.

## Configuration Files

- **image_data.csv**: Auto-generated file tracking captured images (format: index, directory, filename, include)
- **{project}.lp**: Light position file generated during PTM creation
- **Settings**: Stored in system-specific location (Windows: `%APPDATA%/PaleoBytes/PTMGenerator2.ini`)

### Preferences reference

Stored via `QSettings` under `PaleoBytes / PTMGenerator2`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `serial_port` | *(none)* | COM port of the Arduino controller. Must be set before capturing. |
| `ptm_fitter` | `ptmfitter.exe` | Path to the PTM fitter executable. |
| `Number_of_LEDs` | 50 | Number of shots in a full sequence. |
| `RetryCount` | 3 | Automatic retakes before a slot is given up as `-`. |
| `light_position_adjustment` | 0 | Azimuth offset in degrees, to align the dome's LED #1 with the specimen's orientation. |
| `post_shutter_polling` | 1.0 | Seconds to wait after the shutter before scanning for the new file. |
| `language` | `en` | `en` or `ko`. |

## Building Executable

Releases are built with PyInstaller:

```bash
pyinstaller PTMGenerator2.spec
```

The output name is generated from `__version__` in `version.py` plus the build
date — e.g. `PTMGenerator2_v0.1.2_20251107.exe` — so there is no second version
number to keep in step. Bump with `python scripts/bump_version.py <part>`; see
`VERSION_MANAGEMENT.md`.

Check a build before shipping it:

```bash
dist/PTMGenerator2_v0.1.2_20260728.exe --self-test
```

It starts the application headlessly, verifies every bundled icon and
translation resolves, constructs the main window and exits non-zero if anything
is missing. `release.yml` runs it against every build.

`build/` and `dist/` are gitignored; the spec is build configuration and is tracked.

## Arduino Protocol

Firmware in `PTMController/PTMController.ino`. 9600 baud. The PC sends messages
framed with `<` and `>`, comma-separated:

| Message | Effect |
| --- | --- |
| `<ON,n>` | Turn on LED *n* (1-based), all others off. |
| `<SHOOT,n>` | Turn on LED *n* and trigger the shutter. |
| `<OFF>` | Turn all LEDs off. Sent when the serial port closes. |

LED numbers are 1-based (1-50 for the default configuration). The Arduino echoes
human-readable status lines back (`Turn on LED #n`, `Shooting with LED #n turned
on.`) — informational only; the app does not parse them.

### Pinout

| Signal | Arduino pin |
| --- | --- |
| `SER` (74HC595 pin 14) | 8 |
| `RCLK` (74HC595 pin 12) | 9 |
| `SRCLK` (74HC595 pin 11) | 10 |
| Shutter | 19 |

Seven daisy-chained 74HC595 shift registers give 56 outputs, of which 50 drive the
LEDs. The remaining pins run a 7-segment display showing the current LED index. A
rotary encoder with a push button allows manual LED selection and manual shooting
without the PC.

## Translations

Translating is three steps: extract the strings from the source into the `.ts`
files, translate them, then compile the `.ts` files into the binary `.qm` files
the application actually loads at runtime.

```bash
# 1. extract — merges new strings, keeps existing translations
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ko.ts translations/PTMGenerator2_en.ts

# 2. translate — Qt Linguist, or edit the .ts XML directly
linguist translations/PTMGenerator2_ko.ts

# 3. compile — without this the UI still shows the old strings
pyside6-lrelease translations/PTMGenerator2_ko.ts translations/PTMGenerator2_en.ts
```

`pylupdate5` comes with PyQt5. `lrelease` does not: it ships with the Qt
developer tools, so the `dev` extra in `pyproject.toml` pulls in
`PySide6-Essentials`, which provides it as `pyside6-lrelease`
(`sudo apt install qttools5-dev-tools` gives a plain `lrelease` instead, if you
prefer the system package).

Both `.ts` and `.qm` are tracked — the `.qm` files are what PyInstaller bundles,
so they must be recompiled and committed whenever a translation changes.

## Tests

```bash
make test          # or: pytest tests/
make test-cov      # with a coverage report
```

Requires PyQt5 but no display: the suite selects Qt's `offscreen` platform
plugin, so it runs over SSH and in CI as-is. QSettings is redirected to a
temporary directory per test, so running the suite never touches your real
preferences.

## Troubleshooting

### No serial port detected
- Ensure Arduino is connected and drivers are installed
- Check Device Manager (Windows) or `ls /dev/tty*` (Linux/Mac)
- Install CH340 drivers if using CH340-based Arduino clones

Starting a capture with no port configured asks whether to continue. Cancelling
is the default, since without the controller the LEDs and shutter are never
triggered and every slot would time out. Continuing anyway is there for trying
out the interface without hardware attached.

### Images not detected
- Increase "Post Shutter Polling" delay in Preferences
- Check camera is set to save images to the working directory
- Verify supported image formats: PNG, JPG, JPEG, GIF, BMP, TIFF

### Missing images in sequence
- The application will insert placeholder entries for gaps
- Use "Retake Picture" to recapture specific positions
- Check `image_data.csv` to see which positions failed

### PTM generation fails
- Verify PTMfitter executable path in Preferences
- Ensure all required images are present and checked
- Check that filenames don't contain special characters

### Whole files show as modified with no real changes
Line endings are normalized by `.gitattributes` (LF in the repository). If phantom
whole-file diffs appear, run `git add --renormalize .`.

## Legacy code

`legacy/` holds superseded implementations, kept only for reference. They are not
maintained and are not part of the build:

- `legacy/PTMGenerator.py` — the original Tkinter application (needs `Pillow` and `pywin32`).
- `legacy/ptmgenerator2_1.py` — an early snapshot of PTMGenerator2 (v0.1.0).
- `legacy/setup.py` — cx_Freeze build script for the Tkinter app.

## Version History

- **v0.1.2** (2025-11-07): Latest stable release
  - Improved polling behavior
  - Better directory handling
  - Image selection feature

## License

[License information not specified]

## Credits

Developed by PaleoBytes
