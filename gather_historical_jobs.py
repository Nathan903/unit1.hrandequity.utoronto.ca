"""
gather_historical_jobs.py

Walks every git commit in the past 6 months that touched result.csv,
extracts all rows, deduplicates by job ID, and writes historical_jobs.csv.
"""

import subprocess
import csv
import io
import sys
from datetime import datetime, timedelta

SINCE = (datetime.now() - timedelta(days=183)).strftime("%Y-%m-%d")
OUTPUT = "historical_jobs.csv"

def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout

# Get all commit hashes that touched result.csv in the past 6 months
print(f"Fetching commits since {SINCE}...")
log = run(["git", "log", "--format=%H", f"--after={SINCE}", "--", "result.csv"])
hashes = [h.strip() for h in log.strip().splitlines() if h.strip()]
print(f"Found {len(hashes)} commits to scan.")

all_jobs = {}   # id -> row dict (keeps latest-seen version of each job)
fieldnames = None

for i, h in enumerate(hashes):
    if i % 50 == 0:
        print(f"  Processing commit {i+1}/{len(hashes)}...")
    csv_content = run(["git", "show", f"{h}:result.csv"])
    if not csv_content.strip():
        continue
    try:
        reader = csv.DictReader(io.StringIO(csv_content))
        if fieldnames is None and reader.fieldnames:
            fieldnames = reader.fieldnames
        for row in reader:
            job_id = str(row.get("id", "")).strip()
            if job_id and job_id not in all_jobs:
                all_jobs[job_id] = row   # keep first (most recent) occurrence
    except Exception as e:
        print(f"  Warning: could not parse commit {h[:8]}: {e}")

print(f"\nTotal unique jobs found: {len(all_jobs)}")

if not all_jobs:
    print("No jobs found. Exiting.")
    sys.exit(1)

# Sort by closing_date descending so most-recent are at the top
def sort_key(row):
    d = row.get("closing_date", "") or ""
    return d

rows = sorted(all_jobs.values(), key=sort_key, reverse=True)

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Written to {OUTPUT}")
