"""Checks that only mean something against the *packaged* application.

The test suite runs from a source checkout, where `icons/` and `translations/`
are simply on disk. A PyInstaller build has to be told to bundle them, and if
that goes wrong the executable still starts — it just shows no icon and no
Korean. Nothing in a source-based suite can see that.

`PTMGenerator2.exe --self-test` runs these against whatever tree the running
interpreter actually has, frozen or not, so the release workflow can run the
artifact it just built.
"""

import os

from core import resources
from core.light_positions import LED_COUNT, light_vectors
from core.settings import SUPPORTED_LANGUAGES


class CheckFailedError(Exception):
    """A self-test check that did not pass.

    The message is the whole point of this exception — each raise site names
    what is missing from the bundle, which is what the CI log has to show.
    """


def check_icons():
    """Every icon the UI asks for is present."""
    missing = [name for name in resources.ICON if not os.path.exists(resources.icon_path(name))]
    if missing:
        raise CheckFailedError(f"icons missing from the bundle: {', '.join(sorted(missing))}")
    return f"{len(resources.ICON)} icons"


def check_translations():
    """A compiled .qm is present for every language the UI offers."""
    missing = [
        code
        for _label, code in SUPPORTED_LANGUAGES
        if not os.path.exists(resources.translation_path(code))
    ]
    if missing:
        raise CheckFailedError(f"translations missing from the bundle: {', '.join(missing)}")
    return f"{len(SUPPORTED_LANGUAGES)} languages"


def check_light_table():
    """The LED table is intact and still produces unit vectors."""
    vectors = light_vectors()
    if len(vectors) != LED_COUNT:
        raise CheckFailedError(f"expected {LED_COUNT} light vectors, got {len(vectors)}")
    for index, (x, y, z) in enumerate(vectors):
        length = (x * x + y * y + z * z) ** 0.5
        if abs(length - 1.0) > 1e-9:
            raise CheckFailedError(f"LED {index} is not a unit vector (length {length})")
    return f"{LED_COUNT} light vectors"


#: (name, callable) — each returns a short description or raises CheckFailedError.
CHECKS = [
    ("icons", check_icons),
    ("translations", check_translations),
    ("light table", check_light_table),
]


def run(checks=None, log=print):
    """Run every check. Returns True if all passed."""
    ok = True
    for name, check in checks or CHECKS:
        try:
            log(f"  {name}: {check()}")
        except Exception as error:  # a check must never take the process with it
            ok = False
            log(f"  {name}: FAILED — {error}")
    return ok
