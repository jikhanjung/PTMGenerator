# The alpha meets the rig

2026-08-03. No code changed. What changed is what is *known* about the code:
the largest untested surface in the project — everything between the serial port
and a finished PTM — was exercised against the real dome for the first time, and
it worked.

This entry exists because `HANDOFF.md` had said, for five days, that "the alpha
has never met an Arduino," and because the value of a run like this is lost if
what it did and did not cover is not written down the same day.

## What was run

The **v0.2.0-alpha.3 installer**, installed and launched — not `make run` from a
source tree. That matters: it is the first time the frozen, packaged build has
driven the hardware, so the run covers the PyInstaller bundle as well as the
code.

Four things passed:

- **Arduino control and the shutter.** `<ON,n>` / `<SHOOT,n>` / `<OFF>` over the
  real port, with the LEDs lighting and the camera firing. The serial protocol
  in `core/serial_controller.py` has only ever been driven by a fake until now.
- **The capture loop.** `core/capture_session.py` — the largest behavioural
  change of the last cycle, extracted out of the UI and tested exhaustively with
  fakes. What no fake could answer was whether the preparation and polling
  windows suit a real shutter and a real card write. They do.
- **Polling for the arriving image.** The one-second tick noticing a file that
  a camera and a tethering utility, not a test, put on disk.
- **The capture folder discovery.** The dated subfolder created under the
  monitored root during the session, picked up and shown (devlog 009).
- **The built-in fitter.** A PTM fitted in-process from a real capture, with no
  external `PTMfitter.exe` — the default since alpha.3 (devlog 010, P02 phase 4).

## What this does *not* settle

Two limits, stated plainly so neither gets read as more than it is.

**The fit was of a ≤24MP capture.** That is inside what the external
`PTMfitter.exe` handles, so it proves the built-in fitter is *correct on real
files* — the thing the synthetic tests could not prove — but not that it clears
the ceiling that motivated writing it. The 32-bit external fitter fails above
roughly 24 megapixels; a 45MP body exceeds it. Until a real capture at that size
is fitted, the headroom is known only from `ptm_fitter.memory_estimate` and a
measured 641 MB peak on synthetic 48MP data.

So **P02 phase 5 stays blocked.** Retiring `core/ptm_builder.generate` and the
staging directory, the `.lp` codepage rules, the whitespace check and the
exit-code-1 quirk is what the preference exists to make safe, and the case for
pulling the fallback is precisely the case that has not been demonstrated. The
prerequisite is unchanged: fit a real 40MP+ capture first. It needs a different
camera.

**The installer was installed, not exercised.** It installs and the installed
program runs. Untouched: installing over the top (the upgrade path), uninstalling,
and confirming afterwards that `preferences.json` and the dated log both survive
— they live outside the install directory, which the uninstaller removes
(devlog 014), and that separation has never been observed rather than reasoned
about.

Also still open, unchanged by this run: the serial *error* paths (unplugging the
board mid-run, starting a capture while the Arduino IDE holds the port), the
utf-8 fallback against a capture table an older build actually wrote on Korean
Windows, PTM generation from a Korean path on a Korean Windows desktop, and the
preferences migration from a real 0.1.2 `.ini`. These are in `TODOs.md`.

## What this run changes about the plan

The release gate was "verify the alpha against real hardware," a list of seven
items. The happy path — the part that decides whether the tool works at all —
has now been verified end to end on the shipped artifact, and the list collapses
to a single pivot:

**Shoot a high-pixel-count capture on the mirrorless body and fit it.** If a PTM
that the external fitter could never produce comes out correct, then
`PTMfitter.exe` has nothing left to fall back to, P02 phase 5 removes it, and
the version stops being a pre-release. One test, three consequences.

That is the plan as decided, and it is a reasonable one: the fitter is the only
component whose *reason for existing* is still unproven, and everything else on
the old list is failure handling rather than function.

Worth carrying forward alongside it, not as an objection: the remaining items do
not become verified by that capture. The serial error paths (unplugging the
board mid-run, starting a capture while the Arduino IDE holds the port), the
installer's upgrade and uninstall paths, the utf-8 fallback against a table an
older build actually wrote, and the preferences migration from a real 0.1.2
`.ini` are all still untried. A bad outcome in any of them is a confusing dialog
or a lost preference rather than a capture that cannot run — which is why they
do not block the release — but a first non-alpha release is also the first one a
second person installs over an existing copy. The upgrade-over-the-top and the
uninstall are cheap to run and worth doing in the same sitting as the high-res
capture. They stay in `TODOs.md` either way.
