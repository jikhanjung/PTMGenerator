"""The About dialog — the one place the application describes itself.

Modelled on Modan2's, which is the family's: a rich-text `QMessageBox` so the
links are clickable, carrying the name, the version, the vendor, the licence
and the copyright.

Two things here that the version alone cannot give:

* **The build**, from `core.build_info` — a build number, a date and a commit.
  "0.2.0-alpha.3" names a release; a bug report needs to name an executable.
* **Copy diagnostics**, which is what turns a report into a reproducible one.
  It puts the version, the build, the OS, the Qt and Python versions and the
  two directories the application writes to on the clipboard. Those paths are
  the single most common thing to have to ask for, because they differ per OS
  and neither is under the install directory.
"""

import platform
import sys

from PyQt5.QtCore import QT_VERSION_STR, QCoreApplication, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QMessageBox

from core import build_info, paths
from core.resources import icon_path
from version import (
    COMPANY_NAME,
    PROGRAM_COPYRIGHT,
    PROGRAM_HOMEPAGE,
    PROGRAM_ISSUES,
    PROGRAM_LICENSE,
    PROGRAM_MANUAL,
    PROGRAM_NAME,
    PROGRAM_TAGLINE,
)

# The user-visible strings below are wrapped in
# `QCoreApplication.translate("About", ...)`. `self.tr()` is not available --
# the dialog is built by a function rather than by a QWidget subclass -- and
# "About" is the context the .ts files key them on.
#
# Both arguments have to be **string literals at the call site**. pylupdate5
# reads the source rather than running it, so neither a `_tr()` helper nor a
# `CONTEXT` constant extracts anything at all: the code still works, the
# strings just silently stop being translatable and nothing says so. Both were
# tried here first. Same reason the licence line is a `.format()` template and
# not an f-string.


def diagnostics(info=None):
    """What to paste into a bug report.

    Plain text, not rich text: it is going into an issue tracker, and the
    paths matter more than the formatting.
    """
    info = info or build_info.read()
    lines = [
        f"{PROGRAM_NAME} {info['version']}",
        f"build: {info['build_number']} ({info['build_date']}, {info['commit']})",
        f"os: {platform.platform()}",
        f"python: {sys.version.split()[0]}",
        f"qt: {QT_VERSION_STR}",
        f"frozen: {getattr(sys, 'frozen', False)}",
        # Config and data are two different directories on purpose (devlog
        # 014), so reporting only one of them answers half the question.
        f"config: {paths.config_dir()}",
        f"data: {paths.data_dir()}",
        f"log: {paths.log_path()}",
    ]
    return "\n".join(lines)


def _body(info):
    def link(url):
        return f'<a href="{url}">{url}</a>'

    # A .format() template, not an f-string: a message extractor cannot derive
    # a stable msgid from a string built by interpolation.
    licence = QCoreApplication.translate(
        "About", "Distributed under the terms of the {licence} License."
    ).format(licence=PROGRAM_LICENSE)
    build = QCoreApplication.translate("About", "build")
    return (
        f"<b>{PROGRAM_NAME}</b> v{info['version']}<br>"
        f"{PROGRAM_TAGLINE}<br><br>"
        f"{build} {info['build_number']} &middot; {info['build_date']} &middot; "
        f"{info['commit']}<br><br>"
        f"{COMPANY_NAME}<br>"
        f"{PROGRAM_COPYRIGHT}<br>"
        f"{licence}<br><br>"
        f"{link(PROGRAM_HOMEPAGE)}<br>"
        f"{link(PROGRAM_MANUAL)}<br>"
        f"{link(PROGRAM_ISSUES)}"
    )


def build_about_box(parent, info=None):
    """The dialog, and the button that copies diagnostics.

    Returned rather than shown so a test can inspect it without an event loop.
    """
    info = info or build_info.read()

    box = QMessageBox(parent)
    box.setWindowTitle(QCoreApplication.translate("About", "About"))
    # RichText so the anchors are live; QMessageBox opens external links itself.
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(_body(info))
    box.setIconPixmap(
        QPixmap(icon_path("app")).scaled(
            64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    )
    copy_button = box.addButton(
        QCoreApplication.translate("About", "Copy diagnostics"),
        QMessageBox.ButtonRole.ActionRole,
    )
    box.addButton(QMessageBox.StandardButton.Ok)
    return box, copy_button


def show_about(parent, info=None):
    """Show it, and keep it up while diagnostics are being copied.

    A QMessageBox closes on any button, including an ActionRole one, so
    "Copy diagnostics" would otherwise dismiss the dialog the user is reading
    the version out of. Re-showing is the simplest way to make the button act
    on the dialog rather than end it.
    """
    box, copy_button = build_about_box(parent, info)
    while True:
        box.exec_()
        if box.clickedButton() is not copy_button:
            return
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(diagnostics(info))
