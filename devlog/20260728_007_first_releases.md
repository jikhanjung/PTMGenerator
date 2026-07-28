# Building before tagging, and the first two releases

## Date: 2026-07-28

The release workflow existed since devlog 004 and had never run. This entry is
about finding out what that meant.

## The question that changed the outcome

Asked before tagging: *is PyInstaller actually set up?*

It was — a spec updated for the core/ui split with `hiddenimports=['core','ui']`,
a `build` extra, three `requirements-build-*.lock` files, and a `release.yml`
step that ran it. What was not true is that any of it had **ever executed**.
`dist/` held one .exe from December 2024; PyInstaller was not even installed
locally.

So the first run of the build would have been *during a release*, and a failure
there leaves the tag already pushed and the release half-made.

A local build was run first. It succeeded, and the frozen binary passed
`--self-test` with `frozen: True`. That looked like enough.

## It was not enough

The build was then wired into a workflow that does not release
(`build.yml` → `reusable_build.yml`, also called by `release.yml` so there is
one definition rather than two that drift), and run on CI. It failed:

```
ValueError: Received icon image 'icons/PTMGenerator2.png' which exists but is
not in the correct format. On this platform, only ('exe', 'ico') images may be
used as icons.
```

**Linux ignores the icon entirely.** The local build passed because the platform
under test never looked at the thing that was wrong. Only the Windows leg — the
one that produces the artifact users actually download — could see it.

Fixed by converting the existing 512×512 PNG to a multi-size `.ico` (16, 32, 48,
64, 128, 256 — Windows picks a different one per context, and a single-size
icon renders blurry in most of them). Depending on Pillow being installed at
build time to convert the PNG would also have worked, but makes the shipped
artifact depend on a build-time conversion rather than a file in the tree.

`tests/test_packaging.py` now asserts the spec's build inputs: the icon
resolves, it is an `.ico`, it carries those sizes, the `datas` globs match
something, the entry point exists, and the name still comes from `version.py`.
None of that is exercised by running the application.

## Two lessons, and they are different

1. **Run the build before tagging.** This is the one the workflow now enforces.
2. **A green build on one platform says nothing about the platform that
   matters.** This one has no automation beyond the matrix already in place —
   it is why the matrix exists, and why the artifact is built on `windows-latest`
   rather than cross-compiled.

## The releases

`v0.2.0-alpha.1` then `v0.2.0-alpha.2`. Both went through the whole pipeline on
the first attempt, ~3½ minutes each:

    verify-version → test (lint, 3×smoke, 3×tests, translations)
                   → build (pyinstaller, --self-test) → publish

The version check is the step worth having: it refuses to build when the tag
disagrees with `version.py`, which is the "tagged v0.2.4 but forgot to bump"
mistake, caught before anything is published rather than after.

`0.2.0` rather than `0.1.3` because the release adds features (the no-controller
prompt, `--self-test`) and changes the on-disk encoding; alpha because the
serial error handling and the extracted capture loop have not been run against
real hardware.

### One thing was wrong, and was caught before the push

The tag message and the release notes had a stray `---` on the end. The section
regex stops at the next `## [`, which leaves the separator that sits *between*
changelog entries attached to the one before it. Fixed in both
`bump_version.py` and `release.yml`, the tag deleted and remade, then pushed.

Small, but it is the sort of thing that is annoying to fix after publication.

## Legacy capture tables

Not release work, but it landed in the same commit and matters more than the
rest of it.

Pinning `image_data.csv` to UTF-8 (devlog 006) fixed the cross-machine problem
and would have **stranded every table already on disk**, because those were
written in whatever the machine defaulted to — cp949 on Korean Windows.

Reading now falls back `utf-8-sig` → `cp949` → `latin-1`:

- utf-8 first, because cp949 would decode the same bytes into *different*
  characters. The order is what keeps a round-trip lossless, not just what makes
  it succeed.
- latin-1 last because it decodes any byte sequence, so the final attempt always
  succeeds. A legacy name may come back mangled, but the run opens — which beats
  refusing to load it.

A fix that only works for files written after the fix is not a fix.
