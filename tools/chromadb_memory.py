"""ChromaDB vector memory for job descriptions, resumes, and outreach tracking."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
import pdfplumber
import structlog
from sentence_transformers import SentenceTransformer

from models import JobListing

logger = structlog.get_logger()


def get_embeddings_model():
    """Get embedding model: try Ollama first, fall back to sentence-transformers."""
    try:
        # Try Ollama
        import requests

        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            logger.info("embeddings_using", model="ollama_nomic-embed-text")
            return chromadb.utils.embedding_functions.OllamaEmbeddingFunction(
                model_name="nomic-embed-text", url="http://localhost:11434"
            )
    except Exception as e:
        logger.debug("ollama_unavailable", error=str(e))

    # Fall back to sentence-transformers
    logger.info("embeddings_using", model="sentence-transformers_all-MiniLM-L6-v2")
    return chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )


class MemoryManager:
    """Manages ChromaDB vector memory for HuntFlow."""

    def __init__(self, chromadb_path: str = "./data/chromadb"):
        """Initialize ChromaDB with Ollama or sentence-transformers embeddings."""
        os.makedirs(chromadb_path, exist_ok=True)
        self.chromadb_path = chromadb_path
        self.client = chromadb.PersistentClient(path=chromadb_path)
        self.embedding_fn = get_embeddings_model()

        # Initialize collections
        self.job_descriptions = self.client.get_or_create_collection(
            name="job_descriptions",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self.company_profiles = self.client.get_or_create_collection(
            name="company_profiles",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self.resume_content = self.client.get_or_create_collection(
            name="resume_content",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self.outreach_history = self.client.get_or_create_collection(
            name="outreach_history",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

        self.loaded_resumes = {}
        self._auto_load_resumes()
        logger.info("memory_manager_initialized", path=chromadb_path)

    def _auto_load_resumes(self):
        """Auto-load resume PDFs from data/resumes/ directory."""
        resume_dir = Path("./data/resumes")
        if resume_dir.exists():
            for pdf_file in resume_dir.glob("*.pdf"):
                try:
                    variant = pdf_file.stem  # filename without .pdf
                    self.load_resume_pdf(str(pdf_file), variant)
                    logger.info("resume_auto_loaded", variant=variant, path=str(pdf_file))
                except Exception as e:
                    logger.warning("resume_load_failed", variant=pdf_file.stem, error=str(e))

    # ============ Jobs ============

    def store_job(self, job: JobListing):
        """Store job description in vector memory."""
        try:
            self.job_descriptions.upsert(
                ids=[job.url],
                documents=[job.jd_text],
                metadatas=[
                    {
                        "company": job.company,
                        "title": job.title,
                        "url": job.url,
                        "score": job.job_score or 0,
                        "source": job.source,
                        "grade": job.job_grade or "ungraded",
                    }
                ],
            )
            logger.debug("job_stored", url=job.url, company=job.company)
        except Exception as e:
            logger.error("job_store_failed", url=job.url, error=str(e))

    def is_job_seen(self, url: str) -> bool:
        """Fast check if job URL has been stored."""
        try:
            results = self.job_descriptions.get(ids=[url])
            return len(results["ids"]) > 0
        except Exception as e:
            logger.debug("job_seen_check_failed", url=url, error=str(e))
            return False

    def find_similar_jobs(self, query: str, n: int = 10) -> List[Dict[str, Any]]:
        """Find similar jobs by semantic search."""
        try:
            results = self.job_descriptions.query(query_texts=[query], n_results=n)
            jobs = []
            for i, doc_id in enumerate(results["ids"][0]):
                jobs.append({
                    "url": doc_id,
                    "distance": float(results["distances"][0][i]),
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
            return jobs
        except Exception as e:
            logger.error("find_similar_jobs_failed", query=query, error=str(e))
            return []

    # ============ Resumes ============

    def load_resume_pdf(self, pdf_path: str, variant: str):
        """Load resume PDF and chunk into vector memory."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""

            # Clean text
            text = re.sub(r"\s+", " ", text).strip()

            # Chunk with 400-char size and 50-char overlap
            chunks = []
            chunk_size = 400
            overlap = 50
            for i in range(0, len(text), chunk_size - overlap):
                chunk = text[i : i + chunk_size]
                if chunk.strip():
                    chunks.append(chunk)

            # Store chunks
            chunk_ids = [f"{variant}_{i}" for i in range(len(chunks))]
            self.resume_content.upsert(
                ids=chunk_ids,
                documents=chunks,
                metadatas=[{"variant": variant, "chunk_index": i} for i in range(len(chunks))],
            )

            self.loaded_resumes[variant] = {
                "path": pdf_path,
                "chunks": len(chunks),
                "text": text,
            }
            logger.info("resume_loaded", variant=variant, chunks=len(chunks))
        except Exception as e:
            logger.error("resume_load_failed", path=pdf_path, variant=variant, error=str(e))

    def compute_resume_jd_similarity(self, jd_text: str, variant: str = "generic") -> float:
        """Compute average similarity between resume and job description."""
        try:
            if variant not in self.loaded_resumes:
                logger.warning("resume_not_loaded", variant=variant)
                return 0.0

            # Query resume chunks with JD text
            results = self.resume_content.query(
                query_texts=[jd_text],
                n_results=5,
                where={"variant": variant},
            )

            if not results["distances"] or not results["distances"][0]:
                return 0.0

            # Convert distances to similarity (1 - distance for cosine)
            distances = results["distances"][0]
            similarities = [1 - d for d in distances]
            avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

            logger.debug("resume_jd_similarity", variant=variant, score=round(avg_similarity, 3))
            return round(avg_similarity, 3)
        except Exception as e:
            logger.error("resume_jd_similarity_failed", variant=variant, error=str(e))
            return 0.0

    # ============ Outreach ============

    def store_outreach(self, company: str, job_url: str):
        """Store outreach record to prevent duplicates."""
        try:
            # Create a hash ID for the company+url pair
            hash_id = hashlib.md5(f"{company}_{job_url}".encode()).hexdigest()
            doc_text = f"{company} {job_url}"

            self.outreach_history.upsert(
                ids=[hash_id],
                documents=[doc_text],
                metadatas={"company": company, "job_url": job_url, "sent_at": str(os.times())},
            )
            logger.debug("outreach_stored", company=company, url=job_url)
        except Exception as e:
            logger.error("outreach_store_failed", company=company, error=str(e))

    def has_outreach_been_sent(self, company: str, job_url: str) -> bool:
        """Check if outreach to this company+job has been sent."""
        try:
            hash_id = hashlib.md5(f"{company}_{job_url}".encode()).hexdigest()
            results = self.outreach_history.get(ids=[hash_id])
            return len(results["ids"]) > 0
        except Exception as e:
            logger.debug("outreach_check_failed", company=company, error=str(e))
            return False

    # ============ Analytics ============

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about all collections."""
        try:
            return {
                "job_descriptions": {
                    "count": self.job_descriptions.count(),
                    "path": self.chromadb_path,
                },
                "company_profiles": {
                    "count": self.company_profiles.count(),
                },
                "resume_content": {
                    "count": self.resume_content.count(),
                    "loaded_resumes": len(self.loaded_resumes),
                    "variants": list(self.loaded_resumes.keys()),
                },
                "outreach_history": {
                    "count": self.outreach_history.count(),
                },
            }
        except Exception as e:
            logger.error("get_stats_failed", error=str(e))
            return {}


class ChromaMemoryTool:
    """Tool for vector memory operations."""

    name: str = "VectorMemory"
    description: str = (
        "Vector memory operations. "
        "Actions: store_job, is_seen, find_similar, check_outreach, get_stats"
    )

    def __init__(self, chromadb_path: str = "./data/chromadb"):
        """Initialize the memory tool."""
        self.memory = MemoryManager(chromadb_path)

    def _run(self, action: str, data: str = "") -> str:
        """Execute memory actions."""
        try:
            if action == "store_job":
                job_data = json.loads(data) if data else {}
                job = JobListing(**job_data)
                self.memory.store_job(job)
                return f"Stored job: {job.title} at {job.company}"

            elif action == "is_seen":
                url = data
                is_seen = self.memory.is_job_seen(url)
                return json.dumps({"url": url, "seen": is_seen})

            elif action == "find_similar":
                params = json.loads(data) if data else {}
                query = params.get("query", "")
                n = params.get("n", 10)
                results = self.memory.find_similar_jobs(query, n)
                return json.dumps(results, indent=2)

            elif action == "check_outreach":
                params = json.loads(data) if data else {}
                company = params.get("company", "")
                url = params.get("url", "")
                sent = self.memory.has_outreach_been_sent(company, url)
                return json.dumps({"company": company, "url": url, "sent": sent})

            elif action == "get_stats":
                stats = self.memory.get_collection_stats()
                return json.dumps(stats, indent=2)

            else:
                return f"Unknown action: {action}"

        except Exception as e:
            logger.error("memory_tool_error", action=action, error=str(e))
            return f"Error: {str(e)}"


if __name__ == "__main__":
    # Test ChromaDB memory layer
    mm = MemoryManager("./data/test_chromadb")

    # Test job storage
    test_job = JobListing(
        title="Backend Engineer",
        company="TestCo",
        url="https://test.com/1",
        jd_text="We need a Python expert with AWS experience for backend development.",
        source="test",
        job_score=85,
        job_grade="A",
    )

    mm.store_job(test_job)
    assert mm.is_job_seen("https://test.com/1")
    assert not mm.is_job_seen("https://test.com/999")

    # Test similar jobs
    similar = mm.find_similar_jobs("Python backend AWS", n=5)
    print(f"Found {len(similar)} similar jobs")

    # Test statistics
    stats = mm.get_collection_stats()
    print(f"ChromaDB stats: {json.dumps(stats, indent=2)}")

    # Test outreach tracking
    mm.store_outreach("TestCo", "https://test.com/1")
    assert mm.has_outreach_been_sent("TestCo", "https://test.com/1")
    assert not mm.has_outreach_been_sent("TestCo", "https://test.com/999")

    print("[OK] ChromaDB vector memory working correctly")

    # Cleanup
    import shutil

    shutil.rmtree("./data/test_chromadb", ignore_errors=True)
