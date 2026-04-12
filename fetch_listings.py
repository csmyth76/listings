#!/usr/bin/env python3
"""
Fetch freelance project listings from multiple free APIs.
Runs daily via GitHub Actions. Prioritizes FREELANCE/CONTRACT work.
"""

import json
import requests
import time
import re
from datetime import datetime, timezone
from html import unescape


def strip_html(text):
    clean = re.sub(r"<[^>]+>", " ", text or "")
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


FREELANCE_KEYWORDS = [
    "freelance", "contract", "contractor", "project-based", "part-time",
    "consultant", "gig", "independent", "short-term", "temporary",
    "per hour", "hourly", "fixed-price", "milestone", "deliverable",
    "seeking freelancer", "looking for freelancer", "need a developer",
    "build a", "create a", "develop a", "implement a", "design a",
]


def is_likely_freelance(title, description, tags):
    text = f"{title} {description[:500]} {' '.join(str(t) for t in tags)}".lower()
    return any(kw in text for kw in FREELANCE_KEYWORDS)


# ── HackerNews Freelancer threads (BEST freelance source) ────────────────────

def fetch_hn_freelance():
    """Fetch from HN 'Freelancer? Seeking Freelancer?' and 'Who is Hiring?' threads."""
    results = []

    queries = [
        "Freelancer? Seeking freelancer?",
        "Who is hiring?",
    ]

    for query in queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search?query={requests.utils.quote(query)}&tags=ask_hn&hitsPerPage=2"
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            for hit in data.get("hits", []):
                story_id = hit.get("objectID")
                if not story_id:
                    continue

                # Fetch comments (each comment is a freelance gig or job post)
                comments_url = f"https://hn.algolia.com/api/v1/items/{story_id}"
                cresp = requests.get(comments_url, timeout=30)
                cresp.raise_for_status()
                story = cresp.json()

                for child in story.get("children", []):
                    text = strip_html(child.get("text", ""))
                    if len(text) < 50:
                        continue

                    # Extract a title from first line
                    lines = text.split(".")
                    title = lines[0][:120] if lines else "HN Freelance Post"

                    is_freelance = is_likely_freelance(title, text, [])
                    is_seeking = "seeking freelancer" in query.lower()

                    results.append({
                        "title": title,
                        "company": child.get("author", "HN User"),
                        "description": text[:2000],
                        "url": f"https://news.ycombinator.com/item?id={child.get('id', story_id)}",
                        "tags": ["freelance" if is_seeking else "hiring", "hackernews"],
                        "source": "HackerNews",
                        "date": child.get("created_at", ""),
                        "listing_type": "freelance" if (is_seeking or is_freelance) else "mixed",
                    })

                time.sleep(1)
        except Exception as e:
            print(f"  HN ({query}) failed: {e}")

    return results


# ── RemoteOK ─────────────────────────────────────────────────────────────────

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
        tags = item.get("tags", [])
        desc = strip_html(item.get("description", ""))[:2000]
        freelance = is_likely_freelance(title, desc, tags)
        results.append({
            "title": title, "company": item.get("company", ""),
            "description": desc,
            "url": item.get("url", f"https://remoteok.com/l/{item.get('id', '')}"),
            "tags": tags, "source": "RemoteOK",
            "date": item.get("date", ""),
            "listing_type": "freelance" if freelance else "job",
        })
    return results


# ── Arbeitnow ────────────────────────────────────────────────────────────────

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
        tags = item.get("tags", [])
        desc = strip_html(item.get("description", ""))[:2000]
        freelance = is_likely_freelance(title, desc, tags)
        results.append({
            "title": title, "company": item.get("company_name", ""),
            "description": desc,
            "url": item.get("url", ""), "tags": tags,
            "source": "Arbeitnow", "date": item.get("created_at", ""),
            "listing_type": "freelance" if freelance else "job",
        })
    return results


# ── Remotive ─────────────────────────────────────────────────────────────────

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
        job_type = item.get("job_type", "")
        if job_type:
            tags.append(job_type)
        desc = strip_html(item.get("description", ""))[:2000]
        freelance = is_likely_freelance(title, desc, tags) or "contract" in job_type.lower()
        results.append({
            "title": title, "company": item.get("company_name", ""),
            "description": desc,
            "url": item.get("url", ""),
            "tags": [t for t in tags if t],
            "source": "Remotive", "date": item.get("publication_date", ""),
            "listing_type": "freelance" if freelance else "job",
        })
    return results


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Fetching listings at {datetime.now(timezone.utc).isoformat()}")

    all_jobs = []
    for name, fetcher in [
        ("HackerNews Freelance", fetch_hn_freelance),
        ("RemoteOK", fetch_remoteok),
        ("Arbeitnow", fetch_arbeitnow),
        ("Remotive", fetch_remotive),
    ]:
        print(f"Fetching from {name}...")
        jobs = fetcher()
        print(f"  Got {len(jobs)} listings")
        all_jobs.extend(jobs)
        time.sleep(1)

    # De-duplicate by URL
    seen = set()
    unique = []
    for job in all_jobs:
        url = job.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(job)

    # Sort: freelance first, then jobs
    unique.sort(key=lambda j: (0 if j.get("listing_type") == "freelance" else 1))

    freelance_count = sum(1 for j in unique if j.get("listing_type") == "freelance")
    print(f"\nTotal unique listings: {len(unique)}")
    print(f"Freelance/contract: {freelance_count}")
    print(f"Job postings: {len(unique) - freelance_count}")

    sources = {}
    for job in unique:
        s = job.get("source", "Unknown")
        sources[s] = sources.get(s, 0) + 1
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(unique),
        "freelance_count": freelance_count,
        "listings": unique,
    }
    with open("listings.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote listings.json ({len(unique)} listings)")


if __name__ == "__main__":
    main()
