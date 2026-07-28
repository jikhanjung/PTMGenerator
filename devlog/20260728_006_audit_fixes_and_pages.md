# Acting on the R01 audit, and publishing the manual

## Date: 2026-07-28

Follows [R01](20260728_005_R01_code_quality_audit.md), which listed eight items.
Items 1–4 and 6–8 are done; item 5 was declined. This entry records what the
work turned up, which was more than the audit predicted.

## Two crashes, fixed (items 1–2)

Both were confirmed by reproduction before being fixed, and both have regression
tests verified to fail against the previous code — stashing the fix produced
8 failures and 4 errors.

**The serial port.** `SerialController.open()` called `serial.Serial()`
unguarded, so a `SerialException` escaped into a Qt slot and PyQt5 aborted the
process. It now returns `False` and records `last_error`.

The part worth remembering is that the prompt had to change too. There are two
different failures — "no port is configured" and "COM3 could not be opened" —
and they need different actions from the user: the first sends them to
Preferences, the second tells them to check the cable or close the Arduino IDE.
Collapsing both into the existing "no serial port" message would have been the
easy fix and the wrong one.

**Encodings.** `image_data.csv` and the `.lp` file were written with the
platform default. The CSV is written into the capture directory and read back to
reopen a session, so a run captured on Korean Windows (cp949) could not be
reopened on Linux (utf-8), and vice versa. Both are utf-8 now; the CSV reads as
`utf-8-sig` so a file someone opened in a spreadsheet and re-saved still parses.

**The DST bug** (item 3) was the cheapest fix in the list: interval detection
converted two timestamps to naive local datetimes before subtracting them, so a
gap spanning a DST transition was an hour out and read as hundreds of missed
shots. Subtracting the timestamps directly is the same arithmetic without the
discontinuity, and deletes the import.

## The lint number was misleading (item 4)

The audit reported 165 `S` findings. **162 of them were `assert` in tests.** The
honest count across every unadopted group was about ten real findings, seven
groups were already at zero, and the work was one afternoon rather than the
week the raw number implied.

Worth remembering when reading a linter's first run on an unadopted rule group:
count by rule, not by finding, before deciding anything.

## The self-test found a real defect on its first run (item 6)

`--self-test` starts the application headlessly and checks that every declared
resource resolves. Its first run reported:

```
icons: FAILED — icons missing from the bundle: open_directory
```

`icons/open_directory.png` **has never existed in this repository** — no commit
in any branch has ever added it — and yet `ICON` has referenced it and
`setup_ui` has asked for it since the first release. `QIcon()` on a missing path
returns a null icon instead of raising, so the Open Directory button and menu
action have always rendered without one, and nothing anywhere said so.

This is exactly the class of defect the guide's §7 is about: it cannot be seen
from a source checkout, because from a source checkout the *other* resources are
present and the missing one fails silently. The dead reference is removed and
`CLAUDE.md` now says every `ICON` entry must exist.

The same run also caught a bug in the self-test itself — it closed the window's
`OutputRedirector` and then called `print()`, writing to a closed file. Which is
a fair reminder that a checking tool is code too.

## mypy was checking almost nothing (item 8)

`mypy core/ ui/` reported "Success: no issues found", which looked like the
widening was free. It was not: **mypy skips the bodies of unannotated functions
by default**, and this codebase carries few annotations, so almost nothing was
being examined.

With `check_untyped_defs`:

| Scope | Findings |
|---|---:|
| `core/` | 4 |
| `ui/` + entry point | 111 |

`core/` is now clean with it on. `ui/` is not, but the 111 are two systemic
patterns rather than 111 mistakes: Qt's `instance()` and `addMenu()` are typed
Optional, and the entry point bolts `.translator`/`.language`/`.settings` onto
the QApplication object. The second is a genuine design smell that wants a small
typed holder, so it is left in `TODOs.md` rather than blanket-ignored.

Also: the earlier note claiming `ui/` needed `PyQt5-stubs` was wrong. PyQt5
ships `.pyi` files and `py.typed`.

## The manual was built but never published

`docs.yml` uploaded the HTML as a workflow artifact, so reading the manual meant
downloading a zip from a run page. GitHub Pages was already enabled on the
repository with `build_type=workflow` — the site URL existed and had simply
never been deployed to.

Added the deploy job. Pull requests still build (the `-W` build is the check)
but only a push to `main` deploys, so a fork's pull request cannot replace the
published manual. `.nojekyll` matters: Sphinx writes `_static/` and `_sources/`,
and Pages otherwise runs the output through Jekyll, which skips every path
beginning with an underscore and serves the manual with no CSS.

Live at <https://jikhanjung.github.io/PTMGenerator/>.

## Documentation drift

Writing the above surfaced that the docs had drifted in the few days since they
were written — `README.md` still described a `unittest` suite and
`PROGRAM_VERSION` living in `PTMGenerator2.py`, and `CLAUDE.md` quoted a test
count from two commits earlier.

`requirements.txt` was deleted rather than updated. It had already drifted —
missing `semver`, which is a real runtime dependency — and it was a third
declaration of the same thing alongside `pyproject.toml` and nine lockfiles.
Three sources of truth for dependencies is two too many.

## Numbers

| | Before R01 | After |
|---|---|---|
| Tests | 125 | 152 |
| Coverage | 88% | 88% |
| ruff rule groups | 9 | 20 |
| mypy | scope `core/`, bodies unchecked | `core/` + `ui/`, bodies checked in `core/` |
| Frozen build | built, never started | started and checked in CI |
| Manual | built, never published | published on every push to `main` |
