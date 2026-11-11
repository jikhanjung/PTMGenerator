# R02 — Porting to Rust and GPUI: a review

2026-11-11. A review, not a change. Nothing in the tree was modified. The
question was whether PTMGenerator2 should be rewritten in Rust with GPUI (the UI
framework Zed is built on), and if so how.

Web facts carry their source and the date the source showed. Anything marked
**[inference]** is reasoning, not something a source said. Version numbers are
as of the date above. They will go stale; the links will not.

The shared PaleoBytes guides (`.guides/`) were **not checked out** when this was
written, so whatever they say about the family's toolkit is not reflected here.
That should be checked before deciding. A family where every other app is PyQt
makes a single Rust app more expensive than it looks from inside this repository.

## 1. What there is today

| | |
|---|---|
| Language | Python 3.12, pinned to `>=3.12,<3.13` |
| GUI | PyQt5 5.15. Widgets used: `QMainWindow`, `QTableView` with `QStandardItemModel`, `QFileDialog`, `QMessageBox`, `QProgressDialog`, `QComboBox`, `QLineEdit` with validators, `QTimer`, `QTranslator` |
| Runtime dependencies | pyserial, numpy, Pillow, semver, platformdirs |
| Image I/O | Pillow, which wraps libjpeg(-turbo). JPEG in only. |
| PTM computation | `core/ptm_fitter.py`: a 6-coefficient biquadratic fit. The pseudo-inverse of the shared design matrix is built once, then streamed as one rank-1 update per image. |
| File formats | PTM 1.2 LRGB (`core/ptm_format.py`), `.lp`, `image_data.csv`, `preferences.json` |
| Size | `core/` 1,932 lines, `ui/` 1,435 lines, entry point 98 lines. **About 3.4k lines in total.** |
| Tests | 407 collected, 4,257 lines, running offscreen with no display. `core/` is Qt-free and asserted to be so. |
| Translations | Qt `.ts`/`.qm`, English and Korean. The manual is Sphinx, also in both languages, and autodocs `core/`. |
| Distribution | A PyInstaller onedir bundle wrapped in a per-user Inno Setup installer (`PrivilegesRequired=lowest`, fixed `AppId`) |
| OS | Ships for Windows only. CI tests Windows, macOS and Linux. |
| External tool | `PTMfitter.exe`, which is 32-bit, Windows-only and kept as a fallback. Its retirement is TODOs "Phase 5". |

### Where the time goes

`devlog/20260728_010_native_ptm_fitter.md` measured 48 MP × 50 images:

    JPEG decode   54.6 s   (6.8 s across 8 cores)
    the fit        0.9 s
    quantise       2.7 s

Decoding is about 94% of the run. The least-squares part — the bit "Rust will be
faster" is usually about — is under 2%. The decode is **currently sequential**:
the 6.8 s figure was a measurement of what parallel decoding *would* give, not
something the shipped code does.

A capture of 50 shots takes minutes of camera and LED time. The fit runs once,
at the end.

## 2. The Rust side

### Crates

| Need | Crate (latest) | Note |
|---|---|---|
| Serial | `serialport` 4.10.1 (2026-09-08) | The de facto standard. ~21M downloads. [crates.io](https://crates.io/api/v1/crates/serialport) |
| JPEG decode | `image` 0.25.10 (2026-03-10), `zune-jpeg` 0.5.15 (2026-03-26), `turbojpeg` 1.5.1 (2026-07-25) | `turbojpeg` binds the same libjpeg-turbo Pillow uses. `zune-jpeg` is pure Rust with SIMD. [image](https://crates.io/api/v1/crates/image), [zune-jpeg](https://crates.io/api/v1/crates/zune-jpeg), [turbojpeg](https://crates.io/api/v1/crates/turbojpeg) |
| Least squares | `nalgebra` 0.35.0 (2026-05-24) or `faer` 0.24.4 (2026-06-24) | `SVD::pseudo_inverse` in nalgebra; `qr().solve_lstsq` in faer. faer moved to Codeberg; GitHub is a mirror. [nalgebra SVD](https://docs.rs/nalgebra/latest/nalgebra/linalg/struct.SVD.html), [faer](https://faer-rs.github.io/solve.html), [faer-rs repo](https://github.com/sarah-quinones/faer-rs) |
| Config paths | `directories` 6.0.0 / `dirs` 7.0.0 | Same role as platformdirs. [directories](https://crates.io/api/v1/crates/directories), [dirs](https://crates.io/api/v1/crates/dirs) |
| Folder watching | `notify` 8.2.2 (2026-11-08) | The app polls today; this is optional. [crates.io](https://crates.io/api/v1/crates/notify) |
| Translations | `rust-i18n` 4.2.4 (2026-09-29), `fluent` 0.17.0 (2025-05-23) | Neither reads Qt `.ts`; the Korean catalogue would be converted. [rust-i18n](https://crates.io/api/v1/crates/rust-i18n), [fluent](https://crates.io/api/v1/crates/fluent) |
| Native dialogs (if not GPUI) | `rfd` 0.18.0 (2026-11-07) | GTK or the XDG portal on Linux. [rfd](https://github.com/PolyMeilex/rfd) |
| Python bridge | `pyo3` 0.30.1 (2026-10-14), `maturin` 1.16.0 (2026-10-29) | For a Rust core called from the existing app. [pyo3](https://crates.io/api/v1/crates/pyo3), [maturin](https://crates.io/api/v1/crates/maturin) |
| Installer | Inno Setup (unchanged), or `cargo-packager` 0.11.8 (2025-11-27) | Inno wraps any `.exe`, so the template, the `AppId` and the per-user install carry over **[inference]**. Whether cargo-packager's NSIS output can be per-user was not confirmed. [cargo-packager](https://github.com/crabnebula-dev/cargo-packager) |

### What would be written by hand

Nothing here exists as a crate, but none of it is large:

- **The PTM 1.2 container.** It is 242 lines in Python, and
  `tests/fixtures/reference_8x5.ptm` gives a byte-exact target.
- **The fit.** It is a 6×N pseudo-inverse and a streaming accumulation.
- **`.lp` writing** and `POLAR_LIGHT_LIST`.
- **The `<ON,n>`/`<SHOOT,n>` framing.**
- **The capture state machine.**

### How much faster

There are three parts to the run:

- **The fit (0.9 s).** A 6-coefficient solve per pixel is bound by memory, not by
  GEMM, so faer's matmul advantage over OpenBLAS is irrelevant here. faer's own
  benchmark shows it ahead only at large n; at n ≤ 64 the libraries are within
  about 1.3x of each other [faer-core docs](https://docs.rs/crate/faer-core/latest).
  Nothing to gain.
- **Decode (54.6 s).** Per core, Rust with `turbojpeg` is the same libjpeg-turbo
  Pillow calls. A 2025 benchmark of Python decoders put a libjpeg-turbo-based
  Rust decoder (kornia-rs) at 1034 images/s against Pillow's 775 on an M4 Max
  [arXiv 2501.13131](https://arxiv.org/html/2501.13131v1). zune-jpeg's
  documentation claims about 1.5x libjpeg-turbo
  [docs.rs](https://docs.rs/crate/zune-jpeg/0.2.0), but no independent
  comparison against Pillow was found. Expect 1.0–1.5x per core.
  - The large win is **parallelism, which Python can already have**. Pillow
    releases the GIL while decoding (`ImagingSectionEnter` in its C decoder), so
    a thread pool reaches most of the 8-core figure without leaving Python
    **[inference, from Pillow's source; experiment 1 confirms it]**.
- **Quantise (2.7 s).** This is several numpy passes over full-resolution
  arrays. A fused per-pixel loop in Rust would plausibly be several times faster
  and allocate less **[inference]**. That is the one place where Rust clearly
  helps, and it is about 5% of the run.

**[inference]** The realistic comparison is not 58 s against Rust. It is
parallel Python at roughly 10 s against parallel Rust at roughly 6–8 s, after
minutes of capture. Memory is where Rust is a clearer win: fused loops and no
temporaries, against Python's measured 641 MB at 48 MP.

## 3. GPUI today

### Maturity and distribution

- **The registry is stale.** The official crate is `gpui` **0.2.2, published
  2025-10-22**, with nothing since
  ([crates.io](https://crates.io/api/v1/crates/gpui)). Zed's in-tree crate still
  says 0.2.2 while the code moves on in git
  ([Cargo.toml](https://raw.githubusercontent.com/zed-industries/zed/main/crates/gpui/Cargo.toml)).
- **The practical options are a git dependency on the Zed monorepo, or
  `gpui-pre`.** `gpui-pre` is Longbridge's third-party snapshot, at 0.3.12
  (2026-11-09), released roughly weekly
  ([crates.io](https://crates.io/api/v1/crates/gpui-pre)). No official Zed
  endorsement of it was found.
- **The README promises churn.** It says "still pre-1.0" and "There will often
  be breaking changes between versions"
  ([README](https://github.com/zed-industries/zed/blob/main/crates/gpui/README.md)).
  gpui.rs says "For the near future, GPUI is tied to Zed"
  ([gpui.rs](https://www.gpui.rs/)). Zed reaching 1.0 on 2026-04-29 is the
  editor's version, not GPUI's ([Zed blog](https://zed.dev/blog/zed-1-0)).
- **The documentation is the Zed source.** The README's advice is to "read the
  Zed source code or drop a question in the Zed Discord". docs.rs coverage for
  0.2.2 is complete as reference, but only 10 of 46 items have examples, and it
  is a year old ([docs.rs](https://docs.rs/crate/gpui/latest)).

### Platforms

- **Windows** renders with DirectX 11 and DirectWrite. Zed for Windows went
  stable on 2025-10-15, with "we know the work is not over"
  ([Zed blog](https://zed.dev/blog/zed-for-windows-is-here)). DX11 was chosen
  because Vulkan failed on some users' machines
  ([progress report](https://zed.dev/blog/windows-progress-report)).
- **macOS** renders with Metal, and the `font-kit` feature is required or no text
  is drawn ([README](https://raw.githubusercontent.com/zed-industries/zed/main/crates/gpui/README.md)).
- **Linux** renders through wgpu since PR #46758 (2026-02-13), which replaced
  Blade ([PR](https://github.com/zed-industries/zed/pull/46758)). It needs a
  Vulkan- or GL-capable GPU. This matters little, since the app ships for
  Windows.

**[inference]** The lab PC that drives the dome is the machine that matters. A
GPU-rendered UI on an old office PC, or over Remote Desktop, is a risk Qt's
software paths do not carry. It is cheap to test (experiment 3).

### Widgets this app needs

| Need | Core GPUI | gpui-component / "GPUI Kit" |
|---|---|---|
| File and folder picker | Yes. `App::prompt_for_paths`, native and async ([docs](https://docs.rs/gpui/0.2.2/gpui/struct.App.html)) | — |
| Message dialog | Yes. `Window::prompt` ([docs](https://docs.rs/gpui/0.2.2/gpui/struct.Window.html)) | Dialog, AlertDialog |
| Text input, buttons, combo box | **No.** Only `div` and a low-level input handler | Input, NumberInput, Button, Select |
| Table (the capture list) | No | Table, DataTable, VirtualList |
| Progress | Not confirmed in core | Progress, Spinner |
| Image preview | Yes. `img()` takes PNG, JPEG, WebP and others, or an in-memory **BGRA** `RenderImage` ([docs](https://docs.rs/gpui/0.2.2/gpui/struct.RenderImage.html)) | Image |
| i18n | None. Zed's own localisation is an open RFC ([#43592](https://github.com/zed-industries/zed/discussions/43592)) | `rust-i18n` behind `set_locale` |

**This app therefore depends on gpui-component, not just on GPUI.**
gpui-component has been renamed GPUI Kit. It is at 0.9.1 (2026-11-09), released
weekly, has about 20k stars, and pins `gpui-pre =0.3.12` exactly
([repo](https://github.com/longbridge/gpui-component),
[crates.io](https://crates.io/api/v1/crates/gpui-component/0.9.1/dependencies)).
Zed's own `ui` crates are GPL, so they are not a source to copy from (a
third-party claim, not verified:
[gpui-book](https://vanuan.github.io/gpui-book/appendix_a.html)).

### Use outside Zed

awesome-gpui lists about 129 apps, mostly developer tools
([awesome-gpui](https://github.com/zed-industries/awesome-gpui)). Two stand out:

- **Longbridge Pro**, a commercial trading app, is the main production user.
- **Baudrun**, a serial terminal on GPUI and GPUI Kit, is the closest analogue to
  this app and the best evidence that serial plus GPUI works on Windows
  ([Baudrun](https://github.com/packetThrower/Baudrun)).

### Against the alternatives

| | Version | Fits this app because | Risk |
|---|---|---|---|
| **GPUI + GPUI Kit** | gpui 0.2.2 (registry) / gpui-pre 0.3.12 | Polished, fast, a full widget kit, native dialogs | No stable release; follows Zed's churn; two third-party layers (gpui-pre, Kit) between the app and upstream; documentation is the Zed source |
| **egui / eframe** | 0.37.0 (2026-10-15) | A form, a table, a progress bar and a preview are egui's sweet spot. Simple threading model; in-memory RGB images via `ColorImage::from_rgb`; dialogs via rfd. ~24M downloads | Breaking releases ("interfaces are still in flux"); immediate-mode looks less native ([README](https://raw.githubusercontent.com/emilk/egui/main/README.md)) |
| **Slint** | 1.18.1 (2026-09-21) | A stable 1.x API, a declarative UI file, built-in translation tooling | Royalty-free licence requires an AboutSlint widget or a "Made with Slint" badge ([licence](https://raw.githubusercontent.com/slint-ui/slint/master/LICENSES/LicenseRef-Slint-Royalty-free-2.0.md)) |
| **iced** | 0.14.0 (2025-12-07) | Elm-style architecture suits the capture state machine | Self-described "experimental software" ([README](https://raw.githubusercontent.com/iced-rs/iced/master/README.md)) |
| **Tauri** | 2.12.5 (2026-10-21) | Any web UI; a mature packager | Brings a web stack and WebView2 into a small hardware tool ([webviews](https://v2.tauri.app/reference/webview-versions/)) |

**Reasons to pick GPUI anyway.** The UI would look better than egui's. There is
a Windows serial-terminal precedent. It would line up with Zed if PaleoBytes
plans more Rust desktop apps, and that is the one strategic reason.

**[inference]** None of these reasons is about this app's needs. The UI is a form,
a table and a progress dialog. GPUI is the most capable option and the least
stable one, and stability is what a lab tool used a few times a year needs most.

## 4. The work, and how to stage it

### What a full rewrite costs

What dominates is not the 3.4k lines. It is everything around them that was
built and verified for Python:

- **Tests.** 407 tests, 4.3k lines, re-expressed. The hypothesis property tests
  map to `proptest`.
- **Packaging.** PyInstaller and its spec (devlog 007's Windows-only failure is a
  PyInstaller lesson that would no longer apply), the self-test, version handling
  (`version.py`, `bump_version.py`, the release gate), and three lockfiles
  replaced by `Cargo.lock`.
- **Translations.** The Qt `.ts` translation pipeline and its CI drift check.
- **The manual.** It autodocs `core/` and is in two languages; the API page
  becomes rustdoc.
- **Preferences.** The `.ini` → JSON migration, which must keep reading the
  existing `preferences.json`.
- **Hardware verification**, from devlog 017 and TODOs: this cannot be
  automated, and all of it repeats.
- **The installer lifecycle** (devlog 020), which also repeats.

**[inference]** Order of magnitude: weeks rather than days, with hardware and
installer re-verification as the part that cannot be compressed.

### Options

- **A. Stay in Python and take the cheap wins.**
  - Parallel decode in a thread pool.
  - The `QThread` worker already in TODOs.
  - Finish Phase 5.

  Expected: 48 MP × 50 goes from about 58 s to about 10 s. Memory is the cost:
  each in-flight 48 MP image is about 144 MB.
- **B. A Rust core behind PyO3.** Port `ptm_format` and `ptm_fitter` as a crate,
  with a byte-exact check against `reference_8x5.ptm` and the existing Python
  tests as the oracle.
  - Gains: quantise, memory, and a core that a later Rust UI can reuse.
  - Costs: a Rust toolchain in CI, and maturin wheels per platform.
  - The `core/`/`ui/` split is what makes this cheap.
- **C. A full rewrite in Rust with GPUI and GPUI Kit.**
- **D. A full rewrite in Rust with egui (or Slint).**

If Rust is the goal, go **B → D/C**: core first, UI second, never all at once.
The Python app stays shippable throughout, and the fitter is checked against
itself before the UI changes underneath it.

## 5. Recommendation

**Do not port to GPUI now.**

- **Performance does not justify a port.** The bottleneck is JPEG decoding,
  which is the same library in either language, and the parallelism that fixes
  it is available in Python (option A).
- **GPUI is not ready to be a dependency of a lab tool.** It has had no
  registry release in over a year. It is usable in practice only through a
  third-party snapshot, under a third-party widget kit that pins that snapshot
  exactly. Its README promises frequent breaking changes and points to the Zed
  source as the documentation.
- **If there are other reasons to move to Rust**, such as one small binary, no
  Python runtime or PyInstaller, sharing code with other PaleoBytes tools, or
  learning Rust:
  - Start with **option B**.
  - Choose the UI later, **egui or Slint ahead of GPUI**, unless the family is
    standardising on GPUI.
  - Revisit GPUI when `gpui` is published to crates.io on a regular cadence
    again.

### Small experiments before deciding

Each experiment is a throwaway branch or scratch crate, not a change to `main`.

1. **Parallel decode in Python (half a day).**
   - Do: decode 50 synthetic 48 MP JPEGs through a `ThreadPoolExecutor`.
   - Measure: wall-clock and peak RSS against the sequential path.
   - Outcome: if it lands near 7–10 s, the performance case for Rust is closed.
2. **The Rust fitter (1–2 days).**
   - Do: decode with `turbojpeg` and with `zune-jpeg`, run the files in parallel
     with `rayon`, accumulate in a stream and write PTM 1.2.
   - Check correctness the way devlog 010 did: reconstruction correlation
     against the Python fitter's output on the same captures, plus a byte-exact
     read/write round trip of `reference_8x5.ptm`.
   - Measure: wall-clock and RSS at 48 MP × 50 against experiment 1.
3. **A GPUI viewer on the real lab PC (1–2 days).** Build one window with GPUI
   Kit that does the following:
   - picks a folder;
   - lists available serial ports with `serialport`;
   - shows a 48 MP JPEG downscaled;
   - drives a progress bar from a background thread;
   - shows Korean text.

   Build it with `gh workflow run` on a Windows runner, and run it on the dome's
   PC, including over Remote Desktop if that is ever used. Record the binary
   size, startup time and memory.
4. **The same window in egui (1 day).** Compare the two on effort, size and
   look.
5. **Churn (no effort, one month).** Pin the GPUI spike, bump `gpui-pre` and GPUI
   Kit a month later, and count what broke. That measures the cost GPUI's
   README warns about, against this app's actual surface.
