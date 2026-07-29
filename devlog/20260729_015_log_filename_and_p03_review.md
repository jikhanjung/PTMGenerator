# The log filename, settled — and reviewing Modan2's data-directory plan

2026-07-29. Two loose ends left by devlog 014, neither of which changed any
code here. Both are recorded because the useful output of each is a *decision*,
and an undocumented decision gets re-litigated.

## The log filename: the underscore wins

Devlog 014 noticed the two projects disagreed by one character:

    ~/PaleoBytes/Modan2/logs/Modan2.20260728.log
    ~/PaleoBytes/PTMGenerator2/logs/PTMGenerator2_20260728.log

R02 covers where logs go and deliberately says nothing about what they are
called, so neither was wrong. It was left alone here rather than changed
unilaterally, and raised across the projects instead.

**Settled: `<Program>_<YYYYMMDD>.log` is the shared form. Modan2 moves to it.**
Nothing changes in this repository — `core.paths.log_path` already writes that.
The `TODOs.md` entry is gone, and devlog 014's "Noticed while checking the
result" section now carries the resolution, so the divergence is not re-opened
from this side. If a later entry finds the two disagreeing again, it is Modan2
that has drifted.

## Modan2's P03, reviewed: nothing to apply, for a reason worth stating

`../Modan2/devlog/20260728_P03_data_directory_relocation_plan.md` (revised
2026-07-29) makes the data directory configurable, adds a migration, and — after
the revision — replaces the default-location change with a library backup.
Stage 3, moving configuration to the OS config location, is the part this
project already did as devlog 014.

**Stages 1, 2 and 4 have no subject here. This application owns no library.**

That is the whole of it, and it is worth writing down because "we should do
what Modan2 did" is the kind of thing that reads as obviously true a year
later. Modan2 has `data/` (media), `Modan2.db` and `backups/` — the only copy
of a user's research, which is what makes location, migration and backup real
problems. PTMGenerator2's user data — the photographs, the `.lp`, the `.ptm`,
`image_data.csv` — lives in whatever folder the user picked for that session,
and that folder is not even remembered across launches (`ui/main_window.py:96`
starts `monitor_root` at `"."`; only browsing sets it, `:564`). The one path
that does persist is `ptm_fitter`, an executable. `~/PaleoBytes/PTMGenerator2/`
holds the log and nothing else.

So there is no library to back up, no store to relocate, and no path to make
configurable.

### Where the two projects agreed, having got there separately

Stage 3 against devlog 014, item by item: `platformdirs` rather than
`QStandardPaths`; the vendor segment joined by hand instead of passed as
`appauthor`, which is honoured on Windows only; `Application Support` rather
than `Preferences` on macOS; migration on first read, copying and leaving the
original; the log left with the data; settings in Local rather than Roaming,
because window geometry is machine-local state. Two readings of R02 arriving at
the same layout is the confirmation the convention was worth writing.

The `QStandardPaths` argument is stronger here than there. Modan2 found the
failure empirically — resolved before `QApplication` exists, the app-specific
location silently degrades to the shared config root. In this project `core/`
imports no Qt by rule, asserted in a subprocess by `tests/test_smoke.py`, so
that bug is unrepresentable rather than avoided.

### The three traps, checked against this code rather than assumed

P03's transferable findings are hazards, not features, so each was looked for:

- **Investigation 2, defaults frozen at import** — `base_path=mu.DEFAULT_...`
  is evaluated once, so changing the module attribute at runtime does nothing,
  and in Modan2 the callers had split such that reads would see the new
  location and writes the old. There are no module-level path constants in
  `core/paths.py` and no signature defaults to one. Both roots are re-resolved
  on every call, documented as deliberate in the module docstring — and that is
  exactly what makes `PTMGENERATOR2_CONFIG_DIR` and `PTMGENERATOR2_DATA_DIR`
  work. The property that would prevent Modan2's bug is the property the test
  suite already depends on.
- **Investigation 5, a path defined in two places** — everything routes through
  `core/paths.py`. Outside the tests there are two call sites,
  `ui/error_handling.py:54` and `ui/main_window.py:111`.
- **Risk 7, a configured path that has vanished** — no persisted directory to
  vanish. The one persisted path is checked before use
  (`core/ptm_builder.py:199`), and since the built-in fitter became the default
  only someone who chose the external one reaches it.

### One thing the review did shift

P03 justifies keeping logs with the data as "one folder to look in when
something goes wrong." In Modan2 that folder is the library, so it follows.
Here `~/PaleoBytes/PTMGenerator2/` exists *solely* to hold `logs/`, so the
justification is really "the same shape as its siblings" — a user running both
finds logs in the same place. Still the right call, and devlog 014's bootstrap
argument (logging is configured before preferences are read) is untouched. Noted
so the reasoning is not mistaken for the one P03 gives.

## State

347 tests, ruff and mypy clean. No code changed in either half of this entry.
