# Auditing the documentation against the code

2026-07-28. After devlog 010 and 011, every root `.md` was checked line by line
against the source it describes. Also moves the install directory to `{userpf}`.

## Why bother

Two changes in one day moved things the documentation names: preferences, the
log, the build layout, the shipped artifact. Each was updated where it was
obviously wrong, which is not the same as being right — the wrong statements
that survive a hurried pass are the ones in files nobody was editing.

## What the sweep found

Sixteen inaccuracies. The two worth generalising:

**`TODOs.md` had grown two sections describing work that had shipped.** "Enable
the remaining ruff rule groups" proposed picking a `C901` threshold and adding
`N802` waivers — both already in `pyproject.toml` since 2026-07-28. "Translate
the manual" said `docs/manual/` was English-only, three days after the Korean
manual was published. Both directly contradicted the audit table further down
the same file, which correctly recorded them as done.

The failure mode is specific to a plan document: a *state* document gets
rewritten when the state changes, but a plan is append-only unless someone
deliberately prunes it. Worth doing at each release cycle, alongside the devlog
check that `CLAUDE.md` already asks for.

**Three files claimed mypy gates over `ui/`.** `Makefile`, the CI lint job and
the pre-commit hook all pass `core/` only. `mypy ui/` does pass by hand, so the
claim looked true to anyone who tried it — but nothing runs it, and
`check_untyped_defs` is off there, so it would skip the bodies of unannotated
functions anyway. Two layers of "less than it looks".

Others: `README.md`'s `pylupdate5` command still named only `PTMGenerator2.py`,
which since the core/ui split is a 113-line entry point — following it verbatim
would have emptied both catalogues. `CLAUDE.md` named the CI lint job as one of
three places ruff is version-pinned; it installs from the lockfile and pins
nothing. `HANDOFF.md` said "5 workflows" and then listed six.

## One user-facing bug

`ui/error_handling.py` told the user "Details have been written to output.log."
after devlog 011 moved the log to `~/PaleoBytes/PTMGenerator2/logs/`. That file
no longer exists, so anyone following the dialog would have found nothing. It
now prints the real path from `core.paths.log_path()`.

Not a translated string — `ui/error_handling.py` has no `tr()` calls at all,
which is its own small gap and is not fixed here.

`core/settings.py`'s docstring still opened "QSettings stores everything as text
in an .ini file". The coercion it describes is still needed, but for a different
reason now — migrated `.ini` values, and what the Preferences dialog writes
through `str()` — so the docstring says that instead.

## The install directory moved again

`{localappdata}\PaleoBytes\PTMGenerator2` → `{userpf}\PaleoBytes\PTMGenerator2`,
which is `%LOCALAPPDATA%\Programs\PaleoBytes\PTMGenerator2`.

`%LOCALAPPDATA%` proper is for application *data*. A program installed directly
into it sits among the caches rather than with the other per-user programs,
which is where Windows itself puts them and where `{userpf}` points. Modan2
raised it first; the same reasoning applies to all of the PaleoBytes tools.

`{userpf}` needs Inno Setup 6.3 or newer. The workflow pins 6.7.3.

## What was left alone

`CHANGELOG.md`'s older entries describe what was true at each release —
`[0.2.0-alpha.1]` says the exception handler logs to `output.log`, and it did.
A changelog is a record, not a description of the present. Same for the devlog
entries, except where this session's own work was still missing from them: the
docs-build dependency failure was added to 010, and the Windows-only geometry
failure and the installer build result to 011.

## State

331 tests, ruff and mypy clean, both manuals build. The stray zero-byte
`output.log` and `test_output.log` in the repository root — leftovers from the
old logging scheme, never tracked by git — are gone.
