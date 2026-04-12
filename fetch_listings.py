#!/usr/bin/env python3
"""
Fetch freelance project listings from multiple free APIs.
Runs daily via GitHub Actions.
"""

import json
import requests
import time
import re
from datetime import datetime, timezone


def strip_html(text):
    clean = re.sub(r"<[^>]+>", " ", text or "")
    try:
        from html import unescape
        clean = unescape(clean)
    except Exception:
        pass
    return re.sub(r"\s+", " ", clean).strip()


FREELANCE_KEYWORDS = [
    "freelance", "contract", "contractor", "project-based", "part-time",
    "consultant", "gig", "independent", "short-term", "temporary",
    "per hour", "hourly", "fixed-price", "milestone", "deliverable",
    "seeking freelancer", "looking for freelancer",
    "build a", "create a", "develop a", "implement a", "design a",
]


def is_likely_freelance(title, description, tags):
    text = f"{title} {description[:500]} {' '.join(str(t) for t in tags)}".lower()
    return any(kw in text for kw in FREELANCE_KEYWORDS)


# ── HackerNews — only SEEKING FREELANCER posts from recent threads ───────────

def fetch_hn_freelance():
    """Fetch 'SEEKING FREELANCER' posts from recent HN hiring threads."""
    results = []
    cutoff = int(time.time()) - 60 * 86400  # last 60 days

    # Search for the monthly freelancer threads
    queries = [
        ("Ask HN: Freelancer? Seeking freelancer?", True),
        ("Ask HN: Who is hiring?", False),
    ]

    for query_text, is_freelancer_thread in queries:
        try:
            url = (
                "https://hn.algolia.com/api/v1/search?"
                f"query={requests.utils.quote(query_text)}"
                f"&tags=story"
                f"&numericFilters=created_at_i>{cutoff}"
                f"&hitsPerPage=5"
            )
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            print(f"  Found {len(hits)} threads for '{query_text}'")
        except Exception as e:
            print(f"  HN search failed for '{query_text}': {e}")
            continue

        for hit in hits:
            story_id = hit.get("objectID")
            title = hit.get("title", "")
            # Only process threads that match
            title_lower = title.lower()
            if not ("hiring" in title_lower or "freelancer" in title_lower):
                continue

            try:
                cresp = requests.get(
                    f"https://hn.algolia.com/api/v1/items/{story_id}",
                    timeout=30,
                )
                cresp.raise_for_status()
                story = cresp.json()
            except Exception as e:
                print(f"  Failed to fetch thread {story_id}: {e}")
                continue

            children = story.get("children", [])
            print(f"  Thread '{title[:60]}' has {len(children)} comments")

            for child in children:
                text = strip_html(child.get("text", ""))
                if len(text) < 50:
                    continue

                text_upper = text[:300].upper()

                if is_freelancer_thread:
                    # In freelancer threads: ONLY keep "SEEKING FREELANCER" posts
                    if "SEEKING FREELANCER" not in text_upper:
                        continue
                else:
                    # In "Who is hiring" threads: keep posts mentioning contract/freelance
                    text_lower = text[:500].lower()
                    if not any(kw in text_lower for kw in [
                        "contract", "freelance", "part-time", "part time",
                        "consulting", "project-based", "short-term",
                    ]):
                        continue

                # Extract title from first line
                first_line = text.split(".")[0][:120] if text else "HN Post"

                results.append({
                    "title": first_line,
                    "company": child.get("author", "HN User"),
                    "description": text[:2000],
                    "url": f"https://news.ycombinator.com/item?id={child.get('id', story_id)}",
                    "tags": ["freelance", "hackernews"],
                    "source": "HackerNews",
                    "date": child.get("created_at", ""),
                    "listing_type": "freelance",
                })

            time.sleep(1)

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

    # Sort: freelance first
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
