"""Preference keys, defaults and coercion.

QSettings stores everything as text in an .ini file, so a value written as an
int comes back as a string. The defaults and the coercion live here so the two
windows that read preferences cannot drift apart on either.
"""

# Preference keys, as they appear in the .ini.
SERIAL_PORT = "serial_port"
PTM_FITTER = "ptm_fitter"
NUMBER_OF_LEDS = "Number_of_LEDs"
RETRY_COUNT = "RetryCount"
LIGHT_POSITION_ADJUSTMENT = "light_position_adjustment"
POST_SHUTTER_POLLING = "post_shutter_polling"
LANGUAGE = "language"
FITTER = "fitter"

DEFAULTS = {
    SERIAL_PORT: None,
    PTM_FITTER: "ptmfitter.exe",
    NUMBER_OF_LEDS: 50,
    RETRY_COUNT: 3,
    LIGHT_POSITION_ADJUSTMENT: 0,
    POST_SHUTTER_POLLING: 1.0,
    LANGUAGE: "en",
    FITTER: "native",
}

#: How the .ptm is produced. "native" fits in-process and has no size limit
#: beyond memory; "external" shells out to PTMfitter.exe, which is 32-bit and
#: fails above about 24 megapixels. External is kept selectable while the
#: native path proves itself against real captures.
FITTER_NATIVE = "native"
FITTER_EXTERNAL = "external"
SUPPORTED_FITTERS = [("Built-in", FITTER_NATIVE), ("PTMfitter.exe", FITTER_EXTERNAL)]

SUPPORTED_LANGUAGES = [("English", "en"), ("한국어", "ko")]

# Ticks to let the camera settle after the shutter, before looking for a file.
PREPARATION_TIME = 2
# Further ticks to wait for the file to appear before retaking or giving up.
POLLING_TIMEOUT = 5


def value_to_bool(value):
    """Coerce a QSettings value to bool.

    An .ini round-trips True as the string "true", which is truthy either way,
    but so is "false".
    """
    return value.lower() == "true" if isinstance(value, str) else bool(value)


def read_int(settings, key):
    return int(settings.value(key, DEFAULTS[key]))


def read_float(settings, key):
    return float(settings.value(key, DEFAULTS[key]))


def read_str(settings, key):
    return settings.value(key, DEFAULTS[key])
