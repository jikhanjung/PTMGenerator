# Dependabot's first batch, and the checks that had stopped running

2026-11-11. Dependabot had opened seven PRs on 2026-07-27, and nobody had
looked at them. Working through them turned up three problems in CI that had
been invisible for months.

## The PRs

| PR | Bump | Outcome |
|---|---|---|
| #7 | mypy `<2` → `<3` | Merged. mypy 2.4.1 is clean over `core/` and `ui/` |
| #6 | `actions/upload-artifact` 4 → 7 | Merged. `build.yml` was dispatched on the PR branch and produced the installer artifact |
| #3 | `codecov/codecov-action` 4 → 7 | Merged. The step it touched has since been removed; see below |
| #5 | `github/codeql-action` 3 → 4 | Merged. CodeQL ran green on v4; v3 is deprecated in December 2026 |
| #4 | `softprops/action-gh-release` 2 → 3 | Merged |
| #2 | `actions/download-artifact` 4 → 8 | **Open** |
| #1 | `actions/checkout` 4 → 7 | **Open** |

Every action bump was read against its release notes for changed inputs. None
needed a workflow edit:

- **Node 24.** Most of the majors are the move to Node 24, which GitHub-hosted
  runners already have. CI was logging "Node.js 20 is deprecated … forced to run
  on Node.js 24" for the old versions, so these bumps were due.
- **download-artifact v5** changed paths only for downloads *by ID*;
  `release.yml` downloads by name.
- **download-artifact v8** errors on a digest mismatch by default; that is
  wanted.
- **checkout v7** refuses fork checkouts under `pull_request_target` and
  `workflow_run`, neither of which is used here.

`release.yml`'s steps only run on a tag, so #2, #4 and #1's changes there are
checked by release notes, not by a run. The next release is their first real
test.

**Why #1 and #2 are open.** Once #4 had changed `release.yml`, GitHub refused to
merge #2: "refusing to allow an OAuth App to create or update workflow … without
`workflow` scope". The `gh` token has `repo` but not `workflow`. Merging a PR
whose head is behind main in a workflow file means GitHub writes a new version
of that file, and that needs the scope. A head that is current merges fine,
which is why the others went through. Dependabot ignored the rebase request, and
a force-push of a rebased branch was declined. Either of these finishes it:

- run `gh auth refresh -s workflow` and then merge, or
- press **Update branch** on the web and merge.

## mypy: a widened range is not an upgrade

#7's CI was green, but it proved nothing about mypy 2. The lockfiles still pinned
1.20.2:

- `uv pip compile` keeps an existing pin that still satisfies the range, so
  widening `<2` to `<3` changes no lock.
- `lockfiles-current` passes for the same reason.

The `.github/dependabot.yml` comment said that job "is what catches that". It
catches a range the lock no longer *fits*, not one it could now *exceed*. The
comment is corrected, and this branch upgrades mypy explicitly with
`--upgrade-package mypy`. That pulls in `librt` 0.16.0 and the new
`ast-serialize` 0.13.1.

## Security and CodeQL had been switched off

Neither workflow ran on any of the PRs, nor on the push that merged #7.
`gh workflow list --all` showed both as `disabled_inactivity`:

- GitHub turns off scheduled workflows after 60 days with no repository
  activity.
- Turning a workflow off stops its push and pull-request triggers too, not only
  the schedule.

The last runs were the scheduled ones on 2026-10-12. Both were re-enabled. HANDOFF
now says to check for this after a quiet spell.

## Then pip-audit failed: Pillow 12.3.0

Once Security ran again, `pip-audit` failed on all three runtime locks:

- Pillow 12.3.0 has 39 known vulnerabilities (PYSEC-2026-4326 … 4343 and the
  matching CVEs), all fixed in 13.0.0.
- `pyproject.toml` capped Pillow at `<13`, so Dependabot could not have offered
  the fix either.
- Main was in the same state; nothing had been checking.

The cap is now `<14` and Pillow is upgraded explicitly in all nine locks. Run
locally against the new dev lock:

- the full suite: 407 passed;
- mypy and `ruff check` / `ruff format --check`: clean;
- `pip-audit` over the linux, windows and macOS runtime locks: no known
  vulnerabilities.

Pillow is what decodes every capture for the built-in fitter, so this ships. It
is in `CHANGELOG.md` under Unreleased.

## Codecov never worked

The upload was refused on every run, on v4 on main exactly as on v7:
`Upload queued for processing failed: {"message":"Token required - not valid
tokenless upload"}`.

- There is no `CODECOV_TOKEN` secret.
- The organisation has not opted into tokenless uploads.
- `fail_ci_if_error: false` kept the step green, so nobody saw it.

The step is removed, along with the `coverage.xml` it consumed. Coverage is
enforced by `--cov-fail-under=85` on the Linux leg, which never depended on
Codecov.

Keeping the step would mean a third-party action downloading and running a CLI
on every push, for nothing. If a coverage dashboard is wanted later, add the
token *and* the step back together.

## PR docs builds cancelled each other

`docs.yml` put every run in one concurrency group, `pages`. A group holds one
running and one pending run, and a new pending run replaces the old one. So:

- the six Dependabot PRs rebased together cancelled each other's
  **Manual builds**;
- four of six showed as cancelled.

Only pushes to main deploy, so only they need the shared group. Pull requests
now get `docs-<ref>`, and a PR queues only behind its own earlier run.

## Not done

- **#1 and #2**, above. They need the user's token or the web UI.
- **CLAUDE.md and HANDOFF's command block still say "347 tests".** The suite is
  407. Left for whoever next edits those sections.
