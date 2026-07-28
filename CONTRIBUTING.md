# Contributing

## Setting up

```bash
git clone https://github.com/jikhanjung/PTMGenerator.git
cd PTMGenerator
make install-dev
```

That installs the runtime, test, build and docs dependencies and the pre-commit
hooks. Python 3.12 or newer.

## Before opening a pull request

```bash
make lint          # ruff check + ruff format --check
make type-check    # mypy over core/ and ui/
make test          # the suite, ~1.3s
```

The pre-commit hooks run the first two on every commit. CI runs all three plus
the suite on Linux, Windows and macOS, and checks that the compiled
translations match their sources.

## Where code goes

**`core/` must not import PyQt5.** `tests/test_smoke.py` asserts that in a
subprocess, and CI runs it on every platform. The boundary is what lets the
capture policy, the serial protocol and the file formats be tested without a
display or hardware — if a change needs Qt, it belongs in `ui/`.

Concretely:

- Decisions — what to shoot next, whether to retake, how long to wait — go in
  `core/capture_session.py`.
- Rendering those decisions — status bar, table rows, the image preview — stays
  in `ui/main_window.py`.

## Tests

Every change to `core/` should come with tests; it is cheap, because nothing
there needs Qt. Drive `CaptureSession` with fakes rather than constructing a
window and waiting out real one-second ticks:

```python
session = CaptureSession([0, 1], preparation_time=1)
result = session.step(shoot=shots.append, poll=lambda: "/shots/a.jpg")
```

Markers: `unit` (no Qt), `ui` (needs a QApplication), `smoke` (must pass on every
OS), `property` (Hypothesis), `slow`.

For pure logic with an invariant — the light geometry is the example — prefer a
property test over a handful of fixed cases. See
`tests/test_light_positions_properties.py`.

The suite needs no display — `tests/conftest.py` selects Qt's offscreen platform
plugin. Please don't add xvfb.

Two things bite people writing tests here:

- Building a main window replaces `sys.stdout` and opens `output.log` in the
  current directory. Use the `main_window` fixture, which handles both.
- QSettings is global. Use the `settings_dir` fixture, or a script you run once
  will write to your real preferences.

## Translations

The application is English and Korean. If you add a user-visible string, wrap it
in `self.tr(...)` and run:

```bash
make translations
```

That extracts into the `.ts` files and compiles the `.qm` files the application
actually loads. **Commit both.** Editing a `.ts` without compiling ships stale
strings; CI checks for the drift.

Leave the `›` in "Edit › Preferences" alone — it is U+203A and is the key the
`.ts` files are indexed on.

## Dependencies

`pyproject.toml` is the only place dependencies are declared — there is no
`requirements.txt`. The lockfiles pin exact versions with hashes.
After changing a range:

```bash
make lock
```

and commit the regenerated lockfiles. CI fails if they are stale.

## Commits

Explain why, not just what. A commit that fixes a crash should say what the
crash was and how it was reached; the diff already says what changed.

If the reasoning behind a change would not be obvious in six months — including
what you tried and rejected — add a `devlog/` entry. If you are deferring
something, put it in `TODOs.md` with enough context to resume.

## Releasing

Maintainers only, and never by editing `version.py` directly:

1. Describe the change under `## [Unreleased]` in `CHANGELOG.md`.
2. `python scripts/bump_version.py patch`
3. `git push && git push origin v<version>`

See `VERSION_MANAGEMENT.md`.
