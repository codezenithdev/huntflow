# HuntFlow 🎯

> AI-powered job hunting automation — broad US market sweep, not a fixed company list

## Why it's different

Most job bots search a predetermined list of companies you already know.
**HuntFlow sweeps the ENTIRE US startup market by keyword**, discovers companies you'd never find manually,
scores every job by fit, surfaces the top matches, and sends a digestible summary to your Telegram **every day**.

No manual job board scrolling. No repeated research. Just daily intelligence.

## Architecture

- **10 CrewAI agents** orchestrating job discovery, scoring, research, outreach, interview prep, and digests
- **Multi-source scraping**: Ashby HQ, Wellfound, YC, Remotive, LinkedIn, Greenhouse
- **AI backbone**: Groq (free LLM), ChromaDB (embeddings), SQLite (persistence)
- **Daily delivery**: Telegram digest + Streamlit dashboard + CLI tools
- **Zero cost to run**: Groq API is free, runs on Oracle Always Free VM or laptop

## Quick Start (10 min)

```bash
git clone https://github.com/codezenithdev/huntflow && cd huntflow
cp .env.example .env

# Get free API keys
# - GROQ_API_KEY: https://console.groq.com
# - TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID: Follow setup in tools/telegram_notifier.py
# - TAVILY_API_KEY: https://tavily.com (for company research in outreach)

# Copy your resumes
cp ~/Downloads/Shylesh_AI_Resume.pdf data/resumes/
cp ~/Downloads/Shylesh_FS_Resume.pdf data/resumes/

# Install + download models
pip install -r requirements.txt
python -m spacy download en_core_web_sm
playwright install chromium

# Run daily discovery sweep
python cli.py run-daily

# Check pipeline
python cli.py status

# View top jobs
python cli.py jobs --grade A

# Generate interview prep
python cli.py prep "Linear" "Backend Engineer"

# Test Telegram connection
python cli.py test-telegram
```

## Docker (Recommended for Always Free Tier)

```bash
# Copy secrets to .env, then:
docker-compose up -d

# Monitor logs
docker-compose logs -f huntflow

# Dashboard at http://localhost:8501
# Scheduler health at http://localhost:8080/health
```

## System Design

### Job Discovery Pipeline (Daily 8 AM)
1. **Broad sweep**: Search 30+ keyword combinations across all sources (80–250 jobs/day)
2. **ATS scoring**: Match each job against 3 resume variants (AI, FullStack, Backend)
3. **Company research**: Pull funding, tech stack, visa signals for top 20 candidates
4. **Grade assignment**: A+/A (strong fit) → C/D (weak fit) based on ATS + visa + freshness
5. **Upsert to DB**: Top 20 jobs stored with scores, research, and status tracking
6. **Daily digest**: Format top 3 opportunities + pipeline health + follow-up reminders → Telegram

### Outreach Automation (3x/week, 9 AM Mon/Wed/Fri)
1. **Fetch targets**: Top 5 undrafted A+/A jobs by score
2. **Research hook**: Tavily search for recent news, GitHub activity, founder tweets
3. **Resume tailoring**: Pick best resume variant (AI vs FullStack) based on JD keywords
4. **Draft cold email**: 4 sentences max (hook + credential + connection + ask), saved as markdown
5. **Human review**: Drafts staged in `data/outreach/` — never auto-sent

### Interview Prep (On-demand, `prep <company> <title>`)
1. **Company dossier**: Funding, team size, recent news
2. **STAR stories**: Generate 5 real behavioral examples (shipping, debugging, leadership)
3. **Technical prep**: 3–5 problem domains with sample LC-style solutions
4. **System design**: 1-page architecture outline + scaling + failure modes
5. **Save artifact**: Markdown file to `data/prep/{company}_{YYYYMMDD}.md`

## CLI Commands

```bash
# Daily market sweep (80–250 jobs, research top 20, send digest)
python cli.py run-daily

# Draft cold emails for top undrafted A/A+ jobs (3x/week)
python cli.py run-outreach

# Interview prep for specific company + role
python cli.py prep "Linear" "Backend Engineer"

# Send daily digest now (normally 6 PM)
python cli.py digest

# Show pipeline stats: discovered, applied, replied, interviewing, offers
python cli.py status

# List jobs with filters
python cli.py jobs --grade A --source ashby --limit 10

# Check Telegram bot connection
python cli.py test-telegram

# Update application status manually
python cli.py update "https://ashby.com/job/123" replied
```

## Environment Setup

Create a `.env` file at project root:

```
# LLM Provider (free Groq recommended)
LLM_PROVIDER=groq
LLM_MODEL=llama3-8b-8192
GROQ_API_KEY=your_groq_api_key

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Company Research (for outreach hooks)
TAVILY_API_KEY=your_tavily_key

# Optional: OpenAI fallback
OPENAI_API_KEY=...

# Optional: Ollama local
OLLAMA_BASE_URL=http://localhost:11434
```

**Getting API keys:**
- **Groq** (free, no credit card): https://console.groq.com
- **Telegram Bot**: Message @BotFather on Telegram, create bot, get token
- **Telegram Chat ID**: Message @userinfobot, get your user ID
- **Tavily**: https://tavily.com (optional, for outreach research)

## GitHub Actions Scheduling

Set repository secrets:
```
GROQ_API_KEY
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
TAVILY_API_KEY
```

Workflows run on cron:
- **8 AM CST daily**: `python scheduler/scheduler.py --once --job daily`
- **6 PM CST daily**: `python scheduler/scheduler.py --once --job digest`
- **9 AM CST Mon/Wed/Fri**: `python scheduler/scheduler.py --once --job outreach`

## Dashboard

Open http://localhost:8501 (or `streamlit run dashboard/app.py`):

1. **Pipeline Overview**: Metrics (discovered today, grade A+B), funnel, source breakdown, ATS scatter
2. **Job Board**: Filter by grade, source, ATS score; search; expand for details
3. **Outreach Drafts**: Review cold emails before sending (human review required)
4. **Interview Prep**: View prep docs, generate new prep on-demand
5. **Settings**: Config display, manual triggers, logs, database stats

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_scrapers.py -v

# Run with coverage
pytest --cov=agents --cov=tools tests/
```

## Smoke Tests (Verify Setup)

```bash
# 1. Models import
python -c "from models.job_listing import JobListing; print('✓ models')"

# 2. Database initialization
python tools/sqlite_tracker.py

# 3. ChromaDB initialization
python tools/chromadb_memory.py

# 4. Crew imports
python -c "from crews.daily_discovery_crew import create_daily_discovery_crew; print('✓ crews')"

# 5. Pipeline status
python cli.py status

# 6. Telegram connection
python cli.py test-telegram
```

If all pass, you're ready to deploy!

## Deployment

### Local Development
```bash
python cli.py run-daily
```

### Docker (Recommended)
```bash
docker-compose up -d
# Scheduler at :8080/health
# Dashboard at :8501
```

### GitHub Actions (Serverless)
Push `.env` secrets to GitHub repo, workflows run on cron automatically.

### Oracle Always Free VM
1. Clone repo to Always Free VM
2. Set up `.env` with API keys
3. `docker-compose up -d`
4. Access dashboard at http://<vm-ip>:8501

## Monitoring

- **Logs**: `docker-compose logs -f huntflow` or `tail -f logs/scheduler.log`
- **Dashboard**: http://localhost:8501 → Settings page shows recent logs + database stats
- **Health check**: `curl http://localhost:8080/health` → `{"status":"ok"}`
- **Telegram alerts**: Job failures send alerts to your Telegram chat

## Troubleshooting

**Groq API timeout**: Increase `max_tokens` in LLM config
**No jobs discovered**: Check search keywords in `config/search_config.yaml`
**Telegram not sending**: Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
**ATS scorer giving low scores**: Check resume PDFs are in `data/resumes/`
**Dashboard slow**: Database might be locked; restart scheduler

## Contributing

This is a personal project, but forks/improvements welcome!

- Bug reports: GitHub Issues
- Feature ideas: GitHub Discussions
- Code review: PRs with tests

## License

MIT — use and modify freely.

---

Built with ❤️ for job hunting on YOUR terms. No recruiter gatekeeping, no fixed lists, just the entire market at your fingertips.
