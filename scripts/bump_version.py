#!/usr/bin/env python3
"""Bump the version, roll the changelog, and tag the release.

`version.py` is the single source of truth: pyproject.toml, the PyInstaller
spec's output filename and the release workflow's tag check all derive from it
(see tests/test_version_consistency.py). This script automates the release-tag
step so the version, the CHANGELOG entry, the commit and the `v<version>` tag
can never drift out of sync.

Flow:

    1. Choose the new version (bump a part, or set it explicitly).
    2. version.py is rewritten.
    3. CHANGELOG.md's "## [Unreleased]" section is renamed to
       "## [<version>] - <date>" and a fresh empty Unreleased section is added.
    4. version.py + CHANGELOG.md are committed as "chore: release v<version>".
    5. An annotated tag "v<version>" is created on that commit.
    6. With --push, the commit and tag are pushed, which triggers release.yml
       (verify version, run the test matrix, build the exe, publish a release).

Commands — the same vocabulary the sibling projects use:

    major / minor / patch          1.2.3 -> 2.0.0 / 1.3.0 / 1.2.4
    premajor / preminor / prepatch start a pre-release cycle; the optional
      [token]                      token is alpha (default), beta or rc
                                   1.2.3 -> preminor beta -> 1.3.0-beta.1
    prerelease                     bump the pre-release number
                                   1.3.0-beta.1 -> 1.3.0-beta.2
    stage <alpha|beta|rc>          move stage, resetting the number to 1
                                   1.3.0-alpha.4 -> stage beta -> 1.3.0-beta.1
    release                        drop the pre-release suffix
                                   1.3.0-rc.2 -> 1.3.0
    --set X.Y.Z                    an explicit version

Examples:
    python scripts/bump_version.py patch            # 0.1.2 -> 0.1.3
    python scripts/bump_version.py preminor beta    # 0.1.2 -> 0.2.0-beta.1
    python scripts/bump_version.py prerelease       # 0.2.0-beta.1 -> 0.2.0-beta.2
    python scripts/bump_version.py stage rc         # 0.2.0-beta.3 -> 0.2.0-rc.1
    python scripts/bump_version.py release          # 0.2.0-rc.1 -> 0.2.0
    python scripts/bump_version.py patch --push     # also push commit + tag

Dry run:
    python scripts/bump_version.py patch --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

try:
    import semver
except ImportError:
    sys.exit("error: the 'semver' package is required (pip install semver)")

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "version.py"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r'^(__version__\s*=\s*")([^"]+)(")', re.MULTILINE)
UNRELEASED_RE = re.compile(r"^## \[Unreleased\]\s*$", re.MULTILINE)

TOKENS = ("alpha", "beta", "rc")


def current_version():
    match = VERSION_RE.search(VERSION_FILE.read_text(encoding="utf-8"))
    if not match:
        sys.exit(f"error: no __version__ found in {VERSION_FILE}")
    return match.group(2)


def next_version(current, command, token=None, explicit=None):
    """Apply `command` to `current` and return the new version string."""
    if explicit:
        semver.VersionInfo.parse(explicit)  # validate
        return explicit

    version = semver.VersionInfo.parse(current)
    if command in ("major", "minor", "patch"):
        return str(getattr(version, f"bump_{command}")())
    if command in ("premajor", "preminor", "prepatch"):
        part = command[3:]
        return str(getattr(version, f"bump_{part}")().bump_prerelease(token or "alpha"))
    if command == "prerelease":
        if version.prerelease is None:
            sys.exit(
                f"error: {current} is not a pre-release; "
                "use premajor/preminor/prepatch to start one"
            )
        return str(version.bump_prerelease())
    if command == "stage":
        if token not in TOKENS:
            sys.exit(f"error: stage takes one of {', '.join(TOKENS)}")
        base = version.replace(prerelease=None, build=None)
        return str(base.bump_prerelease(token))
    if command == "release":
        if version.prerelease is None:
            sys.exit(f"error: {current} is already a release")
        return str(version.replace(prerelease=None, build=None))
    sys.exit(f"error: unknown command {command!r}")


def write_version(new_version):
    text = VERSION_FILE.read_text(encoding="utf-8")
    VERSION_FILE.write_text(
        VERSION_RE.sub(rf"\g<1>{new_version}\g<3>", text, count=1), encoding="utf-8"
    )


def roll_changelog(new_version, today):
    """Rename the Unreleased section and open a fresh one above it."""
    text = CHANGELOG.read_text(encoding="utf-8")
    if not UNRELEASED_RE.search(text):
        sys.exit(
            "error: CHANGELOG.md has no '## [Unreleased]' section to release. "
            "Add one, or describe the changes there first."
        )
    replacement = f"## [Unreleased]\n\n## [{new_version}] - {today}"
    CHANGELOG.write_text(UNRELEASED_RE.sub(replacement, text, count=1), encoding="utf-8")


def changelog_section(version):
    """The body of one release's changelog entry, for the tag message."""
    text = CHANGELOG.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", re.MULTILINE | re.DOTALL
    )
    match = pattern.search(text)
    if not match:
        return ""
    # Trailing "---" is the separator between entries, not part of this one.
    return match.group(1).strip().removesuffix("---").strip()


def run(command, dry_run):
    printable = " ".join(command)
    if dry_run:
        print(f"  [dry-run] {printable}")
        return
    print(f"  {printable}")
    subprocess.run(command, check=True, cwd=ROOT)


def ensure_clean_worktree(dry_run):
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT, check=True
    )
    if result.stdout.strip():
        message = (
            "error: the working tree has uncommitted changes. "
            "Commit or stash them before releasing."
        )
        if dry_run:
            print(f"  [dry-run] would refuse: {message}")
        else:
            sys.exit(message)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Bump the version, roll the changelog and tag the release.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=[
            "major",
            "minor",
            "patch",
            "premajor",
            "preminor",
            "prepatch",
            "prerelease",
            "stage",
            "release",
        ],
        help="which part to bump",
    )
    parser.add_argument("token", nargs="?", help="alpha, beta or rc, for pre-release commands")
    parser.add_argument("--set", dest="explicit", help="set an explicit X.Y.Z version")
    parser.add_argument("--dry-run", action="store_true", help="print what would happen")
    parser.add_argument("--push", action="store_true", help="push the commit and tag")
    parser.add_argument(
        "--no-commit", action="store_true", help="edit the files but do not commit or tag"
    )
    args = parser.parse_args(argv)

    if not args.command and not args.explicit:
        parser.error("give a command (e.g. patch) or --set X.Y.Z")

    current = current_version()
    new_version = next_version(current, args.command, args.token, args.explicit)
    today = datetime.date.today().isoformat()

    print(f"{current} -> {new_version}")

    if not args.no_commit:
        ensure_clean_worktree(args.dry_run)

    if args.dry_run:
        print(f"  [dry-run] write {VERSION_FILE.name}")
        print(f"  [dry-run] roll CHANGELOG.md Unreleased -> [{new_version}] - {today}")
    else:
        write_version(new_version)
        roll_changelog(new_version, today)
        print(f"  wrote {VERSION_FILE.name} and CHANGELOG.md")

    if args.no_commit:
        print("  --no-commit: stopping before the commit and tag")
        return 0

    run(["git", "add", str(VERSION_FILE.name), "CHANGELOG.md"], args.dry_run)
    run(["git", "commit", "-m", f"chore: release v{new_version}"], args.dry_run)

    notes = changelog_section(new_version) if not args.dry_run else ""
    tag_message = f"v{new_version}\n\n{notes}".strip()
    run(["git", "tag", "-a", f"v{new_version}", "-m", tag_message], args.dry_run)

    if args.push:
        run(["git", "push"], args.dry_run)
        run(["git", "push", "origin", f"v{new_version}"], args.dry_run)
        print("  pushed; release.yml will build and publish")
    else:
        print(f"  not pushed. When ready:  git push && git push origin v{new_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
