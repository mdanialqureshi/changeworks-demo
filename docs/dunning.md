# Dunning

Dunning is the schedule of reminders for unpaid invoices. The default
schedule, in days relative to the due date:

| Offset | Level | Template |
|---|---|---|
| −3 | courtesy | `courtesy` |
| +1 | first | `first-reminder` |
| +7 | second | `second-reminder` |
| +14 | final | `final-notice` |
| +30 | collections | `collections` |

On any day, an open invoice is owed the **highest** step it has
reached that is above the level already sent. If the reminder job does
not run for a few days, the next run sends one reminder at the right
level rather than every step it missed.

No reminders go to:

- drafts;
- invoices with nothing left to pay (paid, or fully credited);
- customers whose reminders are paused (for example during a dispute).

`DunningSchedule.mark_sent()` records the level sent on the invoice, and
`next_reminder_date()` says when the next step falls due.
