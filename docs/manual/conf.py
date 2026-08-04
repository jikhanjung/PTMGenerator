"""Sphinx configuration for the PTMGenerator2 manual."""

import sys
from pathlib import Path

# The repository root, so `from version import ...` resolves.
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from version import COMPANY_NAME, COPYRIGHT_HOLDER, COPYRIGHT_YEARS  # noqa: E402
from version import __version__ as release  # noqa: E402

version = release

project = "PTMGenerator2"
# Derived, not written out again. This line said "2024-2026, PaleoBytes" while
# LICENSE said "2018-2026 Jikhan Jung" -- two spellings of the same fact, which
# is what having two of them produces. The holder is the person; PaleoBytes is
# the brand, and appears as the author below.
copyright = f"{COPYRIGHT_YEARS}, {COPYRIGHT_HOLDER}"
author = COMPANY_NAME

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    # Lets the manual include the repository-root CHANGELOG.md, which is the
    # single source of release history. It does not publish the other *.md
    # files: those live outside this source directory.
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "locale"]

language = "en"
locale_dirs = ["locale/"]
gettext_compact = False

html_theme = "sphinx_rtd_theme"
html_title = f"{project} {release}"
html_static_path = []

html_theme_options = {
    "navigation_depth": 3,
    "collapse_navigation": False,
}

html_context = {
    "display_github": True,
    "github_user": "jikhanjung",
    "github_repo": "PTMGenerator",
    "github_version": "main",
    "conf_py_path": "/docs/manual/",
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# autodoc imports the modules it documents. core/ has no PyQt5 dependency, so
# it imports anywhere; ui/ does, and PyQt5 is in the docs environment via the
# dev extra. Mock nothing -- a real import failure here is worth knowing about.
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_member_order = "bysource"

nitpicky = False
