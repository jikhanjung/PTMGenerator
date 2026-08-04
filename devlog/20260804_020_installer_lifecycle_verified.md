# The installer, installed over itself and then removed

2026-08-04. No code changed except one comment. What changed is what is *known*:
the installer's upgrade and uninstall paths had never been run, and both are
now verified against a real Windows installation rather than against the `.iss`
that `tests/test_packaging.py` reads.

This is the same shape as devlog 017 — a devlog for a *measurement* — and it
exists for the same reason. `TODOs.md` had listed "the installer's upgrade and
uninstall paths" as unverified since the installer was introduced, and the
value of clearing that is lost if what it did and did not cover is not written
down the same day.

## What was run

`v0.2.0-beta.1`, installed **over an existing `v0.2.0-alpha.3`**, then
uninstalled. Not a clean install: the whole point is the pair of transitions.

## The upgrade went in place

The property under test is the one `file-locations.md` §6 says is impossible to
fix after the fact: **a stable `AppId` means an upgrade replaces the existing
installation rather than sitting beside it.** If it had failed, the symptom
would be two entries in Add/Remove Programs and two copies on disk.

    HKCU\...\Uninstall\{3AF7491F-8640-4855-9C69-43326C34327D}_is1
      DisplayVersion   0.2.0-beta.1
      InstallLocation  ...\AppData\Local\Programs\PaleoBytes\PTMGenerator2\

One record. No name-derived `PTMGenerator2_is1` key in any registry view, and
**nothing in HKLM** — which is the other half of the same check: Inno resolves
`HKA` by install mode, so an admin-mode record left over from an older release
would have made the `lowest`-mode installer fail to see it and install a second
copy. There was none, because there has never been an admin-mode release.

One `unins000` (a second install would be `unins001`), one Start-Menu shortcut,
and settings intact — language, serial port, engine, window geometry.

**`build_info.json` earned its keep on its first outing.** "Is the running
binary actually the new one" would otherwise be answered by looking at file
sizes and hoping:

```json
{"version": "0.2.0-beta.1", "build_number": "112",
 "build_date": "2026-08-04", "commit": "cf48851"}
```

That is the exact commit, which is a stronger answer than the version string
alone can give — two builds of one version are indistinguishable without it.

### The 101 files that were not replaced

An early reading of the evidence looked alarming: 101 files under `_internal/`
still carried the alpha.3 build date, against 131 dated the day of the upgrade.
Stale files from the old version would mean the upgrade was partial.

They are not stale. All 101 are **DLLs with a version resource** — `Qt5*.dll`,
`python312.dll`, `MSVCP140`, `VCRUNTIME140` — and Inno compares versioned files
by version, skipping the copy when the existing file matches. They match
because the lockfiles pin the wheels exactly (`pyqt5==5.15.11`,
`pyqt5-qt5==5.15.2`), so the two builds bundle byte-identical Qt. The files
dated the day of the upgrade are the unversioned ones, compared by timestamp:
`LICENSE`, `COPYING`, the Python modules, `build_info.json`. The `.exe` itself
was replaced.

Worth recording because the alarming reading is the first one, and the
resolution — *hashed per-platform lockfiles are why the DLLs are identical* — is
a payoff from a decision made for an unrelated reason.

## The uninstall left the user's data alone

This is the half that matters, and the one no test can reach: `[Files]` writes
only to `{app}` and there is no `[UninstallDelete]`, so Inno's uninstaller
removes what its own log lists and nothing else. `tests/test_packaging.py`
asserts the template's directives, but a test that reads an `.iss` cannot prove
what the uninstaller actually did.

Removed: `{app}`, the registry record, the Start-Menu shortcut.

Kept: the `PaleoBytes` Start-Menu **group**, correctly — CTHarvester is still
in it, and Inno removes a group only when it empties. `PaleoBytes\CTHarvester`
was untouched, which is the family-directory arrangement working rather than
one app's uninstaller taking a sibling's directory with it.

Survived, which is the whole test:

- `preferences.json` under `%LOCALAPPDATA%\PaleoBytes\PTMGenerator2`, with
  every value;
- the dated log under `%USERPROFILE%\PaleoBytes\PTMGenerator2\logs`;
- the legacy `PTMGenerator2.ini` in Roaming, from 2024-12, which the migration
  copies from and never deletes.

**The devlog 014 split is what makes this true.** Had settings lived under the
install directory — the arrangement that was nearly adopted, and reverted the
same day across two sibling projects — an uninstall would have taken them. It
was argued from first principles at the time; it is now observed.

## The one comment that was wrong

Found while checking whether the `.exe` had been replaced. `PTMGenerator2.spec`
said the version was read from `version.py` "for the Windows file properties".
It never was: `EXE()` takes no `version=`, so there is no `VS_VERSION_INFO`
resource. Measured on the installed binary, with a bundled Qt DLL as a control:

    VS_VERSION_INFO present: False        <- PTMGenerator2.exe
    VS_VERSION_INFO present: True         <- Qt5Core.dll

Two options were written down: stamp it, or delete the claim. **Deleted**, and
the reasoning recorded in the spec itself so nobody re-adds it. A Windows
`FILEVERSION` is four integers, which a SemVer pre-release does not fit —
`0.2.0-beta.1` would become `(0, 2, 0, <build>)` with the real string relegated
to `ProductVersion` — and the About dialog now answers "which build is this"
precisely, including the commit, with a button that copies it. Stamping would
have added a lossy second answer to a question already answered well.

The claim had survived three releases. Nobody checks a comment, which is why
the fix is a comment that says what the file *does not* do and why.

## What this does not settle

The high-resolution capture, still. The upgrade and uninstall are the installer
*lifecycle*; the release gate is the fitter's headroom, and it is untouched by
any of this.

And this was one machine, one path: alpha.3 → beta.1 on Windows with the same
user. Not tested: a machine with no previous install (the case that carries the
most regression risk for every *new* user), an install under a different
account, or a downgrade.
