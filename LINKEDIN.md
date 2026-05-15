# LinkedIn Jobs Integration

HuntFlow integrates LinkedIn as a job source using **three different modes** to work around LinkedIn's bot detection and authentication requirements.

## Quick Start

By default, LinkedIn scraping uses **Mode 1 (RSS)** which is:
- ✓ Zero setup required
- ✓ Within LinkedIn's Terms of Service
- ✓ No account needed
- ✓ 50-150 jobs per run

In your `.env`, you already have:
```
LINKEDIN_MODE=rss
LINKEDIN_SCRAPE_DELAY=8.0
LINKEDIN_MAX_JOBS_PER_RUN=50
```

Just run the daily job discovery — LinkedIn will automatically be scraped!

## Three Modes Explained

### Mode 1: RSS (RECOMMENDED)
**Status**: ✅ Default, Safe, Recommended

LinkedIn exposes public job search results as an RSS/XML feed. No login, no API key, no TOS violation.

**How it works**:
- URL: `https://www.linkedin.com/jobs/search/rss?keywords={query}&location=United+States&f_TPR=r86400&f_JT=F`
- Fetches 25 results per page
- Paginates 3 pages per query = 75 jobs per keyword
- With 7 primary queries = up to 525 jobs per run
- After dedup: ~50-150 unique new jobs daily

**Full JD text**:
- RSS gives ~200 char snippet
- HuntFlow attempts to fetch the full JD from the public job page
- Uses httpx (no Playwright) to stay lightweight
- Gracefully falls back to snippet if page is blocked

**Configuration** (in `config/search_config.yaml`):
```yaml
linkedin:
  mode: rss
  rss_pages: 3  # pages to paginate
  fetch_full_jd: true  # fetch full JD from public page
  full_jd_timeout: 10  # seconds to wait for full page
```

**Setup**: Zero setup. Works immediately.

---

### Mode 2: Cookie (Advanced)
**Status**: ⚠️ TOS Violation Risk

Uses your LinkedIn session cookie to access authenticated job search. Returns more results and full JD text automatically.

**WARNING**: This violates LinkedIn's Terms of Service. Your account could be restricted if detected. LinkedIn actively blocks automated session access. Use only if you:
1. Accept the TOS violation risk
2. Use a secondary LinkedIn account (not your main professional profile)
3. Understand LinkedIn can revoke access at any time

**How it works**:
- Extracts your `li_at` session cookie
- Uses LinkedIn's internal Voyager API
- Returns full JD text + more results
- Higher yield but higher risk

**Setup** (if you choose to use Mode 2):

1. **Get your li_at cookie**:
   - Log into LinkedIn in Chrome/Firefox
   - Open DevTools → Application → Cookies → linkedin.com
   - Find the cookie named `li_at` — copy its value (starts with `AQEDARx...`)
   - Copy the entire value (very long string)

2. **Save to .env**:
   ```
   LINKEDIN_MODE=cookie
   LINKEDIN_LI_AT_COOKIE=AQEDARxxxxxxxxxxxx...  # your full li_at value
   ```

3. **Cookie management**:
   - LinkedIn session cookies expire in ~1 year
   - Can be invalidated by LinkedIn anytime
   - When expired, you'll get 401 error → automatic fallback to Mode 1 (RSS)
   - To refresh: re-extract the `li_at` value and update `.env`

**Fallback behavior**:
- If 401 (Unauthorized) → automatically falls back to Mode 1 (RSS)
- If rate limited (429) → circuit breaker activates for 2 hours
- If any other error → returns results collected so far

---

### Mode 3: RapidAPI (Third-Party API)
**Status**: ✅ Safe, Above-Board, Paid

Uses a third-party LinkedIn data API via RapidAPI. No TOS violation, no account restriction risk.

**Pricing**:
- **Free tier**: 100 requests/month (covers ~10 daily runs)
- **Paid**: ~$10/month for 1,000 requests (daily coverage)
- Cost-effective for persistent coverage without risk

**Full JD text**: Always included

**Setup**:

1. **Sign up for RapidAPI** (free account):
   - Visit https://rapidapi.com/rockapis-rockapis-default/api/linkedin-jobs-search
   - Click "Subscribe" → "Free" plan
   - Copy your API key from the dashboard

2. **Save to .env**:
   ```
   LINKEDIN_MODE=rapidapi
   RAPIDAPI_KEY=xxxxxxxxxxxx  # your RapidAPI key
   ```

**Fallback behavior**:
- If rate limited (100 req/month free) → automatic fallback to Mode 1 (RSS)
- If API error → returns results collected so far, falls back to RSS next run

---

## Anti-Detection Measures

LinkedIn actively detects and blocks bots. HuntFlow implements multiple countermeasures:

### 1. Rate Limiting (Stricter than other sources)
- **Base delay**: 8 seconds between requests (default `LINKEDIN_SCRAPE_DELAY`)
- **Jitter**: +0-4 seconds random variation
- **Batch pause**: 30-60 second pause every 10 requests
- **Total per run**: ~5-10 minutes for all queries (stays under radar)

### 2. User-Agent Rotation
```python
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
    "Mozilla/5.0 (X11; Linux x86_64) ...",
]
# Each request uses random agent
```

### 3. Circuit Breaker
- Monitors for blocking (429 rate limit, 403 forbidden, redirects to login)
- If 3+ consecutive failures → triggers 2-hour cooldown
- Prevents repeated requests that get blocked
- Cooldown file: `./data/.linkedin_circuit_breaker`
- Logs: `linkedin_circuit_breaker_triggered`

### 4. URL Normalization
- LinkedIn job URLs have tracking parameters: `?refId=xxx&trackingId=yyy`
- HuntFlow normalizes to: `https://www.linkedin.com/jobs/view/1234567890/`
- Prevents duplicate tracking and duplicate job detection

---

## Configuration Reference

**File**: `config/search_config.yaml`

```yaml
linkedin:
  # Mode selection (rss | cookie | rapidapi)
  mode: rss

  # RSS-specific (Mode 1)
  rss_pages: 3  # 25 results per page, 3 pages = 75 jobs per query
  fetch_full_jd: true  # attempt to get full JD from public page
  full_jd_timeout: 10  # seconds to wait for full page load

  # Rate limiting and circuit breaker
  circuit_breaker_threshold: 3  # failures before cooldown
  circuit_breaker_cooldown: 7200  # 2 hours in seconds
```

**File**: `.env`

```
# LinkedIn mode (rss | cookie | rapidapi)
LINKEDIN_MODE=rss

# Rate limiting
LINKEDIN_SCRAPE_DELAY=8.0  # seconds minimum between requests
LINKEDIN_MAX_JOBS_PER_RUN=50  # daily cap to avoid detection

# Mode 2 (Cookie) — only if using
LINKEDIN_LI_AT_COOKIE=  # your li_at session cookie value

# Mode 3 (RapidAPI) — only if using
RAPIDAPI_KEY=  # your RapidAPI key
```

---

## Automatic Mode Selection & Fallback

HuntFlow's LinkedIn scraper automatically selects the best available mode:

```python
# At startup, it tries:
if LINKEDIN_MODE == "cookie" and LINKEDIN_LI_AT_COOKIE is set:
    start with cookie mode
elif LINKEDIN_MODE == "rapidapi" and RAPIDAPI_KEY is set:
    start with rapidapi mode
else:
    start with rss mode (always works)

# During scraping:
if mode fails (auth error, rate limit, timeout):
    fall back to next mode
if all modes fail:
    return results collected so far
```

**Example fallback chain**:
1. Try Cookie mode → 401 error → fall back to RSS
2. Try RapidAPI mode → 429 (out of free tier) → fall back to RSS
3. RSS always works (worst case: gets snippet text without full JD)

---

## Performance & Coverage

### Expected Yield (Per Run)

**Mode 1 (RSS)**:
- 7 primary queries × 3 pages = 21 RSS feeds
- ~10-20 jobs per query
- ~100-150 new jobs per run
- After dedup: ~50-100 unique jobs daily

**Mode 2 (Cookie)**:
- Full API results (more comprehensive)
- 25-50 jobs per query
- ~150-200 new jobs per run
- Higher risk of detection

**Mode 3 (RapidAPI)**:
- Full API results
- Same as Mode 2 (~150-200 per run)
- Spread across month (100 req/mo free)
- ~3-4 jobs per daily run (free tier)

### Speed

- **Mode 1 (RSS)**: ~5-10 minutes per run
- **Mode 2 (Cookie)**: ~8-15 minutes per run (more data)
- **Mode 3 (RapidAPI)**: ~1-2 minutes per run (API is fast)

---

## Troubleshooting

### RSS Mode Issues

**"No jobs found"**:
- LinkedIn might be blocking the RSS feed temporarily
- Wait 30 minutes, try again
- Check `LINKEDIN_MAX_JOBS_PER_RUN` isn't set too low
- Verify search queries in `config/search_config.yaml`

**"Circuit breaker active"**:
- Delete `./data/.linkedin_circuit_breaker` file
- Wait 2 hours for automatic reset

**"Full JD fetch returning 403"**:
- LinkedIn's public job page has auth wall (normal)
- HuntFlow gracefully uses the RSS snippet instead
- No action needed

### Cookie Mode Issues

**"401 Unauthorized"**:
- Your `li_at` cookie expired
- Re-extract the `li_at` value from your LinkedIn session
- Update `LINKEDIN_LI_AT_COOKIE` in `.env`

**"Account restricted"**:
- LinkedIn detected automated access
- Your account may be restricted for 24-48 hours
- This is why Mode 2 is risky — use a secondary account
- Switch to Mode 1 (RSS) or Mode 3 (RapidAPI) for next run

**"TLS/SSL error"**:
- Rare — usually a LinkedIn server issue
- Automatic fallback to Mode 1 will handle it

### RapidAPI Mode Issues

**"Out of requests"**:
- You've hit the 100/month free tier limit
- Automatic fallback to Mode 1
- To continue, upgrade plan to $10/month or wait until next month

**"Invalid API key"**:
- Check `RAPIDAPI_KEY` in `.env`
- Verify it matches your RapidAPI dashboard

---

## Integration with Job Discovery

LinkedIn is automatically integrated into the daily job discovery:

```python
# In daily_discovery_crew.py
from tools.linkedin_scraper import LinkedInScraper

scraper = LinkedInScraper()
linkedin_jobs = await scraper.scrape()
```

Or use the unified orchestrator:

```python
from tools.job_scraper_orchestrator import JobScraperOrchestrator

orchestrator = JobScraperOrchestrator()
all_jobs = await orchestrator.run_all()  # Includes LinkedIn
```

---

## Recommended Setup

**Start with Mode 1 (RSS)**:
- Zero setup
- Safe
- Good coverage
- Set and forget

**If you need more coverage**:
- Upgrade to Mode 3 (RapidAPI)
- $10/month for reliability
- No TOS risk

**Only use Mode 2 (Cookie) if**:
- You need maximum coverage
- You have a secondary LinkedIn account
- You accept the TOS violation and block risk

---

## Data Sources & Changelog

- **Implemented**: May 2026
- **Modes**: RSS (safe), Cookie (risk), RapidAPI (paid)
- **Expected discovery**: 50-150 jobs/day
- **Source label**: `linkedin_rss`, `linkedin_cookie`, `linkedin_api`

For updates to this guide or issues, check the main README.md.
