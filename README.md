# PTMGenerator2

A desktop application for automated Polynomial Texture Mapping (PTM) image capture and generation.

## Overview

PTMGenerator2 is a PyQt5-based tool designed for archaeological artifact documentation using Polynomial Texture Mapping (PTM) technology. The application automates the process of capturing multiple images under different lighting angles and generates PTM files that can reveal surface details invisible under normal lighting conditions.

## Features

- **Automated Image Capture**: Control DSLR cameras via Arduino-based LED dome systems
- **Serial Communication**: Coordinate lighting and camera triggering through serial protocol
- **Intelligent Polling**: Automatic detection of newly captured images with retry logic
- **Image Management**: Track, preview, and selectively include/exclude images for PTM generation
- **Multi-language Support**: Available in English and Korean (한국어)
- **PTM Generation**: Create PTM files using the integrated PTMfitter engine

## Requirements

### Software Dependencies

- Python 3.x
- PyQt5
- pyserial
- Pillow

Install dependencies:
```bash
pip install -r requirements.txt
```

### Hardware Requirements

- DSLR camera with remote shutter capability
- Arduino-based LED dome controller
- Serial connection to Arduino (USB or Bluetooth)

### External Tools

- PTMfitter executable (`ptmfitter.exe`) - Configure path in Preferences

## Installation

1. Clone or download this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Ensure `ptmfitter.exe` is available (configure path in application preferences)
4. Connect your Arduino LED dome controller via serial port

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

## Configuration Files

- **image_data.csv**: Auto-generated file tracking captured images (format: index, directory, filename, include)
- **{project}.lp**: Light position file generated during PTM creation
- **Settings**: Stored in system-specific location (Windows: `%APPDATA%/PaleoBytes/PTMGenerator2.ini`)

## Building Executable

To create a standalone Windows executable:

```bash
pyinstaller --name "PTMGenerator2_v0.1.2.exe" --onefile --noconsole \
  --add-data "icons/*.png;icons" \
  --add-data "translations/*.qm;translations" \
  --icon="icons/PTMGenerator2.png" \
  PTMGenerator2.py
```

## Arduino Protocol

The application communicates with Arduino using commands wrapped in `<>`:
- `<ON,{led_number}>`: Turn on specific LED
- `<SHOOT,{led_number}>`: Trigger camera shutter
- `<OFF>`: Turn off all LEDs

LED numbers are 1-based (1-50 for default configuration).

## Troubleshooting

### No serial port detected
- Ensure Arduino is connected and drivers are installed
- Check Device Manager (Windows) or `ls /dev/tty*` (Linux/Mac)
- Install CH340 drivers if using CH340-based Arduino clones

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

## Version History

- **v0.1.2** (2025-11-07): Latest stable release
  - Improved polling behavior
  - Better directory handling
  - Image selection feature

## License

[License information not specified]

## Credits

Developed by PaleoBytes
