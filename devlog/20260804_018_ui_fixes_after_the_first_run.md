# What the first real run showed

2026-08-04. Small UI changes, all of the same kind: things that were
technically already correct and still wrong in front of a user. They come out
of actually operating the window (devlog 017) rather than out of a test.

Five of them, reported over the course of one session. The last two arrived
after this entry was first written, which is why it is no longer called "three
things" — they belong here rather than in a second entry, because they have the
same origin.

## The Filename column stopped stretching

`setup_ui` sets the capture table's two columns to `ResizeToContents` and
`Stretch`, so Filename takes whatever the left panel gives it. It does — until
the first capture. `clear_image_data` calls `QStandardItemModel.clear()`, which
removes the *columns*, and a `QHeaderView`'s resize modes are per section: when
the sections go, the modes go with them and the re-created ones come back
`Interactive`. From then on Filename sat at a fixed width and widening the
window widened only the empty space to its right.

Nothing about this is visible in the code at either site — the header is
configured in one method and destroyed in another, three hundred lines apart.
So the fix is not to re-apply the modes at each `clear()` call site but to make
that impossible to forget: `set_table_headers()` sets the labels *and* the
modes, and the three places that were labelling the columns now call it. The
labels and the modes have the same lifetime, so they are set in the same place.

The test resizes the view after a clear and asserts the section grew. Asserting
`sectionResizeMode(1) == Stretch` alone would pass against a header that is
never given the width — checking both means the regression is caught whichever
way it comes back.

## The directory field started at `.`

`monitor_root` defaulted to the literal `"."`, which is the process's working
directory: for `make run` the source tree, for the installed build whatever
Windows hands the shortcut. The field at the top of the window showed a single
dot, and the first thing anyone does is press Browse anyway — but the default
also *is* the watched root until they do, so a Test Shot before choosing a
folder would poll the source tree.

Now `str(Path.home())`, expanded rather than stored as `~`: `monitor_root` is
walked with `os.path` and handed to `os.walk`, neither of which resolves a
tilde, so a literal `"~"` would have been a directory that does not exist.
Nothing further down needed changing because the value was always a plain path
string.

## PTMfitter.exe's size limit was only in a tooltip

The engine choice — built-in or `PTMfitter.exe` — has been in Preferences since
alpha.3, above the executable's path, which is the arrangement asked for. What
was missing was that choosing the external engine has a consequence: it is
32-bit and fails above roughly 24 megapixels (devlog 009). That was said in a
tooltip on the combo, which reaches nobody who is not already hovering it.

It is now also a line under the combo, shown only while `PTMfitter.exe` is the
selection — a warning that is always on screen is furniture, and this one is
false half the time, since the built-in engine has no such limit. The cost of
finding out the hard way is the reason it is not left to the tooltip: the fit
runs *after* every shot of a fifty-image capture has been taken.

The path row is disabled while the built-in engine is selected, since it does
not apply. Disabled and not cleared — `save_settings` still writes it, so
someone trying the built-in engine and going back does not have to find their
executable again. There is a test for exactly that, because "the field is not
in use" is a short step from "the field can be emptied".

One thing to watch: the notice and the tooltip say the same fact in two
strings, so they can drift apart, in two languages. They are separate because
they are read in different postures — one is a hover, one is a standing
statement — but if a third appears, the fact belongs in `core/settings.py` next
to `SUPPORTED_FITTERS` and not in the dialog.


## The capture-folder line explained instead of showing

Under the capture list sat "Waiting for the first shot — watching {root} and
below", replaced after the first shot by "Capture folder: {directory}".

The first half of that is a sentence restating its neighbour: the watched root
is already on screen, in the Directory field directly above. And the label's
job is not to narrate state — it is to show the one path that is *not* shown
anywhere else, because it is discovered from the first shot rather than chosen
by anyone.

So it now holds the path and nothing else, and is empty until there is one. The
label was already selectable text (`TextSelectableByMouse`), which is the tell:
it exists to be copied into a file manager, and a prefix is something you have
to select around.

Two translated strings went with it. That is the cost, and it is the right way
round — a string that is not there cannot go stale in two languages.

## The PTM Fitter row did not line up

Every row in Preferences puts a single widget into the form layout, which
applies its own spacing. One row does not: the fitter path is a `QLineEdit` and
a *Browse* button, so it wraps them in a container — and the container's own
layout contributed a second set of content margins on top of the form's.

Measured before the fix: the field started 9px to the right of every other
field, and the row was 47px tall against 29px for its neighbours. The fix is
`setContentsMargins(0, 0, 0, 0)` on the nested layout, which the main window
already does for the same reason on `capture_list_layout`.

The regression test asserts the two things that were actually wrong — the
fields share a left edge, and the container is exactly as tall as the taller
widget inside it — rather than asserting the margins are zero. Those are the
same thing today, but only one of them is the property anyone cares about. It
tolerates the one-pixel difference between a push button and a line edit,
because that is not what this was about; the margins were worth eighteen.
