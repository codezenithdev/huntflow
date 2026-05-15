# HuntFlow - AI-Powered Job Hunting Automation

HuntFlow is an intelligent job hunting automation platform powered by CrewAI that discovers, analyzes, and helps you apply for job opportunities across the entire US market.

## Key Features

- **Broad Job Discovery**: Searches across 1000+ companies using keyword-based discovery on Ashby, Wellfound, YC, Remotive, Greenhouse, and LinkedIn
- **Smart Filtering**: Scores and ranks opportunities based on fit, salary, and company quality
- **Resume Optimization**: Tailors your resume and cover letters for each position
- **ATS Optimization**: Analyzes resume-job fit and suggests keyword improvements
- **Company Research**: Gathers intelligence about hiring companies
- **Interview Prep**: Generates tailored preparation materials
- **Application Tracking**: Manages application pipeline and follow-ups
- **Outreach Automation**: Creates personalized cold emails for direct outreach
- **Daily Digest**: Summarizes activity and sends Telegram notifications

## Quick Start

### Prerequisites
- Python 3.11+
- Groq API key (free at console.groq.com)
- Optional: Telegram bot token for notifications

### Installation

1. Clone the repository
```bash
cd huntflow
```

2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

4. Configure environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### Usage

#### CLI Commands
```bash
# Discover new job opportunities
python cli.py discover --max-jobs 200

# Prepare application for specific job
python cli.py apply <job_id>

# Generate interview prep materials
python cli.py interview <job_id>

# Send daily digest
python cli.py digest

# Launch dashboard
python cli.py dashboard
```

#### Docker Deployment
```bash
docker-compose up -d
```

## Architecture

### Agents
- **Job Discovery Agent**: Searches all job sources using keyword discovery
- **Resume Optimizer**: Tailors resume for specific roles
- **ATS Keyword Analyzer**: Scores resume-job fit
- **Cover Letter Generator**: Creates personalized cover letters
- **Company Research Agent**: Researches hiring companies
- **Salary Analyzer**: Researches compensation data
- **Outreach Drafter**: Creates cold emails
- **Application Tracker**: Manages application pipeline
- **Interview Coach**: Generates prep materials
- **Digest Coordinator**: Summarizes daily activity

### Data Sources
- **Ashby HQ**: 1000+ companies with open roles (keyword search)
- **Wellfound**: YC startup jobs
- **Y Combinator**: YC-funded company positions
- **Remotive**: Remote job opportunities
- **Greenhouse**: Multi-company job board
- **LinkedIn**: LinkedIn Jobs via RSS, cookie-based, or API

### Storage
- **SQLite**: Application tracking and job history
- **ChromaDB**: Vector memory for job context and company insights
- **File System**: Resume versions, templates, outreach drafts

## Configuration

Edit `config/search_config.yaml` to customize:
- Job search keywords
- Job board preferences
- Location and experience level filters
- Salary requirements
- Industry preferences

## Environment Variables

Key variables in `.env`:
- `GROQ_API_KEY`: LLM provider (recommended: free Groq)
- `TELEGRAM_BOT_TOKEN`: Notification bot token
- `TELEGRAM_CHAT_ID`: Where to send notifications
- `MAX_JOBS_PER_RUN`: How many jobs to process (default: 200)
- `MIN_JOB_SCORE`: Quality threshold (0-100, default: 30)

## Scheduling

HuntFlow runs on a daily schedule:
- **GitHub Actions**: Automated daily runs (configure secrets in repository)
- **Local Scheduler**: APScheduler for local deployment
- **Manual Runs**: Use CLI commands anytime

## Dashboard

Real-time monitoring via Streamlit:
```bash
python cli.py dashboard
```

Metrics:
- Job discovery trends
- Application pipeline status
- Top matching opportunities
- Response rates
- Salary insights

## Testing

```bash
pytest tests/
pytest tests/test_scrapers.py -v
pytest tests/test_ats_scorer.py -v
```

## Troubleshooting

### No jobs found
- Check search keywords in `config/search_config.yaml`
- Verify job board scraper credentials
- Review `MIN_JOB_SCORE` threshold

### Application rate limits
- Adjust `SCRAPE_DELAY_MIN/MAX` in `.env`
- For LinkedIn, use RSS mode (Mode 1) to avoid authentication

### API failures
- Verify API keys in `.env`
- Check rate limits on external services
- Review logs for detailed errors

## License

MIT

## Support

For issues and feature requests, visit the project repository.
