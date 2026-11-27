"""Dunning: when to remind customers about unpaid invoices.

A schedule is a list of steps, each an offset in days from the due date
(negative offsets are before it) and a reminder level. On any day, an
open invoice is owed the highest step it has reached that is above the
level already sent; a run that was skipped for a few days therefore
sends one reminder at the right level instead of several.

Invoices that are paid, still drafts, or belong to a paused customer
get no reminders.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import IntEnum

from .invoice import Invoice


class ReminderLevel(IntEnum):
    COURTESY = 0
    FIRST = 1
    SECOND = 2
    FINAL = 3
    COLLECTIONS = 4


@dataclass(frozen=True, order=True)
class ReminderStep:
    offset_days: int
    level: ReminderLevel
    template: str


DEFAULT_STEPS: tuple[ReminderStep, ...] = (
    ReminderStep(-3, ReminderLevel.COURTESY, "courtesy"),
    ReminderStep(1, ReminderLevel.FIRST, "first-reminder"),
    ReminderStep(7, ReminderLevel.SECOND, "second-reminder"),
    ReminderStep(14, ReminderLevel.FINAL, "final-notice"),
    ReminderStep(30, ReminderLevel.COLLECTIONS, "collections"),
)


@dataclass(frozen=True)
class Reminder:
    """One reminder to send today."""

    invoice: Invoice
    step: ReminderStep
    days_from_due: int


class DunningSchedule:
    """A set of reminder steps and the customers it is paused for."""

    def __init__(
        self,
        steps: Iterable[ReminderStep] = DEFAULT_STEPS,
        *,
        paused: set[str] = set(),
    ) -> None:
        self.steps = tuple(sorted(steps))
        levels = [s.level for s in self.steps]
        if len(set(levels)) != len(levels):
            raise ValueError("each reminder level may appear only once")
        if levels != sorted(levels):
            raise ValueError("levels must rise with the offset")
        self.paused = paused

    def pause(self, customer_id: str) -> None:
        """Stop reminders for a customer (for example, in a dispute)."""
        self.paused.add(customer_id)

    def resume(self, customer_id: str) -> None:
        self.paused.discard(customer_id)

    def _eligible(self, invoice: Invoice) -> bool:
        return (
            not invoice.is_draft
            and invoice.balance_due.amount > 0
            and invoice.customer.id not in self.paused
        )

    def step_for(self, invoice: Invoice, today: date) -> ReminderStep | None:
        """The step ``invoice`` is owed on ``today``, if any."""
        due = invoice.due_date
        if due is None or not self._eligible(invoice):
            return None
        days = (today - due).days
        reached = [s for s in self.steps if s.offset_days <= days]
        if not reached:
            return None
        step = reached[-1]
        sent = invoice.reminder_level
        if sent is not None and step.level <= sent:
            return None
        return step

    def due_reminders(
        self, invoices: Iterable[Invoice], today: date = date.today()
    ) -> list[Reminder]:
        """Reminders to send on ``today``, oldest due date first."""
        found = []
        for invoice in invoices:
            step = self.step_for(invoice, today)
            if step is not None:
                assert invoice.due_date is not None
                days = (today - invoice.due_date).days
                found.append(Reminder(invoice, step, days))
        found.sort(key=lambda r: (r.invoice.due_date, str(r.invoice.number)))
        return found

    def mark_sent(self, reminder: Reminder) -> None:
        """Record that ``reminder`` went out."""
        reminder.invoice.reminder_level = int(reminder.step.level)

    def next_reminder_date(self, invoice: Invoice) -> date | None:
        """The next day a reminder will fall due, if any."""
        due = invoice.due_date
        if due is None or not self._eligible(invoice):
            return None
        sent = invoice.reminder_level
        for step in self.steps:
            if sent is None or step.level > sent:
                return due + timedelta(days=step.offset_days)
        return None
