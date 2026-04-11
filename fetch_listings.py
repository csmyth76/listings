#!/usr/bin/env python3
"""
Fetch freelance job listings from free public APIs and save as JSON.

Runs daily via GitHub Actions. The output file (listings.json) is committed
to the repo so the Databricks app can read it from raw.githubusercontent.com.
"""

import json
import requests
import time
from datetime import datetime, timezone


def fetch_remoteok() -> list[dict]:
    """Fetch all current listings from RemoteOK (free, no key)."""
    try:
        resp = requests.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "PortfolioBuilder/1.0"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  RemoteOK failed: {e}")
        return []

    results = []
    for item in data[1:]:  # skip legal notice
        title = item.get("position", "")
        if not title:
            continue
        results.append({
            "title": title,
            "company": item.get("company", ""),
            "description": (item.get("description", "") or "")[:2000],
            "url": item.get("url", f"https://remoteok.com/l/{item.get('id', '')}"),
            "tags": item.get("tags", []),
            "source": "RemoteOK",
            "date": item.get("date", ""),
        })
    return results


def fetch_arbeitnow() -> list[dict]:
    """Fetch all current listings from Arbeitnow (free, no key)."""
    try:
        resp = requests.get(
            "https://www.arbeitnow.com/api/job-board-api",
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Arbeitnow failed: {e}")
        return []

    results = []
    for item in data.get("data", []):
        title = item.get("title", "")
        if not title:
            continue
        results.append({
            "title": title,
            "company": item.get("company_name", ""),
            "description": (item.get("description", "") or "")[:2000],
            "url": item.get("url", ""),
            "tags": item.get("tags", []),
            "source": "Arbeitnow",
            "date": item.get("created_at", ""),
        })
    return results


def fetch_remotive() -> list[dict]:
    """Fetch all current listings from Remotive (free, no key)."""
    try:
        resp = requests.get(
            "https://remotive.com/api/remote-jobs",
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Remotive failed: {e}")
        return []

    results = []
    for item in data.get("jobs", []):
        title = item.get("title", "")
        if not title:
            continue
        tags = [item.get("category", "")]
        if item.get("job_type"):
            tags.append(item["job_type"])
        results.append({
            "title": title,
            "company": item.get("company_name", ""),
            "description": (item.get("description", "") or "")[:2000],
            "url": item.get("url", ""),
            "tags": [t for t in tags if t],
            "source": "Remotive",
            "date": item.get("publication_date", ""),
        })
    return results


def main():
    print(f"Fetching listings at {datetime.now(timezone.utc).isoformat()}")

    all_jobs = []
    for name, fetcher in [
        ("RemoteOK", fetch_remoteok),
        ("Arbeitnow", fetch_arbeitnow),
        ("Remotive", fetch_remotive),
    ]:
        print(f"Fetching from {name}...")
        jobs = fetcher()
        print(f"  Got {len(jobs)} listings")
        all_jobs.extend(jobs)
        time.sleep(1)  # polite delay

    # De-duplicate by URL
    seen = set()
    unique = []
    for job in all_jobs:
        url = job.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(job)

    print(f"\nTotal unique listings: {len(unique)}")

    # Write output
    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(unique),
        "listings": unique,
    }

    with open("listings.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote listings.json ({len(unique)} listings)")


if __name__ == "__main__":
    main()
