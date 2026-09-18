"""
notify_ta_jobs.py

Multi-profile TA job alert system.
Reads profiles from subscriptions.json, filters result.csv per profile,
and posts GitHub Issue comments for new matching jobs.
Exits 0 if any profile sent a comment, exits 1 if nothing was posted.
"""

import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

CSV_FILE          = "result.csv"
STATE_FILE        = "ta_alert_state.json"
SUBS_FILE         = "subscriptions.json"
MIN_INTERVAL_DAYS = 7   # never send more than once per week per profile
URGENT_DAYS       = 5   # bypass throttle if any job closes within this many days


# ── State helpers ─────────────────────────────────────────────────────────────

def _parse_date_str(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None


def load_state(path, profiles):
    """
    Load per-profile state from JSON.
    Auto-migrates from the old single-profile format if needed.
    Returns: {profile_name: {"last_sent": datetime|None, "sent_ids": set}}
    """
    default = {p["profile"]: {"last_sent": None, "sent_ids": set()} for p in profiles}

    if not os.path.exists(path):
        return default

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Detect old single-profile format (top-level "last_sent" + "sent_ids")
    if "last_sent" in data and "sent_ids" in data:
        print("Migrating ta_alert_state.json to multi-profile format...")
        result = default.copy()
        first_profile = profiles[0]["profile"] if profiles else None
        if first_profile:
            result[first_profile] = {
                "last_sent": _parse_date_str(data.get("last_sent")),
                "sent_ids":  set(data.get("sent_ids", [])),
            }
        return result

    # New multi-profile format
    result = default.copy()
    for name, pdata in data.items():
        result[name] = {
            "last_sent": _parse_date_str(pdata.get("last_sent")),
            "sent_ids":  set(pdata.get("sent_ids", [])),
        }
    return result


def save_state(path, state):
    data = {}
    for name, pdata in state.items():
        data[name] = {
            "last_sent": pdata["last_sent"].strftime("%Y-%m-%d") if pdata["last_sent"] else None,
            "sent_ids":  sorted(pdata["sent_ids"]),
        }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


# ── Date parsing ──────────────────────────────────────────────────────────────

def parse_date(s):
    """Parse any date format using dateutil (bundled with pandas)."""
    if not s or not s.strip():
        return None
    try:
        from dateutil import parser as du_parser
        return du_parser.parse(s.strip(), dayfirst=True)
    except Exception:
        return None


# ── Profile matching ──────────────────────────────────────────────────────────

def matches_profile(row, profile):
    """
    Return True if the CSV row satisfies all of the profile's filter criteria.

    Profile schema:
      campus  : str   — exact match on campus field (case-insensitive)
      ptype   : str | list[str] — exact match on ptype field
      match   : dict  — {field_name: [keywords]}
                  A job passes if ANY keyword matches in ANY listed field (OR logic).
                  Supported fields: "department", "job_title"
    """
    campus = (row.get("campus", "") or "").strip()
    ptype  = (row.get("ptype",  "") or "").strip()
    dept   = (row.get("department", "") or "").strip().lower()
    title  = (row.get("job_title",  "") or "").strip().lower()

    # Campus: exact, case-insensitive
    expected_campus = profile.get("campus", "")
    if expected_campus and campus.lower() != expected_campus.lower():
        return False

    # Ptype: exact, case-insensitive; accepts string or list
    allowed_ptypes = profile.get("ptype", [])
    if isinstance(allowed_ptypes, str):
        allowed_ptypes = [allowed_ptypes]
    if allowed_ptypes and ptype.lower() not in [p.lower() for p in allowed_ptypes]:
        return False

    # Undergrad-only filter:
    # UofT undergrad course codes have 3 digits after the dept letters (e.g. BIO230H1, BCH 242Y)
    # Grad courses have 4 digits (e.g. BIO1001H)
    if profile.get("undergrad_only"):
        import re
        course_id_raw = (row.get("course_id", "") or "").strip()
        m = re.match(r'^[A-Za-z\s]+(\d+)', course_id_raw)
        if not m or len(m.group(1)) != 3:
            return False

    # Keyword matching across specified fields (OR logic)
    # Supported fields: "department", "job_title", "course_id"
    match_cfg = profile.get("match", {})
    if match_cfg:
        course_id_clean = (row.get("course_id", "") or "").strip().upper().replace(" ", "")
        found = False
        for field, keywords in match_cfg.items():
            if field == "course_id":
                # Prefix match for course code (e.g. BIO matches BIO120H1, BIO 230)
                if any(course_id_clean.startswith(kw.upper().replace(" ", "")) for kw in keywords):
                    found = True
                    break
            elif field == "department":
                if any(kw.lower() in dept for kw in keywords):
                    found = True
                    break
            elif field == "job_title":
                if any(kw.lower() in title for kw in keywords):
                    found = True
                    break
            else:
                val = (row.get(field, "") or "").strip().lower()
                if any(kw.lower() in val for kw in keywords):
                    found = True
                    break

        if not found:
            return False

    return True


# ── Notification helpers ──────────────────────────────────────────────────────

def job_url(job_id):
    return f"https://unit1.hrandequity.utoronto.ca/posting/{job_id}"


def build_comment(profile_name, new_jobs, today):
    def short(d):
        return d[:10] if d and len(d) >= 10 else (d or "—")

    lines = [
        f"## 🎓 {profile_name} — TA Job Alert · {today.strftime('%Y-%m-%d')}",
        "",
        f"**{len(new_jobs)} new posting(s)** at **St. George**.",
        "",
        "| Course | Title | Department | Posted | Closes | Link |",
        "|--------|-------|------------|--------|--------|------|",
    ]
    for job in new_jobs:
        course = job.get("course_id", "—")
        title  = job.get("job_title",  "—")
        dept   = job.get("department", "—")
        posted = short(job.get("posting_date", ""))
        closes = short(job.get("closing_date", ""))
        jid    = job.get("id", "")
        link   = f"[Apply]({job_url(jid)})" if jid else "—"
        lines.append(f"| {course} | {title} | {dept} | {posted} | {closes} | {link} |")
    lines += [
        "",
        "---",
        f"*Auto-generated by GitHub Actions · Profile: **{profile_name}***",
    ]
    return "\n".join(lines) + "\n"


def post_comment(issue_number, body):
    """Write body to issue_body.md and post via gh CLI. Returns True on success."""
    with open("issue_body.md", "w", encoding="utf-8") as f:
        f.write(body)
    result = subprocess.run(
        ["gh", "issue", "comment", str(issue_number), "--body-file", "issue_body.md"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        return False
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Load subscriptions
    if not os.path.exists(SUBS_FILE):
        print(f"ERROR: {SUBS_FILE} not found.")
        sys.exit(1)
    with open(SUBS_FILE, encoding="utf-8") as f:
        profiles = json.load(f)

    # Load per-profile state (auto-migrates old format)
    state = load_state(STATE_FILE, profiles)

    # Load CSV once
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

    any_sent = False

    for profile in profiles:
        name  = profile["profile"]
        issue = profile["issue"]

        pstate   = state.setdefault(name, {"last_sent": None, "sent_ids": set()})
        sent_ids = pstate["sent_ids"]

        # Prune IDs of jobs that no longer exist in the CSV
        # (they'll be treated as new if they ever reappear)
        sent_ids &= current_ids

        # ── Filter new matching jobs ──────────────────────────────────────────
        new_jobs = []
        for job_id, row in all_rows:
            if not job_id or job_id in sent_ids:
                continue
            if not matches_profile(row, profile):
                continue
            closing = parse_date(row.get("closing_date", ""))
            if closing is None:
                continue
            closing = closing.replace(hour=0, minute=0, second=0, microsecond=0)
            if closing < today:
                continue          # skip expired
            new_jobs.append(row)

        if not new_jobs:
            print(f"[{name}] No new jobs. Skipping.")
            continue

        # ── Send-frequency gate ───────────────────────────────────────────────
        #
        #   New jobs found?
        #   └── Yes → Any closing within URGENT_DAYS?
        #             ├── Yes (urgent) → send now
        #             └── No → last send ≥ MIN_INTERVAL_DAYS ago?
        #                       ├── Yes → send now
        #                       └── No  → skip (don't mark as sent)
        #
        last_sent  = pstate["last_sent"]
        days_since = (today - last_sent).days if last_sent else MIN_INTERVAL_DAYS

        urgent = any(
            (parse_date(j.get("closing_date", "")) or datetime.max)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            <= today + timedelta(days=URGENT_DAYS)
            for j in new_jobs
        )

        if urgent:
            print(f"[{name}] Urgent — {len(new_jobs)} job(s) — sending now.")
        elif days_since >= MIN_INTERVAL_DAYS:
            print(f"[{name}] Weekly send ({days_since}d since last) — {len(new_jobs)} job(s).")
        else:
            remaining = MIN_INTERVAL_DAYS - days_since
            print(f"[{name}] Throttled — sent {days_since}d ago, next non-urgent in {remaining}d.")
            continue   # do NOT mark jobs as sent

        # ── Sort and post ─────────────────────────────────────────────────────
        new_jobs.sort(key=lambda r: parse_date(r.get("closing_date", "")) or datetime.max)

        body = build_comment(name, new_jobs, today)
        print(f"[{name}] Posting to issue #{issue}...")

        if post_comment(issue, body):
            for job in new_jobs:
                jid = str(job.get("id", "")).strip()
                if jid:
                    sent_ids.add(jid)
            pstate["last_sent"] = today
            pstate["sent_ids"]  = sent_ids
            any_sent = True
            print(f"[{name}] ✓ Done.")
        else:
            print(f"[{name}] ✗ Post failed — state not updated.")

    save_state(STATE_FILE, state)
    sys.exit(0 if any_sent else 1)


if __name__ == "__main__":
    main()
