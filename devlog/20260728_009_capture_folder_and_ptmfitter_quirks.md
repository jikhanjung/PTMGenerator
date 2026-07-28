# Watching for the capture folder, and what PTMfitter actually tolerates

## Date: 2026-07-28

Two problems reported from real use, both about the gap between what the
application assumed and what the equipment does.

## 1. The capture folder does not exist yet

Canon's EOS Utility is pointed at a folder and files each shot into a dated
subfolder beneath it — `<root>/2026-07-28/`. **That subfolder is not created
until the day's first shot.** So at the moment a session is set up, the only
folder that exists to select is the parent, and every shot then lands one level
down, where the poll was not looking.

The poll had been deliberately non-recursive since v0.1.2 ("glob only checks the
specified directory, not subdirectories"), which is why nothing was ever found.

The fix is to stop treating the selected folder as where the images are:

* it is a **monitored root**, searched recursively while waiting for the first
  shot;
* whichever folder that shot lands in becomes the **capture folder** for the
  run, and `image_data.csv` is written there;
* once it is known, later polls look only in it. This runs once a second, and
  walking a season of dated folders every time would be a real cost.

A new run clears the adoption, so a session started after midnight does not
keep writing into yesterday's folder.

Both folders are now on screen, because they can differ: the directory field at
the top keeps showing what is watched, and a line above the capture list shows
where shots are actually going — or `Waiting for the first shot` before one has.

## 2. PTMfitter is from 2001 and it shows

The reported symptoms were vague — "spaces or Korean in the path caused
problems, and it can't handle large images, maybe over 3600 rows". Rather than
guess, the shipped `PTMfitter.exe` was run under WSL interop against generated
image sets.

**The first attempt at measuring was wrong**, and worth recording because the
wrong answer looked convincing: absolute paths were written as `/mnt/d/...`,
which no Windows binary can resolve, so *every* absolute-path case "failed" and
the conclusion would have been "absolute paths are broken". Rewriting them as
`D:\...` gave a completely different result.

What it actually does, with nine images:

    .lp lists bare filenames, cwd = the image directory      works
      ... directory name contains a space                    works
      ... directory name contains Hangul                     works
      ... directory path is very long                        works
    .lp lists absolute paths, ASCII, no spaces               works
    .lp lists absolute paths containing a space              FAILS
    a filename inside the .lp contains a space               FAILS
    -o is an absolute path with a space and Hangul           FAILS
    -o is a relative ASCII name                              works
    a Hangul filename, .lp written as UTF-8                  FAILS
    a Hangul filename, .lp written as CP949                  works

Two independent constraints, not one:

* **It splits each .lp line on whitespace.** A path with a space in it is read
  as part of the light vector. No encoding fixes this.
* **It reads the .lp in the machine's ANSI codepage**, which is what a 2001
  Windows binary calling `fopen` would do. So Hangul works as CP949 and fails
  as UTF-8.

The second one means the encoding change made two days earlier (devlog 006,
"write everything as UTF-8") was **wrong for this file specifically**. It was
right for `image_data.csv`, which only Python reads. Applying one rule to both
files was the mistake; they have different readers.

Where the process runs turns out not to matter at all. So the fix is to keep
everything the fitter parses trivial: bare filenames in the .lp, written in the
local ANSI codepage, a relative ASCII output name, and cwd set to the images.
Python moves the result to wherever the user asked, having no such difficulty.

A name it could not read either way — one containing whitespace — is handled by
copying the images to a temporary directory under `0000.jpg` names first. In
practice this never fires: the files come off the camera as `IMG_9999.JPG`. It
is there so that a renamed file gives a working fit or a clear error rather than
a silently wrong one, which is what a mis-parsed light vector produces.

Also learned: **the fitter exits 1 on success.** Its status cannot be used to
tell whether it worked, so the output file is checked instead — which is why
`generate()` raises `PtmFitterFailedError` when nothing appeared.

### The size limit is real, and it is not about rows

    6000x4000 = 24.0MP x 9 images    OK
    6000x4000 = 24.0MP x 50 images   OK
    8000x6000 = 48.0MP x 9 images    FAIL: "Memory Allocation error. size: 48"

**Image size, not image count.** Fifty 24MP images are fine; nine 48MP images
are not. `PTMfitter.exe` is a 32-bit PE, so its ~2 GB address space is the
ceiling and the coefficient buffer scales with pixels. The "3600 rows"
recollection was presumably where that ceiling landed for the image width in
use at the time.

This matters now rather than theoretically: a 45MP body is over the line, and
several current cameras are.

Nothing in this change addresses it — the fix is to do the fitting in-process,
which is its own piece of work and is filed in `TODOs.md`.

## What was rejected

- **Copying everything to a temp directory for every fit**, which was the first
  idea for the path problem. It would work, but it copies up to fifty full-size
  images per run for a constraint that turns out to affect only the *contents*
  of one small text file. The measurement is what made the cheaper fix visible.
- **Searching recursively on every poll.** Correct, and needlessly expensive
  once the folder is known.
- **Scanning recursively when reopening an old capture.** A monitored root
  holding several dated folders would merge them into one nonsensical run.
  Reopening still expects the folder that holds the images, which is the folder
  the application itself now writes `image_data.csv` into.
