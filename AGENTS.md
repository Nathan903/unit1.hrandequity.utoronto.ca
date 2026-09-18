# CUPE 3902 Unit 1 — Job Postings Tracker

Automatically scrapes TA job postings from [unit1.hrandequity.utoronto.ca](https://unit1.hrandequity.utoronto.ca), publishes them as a searchable HTML page, and sends email alerts for new TA postings via GitHub's notification system.

---

## How the Email Alert System Works

> **No email server or SMTP credentials needed.** GitHub itself sends the emails.

### The Core Trick

GitHub sends an email notification to anyone subscribed to an issue whenever a **new comment** is posted on it. This repo exploits that to act as a free, zero-infrastructure email alert service:

1. One **closed GitHub Issue** exists per alert profile (e.g. Issue #1 for STEM, Issue #2 for Bio).
2. The GitHub Actions workflow runs `notify_ta_jobs.py` on a schedule.
3. When new relevant jobs are found for a profile, the script posts a **comment** on that profile's issue directly via `gh` CLI (called from within Python using `subprocess`).
4. GitHub automatically emails everyone subscribed to that issue.

### Why Issues are Closed

Issues can be (and are) **closed** — GitHub still delivers email notifications for comments on closed issues. Closing them keeps the repo's open issue count clean.

### How to Subscribe / Unsubscribe

- **Subscribe:** Go to the relevant issue → click **Subscribe** in the right sidebar.
- **Unsubscribe:** Same issue → click **Unsubscribe**, or use the unsubscribe link at the bottom of any notification email.
- Manage all GitHub notifications at: https://github.com/settings/notifications

---

## Alert Profiles (`subscriptions.json`)

Profiles are defined in [`subscriptions.json`](subscriptions.json). Each profile has its own GitHub Issue and independent filter criteria. The script loops through all profiles on every run.

### Current Profiles

| Profile | Issue | Description |
|---------|-------|-------------|
| **STEM & programming** | [#1](../../issues/1) | Engineering, computer science, math, FASE departments |
| **Bio** | [#2](../../issues/2) | Biology, pharmacology, BME and related fields — undergrad courses only |

### Profile Schema

```json
{
  "profile": "Display Name",
  "issue": 1,
  "campus": "St. George",
  "ptype": ["TA"],
  "match": {
    "department": ["keyword1", "keyword2"],
    "job_title":  ["keyword3"],
    "course_id":  ["BIO", "CHE"]
  },
  "undergrad_only": true
}
```

- **`campus`** — exact match, case-insensitive
- **`ptype`** — string or list; exact match (e.g. `"TA"`, `"CI"`)
- **`match`** — OR logic across all fields and keywords; supported fields: `department`, `job_title`, `course_id`
- **`course_id` matching** — substring match (e.g. `"BIO"` matches `"BIO230H1"`)
- **`undergrad_only`** — if `true`, skips jobs whose course code doesn't have exactly 3 digits after the dept letters (UofT convention: 3 digits = undergrad, 4 digits = grad)

### Adding a New Profile

1. Add an entry to `subscriptions.json`
2. Create + close a GitHub Issue for it: `gh issue create --title "..." --body "..." && gh issue close <n>`
3. Subscribers go to the issue URL and click **Subscribe**
4. No code changes needed — the script picks up the new profile automatically

---

## Alert Logic (`notify_ta_jobs.py`)

### Per-Profile Decision Tree

```
New unsent matching jobs found for this profile?
├── No  → skip, do nothing
└── Yes → Any job closing within 5 days?
          ├── Yes (urgent) → post comment now
          └── No → has it been ≥ 7 days since last alert for this profile?
                   ├── Yes → post comment now
                   └── No  → skip (do NOT mark jobs as sent — retry next run)
```

**Key behaviour:** throttled jobs are *not* marked as sent, so they are reconsidered every run until they become urgent or the weekly interval passes.

### State File (`ta_alert_state.json`)

Per-profile state committed back to the repo after each alert:

```json
{
  "STEM & programming": {
    "last_sent": "2026-09-15",
    "sent_ids": ["53700", "53701", "..."]
  },
  "Bio": {
    "last_sent": null,
    "sent_ids": []
  }
}
```

- `last_sent` — drives the 7-day throttle per profile independently
- `sent_ids` — job IDs already notified; pruned automatically if a job disappears from the CSV (reappearance = treated as new)

---

## Workflow (`main.yml`)

Runs **every hour, 7 am – 6 pm UTC** (and on every push):

```
download.py        → result.csv    (scrape live postings)
csv_to_html.py     → index.html   (regenerate the HTML table)
notify_ta_jobs.py               (loop profiles, post gh issue comments, update state)
git push           → commits result.csv, index.html, ta_alert_state.json
```

`notify_ta_jobs.py` calls `gh issue comment <n> --body-file issue_body.md` internally via `subprocess` for each profile that needs a notification. `GH_TOKEN` is passed as an env var by the workflow.

Exit code `0` = at least one profile sent → commit message says "Auto update and alert".
Exit code `1` = nothing sent → commit message says "Auto update".

---

## Utility Scripts

| Script | Purpose |
|--------|---------|
| `gather_historical_jobs.py` | Walks all git commits to extract every unique job seen in the past 6 months into `historical_jobs.csv` (one-time use, output is gitignored) |

---

## One-Time Setup (already done)

If recreating on a fresh fork:

```bash
# Create issues for each profile and close them
gh issue create --title "TA Job Alerts" \
  --body "Notification thread for STEM TA jobs at St. George.
Subscribe to issue for email notification of new jobs!"
gh issue close 1

gh issue create --title "Bio TA Job Alerts" \
  --body "Notification thread for Bio/BME/Pharmacology TA jobs at St. George.
Subscribe to issue for email notification of new jobs!"
gh issue close 2

# Ensure workflow permissions
# main.yml must have: permissions: issues: write, contents: write
```
