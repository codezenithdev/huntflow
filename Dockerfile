FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download en_core_web_sm

RUN playwright install chromium --with-deps

COPY . .

RUN mkdir -p data/resumes data/outreach data/prep logs

EXPOSE 8080

HEALTHCHECK --interval=60s --timeout=10s CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "scheduler/scheduler.py"]
