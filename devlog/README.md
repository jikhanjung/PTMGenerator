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
