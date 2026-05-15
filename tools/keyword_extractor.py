"""Keyword extraction, ATS scoring, and job fit scoring for HuntFlow."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

import pdfplumber
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from models import ATSReport, JobListing

logger = logging.getLogger(__name__)

# --- Canonical tech lexicon (lowercase phrases for substring match in JDs / resumes) ---

languages = [
    "java",
    "python",
    "go",
    "golang",
    "rust",
    "typescript",
    "javascript",
    "c++",
    "ruby",
    "scala",
    "kotlin",
]
frameworks = [
    "spring boot",
    "spring",
    "fastapi",
    "flask",
    "django",
    "express",
    "rails",
    "nextjs",
    "next.js",
    "react",
    "vue",
    "angular",
    "svelte",
]
databases = [
    "postgresql",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "dynamodb",
    "cassandra",
    "elasticsearch",
    "clickhouse",
    "sqlite",
]
cloud = [
    "aws",
    "gcp",
    "azure",
    "ec2",
    "s3",
    "lambda",
    "ecs",
    "kubernetes",
    "k8s",
    "docker",
    "terraform",
    "cloudflare",
]
ai_ml = [
    "langchain",
    "langchain4j",
    "spring ai",
    "openai",
    "anthropic",
    "hugging face",
    "pytorch",
    "tensorflow",
    "rag",
    "llm",
    "vector database",
    "pgvector",
    "embedding",
    "inference",
]
messaging = ["kafka", "rabbitmq", "sqs", "pubsub", "nats"]
practices = [
    "microservices",
    "rest api",
    "grpc",
    "graphql",
    "ci/cd",
    "github actions",
    "tdd",
    "event-driven",
]


def _dedupe_preserve_order(terms: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        t = t.strip().lower()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return tuple(out)


ALL_TECH_TERMS: tuple[str, ...] = _dedupe_preserve_order(
    languages
    + frameworks
    + databases
    + cloud
    + ai_ml
    + messaging
    + practices
)


def terms_present_in_text(text: str, terms: tuple[str, ...] = ALL_TECH_TERMS) -> set[str]:
    """Return subset of `terms` that appear as substrings in `text` (case-insensitive)."""
    blob = text.lower()
    return {t for t in terms if t in blob}


class ATSScorer:
    """Loads resume PDFs, extracts keywords, and scores JDs for ATS-style alignment."""

    def __init__(self, resumes_dir: Path | None = None) -> None:
        self._resumes_dir = resumes_dir or (
            Path(__file__).resolve().parent.parent / "data" / "resumes"
        )
        self._resume_text: dict[str, str] = {"ai": "", "fullstack": ""}
        self._resume_keywords: dict[str, set[str]] = {"ai": set(), "fullstack": set()}
        self._sentence_model: Any = None
        self._keybert_model: Any = None

        self._load_resume_pdfs()

    def _find_resume_pdf(self, variant: str) -> Path | None:
        base = self._resumes_dir
        if not base.is_dir():
            logger.warning("Resume directory missing: %s", base)
            return None

        variant_l = variant.lower()
        direct = [
            base / f"{variant_l}.pdf",
            base / f"resume_{variant_l}.pdf",
            base / f"{variant_l}_resume.pdf",
        ]
        for p in direct:
            if p.is_file():
                return p

        for p in sorted(base.glob("*.pdf")):
            stem = p.stem.lower()
            if variant_l in stem or stem == variant_l:
                return p
        return None

    def _extract_pdf_text(self, path: Path) -> str:
        chunks: list[str] = []
        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    if t.strip():
                        chunks.append(t)
        except Exception as exc:
            logger.warning("Failed to read PDF %s: %s", path, exc)
            return ""
        return "\n".join(chunks)

    def _load_resume_pdfs(self) -> None:
        found_any = False
        for variant in ("ai", "fullstack"):
            path = self._find_resume_pdf(variant)
            if not path:
                logger.warning("No PDF found for resume variant %r under %s", variant, self._resumes_dir)
                continue
            found_any = True
            text = self._extract_pdf_text(path)
            self._resume_text[variant] = text
            self._resume_keywords[variant] = terms_present_in_text(text)
            logger.info(
                "Loaded resume variant %r from %s (%d chars, %d lexicon keywords)",
                variant,
                path,
                len(text),
                len(self._resume_keywords[variant]),
            )

        if not found_any:
            logger.warning(
                "No resume PDFs found under %s — ATS scorer uses empty keyword sets",
                self._resumes_dir,
            )

    def _get_resume_text(self, variant: str) -> str:
        return self._resume_text.get(variant, "")

    def _get_resume_keywords(self, variant: str) -> set[str]:
        return set(self._resume_keywords.get(variant, set()))

    def _raw_score(self, jd_text: str, variant: str) -> int:
        jd_lower = jd_text.lower()
        jd_kw = {t for t in ALL_TECH_TERMS if t in jd_lower}
        return len(jd_kw & self._get_resume_keywords(variant))

    def select_resume_variant(self, jd_text: str) -> str:
        jd_l = jd_text.lower()
        ai_signals = [
            "langchain",
            "llm",
            "rag",
            "openai",
            "anthropic",
            "embedding",
            "vector",
            "hugging face",
            "pytorch",
            "tensorflow",
            "ml ",
            "machine learning",
            "ai engineer",
            "model",
            "inference",
        ]
        fs_signals = [
            "react",
            "next.js",
            "nextjs",
            "typescript",
            "vue",
            "angular",
            "frontend",
            "full stack",
            "fullstack",
            "ui ",
            "svelte",
        ]
        ai_count = sum(1 for s in ai_signals if s in jd_l)
        fs_count = sum(1 for s in fs_signals if s in jd_l)
        if ai_count > fs_count:
            return "ai"
        if fs_count > ai_count:
            return "fullstack"
        return (
            "ai"
            if self._raw_score(jd_text, "ai") >= self._raw_score(jd_text, "fullstack")
            else "fullstack"
        )

    def _jd_keywords_with_keybert(self, jd_text: str) -> set[str]:
        jd_lower = jd_text.lower()
        jd_keywords: set[str] = {t for t in ALL_TECH_TERMS if t in jd_lower}

        try:
            from keybert import KeyBERT

            if self._keybert_model is None:
                self._keybert_model = KeyBERT()
            pairs = self._keybert_model.extract_keywords(jd_text, top_n=20)
            for kw, _score in pairs:
                jd_keywords.add(kw.lower().strip())
        except Exception as exc:
            logger.debug("KeyBERT keywords skipped: %s", exc)

        return jd_keywords

    def _semantic_similarity_score(self, jd_text: str, variant: str) -> int:
        resume_body = self._get_resume_text(variant)
        if not jd_text.strip() or not resume_body.strip():
            return 0
        try:
            from sentence_transformers import SentenceTransformer, util

            if self._sentence_model is None:
                self._sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
            model = self._sentence_model
            jd_emb = model.encode(jd_text[:2000], convert_to_tensor=True)
            resume_emb = model.encode(resume_body[:2000], convert_to_tensor=True)
            cosine = float(util.cos_sim(jd_emb, resume_emb)[0][0])
            return int(cosine * 40)
        except Exception as exc:
            logger.debug("Semantic ATS score unavailable: %s", exc)
            return 0

    def compute_ats_score(
        self,
        jd_text: str,
        variant: str = "auto",
        job_id: str = "",
        job_url: str = "",
    ) -> ATSReport:
        if variant == "auto":
            variant = self.select_resume_variant(jd_text)

        if variant not in ("ai", "fullstack"):
            variant = self.select_resume_variant(jd_text)

        jd_keywords = self._jd_keywords_with_keybert(jd_text)
        resume_keywords = self._get_resume_keywords(variant)
        matches = jd_keywords & resume_keywords
        missing = jd_keywords - resume_keywords

        exact_score = min(60, len(matches) * 3)
        semantic_score = self._semantic_similarity_score(jd_text, variant)
        total = min(100, exact_score + semantic_score)

        suggestions = [f"Add '{kw}' to skills or summary" for kw in list(missing)[:5]]

        return ATSReport(
            job_id=job_id,
            job_url=job_url,
            resume_variant=variant,
            score=total,
            missing_keywords=list(missing)[:10],
            present_keywords=list(matches)[:10],
            suggestions=suggestions,
        )


def job_score(job: JobListing, ats_score: int) -> dict[str, Any]:
    """Heuristic opportunity score combining title, stack fit, stage, remote, visa, ATS."""
    score = 0
    reasons: list[str] = []
    jd = job.jd_text.lower()
    title = job.title.lower()

    if any(t in title for t in ["founding", "staff", "principal", "lead", "head of eng"]):
        score += 25
        reasons.append("+25 strong title")
    elif any(t in title for t in ["senior", "sr ", "sr."]):
        score += 15
        reasons.append("+15 senior level")
    elif any(t in title for t in ["engineer", "developer", "swe"]):
        score += 8
        reasons.append("+8 IC role")

    shylu_stack = {
        "java",
        "spring boot",
        "spring",
        "python",
        "react",
        "postgresql",
        "postgres",
        "langchain",
        "openai",
        "docker",
        "aws",
        "kafka",
        "microservices",
        "rest api",
        "kubernetes",
        "redis",
        "mongodb",
        "langchain4j",
        "spring ai",
        "fastapi",
        "golang",
        "go",
        "typescript",
        "nextjs",
        "next.js",
    }
    matched = [t for t in shylu_stack if t in jd]
    stack_score = min(30, len(matched) * 5)
    score += stack_score
    if matched:
        reasons.append(f"+{stack_score} stack: {', '.join(matched[:4])}")

    if any(w in jd for w in ["seed", "series a", "early stage", "founding team", "ground floor"]):
        score += 20
        reasons.append("+20 early-stage")
    elif "series b" in jd:
        score += 12
        reasons.append("+12 series B")
    elif "series c" in jd:
        score += 5
        reasons.append("+5 series C")

    if job.is_remote or any(w in jd for w in ["remote", "fully remote", "work from anywhere"]):
        score += 10
        reasons.append("+10 remote")

    positive_visa = [
        "visa sponsorship",
        "sponsorship available",
        "will sponsor",
        "h1b",
        "opt eligible",
        "open to sponsorship",
    ]
    negative_visa = [
        "must be authorized",
        "no sponsorship",
        "us citizen only",
        "authorized to work without",
        "green card required",
    ]

    visa_flag = "unknown"
    if any(w in jd for w in positive_visa):
        score += 15
        reasons.append("+15 visa sponsorship")
        visa_flag = "positive"
    elif any(w in jd for w in negative_visa):
        score -= 20
        reasons.append("-20 no sponsorship")
        visa_flag = "negative"

    ats_pts = ats_score // 10
    score += ats_pts
    reasons.append(f"+{ats_pts} ATS ({ats_score}/100)")

    score = max(0, min(100, score))
    grade = "A" if score >= 70 else "B" if score >= 50 else "C" if score >= 30 else "D"

    return {"score": score, "grade": grade, "reasons": reasons, "visa_flag": visa_flag}


class ATSKeywordInput(BaseModel):
    """Tool inputs for ATSKeywordScorer."""

    jd_text: str = Field(..., description="Full job description text.")
    variant: str = Field(
        "auto",
        description="Resume variant: 'auto', 'ai', or 'fullstack'.",
    )


class ATSKeywordTool(BaseTool):
    """CrewAI tool: JSON ATSReport for a JD against cached resume PDFs."""

    name: str = "ATSKeywordScorer"
    description: str = (
        "Scores a job description against Shylu's cached resume PDFs (ai vs fullstack). "
        "Returns JSON with ATS-style score, matched/missing keywords, and suggestions."
    )
    args_schema: type[BaseModel] = ATSKeywordInput
    _scorer: ATSScorer | None = PrivateAttr(default=None)

    def _get_scorer(self) -> ATSScorer:
        if self._scorer is None:
            self._scorer = ATSScorer()
        return self._scorer

    def _run(self, jd_text: str, variant: str = "auto") -> str:
        report = self._get_scorer().compute_ats_score(jd_text, variant=variant)
        # JSON-serializable for agents / logs
        payload = report.model_dump(mode="json")
        return json.dumps(payload, default=str)
