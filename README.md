# Portfolio Builder — Job Listings Fetcher

This repo is used by the **Portfolio Builder** Databricks App to get real freelance job listings.

## How it works

```
GitHub Actions (daily at 6am UTC)
    │
    ├── Fetches from RemoteOK, Arbeitnow, Remotive (free, no API keys)
    │
    └── Commits listings.json to this repo
            │
            └── Databricks App reads from raw.githubusercontent.com
```

## Setup (one-time)

1. **Create a new GitHub repo** (public or private)
   - Name it something like `portfolio-builder-listings`

2. **Add these files to the repo:**
   ```
   your-repo/
   ├── .github/
   │   └── workflows/
   │       └── fetch-listings.yml    ← copy from this folder
   ├── fetch_listings.py             ← copy from this folder
   └── README.md                     ← this file (optional)
   ```

3. **Enable GitHub Actions** (should be on by default)

4. **Run it manually the first time:**
   - Go to your repo → Actions tab → "Fetch Job Listings" → "Run workflow"
   - This creates the initial `listings.json`

5. **Update the Databricks app** with your repo URL:
   - In the app's sidebar, enter: `https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/listings.json`
   - Or set the `GITHUB_LISTINGS_URL` env var in app.yaml

## Sources

| Source | API | Key Required | Listings |
|--------|-----|-------------|----------|
| [RemoteOK](https://remoteok.com) | `remoteok.com/api` | No | ~200-300 remote tech jobs |
| [Arbeitnow](https://arbeitnow.com) | `arbeitnow.com/api/job-board-api` | No | ~100-200 jobs |
| [Remotive](https://remotive.com) | `remotive.com/api/remote-jobs` | No | ~200-400 remote jobs |

## Adding more sources

Edit `fetch_listings.py` to add more APIs. Each source should return a list of dicts with:
```python
{"title": "", "company": "", "description": "", "url": "", "tags": [], "source": "", "date": ""}
```
