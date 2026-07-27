# core/ui split, CI and the release process

## Date: 2026-07-28

## Goal

Bring PTMGenerator2 up to the development process the sibling projects
(`../Modan2`, `../CTHarvester`) already run: a tested, linted codebase with a
cross-platform CI matrix, locked dependencies, and a tagged release that builds
the executable and publishes it.

The application is a single Windows executable driving an Arduino LED dome; the
Arduino firmware is a separate concern in `PTMController/`. So the process is
the sibling projects' minus the parts that only make sense for their scale.

## The split

`PTMGenerator2.py` was 1200 lines holding the serial protocol, the capture state
machine, the dome geometry, two file formats and both windows. Nothing below the
widgets could be tested without a `QApplication`, and the state machine could not
be exercised at all without waiting out real one-second ticks.

    core/   imports no PyQt5 — asserted in a subprocess by tests/test_smoke.py
      serial_controller.py  <ON,n> / <SHOOT,n> / <OFF>, port lifecycle
      capture_session.py    preparation, polling, retakes, giving up
      light_positions.py    the polar LED table -> unit vectors
      image_data.py         the capture table, its CSV, rebuilding from disk
      ptm_builder.py        .lp generation and the PTMfitter call
      resources.py          bundled-file lookup, frozen or not
      settings.py           preference keys, defaults, coercion
    ui/     main_window.py, preferences_window.py
    PTMGenerator2.py        entry point

The load-bearing decision is that `CaptureSession` takes the shutter and the file
poll **as arguments**:

```python
result = session.step(shoot=self.serial.shoot, poll=self.poll_for_image)
```

A whole 50-slot run, including retakes and timeouts, is then driven in
microseconds with recorders in their place. `core/capture_session.py` is at 100%
coverage as a result; the previous equivalent had none.

`CaptureSlot` is a `NamedTuple`, so the 4-tuple unpacking and comparisons
already spread through the code and tests kept working unchanged.

## What CI caught that local runs did not

Worth recording, because it is the entire argument for the matrix:

1. **`ModuleNotFoundError: No module named 'core'` on all three platforms.**
   The suite had only ever been run as `python -m pytest`, which puts the
   working directory on `sys.path`. CI ran a bare `pytest`, which does not.
   Fixed with `pythonpath = ["."]` in the pytest config so both work.

2. **A path test failing on Windows only.** It compared `lp_path_for()`'s output
   against an `os.path.join`-built suffix. `join` uses the native separator
   while `lp_path_for` returns whatever its input used, so on Windows it
   compared `specimen01\specimen01.lp` against `specimen01/specimen01.lp`. The
   test was wrong, not the code, but nothing on Linux could ever have said so.

3. **`mypy` caught a real name collision**: `CaptureSlot.index` shadowed
   `tuple.index()`. Renamed to `led_index`, which also reads better.

## Lockfiles

Per-platform, not `--universal`. The reason showed up on the first generation:
`pyqt5-qt5` stopped publishing Windows wheels after 5.15.2 while Linux and macOS
reach 5.15.19. A universal resolve pins one version for every platform and takes
down the Windows leg with "No matching distribution found"; the sibling project
had to patch around it with hand-written environment markers. Resolving once per
platform produced 5.15.19 for linux/macos and 5.15.2 for windows automatically,
with no markers.

## Rejected

- **Extracting the whole capture loop into `core`.** The status-bar messages,
  the table model updates and the image preview are genuinely Qt. The split is
  at the policy/rendering line: the session decides, `take_picture_process`
  renders.
- **Renaming `detect_irregular_intervals`** — again. It reads oddly for a
  function that rebuilds a capture table, but it is referenced from `CLAUDE.md`
  and the docs.
- **Sphinx `sphinx-intl` translation of the manual.** The sibling projects
  translate their manuals; here the application UI is translated but the manual
  is English-only for now. Tracked in `TODOs.md`.
- **`mypy` over `ui/`.** Needs PyQt5 stubs and a module-at-a-time cleanup.
  Tracked in `TODOs.md`.

## Numbers

| | Before | After |
|---|---|---|
| Largest file | 1217 lines | 530 (`ui/main_window.py`) |
| Tests | 0 that completed | 125 |
| Suite runtime | — | ~1.3 s |
| Coverage | — | 88% overall, `core/` 94–100% |
| CI | none | 3 OS x lint, smoke, tests, translations |
