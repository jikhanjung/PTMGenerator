# P02 — Fitting PTMs in-process

**Written**: 2026-07-28
**Against**: v0.2.0-alpha.2
**Status**: plan, not started

A plan, not a record. The entries numbered 003–009 describe work that happened;
this describes work that has not. It follows P01's convention for that.

---

## Why

`PTMfitter.exe` is a 32-bit Hewlett-Packard binary from 2001. Measured
(devlog 009):

    6000x4000 = 24MP x  9 images    OK
    6000x4000 = 24MP x 50 images    OK
    8000x6000 = 48MP x  9 images    FAIL: "Memory Allocation error. size: 48"

**Image size, not image count.** Fifty 24MP images are fine; nine 48MP images
are not. The ~2 GB address space of a 32-bit process is the ceiling, and the
coefficient buffer grows with pixels.

This is not a future concern. A 45MP body is already over the line, and the
current generation of full-frame cameras is mostly at or past it. The
application cannot produce a PTM from the camera someone is most likely to
attach to it.

Two further things go away with the dependency:

- **The path workarounds.** Everything in `core/ptm_builder.py` about bare
  filenames, ANSI codepages and staging directories exists because of that
  binary's parser. All of it becomes dead code.
- **The Windows-only tie.** The rest of the application already runs on Linux
  and macOS — the test matrix proves it — and PTMfitter is the only reason a
  capture cannot be fitted there.

## What a PTM actually is

Per pixel, PTM stores the coefficients of a biquadratic in the light direction,
so that luminance can be re-evaluated for any light:

    L(u, v) = a0*u² + a1*v² + a2*u*v + a3*u + a4*v + a5

where `(u, v)` are the first two components of the (unit) light vector — which
is exactly what the `.lp` file already carries, one per image.

For each pixel that is an ordinary linear least squares of `N` observations
(one per image) on six unknowns. The design matrix is the same for every
pixel — it depends only on the light directions — so it is built once,
pseudo-inverted once, and applied to every pixel as a single matrix
multiplication. numpy does this in a few lines.

The `LRGB` variant that `PTMfitter.exe` emits fits the six coefficients to
*luminance only*, and stores an unmodulated RGB colour per pixel alongside.
That halves the work and the file size versus fitting three sets of
coefficients.

## The file format

The HP technical report (HPL-2001-104) is the nominal specification, but the HP
Labs site is gone. What settles it instead is a **working C implementation**:
`cceh/rti`'s `rti-builder` (`ptmlib.c`, `ptm-encoder.c`), which both reads and
writes PTMs. That is better than the PDF for this purpose — it is what actually
produces files the viewers accept.

Confirmed from `ptm_write_header` and cross-checked against a real 8×6 output
from the shipped `PTMfitter.exe`:

    PTM_1.2\n
    PTM_FORMAT_LRGB\n
    <width>\n
    <height>\n
    <6 floats>  \n      scale, one per coefficient
    <6 ints>    \n      bias,  one per coefficient
    <binary payload>

**Coefficient order** is fixed by `ptm_coefficients_t`:

    cu²  cv²  cuv  cu  cv  c1

**Payload layout** for LRGB: all six coefficients interleaved per pixel for
`width × height × 6` bytes, then RGB interleaved per pixel for
`width × height × 3`. Two blocks, not nine bytes per pixel throughout.

**Rows run bottom to top.** `ptm-encoder.c` flips each source image
vertically while reading it:

```c
size_t flipped_y = (info.height - y - 1);
```

This is exactly the sort of thing that produces a plausible but upside-down
result, silently.

**Quantisation** is per coefficient, over the whole image, from
`ptm_scale_coefficients` — note "over the whole image", which is what makes
banding awkward:

```c
scale[i] = (max[i] - min[i]) / 256.0f;
bias[i]  = -256.0f / (max[i] - min[i]) * min[i];
...
*s = CLIP ((*u * inv_scale[n]) + bias[n]);
```

So the encoder needs the min and max of each coefficient across every pixel
before it can write any of them. Two ways to live with that while banding:

* **hold the unquantised coefficients** — 48e6 × 6 × 4 bytes ≈ 1.1 GB, against
  the 7.2 GB the source images would take; or
* **two passes** — cheap in memory, but it decodes every image twice, and
  decoding is 96% of the runtime. That makes it roughly a 2× slowdown to save
  1.1 GB.

The first looks right on those numbers. Confirm in phase 3 rather than assuming.

The reference also uses LAPACK least squares with the pseudo-inverse computed
once and applied per pixel with `sgemv` — the same shape as the numpy plan
here, which is reassuring.

## Two references, and they are not the same kind of thing

An earlier draft of this plan named `PTMfitter.exe` as the thing to match
byte for byte. That was wrong, and the reason matters:

**Its source is not available.** Byte-identity to a black box is not something a
reimplementation can be *written* towards — only stumbled into. And when the
output differed there would be nothing to read to find out why.

So the two references have different jobs:

- **`rti-builder` is the implementation reference.** Open C, so its header
  writing, coefficient order, row flip and quantisation can be matched
  deliberately and any difference diagnosed by reading it.
- **`PTMfitter.exe` is a behavioural oracle.** It cannot be read, but its inputs
  are entirely under our control, so its behaviour can be *characterised by
  experiment* — and it has to be, because it is what produced every existing
  capture.

### What the probes already established

Nine identical images under nine different lights, colours chosen per pixel
column, JPEG written at 4:4:4 so the fitter sees the colours intended:

| input RGB | stored RGB | c1 |
|---|---|---|
| (255, 0, 0) | (254, 0, 0) | 255 |
| (200, 100, 50) | (200, 100, 50) | 255 |
| (128, 128, 128) | (128, 128, 128) | 255 |

- The payload is exactly `w × h × 9` bytes, no remainder. The byte that was
  unaccounted for earlier was a miscount of the header, not a real field.
- **RGB is interleaved per pixel and stores the input colour verbatim** — not
  normalised, not reordered.
- **c1 comes back as 255 for every pixel regardless of its colour.** With the
  illumination constant across images the luminance is constant, so a raw fit
  would put the pixel's luminance in c1. It does not: the luminance is
  **normalised per pixel**. The magnitude of the colour lives entirely in the
  RGB block, and the polynomial carries only the *shape* of the variation.

That last one is the point. It is a real behaviour that has to be reproduced,
it is not visible in `rti-builder`'s code, and no amount of reading the format
specification would have revealed it. It came out of one designed experiment.

The first attempt at that experiment was also wrong, which is worth recording:
the JPEGs were written with default chroma subsampling, so (255,0,0) reached
the fitter as (90,91,0) and the "stored RGB" looked like nonsense. The probe has
to control the input, including the encoder's defaults.

### Still to characterise

- **The luminance weights.** Constant images cannot show them, because the
  normalisation hides the magnitude. Needs images whose luminance varies with
  light in a known way — e.g. one channel at a time.
- **What the normalisation is exactly.** Peak to 255? Mean? Per pixel or per
  image?
- **Whether the fit is weighted or regularised**, and what happens with fewer
  images than coefficients.
- **The degenerate case.** With every coefficient identical across the image,
  `rti-builder`'s `(max - min)` is zero and its scale/bias formula divides by
  zero. The probe's header came back with round values — `1` and `0` for c1 —
  so PTMfitter has some fallback. Ours needs one too.

## Verification

The ladder, with the target corrected:

1. **Byte-identical to `rti-builder`** on small synthetic sets. This is
   achievable, because both implementations can be read.
2. **Behaviourally equivalent to `PTMfitter.exe`** on the same sets: same
   dimensions, same RGB block, coefficients within a stated tolerance, and the
   same reconstruction when evaluated at each input light. Not byte equality —
   that is not a reasonable thing to demand of a reimplementation of something
   unreadable.
3. **A real 24MP capture**, same criteria, against both.
4. **A 48MP set** — no reference at all, so the check is internal: evaluating
   the fitted polynomial at each input image's own light direction should
   reproduce that image to within quantisation error.
5. **Visual**: open the output of all three in a PTM viewer and compare.

Steps 1 and 2 belong in the test suite with committed fixtures. Step 4 is a
property test in spirit and should be written as one.

**If step 2's tolerance cannot be met**, that is the signal to stop and
characterise further rather than ship something that merely looks right.

## Is Python fast enough?

Measured on this machine (8 cores), extrapolated to a 48MP × 50-image set:

    the fit, pinv @ L      0.9 s
    quantisation           2.7 s
    JPEG decoding         54.6 s   single-threaded
                           6.8 s   across 8 cores

**The fit is 1.6% of the work.** The reason is that the light directions are the
same for every pixel, so the design matrix and its pseudo-inverse are computed
once and the whole image is then one `(6×N) @ (N×P)` multiplication — which
numpy hands to BLAS. That is *the same library the C reference calls* through
`cblas_sgemv`. Python issues the call; the arithmetic happens in the same
compiled code either way. There is no per-pixel Python loop for an interpreter
to be slow in, and the quantisation is likewise a handful of numpy operations.

What actually costs time is libjpeg, which is the same C library whatever the
caller is written in, and which parallelises across images without effort.

For scale: `PTMfitter.exe` takes minutes on a 24MP set. A numpy implementation
across multiple cores is likely to be *faster* than the thing it replaces.

### So: not Rust, and not a C extension

Neither is justified by these numbers — it would mean rewriting 1.6% of the
runtime. `../CTHarvester` uses a Rust module because its hot loop is a per-pixel
traversal that does not reduce to a BLAS call; this problem does.

Revisit if, and only if:

- banded measurements come out materially worse than this projection, or
- decoding is parallelised and the total still misses the target.

Even then the first move is a faster decoder — `pyturbojpeg`, `pillow-simd` —
because that is where the time is. Rewriting the fit would be optimising the
part that is already fast.

## Memory

The reason for doing this at all, so it cannot be an afterthought.

A 48MP set of 50 images is 48e6 × 50 × 3 bytes ≈ 7.2 GB if held at once. It
must be processed in horizontal bands: read band *k* from all 50 images, fit,
write the band's coefficients, discard. Peak residency becomes
`band_height × width × N × 3` plus the output buffer, and band height is chosen
against a memory budget rather than hardcoded.

Pillow reads a JPEG lazily enough for this to work, but 50 open file handles
and 50 partial decodes per band needs measuring — a decode-per-band strategy
may be cheaper than keeping decoders alive. Measure before choosing.

The output itself is 9 bytes/pixel: 432 MB for 48MP, which is fine to build in
memory but should be streamed to disk band by band anyway, since nothing needs
it whole.

## Phases

Each phase ends with something demonstrable and tested. No phase depends on
guessing the next one right.

1. **Read the format.** A `.ptm` reader, checked against outputs from the real
   fitter. Reading first because it is how everything later is verified, and it
   is useful on its own for inspecting a bad fit. Much cheaper than it was
   before `rti-builder` was found — this is now transcription, not discovery.
2. **Fit, unbanded.** Whole-image least squares for images small enough to hold.
   Byte-compare against the reference on synthetic sets. This is the phase that
   establishes correctness.
3. **Band it.** The same fit, in horizontal bands, with a memory budget.
   Verified by producing identical output to phase 2 on the same input.
4. **Wire it in.** A preference selecting the fitter, defaulting to native, with
   `PTMfitter.exe` still selectable. Both paths tested.
5. **Retire the external fitter** once the native one has fitted real captures.
   That removes the path workarounds and the Windows tie, and is the point at
   which `core/ptm_builder.py` shrinks to almost nothing.

Phases 1–3 are self-contained and testable without any UI work at all, which is
what the `core/` boundary is for.

## Risks

- ~~**The format is not fully known.**~~ **Resolved 2026-07-28.** `cceh/rti`'s
  `rti-builder` is a working C reader *and* writer; the header, coefficient
  order, block layout, row order and quantisation are all read off it above.
  This was the largest risk in the plan and it is gone.
- **"Byte-identical" may be unachievable** for reasons that do not matter —
  summation order, `float` vs `double` in the original. Decide the tolerance
  when the first comparison is run, and write down the reasoning.
- ~~**Performance.**~~ **Measured, 2026-07-28** — see above. The fit is 0.9 s of
  a ~57 s job dominated by JPEG decoding, which parallelises. A real banded
  benchmark still belongs in phase 3, but the projection says this is not where
  the risk is.
- **numpy becomes a runtime dependency**, adding roughly 15 MB to the
  executable. Acceptable, but it is a real change to a build that is currently
  38 MB.
- **Scope.** This is the largest single piece of work the project has taken on.
  It is worth it because the alternative is an application that cannot process
  the cameras it is used with — but it should not be started in the same cycle
  as anything else.

## Not doing

- **Rewriting PTMfitter's other modes.** It supports RGB as well as LRGB, and
  fitting options this application has never exposed. Match what the
  application actually produces today: LRGB, quadratic.
- **Keeping bit-compatibility as a permanent goal.** It is a verification tool
  for the transition, not a constraint on the result.
- **A viewer.** Out of scope, however tempting once a reader exists.

## Open questions

- ~~Where does the specification live?~~ Answered: `cceh/rti` (`rti-builder/`)
  is a working implementation and is the reference. HPL-2001-104 is the nominal
  spec but HP Labs is offline; a copy exists in the Internet Archive if the
  prose is ever needed.
- ~~Is the fit weighted, and how is scale/bias derived?~~ Answered above:
  per-coefficient min/max across the whole image, mapped onto 0–255.
- ~~**Byte-identical to which implementation?**~~ Answered above: byte-identity
  to `rti-builder`, behavioural equivalence to `PTMfitter.exe`. Its source is
  not available, so byte-identity to it is not a target a reimplementation can
  be written towards.
- **Does the quantisation need the whole image first?** Yes, per the formula
  above, which the banding design has to accommodate. Accumulating float
  coefficients for 48MP is 48e6 × 6 × 4 bytes ≈ 1.1 GB, which is affordable but
  not free; a two-pass alternative trades memory for time. Measure both.
- Do the viewers in use accept a spec-conformant file that is not byte-identical
  to PTMfitter's? Worth checking before phase 2 sets its acceptance criterion.
