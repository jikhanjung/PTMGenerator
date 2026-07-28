# An installer, and somewhere to put the settings

2026-07-28. Brings PTMGenerator2 in line with Modan2, CTHarvester and
PaperMeister: a per-user Inno Setup installer, and user data under
`%USERPROFILE%\PaleoBytes\PTMGenerator2`.

## Why the two are one change

Shipping an installer forces the data question. A onefile executable run from
the Downloads folder can write `output.log` beside itself and get away with it.
An installed application cannot: the uninstaller deletes `{app}`, so anything
kept there is thrown away with the application. The settings had the same
problem from the other direction — they were in `%APPDATA%\PaleoBytes\
PTMGenerator2.ini`, which survives, but is not where any of the sibling
projects look.

Before:

    output.log                          the current working directory,
                                        whatever that happened to be
    %APPDATA%\PaleoBytes\PTMGenerator2.ini

After:

    %USERPROFILE%\PaleoBytes\PTMGenerator2\
    ├── preferences.json
    └── logs\
        └── PTMGenerator2_20260728.log

## The data directory

`core/paths.py`, Qt-free like the rest of `core/`. Paths are resolved on every
call rather than at import, so `PTMGENERATOR2_DATA_DIR` can be set after the
module is imported — which is what the test suite does, and what stops the suite
writing into the developer's real settings. That has happened before in this
project, from a throwaway script, and it took a while to notice.

Logs are one file per day (`PTMGenerator2_<YYYYMMDD>.log`), opened in **append**
mode. The old file was opened `"w"`, so a second run of the day erased the
first's record — which is the record you want when a capture goes wrong twice.

## Preferences as JSON

QSettings went with it. The replacement, `core/preferences.py`, keeps the
QSettings method names — `value`, `setValue`, `sync` — so `core/settings.py` and
both windows did not change at all. A store that behaves *almost* like the one
it replaces is where the bugs would have been.

Two deliberate differences:

- **Types survive.** QSettings returned everything as a string. The coercion in
  `core/settings.py` stays, because it still has to read what the old `.ini`
  contained, but new values keep their type.
- **A `/` in a key nests**, so `WindowGeometry/MainWindow` is an object in the
  file rather than a flat key with a slash in it. The point of JSON here is that
  someone can open the file.

What did change: QSettings could store a `QRect` directly, JSON cannot.
`ui/geometry.py` converts to `[x, y, w, h]` and back, and refuses anything
malformed rather than raising — a hand-edited preferences file must not stop the
window opening.

### Migration

`migrate_from_ini` reads the old file with `configparser` — a Qt `.ini` is an
ordinary one — and copies across anything the JSON does not already have. It
runs on **every** start, not once behind a flag: it is a no-op when the keys are
there, it costs nothing, and it also picks up an `.ini` restored from a backup
later. Two things it gets right that are easy to get wrong:

- `configparser` lower-cases keys unless `optionxform` is replaced, and
  `Number_of_LEDs` silently becoming `number_of_leds` is a setting that reads as
  its default forever after.
- QSettings wrote geometry as `@Rect(100 100 1400 800)`. Imported as a string it
  would reach the window, which would try to unpack it. Values starting `@` are
  dropped.

The `.ini` is left where it is. Deleting a file the user did not ask us to
delete is not ours to do, and re-reading it is harmless.

The last version anyone actually ran is `0.1.2` (2025-11-07), so the `.ini` that
matters in practice is that one's.

## onefile → onedir

The installer ships a directory, so `PTMGenerator2.spec` gained a `COLLECT` and
the `EXE` gained `exclude_binaries=True`. Two consequences worth recording:

- **The executable's name lost its version.** It was
  `PTMGenerator2_v0.2.0-alpha.2_20260728.exe`; it is now `PTMGenerator2.exe`.
  The version moved to the installer filename and to Add/Remove Programs. A
  versioned name inside `{app}` would leave the previous one behind on every
  upgrade and point the Start Menu shortcut at whichever installed last.
- **Startup gets faster.** A onefile build unpacks itself to a temp directory on
  every launch. At 198 MB that is a visible pause before the window appears.

Verified locally on Linux: `dist/PTMGenerator2/PTMGenerator2 --self-test`
passes against the frozen bundle.

## The installer

`installer/PTMGenerator2.iss.template`, filled in by CI. Following PaperMeister,
which is the cleanest of the three:

- `AppId={{3AF7491F-8640-4855-9C69-43326C34327D}` — generated once, never to be
  changed. Inno keys upgrade detection, the uninstall entry and `{app}` off it,
  so a new AppId makes every existing installation invisible and leaves it
  behind. The doubled brace is Inno's escape for a literal `{`, not a
  placeholder.
- `PrivilegesRequired=lowest` — per user, so `{localappdata}` and
  `{userprograms}` resolve to the invoking user rather than to whoever consented
  to the UAC prompt.
- `DefaultDirName={localappdata}\PaleoBytes\PTMGenerator2` — Local, not Roaming:
  a 198 MB payload would otherwise sync with the profile on domain-joined
  machines.
- `Compression=lzma/normal`, `SolidCompression=no` — solid LZMA trips antivirus
  heuristics more often, and an installer quarantined on the user's machine is
  worse than a larger one.

No `LicenseFile`. `pyproject.toml` declares MIT but there is no `LICENSE` file
to point at, and ISCC fails on a missing one. Adding the line is a one-liner
once the file exists; asserting terms nobody wrote down is not.

Inno Setup 6.7.3 is fetched from a **GitHub release asset**, not from
jrsoftware.org, which only keeps the latest 6.x under `/is/6/` — a pinned URL
there starts 404ing the moment a new version ships. CTHarvester hit this and
took its Windows builds down with it.

## What is checked

Nine tests in `tests/test_packaging.py` compare the template against the spec:
that the spec produces a directory at all, that the installer ships the name the
spec produces, that the AppId is a GUID, that every `{{PLACEHOLDER}}` in the
template is one the workflow actually substitutes. None of that is verifiable
locally otherwise, and the alternative is finding out six minutes into a Windows
runner — or during a release, with the tag already pushed.

One test asserts the installer never writes under `%USERPROFILE%`: whatever it
installs there it would also remove, and that directory is precisely the one
that has to survive.

## State

308 tests, ruff and mypy clean, manual updated in both languages. Not yet built
on Windows — `gh workflow run build.yml` before any tag, per devlog 007.
