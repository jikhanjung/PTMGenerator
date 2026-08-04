# devlog

Working notes, one file per piece of work. Newest last.

These are not documentation — the manual in `docs/manual/` and the guides in the
repository root are. A devlog entry records *why* something was done the way it
was: what was tried, what it broke, what was rejected. When a decision looks
wrong six months later, the entry is where the reasoning lives.

## Naming

    YYYYMMDD_NNN_short_topic.md

`NNN` is a running counter, so the entries sort chronologically and can be
referenced as "devlog 4". Two earlier entries predate this convention and use a
`P01` planning/implementation pair; they are left as they are rather than
renumbered, because commits reference them by name.

## Index

| # | Date | Entry |
|---|---|---|
| — | 2025-11-07 | [Image polling and PTM generation — plan](20251107_P01_ImagePollingAndPTMGeneration.md) |
| — | 2025-11-07 | [Image polling and PTM generation — implementation](20251107_P01_ImagePollingAndPTMGeneration_Implementation.md) |
| 003 | 2026-07-27 | [Repository cleanup and the first test suite](20260727_003_repository_cleanup_and_tests.md) |
| 004 | 2026-07-28 | [core/ui split, CI and the release process](20260728_004_core_ui_split_and_ci.md) |
| 005 | 2026-07-28 | [R01 — code quality audit against the shared guide](20260728_005_R01_code_quality_audit.md) |
| 006 | 2026-07-28 | [Acting on the R01 audit, and publishing the manual](20260728_006_audit_fixes_and_pages.md) |
| 007 | 2026-07-28 | [Building before tagging, and the first two releases](20260728_007_first_releases.md) |
| 008 | 2026-07-28 | [Translating the manual](20260728_008_korean_manual.md) |
| 009 | 2026-07-28 | [Watching for the capture folder, and what PTMfitter actually tolerates](20260728_009_capture_folder_and_ptmfitter_quirks.md) |
| P02 | 2026-07-28 | [Plan: fitting PTMs in-process](20260728_P02_NativePtmFitter.md) |
| 010 | 2026-07-28 | [Fitting PTMs in-process — P02 phases 1–4](20260728_010_native_ptm_fitter.md) |
| 011 | 2026-07-28 | [An installer, and somewhere to put the settings](20260728_011_installer_and_data_directory.md) |
| 012 | 2026-07-28 | [Auditing the documentation against the code](20260728_012_doc_accuracy_sweep.md) |
| 013 | 2026-07-28 | [Making mypy actually check `ui/`](20260728_013_mypy_over_ui.md) |
| 014 | 2026-07-28 | [Applying the PaleoBytes config-location convention](20260728_014_config_location_convention.md) |
| 015 | 2026-07-29 | [The log filename, and reviewing Modan2's data-directory plan](20260729_015_log_filename_and_p03_review.md) |
| 016 | 2026-07-29 | [The shared guides, referenced instead of copied](20260729_016_shared_guides_checkout.md) |
| 017 | 2026-08-03 | [The alpha meets the rig](20260803_017_first_hardware_run.md) |
| 018 | 2026-08-04 | [What the first real run showed](20260804_018_ui_fixes_after_the_first_run.md) |
| 019 | 2026-08-04 | [Auditing against the guide, and the two items the table could not hold](20260804_019_guide_audit_and_the_gates_nobody_checked.md) |
| 020 | 2026-08-04 | [The installer, installed over itself and then removed](20260804_020_installer_lifecycle_verified.md) |

P-series entries (`P01`, `P02`, …) are **plans**: work that has not happened
yet, written down before starting so the approach and the verification strategy
can be argued with. An entry describing work that *did* happen gets a number
instead.

R-series entries (`R01`, `R02`, …) are audits rather than changes: a review of
the whole tree against a standard, with the state found recorded separately from
what was then done about it. The convention comes from Modan2.

## Writing an entry

There is no template, but the useful ones answer:

- What was the problem, concretely? Include the error, the reproduction, the
  numbers.
- What was the root cause, as opposed to the symptom?
- What was changed, with file references.
- What was considered and rejected, and why. This is the part that stops the
  same idea being re-litigated.
- What is still open. If it is real work, it also belongs in `TODOs.md`.
