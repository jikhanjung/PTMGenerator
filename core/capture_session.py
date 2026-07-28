"""Sequencing a capture run.

One tick per second, driven by a QTimer in the UI. Each slot goes

    idle -> preparing -> polling -> (recorded | retake) -> next slot

and the run ends when the queue drains. This object owns the sequencing only:
firing the shutter and looking for the resulting file are injected, so the
policy — how long to wait, when to retake, when to give up — can be tested
without a controller, a camera or a clock.
"""

from typing import NamedTuple

IDLE = "idle"
PREPARING = "preparing picture"
POLLING = "polling"


class StepResult(NamedTuple):
    """What one tick did, for the UI to render."""

    event: str
    #: Set when a slot was decided: (led_index, image_path or None).
    recorded: tuple | None = None
    #: True once the queue has drained and the run is over.
    finished: bool = False


# StepResult.event values
PREPARING_SHOT = "preparing"
WAITING = "waiting"
CAPTURED = "captured"
RETAKING = "retaking"
GAVE_UP = "gave_up"


class CaptureSession:
    """The queue of LEDs still to shoot, and the state of the current one."""

    def __init__(self, indices, preparation_time=2, polling_timeout=5, max_retakes=0):
        """
        Args:
            indices: LED indices to capture, in order.
            preparation_time: Ticks to let the camera settle after the shutter
                before looking for a file.
            polling_timeout: Further ticks to wait for the file to appear.
            max_retakes: Times to re-fire a slot before recording it as missing.
        """
        self.queue = list(indices)
        self.preparation_time = preparation_time
        self.polling_timeout = polling_timeout
        self.max_retakes = max_retakes

        self.status = IDLE
        self.second_counter = 0
        self.retake_counter = 0
        # -1 is a sentinel meaning "no slot has been finished yet"; after that
        # it takes the same domain as current_index, which is None once the
        # queue drains.
        self.previous_index: int | None = -1
        self.current_index: int | None = self.queue.pop(0) if self.queue else None
        self.finished = self.current_index is None

    @property
    def is_new_slot(self):
        """True while the current slot has not been shot yet."""
        return self.current_index != self.previous_index

    def step(self, shoot, poll):
        """Advance one tick.

        Args:
            shoot: Called as shoot(led_index) to light the LED and fire.
            poll: Called as poll() -> image path, or None if nothing new.

        Returns:
            StepResult: what happened, and whether the run is over.
        """
        if self.finished:
            return StepResult(GAVE_UP, finished=True)

        if self.status == IDLE:
            self.status = PREPARING
            shoot(self.current_index)
            self.second_counter += 1
            return StepResult(PREPARING_SHOT)

        if self.status == PREPARING:
            if self.second_counter == self.preparation_time:
                self.status = POLLING
            self.second_counter += 1
            return StepResult(PREPARING_SHOT)

        # POLLING
        image = poll()
        if image is None:
            if self.second_counter < self.polling_timeout:
                self.second_counter += 1
                return StepResult(WAITING)
            if self.retake_counter < self.max_retakes:
                self.retake_counter += 1
                self.second_counter = 0
                self.status = IDLE
                return StepResult(RETAKING)
            return self._finish_slot(GAVE_UP, (self.current_index, None))

        return self._finish_slot(CAPTURED, (self.current_index, image))

    def _finish_slot(self, event, recorded):
        """Record the outcome and move to the next LED."""
        self.second_counter = 0
        self.retake_counter = 0
        self.status = IDLE
        self.previous_index = self.current_index
        if self.queue:
            self.current_index = self.queue.pop(0)
        else:
            self.finished = True
        return StepResult(event, recorded=recorded, finished=self.finished)
