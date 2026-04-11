#!/usr/bin/env python3
"""
Fetch freelance job/project listings from multiple free APIs and save as JSON.
Runs daily via GitHub Actions. Prioritizes FREELANCE PROJECT sources.
"""

import json
import requests
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
import re


def strip_html(text):
    """Remove HTML tags from a string."""
    clean = re.sub(r"<[^>]+>", " ", text or "")
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


UPWORK_QUERIES = [
    "data+engineering", "machine+learning", "python+data",
    "chatbot", "NLP", "dashboard+analytics", "ETL+pipeline",
    "AI+automation", "web+scraping+data", "data+analysis",
    "conversational+AI", "SQL+database",
]

def fetch_upwork_rss():
    """Fetch real Upwork freelance project postings via RSS feeds."""
    results = []
    seen_urls = set()
    for query in UPWORK_QUERIES:
        url = f"https://www.upwork.com/ab/feed/jobs/rss?q={query}&sort=recency"
        try:
            resp = requests.get(url, headers={"User-Agent": "PortfolioBuilder/1.0"}, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item"):
                link = item.findtext("link", "")
                if link in seen_urls:
                    continue
                seen_urls.add(link)
                title = item.findtext("title", "")
                desc = strip_html(item.findtext("description", ""))
                pub_date = item.findtext("pubDate", "")
                results.append({
                    "title": title, "company": "Upwork Client",
                    "description": desc[:2000], "url": link,
                    "tags": [query.replace("+", " ")],
                    "source": "Upwork", "date": pub_date,
                })
        except Exception as e:
            print(f"  Upwork RSS ({query}) failed: {e}")
        time.sleep(0.5)
    return results


def fetch_remoteok():
    try:
        resp = requests.get("https://remoteok.com/api",
            headers={"User-Agent": "PortfolioBuilder/1.0"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  RemoteOK failed: {e}")
        return []
    results = []
    for item in data[1:]:
        title = item.get("position", "")
        if not title:
            continue
        results.append({
            "title": title, "company": item.get("company", ""),
            "description": strip_html(item.get("description", ""))[:2000],
            "url": item.get("url", f"https://remoteok.com/l/{item.get('id', '')}"),
            "tags": item.get("tags", []), "source": "RemoteOK",
            "date": item.get("date", ""),
        })
    return results


def fetch_arbeitnow():
    try:
        resp = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=30)
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
            "title": title, "company": item.get("company_name", ""),
            "description": strip_html(item.get("description", ""))[:2000],
            "url": item.get("url", ""), "tags": item.get("tags", []),
            "source": "Arbeitnow", "date": item.get("created_at", ""),
        })
    return results


def fetch_remotive():
    try:
        resp = requests.get("https://remotive.com/api/remote-jobs", timeout=30)
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
            "title": title, "company": item.get("company_name", ""),
            "description": strip_html(item.get("description", ""))[:2000],
            "url": item.get("url", ""),
            "tags": [t for t in tags if t],
            "source": "Remotive", "date": item.get("publication_date", ""),
        })
    return results


WWR_CATEGORIES = [
    "remote-programming-jobs",
    "remote-design-jobs",
    "remote-devops-sysadmin-jobs",
]

def fetch_weworkremotely():
    results = []
    for category in WWR_CATEGORIES:
        url = f"https://weworkremotely.com/categories/{category}.json"
        try:
            resp = requests.get(url, headers={"User-Agent": "PortfolioBuilder/1.0"}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            for item in data:
                title = item.get("title", "")
                if not title:
                    continue
                results.append({
                    "title": title, "company": item.get("company_name", ""),
                    "description": strip_html(item.get("description", ""))[:2000],
                    "url": item.get("url", ""),
                    "tags": [category.replace("remote-", "").replace("-jobs", "")],
                    "source": "WeWorkRemotely",
                    "date": item.get("published_at", ""),
                })
        except Exception as e:
            print(f"  WWR ({category}) failed: {e}")
        time.sleep(0.5)
    return results


def main():
    print(f"Fetching listings at {datetime.now(timezone.utc).isoformat()}")
    all_jobs = []
    for name, fetcher in [
        ("Upwork RSS", fetch_upwork_rss),
        ("RemoteOK", fetch_remoteok),
        ("Arbeitnow", fetch_arbeitnow),
        ("Remotive", fetch_remotive),
        ("WeWorkRemotely", fetch_weworkremotely),
    ]:
        print(f"Fetching from {name}...")
        jobs = fetcher()
        print(f"  Got {len(jobs)} listings")
        all_jobs.extend(jobs)
        time.sleep(1)

    seen = set()
    unique = []
    for job in all_jobs:
        url = job.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(job)

    print(f"\nTotal unique listings: {len(unique)}")
    sources = {}
    for job in unique:
        s = job.get("source", "Unknown")
        sources[s] = sources.get(s, 0) + 1
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(unique),
        "listings": unique,
    }
    with open("listings.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote listings.json ({len(unique)} listings)")


if __name__ == "__main__":
    main()
