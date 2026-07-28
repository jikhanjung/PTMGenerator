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
`ptm_scale_coefficients`:

```c
scale[i] = (max[i] - min[i]) / 256.0f;
bias[i]  = -256.0f / (max[i] - min[i]) * min[i];
...
*s = CLIP ((*u * inv_scale[n]) + bias[n]);
```

So the encoder needs the min and max of each coefficient across every pixel
before it can write any of them — which constrains the banding strategy below:
either two passes, or accumulate the coefficients unquantised and scale at the
end.

The reference also uses LAPACK least squares with the pseudo-inverse computed
once and applied per pixel with `sgemv` — the same shape as the numpy plan
here, which is reassuring.

## Verification

This is the part that decides whether the work is worth starting, and it is
unusually favourable here:

**`PTMfitter.exe` works up to 24MP, so it is a reference implementation for
everything below that line.** A native fitter can be checked against it byte
for byte on sets it can handle, and only then trusted on the sets it cannot.

The ladder:

1. **Byte-identical output** on small synthetic sets (8×6, 64×64) — proves the
   header, the quantisation and the ordering.
2. **Byte-identical, or bounded-difference, output** on a real 24MP capture.
   Exact equality may not survive floating-point ordering differences; if not,
   the acceptance criterion becomes a maximum per-coefficient deviation, chosen
   and justified, not discovered after the fact.
3. **A 48MP set** — no reference, so the checks are internal: the fit
   reproduces the input images at their own light positions to within
   quantisation error.
4. **Visual**: open both in a PTM viewer and compare.

Steps 1 and 2 belong in the test suite, with the reference `.ptm` committed as
a fixture for the small sets. Step 3 is a property test in spirit: for every
input image, evaluating the fitted polynomial at that image's light direction
should return approximately that image.

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
- **Performance.** PTMfitter takes minutes on a large set; a naive Python
  implementation could take much longer. The per-pixel work is a single matmul
  against a precomputed pseudo-inverse, so this should be fine, but a 48MP × 50
  benchmark belongs in phase 3, not at the end.
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
- **Byte-identical to which implementation?** There are now two references that
  need not agree with each other: the shipped `PTMfitter.exe` and `rti-builder`.
  They will differ at least in floating-point details, and possibly in the
  min/max derivation. Decide early which one is the target — `PTMfitter.exe`,
  since it is what has produced every existing capture.
- **Does the quantisation need the whole image first?** Yes, per the formula
  above, which the banding design has to accommodate. Accumulating float
  coefficients for 48MP is 48e6 × 6 × 4 bytes ≈ 1.1 GB, which is affordable but
  not free; a two-pass alternative trades memory for time. Measure both.
- Do the viewers in use accept a spec-conformant file that is not byte-identical
  to PTMfitter's? Worth checking before phase 2 sets its acceptance criterion.
