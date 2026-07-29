# The shared guides, referenced instead of copied

2026-07-29. No code changed. What changed is where this repository expects to
find the family-wide conventions, and the answer is deliberately **not "in this
repository."**

## The problem with the arrangement the guides themselves recommended

The shared guide set carries an instruction near the top: *"Copy this directory
into a project's `docs/` and adopt it as a contract."* That is what a portable
standard is supposed to say, and it is what this project would have done.

> **Same-day addendum.** That instruction has since been changed at the source —
> the guide READMEs now say to *reference* the directory rather than copy it. The
> quote is left as it stood when this decision was made, because the decision was
> a departure from the guidance at the time, and the correction came out of it.

Then the failure mode showed up in the source material, one day after the guides
were written. The file-locations guide had distilled a sibling project's plan for
making its data directory configurable, including a recommendation to split
storage — media in `Documents`, the database on fixed local storage. The next day
the upstream plan was **revised and that compromise was withdrawn**, on the
grounds that a data directory without its database is a pile of files named by
object id, so the half that gets backed up has no recovery value.

The guide did not know. It could not know: it is a generalization of a snapshot,
and the snapshot moved. **A guide can go stale before the thing it generalizes**,
and the stale part was a *"do this"* sentence rather than a piece of background.

Now multiply that by every project that took the "copy it in" advice literally.
Four copies, four staleness clocks, and the copies do not report in.

## What is here instead

`.guides/` — a symlink to a checkout of the shared guide set. `.gitignore`
covers it. `CLAUDE.md` names it in **Conventions** so an agent session finds it
without being told.

Consequences worth stating plainly:

- **Updating is `git pull` in the checkout.** There is one owner and no copies,
  so the drift above is structurally impossible rather than merely discouraged.
- **It is not committed here.** The guides are private; this repository is
  public. Committing them, or even copying them into `docs/`, would publish them
  — which is the same outcome as the publishing option that was considered and
  declined.
- **The link can dangle.** On a machine without the checkout, `.guides` resolves
  to nothing. This matters more than it sounds: a broken symlink reads as *an
  empty directory*, not as an error, so the failure looks like "the guides don't
  cover that." Hence the wording in `CLAUDE.md` — check the link before
  concluding the guides are silent.

## Setting it up on another machine

The checkout is a partial, sparse clone of the private docs repository —
`guides/` only, nothing else:

```
git clone --filter=blob:none --sparse <devdocs>
cd devdocs && git sparse-checkout set --no-cone '/guides/'
```

Then, from a sibling project directory:

```
ln -s ../devdocs/guides .guides
```

Three details are load-bearing, and each was found by getting it wrong first:

- **`--no-cone` is required.** Cone mode always materializes the files at each
  parent level, so the repository's root files come along with it. That is not a
  size problem (tens of KB) — it is that the pipeline scripts sitting next to a
  `guides/`-only checkout **look runnable**, and the docs repo's own `CLAUDE.md`
  would attach its unrelated instructions to any session opened there.
- **The pattern needs the leading `/`.** Non-cone patterns are gitignore-style,
  so a bare `guides` matches *at any depth* — it pulled in an unrelated
  `guides/` directory nested inside the archive. `'/guides/'` anchors it to the
  root. Without the anchor, a clone taken specifically to avoid the archive
  gets part of the archive.
- **Use a relative symlink target.** The sibling projects sit next to the
  checkout, and the absolute path differs per machine. Relative also survives
  moving the whole tree. On WSL over a Windows drive both forms work and Windows
  sees them as a junction (absolute) or a directory symlink (relative); the
  relative one keeps no drive letter.

`--filter=blob:none` is worth one caveat: the objects for the rest of the
repository are never fetched, so widening the checkout later needs the network.
For a machine that only reads the guides, that is the right trade.

## What this does not change

Nothing in `core/` or `ui/`, no dependency, no build step. The guides are
reference material for whoever is working here, not an input to the program.
This entry exists so the *absence* of a `docs/guides/` directory reads as a
decision rather than an oversight.
