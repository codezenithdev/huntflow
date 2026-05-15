"""Static seeker profile for HuntFlow agents (resume, stack, credentials, constraints)."""

SEEKER_PROFILE = {
    "name": "Angushylesh Subburaj",
    "goes_by": "Shylu",
    "role_targets": [
        "Founding Engineer",
        "Backend Engineer",
        "Full-Stack Engineer",
        "AI Engineer",
        "Platform Engineer",
        "Staff Engineer",
    ],
    "core_stack": [
        "Java",
        "Spring Boot",
        "Python",
        "React",
        "PostgreSQL",
        "LangChain4j",
        "Spring AI",
        "OpenAI API",
        "AWS",
        "Docker",
        "Kafka",
        "Redis",
        "Microservices",
    ],
    "credentials": {
        "suede": "Suede — AI2 Incubator-backed B2B SaaS, ~3-person founding team, 50+ zero-downtime Vercel deploys",
        "cntndr": "CNTNDR Beat Battle Platform — bracket logic, track submission flows, React UI, full lifecycle ownership",
        "corseco": "Corseco QC — FastAPI + Anthropic Vision API + React + Docker defect classification system",
        "mquotient": "MQuotient NLP Pipeline — 95% PDF extraction accuracy, 40% manual processing reduction",
        "peakhealth": "Peakhealth APIs — React/Next.js stress-monitoring platform, 200+ users, 20% retention improvement",
        "controlytics": "Controlytics IoT — Spring Boot + MQTT, 100+ concurrent devices, GPS tracking microservice",
        "know_my_health": "know-my-health — AWS CLI tool (EC2/EBS/ELB/S3 metrics aggregation)",
    },
    "education": "M.S. Computer Science, University of Illinois Springfield (Dec 2025)",
    "certs": [
        "AWS Solutions Architect Associate (SAA-C03)",
        "AWS Cloud Practitioner (CLF-C02)",
    ],
    "visa": "F-1 STEM OPT, expires May 2027",
    "location": "Springfield, IL — open to remote or US relocation",
    "github": "github.com/codezenithdev",
    "linkedin": "linkedin.com/in/angushylesh-subburaj/",
    "target_market": "Any US startup, seed to Series B — broad market sweep",
    "resume_variants": {
        "ai": "Shylesh_AI_Resume.pdf — ML/AI/backend-heavy roles",
        "fullstack": "Shylesh_FS_Resume.pdf — full-stack/frontend-inclusive roles",
    },
}


def seeker_agent_system_context() -> str:
    """Short factual block injected as each agent's system prompt."""
    p = SEEKER_PROFILE
    roles = ", ".join(p["role_targets"])
    stack = ", ".join(p["core_stack"])
    cred_keys = ", ".join(p["credentials"].keys())
    return (
        f"You support {p['name']} (goes by {p['goes_by']}). "
        f"Target roles: {roles}. Core stack: {stack}. "
        f"Education: {p['education']}. Visa: {p['visa']}. Location: {p['location']}. "
        f"GitHub: {p['github']}; LinkedIn: {p['linkedin']}. "
        f"Market focus: {p['target_market']}. "
        f"Credential story keys (use full text from task context when needed): {cred_keys}. "
        "Never invent employers, dates, or metrics not grounded in this profile."
    )
