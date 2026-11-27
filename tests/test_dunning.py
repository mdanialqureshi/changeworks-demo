import pytest

from quillstack_billing.dunning import (
    DEFAULT_STEPS,
    DunningSchedule,
    ReminderLevel,
    ReminderStep,
)


def test_default_steps_rise_with_offset() -> None:
    schedule = DunningSchedule()
    offsets = [s.offset_days for s in schedule.steps]
    assert offsets == sorted(offsets)
    assert schedule.steps[0].level is ReminderLevel.COURTESY
    assert schedule.steps[-1].level is ReminderLevel.COLLECTIONS
    assert len(schedule.steps) == len(DEFAULT_STEPS)


def test_steps_are_sorted_on_construction() -> None:
    steps = [
        ReminderStep(10, ReminderLevel.SECOND, "b"),
        ReminderStep(1, ReminderLevel.FIRST, "a"),
    ]
    schedule = DunningSchedule(steps)
    assert [s.template for s in schedule.steps] == ["a", "b"]


def test_duplicate_levels_are_refused() -> None:
    with pytest.raises(ValueError, match="once"):
        DunningSchedule(
            [
                ReminderStep(1, ReminderLevel.FIRST, "a"),
                ReminderStep(2, ReminderLevel.FIRST, "b"),
            ]
        )


def test_levels_must_rise_with_offset() -> None:
    with pytest.raises(ValueError, match="rise"):
        DunningSchedule(
            [
                ReminderStep(1, ReminderLevel.SECOND, "a"),
                ReminderStep(5, ReminderLevel.FIRST, "b"),
            ]
        )
