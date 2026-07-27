"""Capture sequencing: preparation, polling, retakes, giving up.

The session performs no IO, so a whole run can be driven here in microseconds
with the shutter and the file poll replaced by recorders.
"""

import pytest

from core.capture_session import (
    CAPTURED,
    GAVE_UP,
    IDLE,
    POLLING,
    PREPARING,
    RETAKING,
    WAITING,
    CaptureSession,
)

pytestmark = pytest.mark.unit


class Rig:
    """Records shutter fires and hands out canned poll results."""

    def __init__(self, results=()):
        self.shots = []
        self.results = list(results)
        self.polls = 0

    def shoot(self, index):
        self.shots.append(index)

    def poll(self):
        self.polls += 1
        return self.results.pop(0) if self.results else None


def drive(session, rig, ticks):
    return [session.step(rig.shoot, rig.poll) for _ in range(ticks)]


def test_first_slot_is_dequeued_on_construction():
    session = CaptureSession([3, 7, 9])
    assert session.current_index == 3
    assert session.queue == [7, 9]
    assert not session.finished


def test_empty_queue_starts_finished():
    session = CaptureSession([])
    assert session.finished
    assert session.current_index is None


def test_first_tick_fires_the_shutter():
    session, rig = CaptureSession([0]), Rig()
    session.step(rig.shoot, rig.poll)
    assert rig.shots == [0]
    assert session.status == PREPARING


def test_no_polling_during_preparation():
    session, rig = CaptureSession([0], preparation_time=2), Rig()
    drive(session, rig, 3)
    assert rig.polls == 0, "looked for a file before the camera had settled"
    assert session.status == POLLING


def test_image_found_records_the_slot_and_advances():
    session = CaptureSession([0, 1], preparation_time=1)
    rig = Rig(results=["/shots/a.jpg"])
    results = drive(session, rig, 3)
    captured = [r for r in results if r.event == CAPTURED]
    assert captured and captured[0].recorded == (0, "/shots/a.jpg")
    assert session.current_index == 1


def test_timeout_gives_up_when_no_retakes_are_allowed():
    session = CaptureSession([0], preparation_time=1, polling_timeout=2, max_retakes=0)
    rig = Rig()
    results = drive(session, rig, 8)
    gave_up = [r for r in results if r.event == GAVE_UP and r.recorded]
    assert gave_up and gave_up[0].recorded == (0, None)


def test_timeout_retakes_up_to_the_limit():
    session = CaptureSession([0], preparation_time=1, polling_timeout=1, max_retakes=2)
    rig = Rig()
    results = drive(session, rig, 20)
    assert sum(1 for r in results if r.event == RETAKING) == 2
    assert rig.shots == [0, 0, 0], "the shutter should fire once per attempt"


def test_a_retake_that_succeeds_records_the_image():
    session = CaptureSession([0], preparation_time=1, polling_timeout=1, max_retakes=1)
    # One poll per attempt at this timeout: nothing on the first, a file on the
    # retake.
    rig = Rig(results=[None, "/shots/late.jpg"])
    results = drive(session, rig, 12)
    captured = [r for r in results if r.event == CAPTURED]
    assert captured and captured[0].recorded == (0, "/shots/late.jpg")


def test_waiting_while_the_poll_window_is_open():
    session = CaptureSession([0], preparation_time=1, polling_timeout=5)
    rig = Rig()
    results = drive(session, rig, 4)
    assert any(r.event == WAITING for r in results)
    assert not session.finished


def test_run_finishes_when_the_queue_drains():
    session = CaptureSession([0, 1], preparation_time=1)
    rig = Rig(results=["/a.jpg", "/b.jpg"])
    results = drive(session, rig, 8)
    assert results[-1].finished or session.finished
    assert session.finished


def test_stepping_a_finished_session_is_harmless():
    session, rig = CaptureSession([]), Rig()
    result = session.step(rig.shoot, rig.poll)
    assert result.finished
    assert rig.shots == []


def test_counters_reset_between_slots():
    session = CaptureSession([0, 1], preparation_time=1, polling_timeout=1, max_retakes=1)
    rig = Rig(results=["/a.jpg"])
    drive(session, rig, 3)
    assert session.current_index == 1
    assert session.second_counter == 0
    assert session.retake_counter == 0
    assert session.status == IDLE


def test_is_new_slot_tracks_whether_the_shot_has_been_taken():
    session = CaptureSession([0, 1], preparation_time=1)
    rig = Rig(results=["/a.jpg"])
    assert session.is_new_slot
    drive(session, rig, 3)
    assert session.is_new_slot, "moved to LED 1, which has not been shot yet"


def test_retake_only_queue_covers_the_selected_leds():
    session = CaptureSession([4, 9])
    assert session.current_index == 4
    assert session.queue == [9]
