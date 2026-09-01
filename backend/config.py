"""Central configuration for the CampusSync AI backend.

All tunables are read from the environment so the same image can run in
development, Docker and CI without code changes.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_ollama import ChatOllama

load_dotenv()


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent

DOCUMENTS_DIR = Path(
    os.getenv("DOCUMENTS_DIR", BASE_DIR / "data" / "documents")
)

TIMETABLE_DIR = DOCUMENTS_DIR / "timetable"

LMS_DIR = DOCUMENTS_DIR / "lms"


# --------------------------------------------------------------------------
# LLM
# --------------------------------------------------------------------------

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

PLANNING_MODEL = os.getenv("PLANNING_MODEL", "qwen2.5:3b")

EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", PLANNING_MODEL)

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# How many times an LLM call is retried when it returns output that fails
# schema or semantic validation.
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))


llm = ChatOllama(
    model=PLANNING_MODEL,
    temperature=LLM_TEMPERATURE,
    base_url=OLLAMA_BASE_URL,
)

extraction_llm = ChatOllama(
    model=EXTRACTION_MODEL,
    temperature=LLM_TEMPERATURE,
    base_url=OLLAMA_BASE_URL,
)


# --------------------------------------------------------------------------
# Scheduling rules
# --------------------------------------------------------------------------

COLLEGE_START = os.getenv("COLLEGE_START", "08:00")

COLLEGE_END = os.getenv("COLLEGE_END", "16:00")

STUDY_DAY_END = os.getenv("STUDY_DAY_END", "22:00")

# Gaps shorter than this (minutes) are not useful study slots.
MIN_STUDY_SLOT_MINUTES = int(os.getenv("MIN_STUDY_SLOT_MINUTES", "30"))


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------

# Document extraction is deterministic per document, so its result is cached
# on disk. Only the planning call then runs on each request.
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
}

CACHE_DIR = Path(os.getenv("CACHE_DIR", BASE_DIR / ".cache"))


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def configure_logging() -> None:
    """Configure root logging once, at application start."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# --------------------------------------------------------------------------
# Database & auth
# --------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'campussync.db'}")

SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "12"))

# Uploaded documents are written here, namespaced per student.
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "data" / "uploads"))

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
