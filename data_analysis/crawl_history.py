"""
crawl_history.py — Historical job posting crawler for unit1.hrandequity.utoronto.ca

Fetches individual posting pages by ID, extracts structured data from the
Inertia.js `data-page` JSON blob, and stores results in SQLite.

Usage:
    python crawl_history.py                # full crawl from ID 1 upward
    python crawl_history.py --max-id 500   # stop at ID 500 (for testing)
    python crawl_history.py --workers 10   # tune concurrency
    python crawl_history.py --resume       # (default) skip IDs already in DB

Stop condition: once ID > 40000, stop after 10 consecutive IDs with no valid
posting found (across all URL variants).

Storage: history.db (SQLite) — compact, queryable, resumable.
"""

import argparse
import html
import json
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Lock

import requests

# ── Configuration ──────────────────────────────────────────────────────────────
BASE_URL = "https://unit1.hrandequity.utoronto.ca/posting/{}"
DB_FILE = "history.db"
REQUEST_TIMEOUT = 12  # seconds
REQUEST_DELAY = 0.05  # seconds between worker requests (polite)
STOP_CONSECUTIVE = 500  # consecutive 404-only IDs before stopping (if ID > 40000)
STOP_AFTER_ID = 40000  # only apply consecutive-miss stop above this ID

# URL ID variants to try for each numeric ID
def url_variants(n: int) -> list[str]:
    s = str(n)
    # plain + zero-padded to 2,3,4,5 digits (only when shorter than that)
    seen, variants = set(), []
    for width in [0, 2, 3, 4, 5]:
        v = s.zfill(width) if width else s
        if v not in seen:
            seen.add(v)
            variants.append(BASE_URL.format(v))
    return variants


# ── SQLite setup ────────────────────────────────────────────────────────────────
def init_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")      # safe concurrent writes
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS postings (
            id                    INTEGER PRIMARY KEY,
            url_variant           TEXT,            -- which URL pattern worked
            job_title             TEXT,
            course_id             TEXT,
            emergency             INTEGER,         -- 0/1
            campus_id             INTEGER,
            campus_name           TEXT,
            department_id         INTEGER,
            department_name       TEXT,
            position_type_id      INTEGER,
            position_type_name    TEXT,
            position_type_short   TEXT,
            positions             TEXT,            -- "est. 3" etc – keep as text
            appointment_size      TEXT,            -- hours, often "105"
            appointment_startdate TEXT,
            appointment_enddate   TEXT,
            posting_date          TEXT,            -- ISO date string
            closing_date          TEXT,
            expiry_date           TEXT,
            created_at            TEXT,
            salary                TEXT,
            course_enrolment      TEXT,
            duties                TEXT,
            qualifications_min    TEXT,
            qualifications_pref   TEXT,
            experience_criterion  TEXT,
            tutorial              TEXT,
            application_procedure TEXT,
            raw_json              TEXT             -- full posting JSON for future use
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS misses (
            id INTEGER PRIMARY KEY   -- IDs tried across all variants with no posting
        )
    """)
    conn.commit()
    return conn


# ── Parsing ─────────────────────────────────────────────────────────────────────
_DATA_PAGE_RE = re.compile(r'data-page="([^"]*)"', re.DOTALL)

def parse_posting(html_text: str):
    """Return the posting dict from an Inertia data-page blob, or None."""
    m = _DATA_PAGE_RE.search(html_text)
    if not m:
        return None
    try:
        data = json.loads(html.unescape(m.group(1)))
    except json.JSONDecodeError:
        return None
    props = data.get("props", {})
    posting = props.get("item")
    return posting   # None if not present (e.g. 404 page still returns 200)


def _isodate(val):
    """Normalise a date value to a bare ISO date string YYYY-MM-DD or None."""
    if not val:
        return None
    # Already looks like 2026-02-18T... → strip time
    if "T" in str(val):
        return str(val)[:10]
    return str(val)


def posting_to_row(posting: dict, url_variant: str) -> dict:
    campus = posting.get("campus") or {}
    dept   = posting.get("department") or {}
    ptype  = posting.get("position_type") or {}
    return {
        "id":                    posting["id"],
        "url_variant":           url_variant,
        "job_title":             posting.get("job_title"),
        "course_id":             posting.get("course_id"),
        "emergency":             1 if posting.get("emergency") else 0,
        "campus_id":             campus.get("id"),
        "campus_name":           campus.get("name"),
        "department_id":         dept.get("id"),
        "department_name":       dept.get("name"),
        "position_type_id":      ptype.get("id"),
        "position_type_name":    ptype.get("name"),
        "position_type_short":   ptype.get("shortname"),
        "positions":             posting.get("positions"),
        "appointment_size":      posting.get("appointment_size"),
        "appointment_startdate": _isodate(posting.get("appointment_startdate")),
        "appointment_enddate":   _isodate(posting.get("appointment_enddate")),
        "posting_date":          _isodate(posting.get("posting_date")),
        "closing_date":          _isodate(posting.get("closing_date")),
        "expiry_date":           _isodate(posting.get("expiry_date")),
        "created_at":            _isodate(posting.get("created_at")),
        "salary":                posting.get("salery"),   # note: site spells it this way
        "course_enrolment":      posting.get("course_enrolment"),
        "duties":                posting.get("duties"),
        "qualifications_min":    posting.get("qualifications_minimum"),
        "qualifications_pref":   posting.get("qualifications_preferred"),
        "experience_criterion":  posting.get("experience"),
        "tutorial":              posting.get("tutorial"),
        "application_procedure": posting.get("application_procedure"),
        "raw_json":              json.dumps(posting, ensure_ascii=False),
    }


# ── Fetcher ─────────────────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (historical-crawler/1.0)"})

_write_lock = Lock()

def fetch_id(numeric_id: int, conn: sqlite3.Connection, stats: dict) -> bool:
    """Try all URL variants for a numeric ID. Returns True if a posting was saved."""
    time.sleep(REQUEST_DELAY)

    for url in url_variants(numeric_id):
        try:
            resp = SESSION.get(url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            continue

        if resp.status_code == 404:
            continue

        if resp.status_code != 200:
            continue   # unexpected – skip this variant

        posting = parse_posting(resp.text)
        if posting is None:
            continue

        row = posting_to_row(posting, url)

        with _write_lock:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO postings VALUES (
                        :id, :url_variant, :job_title, :course_id, :emergency,
                        :campus_id, :campus_name, :department_id, :department_name,
                        :position_type_id, :position_type_name, :position_type_short,
                        :positions, :appointment_size,
                        :appointment_startdate, :appointment_enddate,
                        :posting_date, :closing_date, :expiry_date, :created_at,
                        :salary, :course_enrolment, :duties,
                        :qualifications_min, :qualifications_pref,
                        :experience_criterion, :tutorial,
                        :application_procedure, :raw_json
                    )
                """, row)
                conn.commit()
                stats["found"] += 1
            except sqlite3.Error as e:
                print(f"  [DB ERROR] id={numeric_id}: {e}")
        return True  # found a posting — no need to try more variants

    # No variant yielded a posting
    with _write_lock:
        conn.execute("INSERT OR IGNORE INTO misses VALUES (?)", (numeric_id,))
        conn.commit()
    return False


# ── Main crawl loop ─────────────────────────────────────────────────────────────
def already_processed(conn: sqlite3.Connection) -> set[int]:
    seen = set()
    seen.update(r[0] for r in conn.execute("SELECT id FROM postings"))
    seen.update(r[0] for r in conn.execute("SELECT id FROM misses"))
    return seen


def crawl(max_id: int | None, workers: int):
    conn = init_db(DB_FILE)
    done = already_processed(conn)

    stats = {
        "scanned": 0,
        "found": 0,
        "consecutive_misses": 0,
        "start_time": time.time(),
    }

    print(f"Resuming crawl. Already processed: {len(done)} IDs.")
    print(f"Workers: {workers} | Stop condition: {STOP_CONSECUTIVE} consecutive misses after ID {STOP_AFTER_ID}")
    if max_id:
        print(f"Max ID: {max_id}")
    print()

    numeric_id = 0
    stop_flag = False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}

        def submit_next():
            nonlocal numeric_id
            while True:
                numeric_id += 1
                if max_id and numeric_id > max_id:
                    return False
                if numeric_id not in done:
                    futures[pool.submit(fetch_id, numeric_id, conn, stats)] = numeric_id
                    return True
                # skip already-done, but count against consecutive-miss logic?
                # No — already-done IDs are neutral; only fresh misses count.

        # Pre-fill the pool
        for _ in range(workers * 2):
            if not submit_next():
                break

        while futures:
            done_future = next(as_completed(futures))
            fid = futures.pop(done_future)
            found = done_future.result()
            stats["scanned"] += 1

            if found:
                stats["consecutive_misses"] = 0
            else:
                if fid > STOP_AFTER_ID:
                    stats["consecutive_misses"] += 1

            # Progress print every 100 IDs
            if stats["scanned"] % 100 == 0:
                elapsed = time.time() - stats["start_time"]
                rate = stats["scanned"] / elapsed if elapsed else 0
                print(
                    f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] "
                    f"id≈{fid:>6}  scanned={stats['scanned']:>6}  "
                    f"found={stats['found']:>5}  "
                    f"consec_miss={stats['consecutive_misses']:>3}  "
                    f"rate={rate:.1f}/s"
                )

            # Check stop condition
            if fid > STOP_AFTER_ID and stats["consecutive_misses"] >= STOP_CONSECUTIVE:
                print(f"\nStop condition met at ID {fid} ({stats['consecutive_misses']} consecutive misses).")
                stop_flag = True
                break

            # Submit more work
            if not stop_flag:
                if not submit_next():
                    pass  # hit max_id or we'll drain naturally

        # Cancel remaining futures if we stopped early
        if stop_flag:
            for f in list(futures):
                f.cancel()

    elapsed = time.time() - stats["start_time"]
    print(f"\n{'='*60}")
    print(f"Crawl complete.")
    print(f"  Total scanned : {stats['scanned']}")
    print(f"  Postings saved: {stats['found']}")
    print(f"  Elapsed       : {elapsed/60:.1f} min")
    total_in_db = conn.execute("SELECT count(*) FROM postings").fetchone()[0]
    print(f"  Total in DB   : {total_in_db}")
    conn.close()


# ── Entry point ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl all historical job postings")
    parser.add_argument("--max-id",  type=int, default=None,
                        help="Stop at this ID (for testing)")
    parser.add_argument("--workers", type=int, default=6,
                        help="Number of concurrent HTTP workers (default: 6)")
    args = parser.parse_args()
    crawl(max_id=args.max_id, workers=args.workers)
