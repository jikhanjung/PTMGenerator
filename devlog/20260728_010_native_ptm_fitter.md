# Fitting PTMs in-process — P02 phases 1–4

2026-07-28. Implements `devlog/20260728_P02_NativePtmFitter.md` up to and
including the UI. Phase 5 (deleting the external path) waits on real captures.

## The problem, restated

`PTMfitter.exe` is 32-bit and dies at 48 megapixels:

    6000x4000 = 24MP x 50 images   OK
    8000x6000 = 48MP x  9 images   FAIL: "Memory Allocation error. size: 48"

Size, not count. A 45MP body is already over the line. Everything below exists
so that ceiling is the machine's memory instead.

## What was built

| Module | What it is |
|---|---|
| `core/ptm_format.py` | PTM 1.2 LRGB container: read, write, quantise |
| `core/ptm_fitter.py` | The least-squares fit, batch and streaming |
| `core/ptm_builder.py` | `generate_native` beside the existing `generate` |
| `core/settings.py` | `FITTER`, defaulting to `native` |
| `ui/preferences_window.py` | The **PTM Engine** selector |
| `ui/main_window.py` | Dispatch, a progress dialog, and cancellation |

49 tests for the two new core modules, 9 more for the UI dispatch.

## Phase 1 — the container

Transcribed from `cceh/rti`'s `rti-builder` rather than guessed, then checked
against `tests/fixtures/reference_8x5.ptm`, which the real `PTMfitter.exe`
produced from twelve JPEGs committed beside it (52 KB in total).

Two things in the format are easy to get wrong and still produce a file that
opens:

- **Rows run bottom to top.** A reader that forgets is vertically mirrored, and
  no dimension check catches it. `test_rows_are_returned_top_down` correlates
  the stored RGB against the source both ways up and requires the flipped one to
  be *worse* — otherwise the test would pass on a fixture too symmetric to tell.
- **Each coefficient is quantised across the whole image**, so a byte is
  meaningless without that coefficient's scale and bias from the header.

The scale is rounded to the six decimals the header stores *before* being used
to quantise. Quantising against a scale the file cannot represent makes the
written file disagree with the values it was built from — a small effect, but a
gratuitous one.

`test_written_bytes_match_the_reference` was not required by the plan and is
true anyway: read the reference, write it back, compare bytes.

## Phase 2 — the fit

    L(u, v) = c0·u² + c1·v² + c2·uv + c3·u + c4·v + c5

The light directions are shared by every pixel, so the design matrix and its
pseudo-inverse are built once and applied to the whole image in one matrix
multiplication, which numpy hands to BLAS — the same library `rti-builder`
reaches for through `cblas_sgemv`.

**We do not match PTMfitter's bytes, and cannot.** `rti-builder` fits raw
luminance and divides the stored RGB by it; PTMfitter stores RGB verbatim and
normalises the luminance instead. Same least-squares problem, normalisation in
different places. So the acceptance criterion is reconstruction, not bytes:
evaluate both files at each input light and compare against the source image.

Ours is not worse. Correlation with the source is 0.995–0.9999 across the twelve
fixture lights, and our RMSE is lower on nine of the twelve.

`test_the_stored_colour_is_normalised_by_luminance` pins the difference
deliberately, so the divergence from PTMfitter reads as a decision rather than a
bug the next person tries to fix.

## Phase 3 — streaming, which replaced banding

The plan called for horizontal bands with a memory budget. Streaming is better
and simpler. The least squares decomposes into one rank-1 update per image:

    coefficients = solver @ L = Σᵢ outer(solver[:, i], L[i])

so nothing needs to hold more than one image at a time — and each image is
decoded *exactly once*, where banding re-decodes every image once per band.
Decoding is ~96% of the runtime, so banding would have cost roughly its band
count in wall-clock. Memory is bounded and the work goes down.

Getting the memory to the estimate took four rounds, each found by measuring
rather than reasoning (peak RSS, 48MP × 50 synthetic):

| | Peak RSS | What was wrong |
|---|---|---|
| First working version | 2369 MB | |
| | 1820 MB | `np.outer` materialised a (6, pixels) product per image |
| | 892 MB | whole-array `quantise` allocated ~6 full-res float copies |
| | 641 MB | a redundant `luminance_sum` accumulator |

Estimate: 672 MB. `memory_estimate` was itself wrong first — it counted the
buffers the algorithm conceptually needs rather than the ones it allocates, and
came out at half the measured figure, which is worse than not estimating at all.
`test_memory_estimate_counts_every_full_resolution_buffer` now pins it.

Two subtleties that only tests would have caught:

- **`for image in images` keeps two images alive.** The loop variable still
  references the previous image while the loader produces the next — 288 MB of
  overlap at 48MP. Replaced with an explicit `while True: next(images)` and a
  `del`. `test_only_one_image_is_alive_at_a_time` hands out weakref'd arrays and
  asserts the previous one has been collected; it failed when first written.
- **`quantise` silently mutated its caller's array** once `quantise_planes`
  became in-place. Both halves of the contract now have a test.

`fit` (batch) is kept for small sets and for testing: `test_streaming_agrees_
with_the_batch_fit` compares the two arrays element for element.

## Not Rust, not a C extension

Measured at 48MP × 50:

    JPEG decode   54.6 s   (6.8 s across 8 cores)
    the fit        0.9 s
    quantise       2.7 s

The fit is 1.6% of the runtime. Rewriting it in a faster language optimises the
part that is already free; the decoder is libjpeg either way. This is recorded
because "Python will be too slow" was the obvious objection and it turned out to
be measurably wrong.

## Phase 4 — wiring it in

`Preferences → PTM Engine`, defaulting to **Built-in**, with **PTMfitter.exe**
still selectable. The external path is kept for now because it is what the
built-in fitter is checked against, and because nothing has yet fitted a real
capture — the preference is what makes phase 5 safe to defer rather than rushed.

`generate_ptm_natively` shows a `QProgressDialog` driven by the fit's
`progress(done, total)` callback. Fifty full-size images take tens of seconds, so
a frozen window was not an option. The callback calls `processEvents` rather than
running the fit on a worker thread: that is the smaller change, it keeps Cancel
working, and the thread version is now in `TODOs.md` next to the capture loop,
which has the same problem. Cancelling raises through the fit and writes nothing.

Verified by running the app, not only the suite: 24 shots at 1200×800 through
the real window under the offscreen platform, `Saved …/run.ptm`, reconstruction
correlation 0.9949 against the first shot, progress dialog observed at 50%.

## What is not proven

**A real 48MP capture.** The whole motivation, and the one thing still untested
on real files — it needs a different camera. The 641 MB figure above is
synthetic data. Until that run happens, phase 5 stays open and `PTMfitter.exe`
stays selectable.

## The docs build broke on it

`api.rst` autodocs `core/`, and autodoc imports what it documents. `core/`
picked up numpy and Pillow with the fitter, so the manual build failed on
`No module named 'numpy'` — and with `-W`, a warning *is* the build. Both
packages are now named in `docs/manual/requirements.txt` with the reason.

Worth remembering as a rule rather than an incident: **a new dependency in
`core/` is a new dependency of the documentation.** Nothing else in the tree
imports `core/` from a separate environment.

While fixing it, the `from PIL import Image` inside `load_image` moved to module
level. It was function-local for no stated reason and Pillow is a declared
dependency.

## State

262 tests, 91.8% coverage, ruff and mypy clean. Manual updated in both
languages; six new UI strings translated.
