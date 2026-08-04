# Auditing against the guide, and the two items the table could not hold

2026-08-04. The whole application was read against `.guides/` — all five
documents, 1,587 lines — rather than against the summary of it kept in
`TODOs.md`. That distinction turned out to be the finding.

Most of it was already there, and `desktop/file-locations.md` in particular is
adopted end to end: the vendor segment, the two independent overrides, the
migration on first read, and `tests/test_paths.py` covering §7's checklist item
by item. What was missing clustered in one place, and for one reason.

## The tracking table had stopped tracking the guide

`TODOs.md` carried a status table of ten checklist items, verified 2026-07-28.
The guide's checklist now has **thirteen**, and the table's numbering was
against a structure that no longer exists — it cited "§14" and "Appendix A item
2".

The consequence is not cosmetic. Two items had been added to the guide since,
and because the table was indexed on its own history rather than on the source,
**there was nowhere for them to be recorded** — so nobody looked. Both were
missing:

- item 6, the `guard_slot` decorator;
- item 13, "verify each gate actually sees what you think it sees".

Item 6 is the sharper case, because the project had *already found it*. The R01
audit (devlog 005) recorded "❌ **No excepthook, no slot guards**". The excepthook
half was fixed; the guard half was not, and when the table was rewritten
afterwards the row for it did not survive. A finding can be lost between the
audit that made it and the table that is supposed to carry it.

The table is now numbered on `.guides/desktop/README.md` directly. That is the
rule worth keeping: **an adoption table indexed on anything other than the thing
it is adopting will silently stop covering it**, and the failure is invisible
because the table still looks complete.

## The gate that checked nothing was not checking nothing — yet

`ci.md` §8 is the guide's starred section: the most expensive failure is not a
red gate but a green one that examines nothing. Its last row is about exactly
the shape this project has — a `--self-test` flag guarding the build.

`reusable_build.yml` runs `PTMGenerator2.exe --self-test` against the frozen
bundle, and it is the *only* thing that can see a PyInstaller build shipped
without its icons or its translations. It had **no test at all**:
`core/self_test.py` was at 29% coverage and `PTMGenerator2.py`'s `self_test()`
and `main()` at 0%.

So the guide's own method was applied before writing anything: run the gate
against known-bad input. Injecting an `ICON` entry with no file behind it
produced `self-test FAILED` and exit 1. **The gate works.** What it lacked was
anything to stop it quietly ceasing to.

`tests/test_self_test.py` now pins both halves: that the flag is parsed and
short-circuits startup, and that a bundle missing a file fails the run. The
end-to-end pair runs in a subprocess — not as a workaround for the
session-scoped `QApplication`, but because *the process and its exit code are
what CI actually contracts on*.

Two details worth writing down. Breaking the flag deliberately made the
subprocess tests hang rather than fail, because `main()` then opens a window and
waits on an event loop; the `subprocess.run` timeout is 45s so it fails *below*
CI's per-test `--timeout=60` and reports the subprocess output rather than
being killed with nothing to show. And the "does it fail?" test is the one that
matters — the "does it pass?" test would go on passing if `run()` started
returning True unconditionally.

## guard_slot, and the trap the guide names

The excepthook's own docstring said it: "This hook is the backstop, not the
fix." PyQt5 runs `sys.excepthook` and then **aborts the process**, so the hook
guarantees the traceback reaches the log and nothing more. All fifteen connected
slots across both windows are now wrapped in `guard_slot(context)`.

The guide warns about one implementation trap, and it is real. sip decides how
many of a signal's arguments to forward by **introspecting the slot**, and a
plain `def wrapper(*args, **kwargs)` advertises that it accepts everything — so
every guarded slot on `clicked(bool)` or `currentIndexChanged(int)` starts
receiving an argument the real function never declared. Removing the trimming
and re-running the tests reproduces it exactly:

    TypeError: Widget.on_clicked() takes 1 positional argument but 2 were given

A guard that breaks precisely the slots it was added to protect. `_positional_limit`
introspects the wrapped function and trims the surplus, and two tests drive real
`QPushButton.clicked` and `QComboBox.currentIndexChanged` through guarded slots
rather than calling them directly, because calling them directly is what would
miss it.

`test_every_connected_slot_is_guarded` greps the two window modules for
`.connect(self.…)` and asserts each target carries the marker the decorator
leaves. Partial coverage of this pattern is worse than none: a window where most
handlers are guarded reads as protected, so the unguarded one is the one nobody
checks — and it aborts the process exactly as an unguarded window would.

The wait-cursor drain is in the guard although **nothing in this project sets an
override cursor**. It is there so that whoever adds the first one does not also
have to remember this, and it checks for a running `QApplication` first, because
`QApplication.overrideCursor()` without one calls `qFatal()` and takes the
process down — which would be an absurd way for an error handler to fail.

## The About dialog, and what a build number is for

`branding.md` §2 asks the About dialog to be the one place the application
describes itself. It was `"PTMGenerator2 v0.2.0-alpha.3"` in a `QMessageBox`.

It is now modelled on Modan2's — rich text so the links are live — and carries
the vendor, the licence, the copyright, three links, the build, and a **Copy
diagnostics** button. The diagnostics are the part that earns its keep: version,
build, OS, Python, Qt, and *both* directories the application writes to.
Config and data are deliberately separate (devlog 014), so "where are your
settings and your log" is two questions, and this answers both without anyone
having to ask.

`core/build_info.py` reads a `build_info.json` the spec stamps at build time.
The fallback for a source checkout is `"local"` / `"development"` / `"unknown"`,
deliberately not number-shaped: a build number of `1` in a bug report is a lie
nobody can detect, where `local` is true and reads as true at a glance. Same
reasoning as the guide's `0.0.0+unknown` version fallback.

The copyright line is `© 2018-2026 Jikhan Jung`. The guide requires the About
dialog, `LICENSE` and the package metadata to agree, and they did not:
`LICENSE` said `2018-2026 Jikhan Jung` while `docs/manual/conf.py` said
`2024-2026, PaleoBytes` — different holder *and* different years.

Settled in favour of the person, on the reasoning that **PaleoBytes is a brand,
and a brand does not hold a copyright.** It is the name on the installer, the
Start-Menu group and the config path — an identifier — where the holder is a
legal fact that `LICENSE` already records. So `PaleoBytes` stays as the vendor
everywhere it was already load-bearing, and as Sphinx's `author`; the copyright
line is the person, matching Modan2.

Both are now derived from `COPYRIGHT_YEARS` and `COPYRIGHT_HOLDER` in
`version.py` rather than written out twice, because Sphinx wants the years and
the holder *without* the symbol and so cannot reuse the formatted string —
which is precisely how the two spellings drifted in the first place. A test
asserts the About string appears in `LICENSE`.

The dialog's strings are translated, and getting there took two wrong turns
worth recording. `self.tr()` is unavailable in a module function, so they use
`QCoreApplication.translate`. **Both arguments have to be string literals at
the call site**: pylupdate5 reads the source rather than running it, so a
`_tr()` helper extracted nothing, and neither did hoisting the context into a
`CONTEXT` constant. In both cases the code kept working and the strings simply
stopped being translatable, with nothing failing.

The first test written for this looked for `translate("About", ...)` in the
source — and **passed against both broken versions**, because a call that is
no longer in that shape is not found rather than reported. The test now
installs the Korean catalogue and asserts the rendered text comes back Korean.
A gate that checks the shape of a call is a gate that stops looking the moment
the shape changes; that is the same lesson as §8, arrived at from the other
side.

## The build number, checked against the sibling rather than assumed

`ci.md` §6 asks for a build number derived from the commit count, not
`github.run_number`. This project used `github.run_number`.

The guide's own §"How to adopt" warns against claiming to match a sibling
without reading it, so `../Modan2` was read: a `compute-build-number` job running
`git rev-list --count HEAD` with **`fetch-depth: 0`**, passed into
`reusable_build.yml` as an input. That last part is the one that would have been
got wrong from memory — `actions/checkout` is shallow by default and
`rev-list --count` on a shallow clone returns `1`.

Copied as-is into `build.yml` and `release.yml`. `BUILD_NUMBER` now also reaches
the PyInstaller step, not only Inno Setup, because the spec needs it to stamp
the metadata — and a step in the build asserts that the number CI passed is the
number that came out the other end, since "the metadata file exists" and "the
metadata file says what we told it" are different claims.

## Smaller things

`.pre-commit-config.yaml`'s mypy hook pinned mirrors-mypy `v1.8.0` while the
lockfile CI installs pins `1.20.2` — the two-year drift `ci.md` §8 describes
verbatim. It is now `language: system` running the project's mypy with **the CI
command, character for character**, and `pass_filenames: false`, because mypy
follows imports differently depending on which files it is handed.

`SHA256SUMS.txt` is published with the release. `upx=False` in the spec, for the
same antivirus reason `SolidCompression=no` was already chosen in the installer.
`.gitattributes` gained `*.ico` and the `.bat`/`.cmd` CRLF rules. The README
gained the Linux/WSL `xcb` fix path.

## The Python version, decided rather than widened

The matrix ran one Python version while `requires-python` said `>=3.12` — so
3.13 and 3.14 were claimed and untested. The guide permits collapsing to one
version, but *deliberately*, and this had never been decided.

It has now, and in the direction of narrowing rather than adding a leg:
`>=3.12,<3.13`. The argument is that **nobody runs this from source.** The
artifact is a Windows installer carrying its own interpreter, and anyone
working on the code sets up their own environment — so a second matrix leg
would buy coverage of a configuration no user is in. That is the cost side of
the guide's own effort-calibration table, applied honestly rather than adopted
wholesale.

Where the mismatch *was* real is the lockfiles: `make lock` compiles them for
3.12 only, so metadata admitting 3.13 would have put a contributor on a newer
interpreter into a `--require-hashes` failure with nothing explaining it. The
pin makes the metadata describe what actually exists.

`tests/test_version_consistency.py` now couples the claim to the matrix in both
directions, so they cannot drift apart again. Narrowing the bound was a
one-line change; the test is what stops it quietly becoming `>=3.12` again the
next time someone edits that line — and the negative control confirmed it fails
on a widened bound rather than only on a narrowed matrix.

## What is still open

`pip-audit` and `uv` are still `pip install`ed unpinned in `security.yml`, where
the guide asks for anything CI installs ad-hoc to be folded into the dev extra so
the lock covers it. Low stakes — neither ships — but it is the same class of
thing as the ruff pin.

And `core/resources.resource_path` resolves the non-frozen case against
`os.path.abspath(".")`, so it depends on the working directory. Nothing hits it
today because the tests that chdir do not read resources, but `build_info.py`
deliberately does not use it for that reason, which is a hint that it wants
fixing rather than working around a second time.
