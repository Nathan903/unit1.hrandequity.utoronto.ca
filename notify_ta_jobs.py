"""
notify_ta_jobs.py

Filters newly opened STEM TA jobs at St. George campus.
Generates issue_body.md to be posted as a GitHub Issue comment.
Exits with code 1 if there is nothing new to post (so the workflow can skip).
"""

import csv
import os
import sys
from datetime import datetime, timedelta

# ── Configuration ────────────────────────────────────────────────────────────
CSV_FILE        = "result.csv"
STATE_FILE      = "ta_alert_state.json" # single file: sent IDs + last sent date
OUTPUT_MD       = "issue_body.md"
CAMPUS_FILTER      = "St. George"         # exact match (case-insensitive)
PTYPE_FILTER       = "TA"                 # exact match
DEPT_KEYWORDS      = ["engineering", "computer", "math"]
MIN_INTERVAL_DAYS  = 7                    # never send more than once per week
URGENT_DAYS        = 5                    # send immediately if a job closes within this many days
# ─────────────────────────────────────────────────────────────────────────────


def load_state(path):
    """Load state from JSON. Returns (sent_ids: set, last_sent: datetime|None)."""
    import json
    if not os.path.exists(path):
        return set(), None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    sent_ids = set(data.get("sent_ids", []))
    raw_date = data.get("last_sent", "")
    try:
        last_sent = datetime.strptime(raw_date, "%Y-%m-%d") if raw_date else None
    except ValueError:
        last_sent = None
    return sent_ids, last_sent


def save_state(path, sent_ids, last_sent):
    import json
    data = {
        "last_sent": last_sent.strftime("%Y-%m-%d") if last_sent else None,
        "sent_ids":  sorted(sent_ids),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

def parse_date(s):
    """Parse a date string in any format using dateutil (bundled with pandas)."""
    if not s or not s.strip():
        return None
    try:
        from dateutil import parser as du_parser
        return du_parser.parse(s.strip(), dayfirst=True)
    except Exception:
        return None


def is_stem(department):
    dept_lower = (department or "").lower()
    return any(kw in dept_lower for kw in DEPT_KEYWORDS)


def is_st_george(campus):
    return (campus or "").strip().lower() == CAMPUS_FILTER.lower()


def is_ta(ptype):
    return (ptype or "").strip().lower() == PTYPE_FILTER.lower()


def job_url(job_id):
    return f"https://unit1.hrandequity.utoronto.ca/posting/{job_id}"


def main():
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    sent_ids, last_sent_dt = load_state(STATE_FILE)

    # ── Load all rows and collect current IDs ─────────────────────────────────
    all_rows = []
    current_ids = set()
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            job_id = str(row.get("id", "")).strip()
            if job_id:
                current_ids.add(job_id)
            all_rows.append((job_id, row))

    # Prune sent_ids: remove any ID that no longer appears in the CSV.
    # If it reappears in the future it will be treated as a new job.
    sent_ids &= current_ids

    # ── Filter for new alertable jobs ─────────────────────────────────────────
    new_jobs = []
    for job_id, row in all_rows:
        if not job_id or job_id in sent_ids:
            continue

        campus      = row.get("campus", "")
        ptype       = row.get("ptype", "")
        department  = row.get("department", "")
        closing_raw = row.get("closing_date", "")

        if not is_st_george(campus):
            continue
        if not is_ta(ptype):
            continue
        if not is_stem(department):
            continue

        closing = parse_date(closing_raw)
        if closing is None:
            continue
        closing = closing.replace(hour=0, minute=0, second=0, microsecond=0)

        # Skip expired jobs; include all future jobs regardless of how far out
        if closing < today:
            continue
        new_jobs.append(row)

    if not new_jobs:
        print("No new STEM TA jobs found. Nothing to post.")
        sys.exit(1)  # signal to the workflow: skip posting

    # ── Send-frequency gate (mirrors decision tree) ───────────────────────────
    #
    #   New jobs found?
    #   └── Yes → Any closing within URGENT_DAYS?
    #             ├── Yes (urgent) → send now
    #             └── No → last send ≥ MIN_INTERVAL_DAYS ago?
    #                       ├── Yes → send now
    #                       └── No  → skip (don't mark as sent)
    #
    last_sent  = last_sent_dt
    days_since = (today - last_sent).days if last_sent else MIN_INTERVAL_DAYS

    urgent = any(
        (parse_date(j.get("closing_date", "")) or datetime.max)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        <= today + timedelta(days=URGENT_DAYS)
        for j in new_jobs
    )

    if urgent:
        print(f"Urgent: {sum(1 for j in new_jobs if (parse_date(j.get('closing_date','')) or datetime.max).replace(hour=0,minute=0,second=0,microsecond=0) <= today + timedelta(days=URGENT_DAYS))} job(s) closing within {URGENT_DAYS} days — sending now.")
    elif days_since >= MIN_INTERVAL_DAYS:
        print(f"Weekly send: {days_since}d since last notification — sending now.")
    else:
        remaining = MIN_INTERVAL_DAYS - days_since
        print(f"New jobs found but throttled: sent {days_since}d ago, next non-urgent send in {remaining}d.")
        sys.exit(1)  # skip posting; do NOT mark jobs as sent

    # Sort by closing date ascending
    new_jobs.sort(key=lambda r: parse_date(r.get("closing_date", "")) or datetime.max)

    # ── Build Markdown body ───────────────────────────────────────────────────
    lines = []
    lines.append(f"## 🎓 STEM TA Job Alert — {today.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"**{len(new_jobs)} new posting(s)** at **St. George**.")
    lines.append("")
    lines.append("| Course | Title | Department | Posted | Closes | Link |")
    lines.append("|--------|-------|------------|--------|--------|------|")

    for job in new_jobs:
        course  = job.get("course_id", "—")
        title   = job.get("job_title", "—")
        dept    = job.get("department", "—")
        posted  = job.get("posting_date", "—")
        closes  = job.get("closing_date", "—")
        jid     = job.get("id", "")

        # Compact date display: keep only date part
        def short(d):
            return d[:10] if d and len(d) >= 10 else d

        url  = job_url(jid) if jid else ""
        link = f"[Apply]({url})" if url else "—"
        lines.append(f"| {course} | {title} | {dept} | {short(posted)} | {short(closes)} | {link} |")

    lines.append("")
    lines.append("---")
    lines.append(f"*Auto-generated by [unit1.hrandequity.utoronto.ca](https://github.com) workflow · Filters: STEM TA · St. George*")

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Found {len(new_jobs)} new job(s). issue_body.md written.")

    # ── Update sent IDs and last-sent date ───────────────────────────────────
    for job in new_jobs:
        job_id = str(job.get("id", "")).strip()
        if job_id:
            sent_ids.add(job_id)
    save_state(STATE_FILE, sent_ids, today)

    sys.exit(0)  # signal to the workflow: go ahead and post


if __name__ == "__main__":
    main()
