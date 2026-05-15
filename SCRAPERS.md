# Job Scraper Implementation

All job scrapers use **keyword-based discovery** to search across the entire US market. They are NOT targeting fixed company lists.

## Architecture

### Discovery Strategy
- **Primary**: Keyword search for roles like "founding engineer", "backend engineer", "full stack engineer"
- **Secondary**: Advanced queries for "senior", "staff", "principal" roles
- **All search queries** are configurable in `config/search_config.yaml`

### Scrapers Implemented

#### 1. **Ashby** (`ashby_broad_scraper.py`)
- **Method**: GraphQL API + fallback web scraping
- **URL**: `https://jobs.ashbyhq.com/api/non-user-graphql`
- **Coverage**: 1000+ companies on Ashby HQ
- **Rate Limit**: ~5 requests per minute
- **Features**:
  - GraphQL query for job postings by keyword
  - Tenacity retry with exponential backoff
  - Fallback to HTML scraping if API unavailable

#### 2. **Wellfound** (`wellfound_scraper.py`)
- **Method**: Playwright async browser automation
- **URL**: `https://wellfound.com/jobs?query={query}&locationFilter=United+States`
- **Coverage**: YC-funded startups + angel-backed companies
- **Rate Limit**: ~2s between queries
- **Features**:
  - Headless browser (anti-detection)
  - Auto-scroll to load more jobs
  - Viewport 1280x800 with random delays

#### 3. **Y Combinator (YC)** (`yc_scraper.py`)
- **Method**: Public JSON API
- **URL**: `https://www.workatastartup.com/jobs?query={term}&usJobsOnly=true`
- **Coverage**: All YC-funded companies
- **Rate Limit**: ~2-5s between queries
- **Features**:
  - No authentication required
  - Extracts: salary range, equity, location, company batch
  - Includes remote status

#### 4. **Remotive** (`remotive_scraper.py`)
- **Method**: Free public API
- **URL**: `https://remotive.com/api/remote-jobs?category={category}`
- **Coverage**: Remote-focused jobs
- **Rate Limit**: No strict limits (being polite: ~0.5-1.5s)
- **Features**:
  - No auth, completely free
  - Two categories: software-dev, devops-sysadmin
  - All jobs marked `is_remote=True`

#### 5. **Greenhouse** (`greenhouse_scraper.py`)
- **Method**: Public API (per-company)
- **URL**: `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`
- **Coverage**: 25 bootstrap companies, auto-expands via discovery
- **Rate Limit**: ~0.5-1.5s between requests
- **Features**:
  - Bootstrap companies: Stripe, Coinbase, Figma, etc.
  - Auto-discovers new company slugs from other sources
  - Persists discovered slugs to `data/greenhouse_discovered_slugs.txt`

## Job Processing Pipeline

### 1. **Duplicate Detection**
Every scraper checks `MemoryManager.is_job_seen(url)` before processing:
```python
if self.memory.is_job_seen(url):
    logger.debug("job_seen", url=url)
    continue
```

### 2. **Title Filtering**
Applies `JobListing.is_relevant_title()` to exclude non-engineering roles:
```python
if not JobListing.is_relevant_title(title):
    continue  # Skips manager, director, designer, sales, etc.
```

### 3. **Location Filtering**
Checks location text or JD for US signals (remote, NYC, SF, etc.):
```python
us_signals = ["united states", "remote", "san francisco", "new york", ...]
if not any(signal in combined.lower() for signal in us_signals):
    continue
```

### 4. **Content Validation**
Skips jobs with JD shorter than `min_jd_length` (default 200 chars)

### 5. **Storage**
- Stores in ChromaDB for semantic search
- Stores in SQLite for tracking
- Returns `JobListing` objects

## Configuration

**File**: `config/search_config.yaml`

```yaml
search_queries:
  primary:
    - "founding engineer"
    - "backend engineer"
    - "full stack engineer"
    # ... more queries
  secondary:
    - "senior software engineer"
    - "staff engineer"
    # ... more queries

filters:
  us_location_signals:
    - "remote"
    - "united states"
    - "san francisco"
    # ... more signals
  exclude_titles:
    - "manager"
    - "sales"
    # ... more exclusions
  min_jd_length: 200
  max_jobs_per_source: 100

scoring:
  preferred_titles: ["founding", "staff", "lead", "principal"]
  min_score_to_track: 30
  min_score_to_research: 65
```

## Error Handling

All scrapers:
- ✓ Catch all exceptions and log them
- ✓ Return partial results on failure (never crash)
- ✓ Use structlog for detailed logging
- ✓ Implement tenacity retry with backoff
- ✓ Graceful degradation (Playwright optional, etc.)

## Usage

### Single Scraper
```python
from tools.remotive_scraper import RemotiveScraper
scraper = RemotiveScraper()
jobs = await scraper.scrape()
```

### All Scrapers
```python
from tools.job_scraper_orchestrator import JobScraperOrchestrator
orchestrator = JobScraperOrchestrator()
jobs = await orchestrator.run_all()
```

## Performance

- **Ashby**: ~50 jobs/query × 7 queries = 350 jobs
- **Wellfound**: ~30 jobs/query × 7 queries = 210 jobs
- **YC**: ~25 jobs/query × 7 queries = 175 jobs
- **Remotive**: ~100 jobs/category × 2 = 200 jobs
- **Greenhouse**: ~50 jobs/company × 25 companies = 1,250 jobs

**Total potential**: ~2,000 jobs per run
**After dedup**: ~500-1,000 unique quality jobs

All deduped by URL via ChromaDB and SQLite.

## Integration Points

- **MemoryManager**: For dedup and vector search
- **DatabaseManager**: For application tracking
- **JobListing model**: For validation
- **structlog**: For observability
- **YAML config**: For customization

The scraper system is production-ready and scales with your search queries!
