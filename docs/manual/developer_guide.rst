Developer guide
===============

Setting up
----------

.. code-block:: bash

   git clone https://github.com/jikhanjung/PTMGenerator.git
   cd PTMGenerator
   make install-dev

That installs the runtime, test, build and docs dependencies, and the pre-commit
hooks.

Everyday commands
-----------------

.. code-block:: bash

   make test          # the suite, ~1.3s
   make test-cov      # with a coverage report
   make lint          # ruff check + ruff format --check
   make type-check    # mypy over core/
   make run           # run the application
   make build         # PyInstaller -> dist/
   make docs          # this manual

Testing
-------

The suite needs **no display**: ``tests/conftest.py`` selects Qt's ``offscreen``
platform plugin before PyQt5 is imported, so it runs over SSH and in CI without
xvfb. Do not add xvfb.

QSettings is redirected to a temporary directory per test, so running the suite
never reads or writes real preferences.

To test capture behaviour, drive :py:class:`core.capture_session.CaptureSession`
directly with fakes rather than constructing a window and waiting out real
ticks:

.. code-block:: python

   session = CaptureSession([0, 1], preparation_time=1)
   result = session.step(shoot=shots.append, poll=lambda: "/shots/a.jpg")

Markers: ``unit`` (no Qt), ``ui`` (needs a QApplication), ``smoke`` (must pass
on every OS in the matrix), ``slow``.

Code quality
------------

ruff replaces black, isort, flake8 and pyupgrade, and is **pinned to an exact
version in three places that must move together**: ``pyproject.toml``,
``.pre-commit-config.yaml`` and the lint job in ``.github/workflows/test.yml``.
A newer ruff formats code the previous one accepted, so an unpinned bump
reformats the tree from under an unrelated pull request.

mypy is scoped to ``core/``. Widening it to ``ui/`` means teaching it about
PyQt5's stubs; do that a module at a time, each one clean before it joins the
invocation. Tracked in ``TODOs.md``.

Translations
------------

Three steps. Skipping the third is the usual mistake — the ``.qm`` files are
what the application loads, and CI checks for drift.

.. code-block:: bash

   make translations   # pylupdate5 extract, then pyside6-lrelease compile

``pylupdate5`` ships with PyQt5; ``lrelease`` does not, so ``PySide6-Essentials``
provides it as ``pyside6-lrelease``.

Editing a ``.ts`` by hand is fine; Qt Linguist is nicer. Both ``.ts`` and ``.qm``
are committed.

Dependencies
------------

``pyproject.toml`` declares ranges; the nine lockfiles pin exact versions with
hashes so CI, contributors and release builds install byte-identical trees.
Regenerate with ``make lock`` after changing a range, and commit the result —
CI fails otherwise.

They are per-platform on purpose. A universal resolve pins one version per
package for every OS without checking wheel coverage, and ``pyqt5-qt5`` stopped
publishing Windows wheels after 5.15.2 while Linux and macOS reach 5.15.19.

Releasing
---------

1. Describe the change under ``## [Unreleased]`` in ``CHANGELOG.md``.
2. ``python scripts/bump_version.py patch`` — or ``minor``, ``preminor beta``,
   ``prerelease``, ``stage rc``, ``release``.
3. ``git push && git push origin v<version>``.

``release.yml`` refuses the tag if it disagrees with ``version.py``, gates on the
full test matrix, builds the Windows executable, and publishes a release whose
notes come from the matching ``CHANGELOG.md`` section.

Never edit ``version.py`` by hand — the changelog and the tag drift apart.

Recording decisions
-------------------

``devlog/`` holds one file per piece of work, recording *why* something was done
the way it was: what was tried, what it broke, what was rejected. ``TODOs.md``
holds deferred work with enough context to resume. See ``devlog/README.md``.
