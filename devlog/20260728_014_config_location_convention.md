# Applying the PaleoBytes config-location convention

2026-07-28. Implements `../PaperMeister/devlog/20260728_R02_Config_File_Location_Convention.md`,
which was written to be applied across the product family. It arrived hours
after devlog 011 put `preferences.json` in the data directory, so this corrects
that before anything shipped with it.

## What changed

    before                                        after
    ~/PaleoBytes/PTMGenerator2/                   <OS config>/PaleoBytes/PTMGenerator2/
      preferences.json                              preferences.json
      logs/PTMGenerator2_<date>.log               ~/PaleoBytes/PTMGenerator2/
                                                    logs/PTMGenerator2_<date>.log

Concretely:

    Windows   %LOCALAPPDATA%\PaleoBytes\PTMGenerator2\preferences.json
    macOS     ~/Library/Application Support/PaleoBytes/PTMGenerator2/preferences.json
    Linux     ~/.config/PaleoBytes/PTMGenerator2/preferences.json

## Why configuration leaves the data directory

R02 gives three reasons and all three apply here, though only two bite today:

1. **They are different kinds of thing.** Settings are machine-local state —
   window position, serial port — that costs nothing to recreate. Data is not.
   They are opposites on backup, sync and migration.
2. **It pre-empts a bootstrap cycle.** The moment the data location becomes
   configurable, a settings file *inside* the data directory means reading the
   settings to find the data and finding the data to read the settings.
   Separation is a precondition for that feature, not a consequence of it.
3. **Credentials do not travel with the data.** PTMGenerator2 stores none today.
   A capture folder does end up on shared drives, so this is worth inheriting
   rather than rediscovering.

## Why `platformdirs` and not `QStandardPaths`

`core/` imports no Qt — that boundary is asserted in a subprocess by
`tests/test_smoke.py` and is what makes the suite run without a display. A path
module is exactly the thing a script or a future CLI imports, and pulling a GUI
toolkit in there would make a headless one-off need one.

It also matters for the family being consistent on macOS, where the two
disagree: `platformdirs` gives `Application Support`, `QStandardPaths`'
`AppConfigLocation` gives `Preferences`. Apple's answer is the former —
`Preferences` belongs to the defaults/plist system, and JSON an application
manages itself belongs in `Application Support`. Mixing the two tools across
projects is where that would have split.

## The vendor segment is joined by hand

`platformdirs` takes an `appauthor`, and honours it **on Windows only** —
macOS and Linux convention has no vendor directory, so it is deliberately
dropped. Passing it would have silently produced
`~/.config/PTMGenerator2` on Linux and lost the grouping.

So: take the root, join `PaleoBytes/PTMGenerator2` ourselves. All three
resulting paths are legitimate on their platform; a vendor directory is not
forbidden, just not the convention.

`test_configuration_carries_the_vendor_segment` pins it, because the failure is
invisible on the developer's Windows machine and only shows up on someone
else's.

## The log stays where it is

R02 says not to move logs, for two reasons that both hold here:

- **Bootstrap.** `initialize_variables()` opens the log before preferences are
  read. A log location that followed a setting would need either a discarded
  first log or a double initialisation.
- **Investigation.** After a failed capture, one folder to look in beats two.

So `core/paths.py` now has two roots and two environment overrides,
`PTMGENERATOR2_CONFIG_DIR` and `PTMGENERATOR2_DATA_DIR`, redirected
independently. `test_the_log_stays_with_the_data` pins the split, since "tidy
everything into one place" is exactly the change someone would make later
without knowing why.

## Migration hangs off the first read

The part of R02 most worth transcribing, because the obvious implementation is
the wrong one. It was in the entry point before this; it is now in
`Preferences.__init__`.

**Why not the entry point:** a script or a CLI does not run application startup.
Hook migration there and you get executions that silently run *without* the
user's settings — and they will be the ones nobody is watching.

Two rules go with it, and each has a test:

- **Never overwrite an existing file at the new location.** An old file
  reinstating a setting the user has since changed is a silent regression.
  Migration only runs when the new store reads back empty.
- **Never delete the original.** It costs nothing to leave, and an older build
  still finds its settings if someone rolls back.

Copying settings automatically is safe in a way that copying *data* is not:
under a kilobyte, and no cost to getting it wrong. That is precisely the
asymmetry R02 draws.

Two legacy sources, newest first: the `preferences.json` devlog 011 briefly put
in the data directory, then the QSettings `.ini` from 0.1.2 and earlier. A
machine with both takes the later one.

## Checklist

R02's, worked through:

- [x] `platformdirs` added, all nine lockfiles regenerated
- [x] `config_dir()` / `preferences_path()` / `legacy_preferences_path()`
- [x] vendor segment joined manually, not passed as `appauthor`
- [x] migration on the first read, not at startup
- [x] tests: outside the data directory, vendor segment, copied, **not
      overwritten**, and reached without going through the entry point
- [x] the log left where it was

## Noticed while checking the result

The layout now matches Modan2's, which is the useful confirmation that the
convention was read the same way twice. The log *names* do not:

    ~/PaleoBytes/Modan2/logs/Modan2.20260728.log
    ~/PaleoBytes/PTMGenerator2/logs/PTMGenerator2_20260728.log

Dot against underscore. R02 covers where logs go and deliberately says nothing
about what they are called, so this is not a violation of anything — but it is
the kind of small divergence a shared convention exists to avoid, and it is
cheaper to settle now than after either project has logs worth keeping. Left
alone here rather than changed unilaterally.

**Settled 2026-07-29: the underscore wins.** `<Program>_<YYYYMMDD>.log` is the
shared form, and Modan2 moves to it; nothing changes here, since
`core.paths.log_path` already writes
`~/PaleoBytes/PTMGenerator2/logs/PTMGenerator2_<date>.log`. Recorded so the
divergence is not re-opened from this side — if a future entry finds the two
projects disagreeing again, it is Modan2 that has drifted.

## State

347 tests, ruff and mypy clean, both manuals build, all nine lockfiles in sync.
