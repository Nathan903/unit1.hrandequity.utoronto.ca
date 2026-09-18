# CUPE 3902 Unit 1 — Job Postings Tracker

Automatically scrapes TA job postings from [unit1.hrandequity.utoronto.ca](https://unit1.hrandequity.utoronto.ca), publishes them as a searchable HTML page, and sends email alerts for new STEM TA postings via GitHub's notification system.

---

## How the Email Alert System Works

> **No email server or SMTP credentials needed.** GitHub itself sends the emails.

### The Core Trick

GitHub sends an email notification to anyone subscribed to an issue whenever a **new comment** is posted on it. This repo exploits that to act as a free, zero-infrastructure email alert service:

1. A **"TA Job Alerts" issue** exists on this repo (closed, but still receiving comments).
2. The GitHub Actions workflow runs `notify_ta_jobs.py` on a schedule.
3. When new relevant jobs are found, the workflow posts a **comment** on that issue using the `gh` CLI:
   ```bash
   gh issue comment <issue-number> --body-file issue_body.md
   ```
4. GitHub automatically emails everyone subscribed to the issue — including the repo owner.

### Why the Issue is Closed

The issue can be (and is) **closed** — GitHub still delivers email notifications for comments on closed issues. Closing it keeps the repo's open issue count clean.

### How to Subscribe / Unsubscribe

- **Subscribe:** Go to the "TA Job Alerts" issue → click **Subscribe** in the right sidebar.
- **Unsubscribe:** Same issue → click **Unsubscribe**, or use the unsubscribe link at the bottom of any notification email.
- You can also manage all GitHub notifications at: https://github.com/settings/notifications

---

## Alert Logic (`notify_ta_jobs.py`)

Filters jobs from `result.csv` using these criteria:
- `ptype = TA` (exact match)
- `campus = St. George` (exact match, case-insensitive)
- Department contains `engineering`, `computer`, or `math`
- Job is not already expired (closing date ≥ today)
- Job ID has not been previously alerted (tracked in `ta_alert_state.json`)

### Send Frequency Decision Tree

```
New unsent matching jobs found?
├── No  → skip, do nothing
└── Yes → Any job closing within 5 days?
          ├── Yes (urgent) → post comment now
          └── No → has it been ≥ 7 days since last alert?
                   ├── Yes → post comment now
                   └── No  → skip (do NOT mark jobs as sent — retry next run)
```

**Key behaviour:** if the weekly throttle kicks in, jobs are *not* marked as sent, so they will be reconsidered on every future run until they either become urgent or the week is up.

### State File (`ta_alert_state.json`)

A single JSON file committed back to the repo after each alert:

```json
{
  "last_sent": "2026-09-15",
  "sent_ids": ["53700", "53701", "53813", "..."]
}
```

- `last_sent` — date of the last posted comment (drives the 7-day throttle)
- `sent_ids` — job IDs already notified; automatically pruned if a job disappears from the CSV (so if it reappears later it counts as new)

---

## Workflow (`main.yml`)

Runs **every hour, 7 am – 6 pm UTC** (on push too):

```
download.py       → result.csv         (scrape live postings)
csv_to_html.py    → index.html         (regenerate the table)
notify_ta_jobs.py → issue_body.md      (find new jobs, decide whether to send)
gh issue comment  → GitHub Issue       (post the comment → triggers email)
git push          → commits updated data + ta_alert_state.json
```

The workflow step that posts the comment only runs if `notify_ta_jobs.py` exits with code `0` (new jobs to send). Exit code `1` means "nothing to post" and the comment step is skipped silently.

---

## One-Time Setup (already done)

If you ever need to recreate the alert issue on a fresh fork:

```bash
# Create the mega-issue
gh issue create --title "TA Job Alerts" \
  --body "Notification thread for STEM TA jobs. Alerts posted as comments by GitHub Actions."

# Close it (optional but clean)
gh issue close <number>

# Update main.yml if the issue number isn't 1:
# gh issue comment <number> --body-file issue_body.md
```

Make sure the workflow has `permissions: issues: write` — already set in `main.yml`.
