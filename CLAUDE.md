# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PTMGenerator2 is a PyQt5-based desktop application for automated Polynomial Texture Mapping (PTM) image capture and generation. The application controls a DSLR camera via serial communication with an Arduino-based LED dome, capturing images under different lighting angles to create PTM files for archaeological artifact documentation.

## Core Architecture

### Main Application (`PTMGenerator2.py`)

- **PTMGeneratorMainWindow**: Main application window managing the entire workflow
  - Image capture sequencing with 50 LED positions (configurable)
  - Serial communication with Arduino controller for LED/camera control
  - Image polling and validation with automatic retry logic
  - CSV-based image tracking with include/exclude checkboxes
  - PTM file generation via external `ptmfitter.exe` executable

- **PreferencesWindow**: Settings dialog for configuration
  - Serial port selection
  - PTM fitter executable path
  - Number of LEDs, retry count, polling delays
  - Light position adjustment (angular offset)
  - Multi-language support (English, Korean)

### Key Components

- **Serial Communication**: Controls Arduino via serial protocol with `<COMMAND>` format
  - `ON,{led_index}`: Turn on specific LED
  - `SHOOT,{led_index}`: Trigger camera shutter
  - `OFF`: Turn off all LEDs

- **Image Polling**: Monitors directory for new image files after shutter trigger
  - Configurable post-shutter polling delay (default 1 second)
  - Timeout-based failure detection (5 seconds default)
  - Automatic retry with configurable maximum attempts

- **Light Positions**: `POLAR_LIGHT_LIST` defines 50 dome positions as (theta, phi) polar coordinates
  - Converted to Cartesian (x,y,z) for PTM generation
  - Adjustable angular offset for dome alignment corrections

## Development Commands

### Running the Application

```bash
python PTMGenerator2.py
```

### Running Tests

```bash
python test_PTMGenerator2.py
```

### Building Executable (Windows)

```bash
pyinstaller --name "PTMGenerator2_v{VERSION}_{DATE}.exe" --onefile --noconsole \
  --add-data "icons/*.png;icons" \
  --add-data "translations/*.qm;translations" \
  --icon="icons/PTMGenerator2.png" \
  PTMGenerator2.py
```

### Translation Workflow

```bash
# Extract translatable strings to .ts files
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_en.ts
pylupdate5 PTMGenerator2.py -ts translations/PTMGenerator2_ko.ts

# Edit translations with Qt Linguist
linguist

# Compile .ts to .qm files (done automatically by linguist)
```

## Application State Machine

The image capture process uses a state-based timer (`take_picture_process`):

1. **idle**: Initialize capture, send SHOOT command
2. **preparing picture**: Wait for preparation time (default 2 seconds)
3. **polling**: Poll directory for new image, handle retry logic
4. Returns to **idle** for next image or stops when complete

## File Organization

- `PTMGenerator2.py`: Main application (current version)
- `PTMGenerator.py`, `ptmgenerator2_1.py`: Legacy versions
- `interval.py`: Standalone utility for detecting irregular image time intervals
- `test_PTMGenerator2.py`: Unit tests for core functions
- `setup.py`: cx_Freeze build configuration (legacy)
- `image_data.csv`: Auto-generated tracking file (format: index, directory, filename, include)
- `{project}.lp`: Light position file generated for PTM fitting

## Critical Implementation Details

### Image Detection Logic

The application detects new images by monitoring file modification times (`st_mtime`) in the working directory. Only files created after `self.last_checked` timestamp are considered. Supported formats: PNG, JPG, JPEG, GIF, BMP, TIFF.

### Irregular Interval Detection

The `detect_irregular_intervals` method analyzes time gaps between images to identify missing captures. It determines the typical interval from existing images and inserts placeholder entries (`"-"`) for missing positions, ensuring the final dataset has exactly 50 entries aligned with LED positions.

### Settings Persistence

Application settings are stored using `QSettings` in INI format under `COMPANY_NAME="PaleoBytes"` and `PROGRAM_NAME="PTMGenerator2"`. Settings include window geometry, serial port, language, LED count, and retry behavior.

### Resource Path Resolution

The `resource_path()` function handles both development and PyInstaller frozen executable contexts by checking for `sys._MEIPASS` to locate bundled resources (icons, translations).

## Dependencies

- **PyQt5**: GUI framework
- **pyserial**: Arduino communication
- **Pillow**: Image handling
- **pyinstaller**: Executable packaging

External: `ptmfitter.exe` (PTM generation binary, not included in repository)

## Important Constraints

- The application expects exactly `number_of_LEDs` (default 50) images for PTM generation
- LED indices are 1-based when communicating with Arduino but 0-based internally
- Serial communication requires 2-second initialization delay after port open
- Image filenames are converted to lowercase extensions before PTM generation
- The CSV format changed between versions - code supports both 3-field (legacy) and 4-field (with include flag) formats
