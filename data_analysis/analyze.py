"""
analyze.py — Interesting statistics from the crawled job posting history.

Run this after crawl_history.py has populated history.db.

Usage:
    python analyze.py
    python analyze.py --db history.db --out analysis_output

Produces:
  - Console print of key stats
  - PNG charts in the output folder
"""

import argparse
import os
import sqlite3
import warnings

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Helpers ────────────────────────────────────────────────────────────────────
STYLE = "seaborn-v0_8-darkgrid"


def load_df(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM postings", conn)
    conn.close()

    # Parse dates
    for col in ["posting_date", "closing_date", "expiry_date",
                "appointment_startdate", "appointment_enddate", "created_at"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # Derived columns
    df["posting_year"]  = df["posting_date"].dt.year
    df["posting_month"] = df["posting_date"].dt.month          # 1–12
    df["posting_month_name"] = df["posting_date"].dt.strftime("%b")
    df["posting_dow"]   = df["posting_date"].dt.dayofweek      # 0=Mon
    df["posting_dow_name"] = df["posting_date"].dt.strftime("%a")

    # Lead time: days between posting_date and closing_date
    df["lead_days"] = (df["closing_date"] - df["posting_date"]).dt.days

    # Positions as numeric (best-effort)
    df["positions_num"] = pd.to_numeric(df["positions"], errors="coerce")

    # Appointment hours as numeric (best-effort)
    df["appt_hours"] = pd.to_numeric(
        df["appointment_size"].str.extract(r"(\d+)")[0], errors="coerce"
    )

    return df


def save(fig, name: str, out_dir: str):
    path = os.path.join(out_dir, name)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  → saved {path}")


MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DOW_ORDER   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ── Plots ──────────────────────────────────────────────────────────────────────

def plot_postings_over_time(df, out_dir):
    """Total postings per year-month as an area chart."""
    monthly = (
        df.dropna(subset=["posting_date"])
          .groupby(df["posting_date"].dt.tz_localize(None).dt.to_period("M"))
          .size()
          .sort_index()
    )
    fig, ax = plt.subplots(figsize=(14, 4))
    monthly.plot(ax=ax, kind="area", color="#4c72b0", alpha=0.7, linewidth=1.2)
    ax.set_title("Number of Job Postings per Month (all time)", fontsize=14, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Postings")
    fig.tight_layout()
    save(fig, "01_postings_over_time.png", out_dir)


def plot_annual_trend(df, out_dir):
    """Postings per year bar chart."""
    annual = df.dropna(subset=["posting_year"]).groupby("posting_year").size()
    fig, ax = plt.subplots(figsize=(10, 4))
    annual.plot(kind="bar", ax=ax, color="#4c72b0", edgecolor="white")
    ax.set_title("Total Postings per Year", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Postings")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    save(fig, "02_postings_per_year.png", out_dir)


def plot_monthly_seasonality(df, out_dir):
    """Avg monthly postings across all years — reveals academic calendar patterns."""
    monthly = (
        df.dropna(subset=["posting_month_name"])
          .groupby(["posting_year", "posting_month_name"])
          .size()
          .reset_index(name="count")
          .groupby("posting_month_name")["count"]
          .mean()
          .reindex(MONTH_ORDER)
    )
    fig, ax = plt.subplots(figsize=(10, 4))
    monthly.plot(kind="bar", ax=ax, color="#dd8452", edgecolor="white")
    ax.set_title("Average Postings by Month (all years) — Seasonal Pattern", fontsize=14, fontweight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel("Avg postings")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    save(fig, "03_seasonal_pattern.png", out_dir)


def plot_stgeorge_engineering_timing(df, out_dir):
    """When do St. George engineering/CS TA jobs get posted? (month + day-of-week)"""
    # Filter: St. George campus, engineering-ish departments or courses
    eng_keywords = r"engineer|comput|electrical|mechanic|chem|civil|material|ece|csc|aps|aer|chm|phy|mie|esc|msc|mec"
    sg = df[
        (df["campus_name"].str.lower() == "st. george") &
        (
            df["department_name"].str.contains(eng_keywords, case=False, na=False, regex=True) |
            df["course_id"].str.match(r"(APS|ECE|CSC|ESC|MIE|AER|CHM|PHY|MSE|MEC|BME|CHE|CIV|IND|JRE|ROB|TEP|HPS|MAT|STA)", case=False, na=False)
        )
    ]
    print(f"\n  St. George Engineering/CS postings found: {len(sg)}")

    if len(sg) < 5:
        print("  (not enough data for this chart)")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4))

    # Month distribution
    m_counts = sg["posting_month_name"].value_counts().reindex(MONTH_ORDER).fillna(0)
    m_counts.plot(kind="bar", ax=ax1, color="#55a868", edgecolor="white")
    ax1.set_title("By Month", fontweight="bold")
    ax1.set_xlabel("")
    ax1.set_ylabel("Postings")
    ax1.tick_params(axis="x", rotation=0)

    # Day-of-week distribution
    d_counts = sg["posting_dow_name"].value_counts().reindex(DOW_ORDER).fillna(0)
    d_counts.plot(kind="bar", ax=ax2, color="#c44e52", edgecolor="white")
    ax2.set_title("By Day of Week", fontweight="bold")
    ax2.set_xlabel("")
    ax2.tick_params(axis="x", rotation=0)

    fig.suptitle("St. George Engineering/CS TA Posting Timing", fontsize=14, fontweight="bold")
    fig.tight_layout()
    save(fig, "04_stgeorge_eng_timing.png", out_dir)

    # Also print peak month
    peak_month = m_counts.idxmax()
    print(f"  Peak posting month for St. George Engineering/CS: {peak_month}")


def plot_campus_breakdown(df, out_dir):
    counts = df["campus_name"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 5))
    wedges, texts, autotexts = ax.pie(
        counts, labels=counts.index, autopct="%1.1f%%",
        startangle=140, pctdistance=0.82,
        colors=["#4c72b0", "#dd8452", "#55a868", "#c44e52", "#9374b2"],
    )
    ax.set_title("Postings by Campus", fontsize=14, fontweight="bold")
    fig.tight_layout()
    save(fig, "05_campus_breakdown.png", out_dir)


def plot_top_departments(df, out_dir, n=25):
    top = df["department_name"].value_counts().head(n)
    fig, ax = plt.subplots(figsize=(10, 7))
    top[::-1].plot(kind="barh", ax=ax, color="#4c72b0", edgecolor="white")
    ax.set_title(f"Top {n} Departments by Number of Postings", fontsize=14, fontweight="bold")
    ax.set_xlabel("Postings")
    fig.tight_layout()
    save(fig, "06_top_departments.png", out_dir)


def plot_position_type_breakdown(df, out_dir):
    counts = df["position_type_name"].value_counts()
    fig, ax = plt.subplots(figsize=(9, 4))
    counts.plot(kind="bar", ax=ax, color="#8172b3", edgecolor="white")
    ax.set_title("Postings by Position Type", fontsize=14, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Postings")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    save(fig, "07_position_types.png", out_dir)


def plot_emergency_rate_over_time(df, out_dir):
    """Fraction of postings that are marked 'emergency' per year."""
    yearly = df.dropna(subset=["posting_year"]).groupby("posting_year").agg(
        total=("emergency", "count"),
        emerg=("emergency", "sum"),
    )
    yearly["rate"] = yearly["emerg"] / yearly["total"] * 100
    fig, ax = plt.subplots(figsize=(10, 4))
    yearly["rate"].plot(ax=ax, marker="o", color="#c44e52", linewidth=2)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_title("Emergency Posting Rate per Year", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("% Emergency")
    fig.tight_layout()
    save(fig, "08_emergency_rate.png", out_dir)


def plot_lead_time_distribution(df, out_dir):
    """Distribution of days between posting_date and closing_date."""
    lead = df["lead_days"].dropna()
    lead = lead[(lead >= 0) & (lead <= 90)]   # reasonable range
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(lead, bins=45, color="#4c72b0", edgecolor="white", alpha=0.85)
    ax.axvline(lead.median(), color="#c44e52", linestyle="--", linewidth=1.8,
               label=f"Median: {lead.median():.0f} days")
    ax.set_title("Distribution of Days Between Posting and Closing Date", fontsize=14, fontweight="bold")
    ax.set_xlabel("Days")
    ax.set_ylabel("Count")
    ax.legend()
    fig.tight_layout()
    save(fig, "09_lead_time_distribution.png", out_dir)


def plot_positions_per_posting(df, out_dir):
    """Distribution of number of positions per posting (e.g. how many TAs per course)."""
    pos = df["positions_num"].dropna()
    pos = pos[(pos >= 1) & (pos <= 50)]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(pos, bins=range(1, 52), color="#55a868", edgecolor="white", alpha=0.85)
    ax.axvline(pos.median(), color="#c44e52", linestyle="--", linewidth=1.8,
               label=f"Median: {pos.median():.0f}")
    ax.set_title("Number of Positions per Posting", fontsize=14, fontweight="bold")
    ax.set_xlabel("Positions")
    ax.set_ylabel("Count")
    ax.legend()
    fig.tight_layout()
    save(fig, "10_positions_per_posting.png", out_dir)


def plot_appointment_hours(df, out_dir):
    """Distribution of appointment hours (size of appointment)."""
    hrs = df["appt_hours"].dropna()
    hrs = hrs[(hrs >= 1) & (hrs <= 500)]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(hrs, bins=50, color="#dd8452", edgecolor="white", alpha=0.85)
    ax.axvline(hrs.median(), color="#4c72b0", linestyle="--", linewidth=1.8,
               label=f"Median: {hrs.median():.0f} h")
    ax.set_title("Distribution of Appointment Size (Hours)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Hours")
    ax.set_ylabel("Count")
    ax.legend()
    fig.tight_layout()
    save(fig, "11_appointment_hours.png", out_dir)


def plot_day_of_week_all(df, out_dir):
    """On which days of the week are postings most commonly made?"""
    dow = df["posting_dow_name"].value_counts().reindex(DOW_ORDER).fillna(0)
    fig, ax = plt.subplots(figsize=(8, 4))
    dow.plot(kind="bar", ax=ax, color="#8172b3", edgecolor="white")
    ax.set_title("Postings by Day of Week (all postings)", fontsize=14, fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Postings")
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    save(fig, "12_day_of_week.png", out_dir)


def plot_top_courses(df, out_dir, n=20):
    """Most frequently posted courses."""
    top = df["course_id"].dropna().value_counts().head(n)
    fig, ax = plt.subplots(figsize=(10, 6))
    top[::-1].plot(kind="barh", ax=ax, color="#4c72b0", edgecolor="white")
    ax.set_title(f"Top {n} Most Frequently Posted Courses", fontsize=14, fontweight="bold")
    ax.set_xlabel("Times Posted")
    fig.tight_layout()
    save(fig, "13_top_courses.png", out_dir)


def plot_stgeorge_eng_by_year(df, out_dir):
    """Yearly growth of St. George Engineering/CS postings."""
    eng_keywords = r"engineer|comput|electrical|mechanic|chem|civil|material|ece|csc|aps|aer|chm|phy|mie|esc"
    sg = df[
        (df["campus_name"].str.lower() == "st. george") &
        (
            df["department_name"].str.contains(eng_keywords, case=False, na=False, regex=True) |
            df["course_id"].str.match(r"(APS|ECE|CSC|ESC|MIE|AER|CHM|PHY|MSE|MEC|BME|CHE|CIV|IND)", case=False, na=False)
        )
    ]
    if len(sg) < 5:
        return
    yearly = sg.dropna(subset=["posting_year"]).groupby("posting_year").size()
    fig, ax = plt.subplots(figsize=(10, 4))
    yearly.plot(kind="bar", ax=ax, color="#55a868", edgecolor="white")
    ax.set_title("St. George Engineering/CS Postings per Year", fontsize=14, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Postings")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    save(fig, "14_stgeorge_eng_by_year.png", out_dir)


# ── Console stats ──────────────────────────────────────────────────────────────
def print_stats(df: pd.DataFrame):
    print("\n" + "="*60)
    print("  HISTORICAL POSTING STATISTICS")
    print("="*60)
    print(f"  Total postings in DB         : {len(df):,}")

    yr_min = df["posting_year"].min()
    yr_max = df["posting_year"].max()
    print(f"  Date range                   : {yr_min:.0f} – {yr_max:.0f}")

    print(f"  Unique campuses              : {df['campus_name'].nunique()}")
    print(f"  Unique departments           : {df['department_name'].nunique()}")
    print(f"  Unique courses               : {df['course_id'].nunique()}")
    print(f"  Emergency postings           : {df['emergency'].sum():,} ({df['emergency'].mean()*100:.1f}%)")

    med_lead = df["lead_days"].median()
    print(f"  Median lead time (post→close): {med_lead:.0f} days")
    med_pos = df["positions_num"].median()
    print(f"  Median positions per posting : {med_pos:.1f}")

    print("\n  --- Top 5 Campuses ---")
    print(df["campus_name"].value_counts().head(5).to_string())

    print("\n  --- Top 5 Position Types ---")
    print(df["position_type_name"].value_counts().head(5).to_string())

    print("\n  --- Top 10 Departments ---")
    print(df["department_name"].value_counts().head(10).to_string())

    print("\n  --- Postings by Season ---")
    season_map = {12: "Winter", 1: "Winter", 2: "Winter",
                  3: "Spring",  4: "Spring",  5: "Spring",
                  6: "Summer",  7: "Summer",  8: "Summer",
                  9: "Fall",   10: "Fall",   11: "Fall"}
    df["season"] = df["posting_month"].map(season_map)
    print(df["season"].value_counts().reindex(["Fall","Winter","Spring","Summer"]).to_string())
    print("="*60 + "\n")


# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Analyze crawled job posting history")
    parser.add_argument("--db",  default="history.db",       help="SQLite DB path")
    parser.add_argument("--out", default="analysis_output",  help="Output folder for charts")
    parser.add_argument("--style", default=STYLE,            help="Matplotlib style")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    plt.style.use(args.style)

    print(f"Loading data from {args.db} ...")
    df = load_df(args.db)
    print(f"Loaded {len(df):,} postings.")

    print_stats(df)

    print("Generating charts ...")
    plot_postings_over_time(df, args.out)
    plot_annual_trend(df, args.out)
    plot_monthly_seasonality(df, args.out)
    plot_stgeorge_engineering_timing(df, args.out)
    plot_campus_breakdown(df, args.out)
    plot_top_departments(df, args.out)
    plot_position_type_breakdown(df, args.out)
    plot_emergency_rate_over_time(df, args.out)
    plot_lead_time_distribution(df, args.out)
    plot_positions_per_posting(df, args.out)
    plot_appointment_hours(df, args.out)
    plot_day_of_week_all(df, args.out)
    plot_top_courses(df, args.out)
    plot_stgeorge_eng_by_year(df, args.out)

    print(f"\nAll done. Charts saved to '{args.out}/'")


if __name__ == "__main__":
    main()
